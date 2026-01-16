"""
API routes for chat functionality.
"""
import time
import re
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel

from app.services.gap_service import GapService
from app.ai.llm_service import LLMService
from app.api.analyze import get_document, documents_store
from app.monitoring import monitor

router = APIRouter()

# Initialize services lazily
llm_service = None
gap_service = None


def get_llm_service():
    """Get LLM service instance (lazy initialization)."""
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service


def get_gap_service():
    """Get gap service instance (lazy initialization)."""
    global gap_service
    if gap_service is None:
        from app.services.gap_service import GapService
        gap_service = GapService()
    return gap_service


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request model for chat."""
    document_id: str
    message: str
    conversation_history: Optional[List[ChatMessage]] = []
    gap_concept: Optional[str] = None  # Optional: if chatting about a specific gap (legacy support)
    gap_concepts: Optional[List[str]] = []  # Optional: array of gap concepts (for filter-aware chat)
    filter_type: Optional[str] = None  # Optional: "critical", "safe", or "all" - indicates which filter is active


class ChatResponse(BaseModel):
    """Response model for chat."""
    response: str
    document_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """
    Chat with AI tutor about a document.
    
    Args:
        request: Chat request with document ID, message, and optional history
        
    Returns:
        Chat response from AI
    """
    chat_start_time = time.time()
    has_gap_context = bool((request.gap_concepts and len(request.gap_concepts) > 0) or request.gap_concept)
    
    try:
        document_id = request.document_id
        
        # Track chat session start
        monitor.track_chat_session(
            document_id=document_id,
            has_gap_context=has_gap_context,
            gap_count=len(request.gap_concepts) if request.gap_concepts else (1 if request.gap_concept else 0),
            filter_type=request.filter_type
        )
        
        # Get document from store
        document = get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        if not document.extraction or not document.extraction.text:
            raise HTTPException(
                status_code=400,
                detail="Document has no extracted text"
            )
        
        # Get document context using RAG
        # Priority: gap_concepts[] (new) > gap_concept (legacy) > full document
        document_context = ""
        gap_service = get_gap_service()
        
        # Check for multiple gap concepts (new approach - filter-aware)
        if request.gap_concepts and len(request.gap_concepts) > 0:
            # Use multi-concept RAG retrieval
            print(f"📚 Retrieving context for {len(request.gap_concepts)} gap concepts: {request.gap_concepts[:3]}...")
            document_context = gap_service.get_gaps_context(
                gap_concepts=request.gap_concepts,
                document_id=document_id,
                max_chars=15000  # Increased context window to support 20+ gaps
            )
        elif request.gap_concept:
            # Legacy: single gap concept
            print(f"📚 Retrieving context for single gap concept: {request.gap_concept}")
            document_context = gap_service.get_gap_context(
                gap_concept=request.gap_concept,
                document_id=document_id
            )
        
        # Fallback: use full document text if RAG didn't return context
        if not document_context or len(document_context.strip()) < 100:
            print("📄 RAG context insufficient, using full document text (first 8000 chars)")
            document_context = document.extraction.text[:8000]
        
        # Convert conversation history to dict format
        conversation_history = []
        for msg in request.conversation_history:
            conversation_history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Detect if this is an exam question generation request
        is_exam_question_request = bool(
            re.search(r'\b(exam|test|quiz|question|practice|problem|exercise)\b', request.message, re.IGNORECASE)
        )
        
        # Build system prompt based on context and filter type
        system_prompt = None
        
        # Determine which concepts to focus on
        concepts_to_explain = []
        if request.gap_concepts and len(request.gap_concepts) > 0:
            concepts_to_explain = request.gap_concepts
        elif request.gap_concept:
            concepts_to_explain = [request.gap_concept]
        
        if concepts_to_explain:
            # Build filter-aware system prompt
            filter_context = ""
            if request.filter_type:
                filter_descriptions = {
                    "critical": "CRITICAL gaps (must know for exams and assignments)",
                    "safe": "SAFE gaps (nice to know for deeper understanding)",
                    "all": "all knowledge gaps"
                }
                filter_context = f"\n\nThe student is currently viewing {filter_descriptions.get(request.filter_type, 'knowledge gaps')}."
            
            concepts_list = ", ".join(concepts_to_explain[:5])  # Show first 5
            if len(concepts_to_explain) > 5:
                concepts_list += f", and {len(concepts_to_explain) - 5} more"
            
            system_prompt = f"""You are an expert tutor helping a student understand knowledge gaps in their course materials.{filter_context}

The student needs help with these concepts: {concepts_list}

Your role as a gap-finding tutor:
1. Start by explaining these concepts clearly and simply
2. Identify and explain the "gaps" in their understanding - not just the formula, but:
   - The "Why" gap: Why does this concept/formula work? What's the underlying principle?
   - The "When" gap: When does this apply? When does it fail? What are the exceptions?
   - The "Detail" gap: What are the subtle but important details (like the +C in integration)?
   - The "Geometric/Visual" gap: What does this mean visually or geometrically?
   - The "Connection" gap: How does this relate to other concepts in their materials?
3. Relate explanations to their specific course materials and document context
4. Provide examples from their document when possible
5. Be encouraging and supportive
6. Break down complex ideas into digestible steps
7. Answer any questions they have - don't restrict yourself to only these concepts

IMPORTANT: While you should prioritize explaining the concepts listed above, the student can ask about ANYTHING related to their document. Be helpful and comprehensive in your responses. Your goal is to help them truly understand, not just memorize formulas.

Use the document context provided to give specific, relevant explanations that fill knowledge gaps."""
        else:
            # General chat (no specific gap context)
            system_prompt = """You are a helpful tutor assisting a student with their course materials.

Your role as a gap-finding tutor:
1. Answer questions clearly and accurately using the document context
2. When explaining concepts, identify and fill knowledge gaps:
   - Explain the "why" behind formulas and concepts
   - Explain when rules apply and when they fail (exceptions)
   - Point out important details that are easy to miss
   - Provide geometric/visual interpretations when helpful
   - Connect concepts to other topics in their materials
3. Be encouraging and supportive
4. Provide examples from their document when relevant
5. Help them understand concepts step by step
6. Be comprehensive - help them truly understand, not just memorize

Use the document context provided to give specific, relevant answers that address knowledge gaps."""
        
        # Get LLM service and generate response
        llm = get_llm_service()
        response_start_time = time.time()
        response_text = llm.chat_with_context(
            user_message=request.message,
            conversation_history=conversation_history,
            document_context=document_context,
            system_prompt=system_prompt
        )
        response_duration = time.time() - response_start_time
        
        # Detect incomplete responses (ends mid-sentence, no punctuation, very short)
        is_incomplete = (
            len(response_text) < 50 or  # Very short response
            (not response_text.strip().endswith(('.', '!', '?', ':', ';')) and len(response_text) > 100) or  # No ending punctuation
            response_text.count('.') < 2 and len(response_text) > 200  # Very few sentences for long response
        )
        
        # Track chat message metrics
        monitor.track_chat_message(
            document_id=document_id,
            response_length=len(response_text),
            response_duration=response_duration,
            context_size=len(document_context),
            message_count=len(conversation_history) + 1,  # +1 for current message
            is_incomplete=is_incomplete,
            is_exam_question_request=is_exam_question_request,
            has_gap_context=has_gap_context
        )
        
        # Track exam question generation if detected
        if is_exam_question_request:
            # Estimate question count from response (look for numbered questions or question marks)
            question_count = max(1, response_text.count('?') // 2)  # Rough estimate
            monitor.track_exam_question_generation(
                document_id=document_id,
                gap_concepts=concepts_to_explain,
                question_count=question_count,
                generation_duration=response_duration,
                success=True
        )
        
        return ChatResponse(
            response=response_text,
            document_id=document_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        # Track failed chat request
        if has_gap_context:
            monitor.track_chat_message(
                document_id=document_id if 'document_id' in locals() else 'unknown',
                response_length=0,
                response_duration=time.time() - chat_start_time,
                context_size=0,
                message_count=0,
                is_incomplete=True,
                is_exam_question_request=False,
                has_gap_context=has_gap_context
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat: {str(e)}"
        )


@router.post("/chat/explain-gap")
async def explain_gap_auto(request: Dict):
    """
    Auto-explain a gap concept (for auto-injected prompts).
    This endpoint is called when user opens chat for a specific gap.
    
    Args:
        request: Dict with document_id and gap_concept
        
    Returns:
        Auto-generated explanation
    """
    try:
        document_id = request.get("document_id")
        gap_concept = request.get("gap_concept")
        
        if not document_id or not gap_concept:
            raise HTTPException(
                status_code=400,
                detail="document_id and gap_concept are required"
            )
        
        # Get document
        document = get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        # Get relevant context using RAG
        gap_service = get_gap_service()
        document_context = gap_service.get_gap_context(
            gap_concept=gap_concept,
            document_id=document_id
        )
        
        if not document_context:
            document_context = document.extraction.text[:5000]
        
        # Generate explanation using LLM
        llm = get_llm_service()
        explanation = llm.explain_concept(
            concept=gap_concept,
            document_context=document_context
        )
        
        return {
            "explanation": explanation,
            "gap_concept": gap_concept,
            "document_id": document_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in auto-explain endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating explanation: {str(e)}"
        )

