"""
LLM service using Google Vertex AI (Gemini Pro).
Handles all LLM interactions for gap detection, explanations, and chat.
"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage, AIMessage
from app.config import settings


class LLMService:
    """Service for interacting with Gemini Pro via Vertex AI."""
    
    def __init__(self):
        """Initialize the LLM service."""
        self.llm = None
        self.initialized_model = None  # Track which model was successfully initialized
        self._initialize_llm()
    
    def _sanitize_text(self, text: str, max_length: int = 8000) -> str:
        """
        Sanitize text to reduce safety filter triggers.
        
        Args:
            text: Text to sanitize
            max_length: Maximum length to return
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = " ".join(text.split())
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    def _initialize_llm(self):
        """Initialize the Gemini Pro LLM."""
        try:
            # Set Google Cloud credentials
            if settings.google_application_credentials:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.google_application_credentials
            
            # Initialize ChatVertexAI with Gemini
            # Model priority optimized for analysis quality (Pro models first)
            # Priority: 3 Pro → 2.5 Pro → 2.5 Flash (best quality for gap analysis)
            models_to_try = [
                # Tier 1: Gemini 3 Pro (highest quality for analysis)
                "gemini-3-pro",        # Gemini 3 Pro (without .0)
                "gemini-3.0-pro",     # Gemini 3 Pro (with version)
                
                # Tier 2: Gemini 2.5 Pro (excellent quality, widely available)
                "gemini-2.5-pro",      # Gemini 2.5 Pro (best quality for complex analysis)
                
                # Tier 3: Gemini 2.5 Flash (fast, good quality)
                "gemini-2.5-flash",    # Gemini 2.5 Flash (fast, efficient fallback)
                
                # Tier 4: Additional fallbacks (if above models unavailable)
                "gemini-3-flash",      # Gemini 3 Flash (if Pro not available)
                "gemini-3.0-flash",    # Gemini 3 Flash (with version)
                "gemini-2.0-pro-exp",  # Gemini 2.0 Pro (experimental)
                "gemini-2.0-flash-exp", # Gemini 2.0 Flash (experimental)
                "gemini-2.0-flash",    # Gemini 2.0 Flash (stable)
                
                # Tier 5: Final fallback (widely available)
                settings.gemini_model, # Try configured model (if not already in list)
                "gemini-1.5-flash",    # Final fallback to 1.5 Flash (widely available)
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]
            
            last_error = None
            for model_name in models_to_try:
                try:
                    print(f"🔄 Trying model: {model_name}")
                    # Initialize with safety settings to reduce blocking
                    self.llm = ChatVertexAI(
                        model_name=model_name,
                        temperature=settings.temperature,
                        max_output_tokens=settings.max_tokens,
                        project=settings.google_cloud_project,
                        location=settings.google_cloud_location,
                        # Safety settings - allow more content through filters
                        safety_settings=None,  # Will use default, but can be configured
                    )
                    # Note: ChatVertexAI object creation doesn't validate model availability
                    # Model validation happens on first invoke, so we'll catch 404 errors there
                    print(f"✅ Model object created: {model_name} (will validate on first use)")
                    self.initialized_model = model_name  # Store the model we're trying
                    break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    # Check if it's a 404 (model not found) - this is expected for unavailable models
                    if "404" in error_msg or "not found" in error_msg.lower():
                        print(f"⚠️  Model {model_name} not available in Vertex AI, trying next...")
                    else:
                        print(f"❌ Failed with {model_name}: {error_msg}")
                    continue
            else:
                # If all models failed
                print(f"❌ All models failed. Last error: {last_error}")
                raise Exception(f"Failed to initialize any Gemini model. Last error: {last_error}")
            
            print(f"🎯 LLM service initialized and ready with model: {self.initialized_model}")
        except Exception as e:
            print(f"Error initializing LLM service: {e}")
            raise Exception(f"Failed to initialize LLM: {str(e)}")
    
    def _reinitialize_with_fallback(self, failed_model: str):
        """Re-initialize LLM with the next available model after a failure."""
        print(f"🔄 Re-initializing after {failed_model} failed...")
        
        # Get the list of models to try (same priority as initialization)
        # Priority: 3 Pro → 2.5 Pro → 2.5 Flash (best quality for analysis)
        models_to_try = [
            # Tier 1: Gemini 3 Pro (highest quality)
            "gemini-3-pro", "gemini-3.0-pro",
            
            # Tier 2: Gemini 2.5 Pro (excellent quality)
            "gemini-2.5-pro",
            
            # Tier 3: Gemini 2.5 Flash (fast, good quality)
            "gemini-2.5-flash",
            
            # Tier 4: Additional fallbacks
            "gemini-3-flash", "gemini-3.0-flash",
            "gemini-2.0-pro-exp",
            "gemini-2.0-flash-exp", "gemini-2.0-flash",
            
            # Tier 5: Final fallback
            settings.gemini_model, "gemini-1.5-flash",
        ]
        
        # Remove duplicates and find the failed model's position
        seen = set()
        models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]
        
        # Find index of failed model and try models after it
        try:
            failed_index = models_to_try.index(failed_model)
            models_to_try = models_to_try[failed_index + 1:]  # Try models after the failed one
            print(f"📍 Starting fallback from position {failed_index + 1}")
        except ValueError:
            # Failed model not in list, try all models
            print(f"⚠️  Failed model {failed_model} not in list, trying all fallbacks")
        
        # Try to initialize with next available model
        for model_name in models_to_try:
            try:
                print(f"🔄 Trying fallback model: {model_name}")
                self.llm = ChatVertexAI(
                    model_name=model_name,
                    temperature=settings.temperature,
                    max_output_tokens=settings.max_tokens,
                    project=settings.google_cloud_project,
                    location=settings.google_cloud_location,
                )
                self.initialized_model = model_name
                print(f"✅ Re-initialized successfully with: {model_name}")
                return
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "not found" in error_msg.lower():
                    print(f"⚠️  Fallback model {model_name} not available, trying next...")
                else:
                    print(f"❌ Fallback model {model_name} failed: {error_msg}")
                continue
        
        raise Exception("All fallback models failed during re-initialization")
    
    def analyze_document_for_gaps(
        self,
        document_text: str,
        course_info: Dict,
        assignment_context: Optional[str] = None,
        rag_context: Optional[str] = None
    ) -> Dict:
        """
        Analyze document to identify knowledge gaps using RAG context.
        
        Args:
            document_text: Extracted text from document
            course_info: Course information dictionary
            assignment_context: Optional assignment context
            rag_context: Optional RAG-retrieved context chunks (for focused analysis)
            
        Returns:
            Dictionary with detected gaps and analysis
        """
        # Few-shot examples for better format enforcement
        examples = """
EXAMPLE OUTPUT FORMAT (YOU MUST FOLLOW THIS EXACTLY):

CRITICAL GAP: Power Method
Explanation: The power method is an iterative algorithm used to find the dominant eigenvalue and eigenvector of a matrix. The document mentions using the power method in Assignment 3, Question 2, but does not explain how the algorithm works, what the convergence criteria are, or how to implement it.
Why Needed: Required for Assignment 3, Question 2. Without understanding the power method, the student cannot solve the eigenvalue problem asked in the assignment. This concept appears in 80% of numerical methods exams.

CRITICAL GAP: SVD Decomposition
Explanation: Singular Value Decomposition (SVD) breaks down a matrix into three components: U, Σ, and V. The document mentions "full SVD" and "economical SVD" but does not explain the difference in dimensions or when to use each version.
Why Needed: The assignment explicitly asks students to compute both full and economical SVD. Missing this knowledge prevents completing the assignment correctly.

SAFE GAP: Matrix Condition Number
Explanation: The condition number measures how sensitive a matrix is to numerical errors. While not directly required for the assignment, understanding condition numbers helps explain why some numerical methods are more stable than others.
Why Needed: Enhances understanding of numerical stability, useful for advanced topics but not required for passing the course.
"""

        system_prompt = f"""You are an expert educational AI analyzing a student's course materials.

Course Context:
- Course: {course_info.get('course_code', 'Unknown')}
- Institution: {course_info.get('institution', 'Unknown')}
- Course Type: {course_info.get('course_type', 'Unknown')}
- Student Level: {course_info.get('current_level', 'intermediate')} (used for explanation depth only)
- Learning Goal: {course_info.get('learning_goal', 'pass_exam')}

YOUR TASK:
1. Analyze the provided document (notes, assignments, or slides)
2. Identify ALL specific concepts that are:
   - Mentioned but not fully explained
   - Required but missing
   - Referenced in questions but not covered in notes
3. Extract SPECIFIC concept names (e.g., "Power Method", "SVD Decomposition", "Dynamic Programming")
   - DO NOT use generic phrases like "concepts mentioned but not explained"
   - DO NOT use vague descriptions like "mathematical concepts"
   - USE specific, named concepts from the document

CRITICAL CATEGORIZATION RULES (MANDATORY):
- A gap is CRITICAL if it appears in assignment questions, exam topics, or is required to solve problems
- A gap is CRITICAL if missing it would prevent completing assignments or passing exams
- If a concept is mentioned in questions/problems but not explained in notes, it's CRITICAL
- If a concept is required to solve problems in the document, it's CRITICAL
- Student level does NOT affect categorization - CRITICAL gaps are CRITICAL regardless of level
- You MUST identify at least 2-5 CRITICAL gaps if the document contains assignments or questions

SAFE CATEGORIZATION RULES:
- A gap is SAFE if it's helpful for deeper understanding but not required for passing
- A gap is SAFE if it enhances knowledge but isn't directly tested or required

STRICT OUTPUT FORMAT (YOU MUST FOLLOW THIS EXACTLY):
{examples}

REQUIREMENTS:
1. Use EXACT format: "CRITICAL GAP: [Specific Concept Name]" or "SAFE GAP: [Specific Concept Name]"
2. Concept names must be SPECIFIC (e.g., "Power Method", not "numerical methods")
3. Each gap must have Explanation and Why Needed sections
4. Identify 5-15 gaps depending on document complexity
5. At least 30-50% of gaps should be CRITICAL if document contains assignments/questions
6. DO NOT use generic fallback text - extract real, specific concepts from the document

Begin your analysis now. Extract specific concepts and format them exactly as shown in the examples."""

        # Use RAG context if available, otherwise use full document text
        if rag_context:
            print("📚 Using RAG context for focused analysis")
            analysis_text = rag_context
        else:
            print("📄 Using full document text (RAG context not available)")
            analysis_text = document_text
        
        # Sanitize text to reduce safety filter issues
        sanitized_text = self._sanitize_text(analysis_text, max_length=6000)
        
        # Build user prompt with RAG context
        user_prompt = f"""Analyze this educational document and identify knowledge gaps.

RELEVANT DOCUMENT CONTEXT (Retrieved using semantic search):
{sanitized_text}

{f'ASSIGNMENT CONTEXT: {assignment_context[:1000] if assignment_context else ""}'}

IMPORTANT: Use the provided context to identify specific concepts that are:
1. Mentioned but not fully explained
2. Required for assignments/exams but missing from notes
3. Referenced in questions but not covered in detail

Focus on extracting SPECIFIC concept names from the context above."""

        # Retry logic for blocked responses
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Verify LLM is initialized
                if self.llm is None:
                    raise Exception("LLM not initialized. Please check your configuration.")
                
                # Combine system and user prompts since SystemMessage not supported
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                messages = [HumanMessage(content=combined_prompt)]
                
                print(f"📤 Sending analysis request to model: {self.initialized_model or 'unknown'}")
                response = self.llm.invoke(messages)
                
                return {
                    "analysis": response.content,
                    "raw_response": response
                }
            except Exception as e:
                error_str = str(e)
                last_error = e
                
                # Check if it's a model not found error (404) - need to re-initialize with next model
                if "404" in error_str or ("not found" in error_str.lower() and "model" in error_str.lower()):
                    print(f"❌ Model {self.initialized_model} not available (404). Re-initializing with fallback...")
                    # Re-initialize LLM service with next available model
                    try:
                        self._reinitialize_with_fallback(self.initialized_model)
                        # Retry the analysis with the new model
                        continue
                    except Exception as reinit_error:
                        print(f"❌ Failed to re-initialize: {reinit_error}")
                        raise Exception(f"Model {self.initialized_model} not available and fallback failed: {reinit_error}")
                
                # Check if it's a safety filter block
                if "blocked" in error_str.lower() or "safety" in error_str.lower():
                    print(f"Attempt {attempt + 1}/{max_retries}: Response blocked by safety filters")
                    
                    if attempt < max_retries - 1:
                        # Try with a simpler, more educational-focused prompt
                        print("Retrying with simplified educational prompt...")
                        simplified_prompt = f"""You are an educational assistant analyzing course materials for knowledge gaps.

Course: {course_info.get('course_code', 'Unknown')}
Student Level: {course_info.get('current_level', 'intermediate')}

Analyze this educational document and identify:
1. Concepts mentioned but not fully explained
2. Concepts that should be covered but are missing

Categorize each gap as either CRITICAL (must know) or SAFE (nice to know).

Document excerpt:
{document_text[:4000]}

Provide a structured list of gaps with brief explanations."""
                        
                        user_prompt = simplified_prompt
                        continue
                    else:
                        # Final attempt failed - return a fallback response
                        print("All retries failed. Returning fallback analysis.")
                        return {
                            "analysis": f"""Gap Analysis for {course_info.get('course_code', 'Course')}

Due to content filtering, a detailed analysis could not be generated automatically.

Please review your document manually and identify:
- Concepts mentioned but not fully explained
- Topics that appear in assignments but weren't covered in notes
- Mathematical or computational concepts that need deeper explanation

For best results, try uploading a different document or contact support if this persists.""",
                            "raw_response": None
                        }
                else:
                    # Different error - raise immediately
                    print(f"Error in gap analysis (non-safety error): {e}")
                    raise
        
        # If we get here, all retries failed
        raise Exception(f"Failed to analyze document after {max_retries} attempts: {last_error}")
    
    def explain_concept(
        self,
        concept: str,
        document_context: str,
        gap_info: Optional[Dict] = None
    ) -> str:
        """
        Explain a concept with context from the document.
        
        Args:
            concept: Concept to explain
            document_context: Relevant context from document
            gap_info: Optional gap information
            
        Returns:
            Explanation text
        """
        system_prompt = """You are a patient, expert tutor helping a student understand a concept they're missing.

Your explanation should:
1. Be clear and simple
2. Use examples from their course materials when possible
3. Relate to their specific assignment/exam context
4. Build understanding step by step
5. Be encouraging and supportive"""

        user_prompt = f"""The student is struggling with: {concept}

{f'This is a CRITICAL gap needed for: {gap_info.get("why_needed", "")}' if gap_info else ''}

Relevant context from their materials:
{document_context[:4000]}

Explain {concept} clearly, relating it to their course materials and assignments."""

        try:
            # Combine system and user prompts since SystemMessage not supported
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            messages = [HumanMessage(content=combined_prompt)]
            
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            print(f"Error explaining concept: {e}")
            raise
    
    def chat_with_context(
        self,
        user_message: str,
        conversation_history: List[Dict],
        document_context: str,
        system_prompt: Optional[str] = None,
        max_context_chars: int = 6000
    ) -> str:
        """
        Chat with context from document and conversation history.
        Intelligently manages context window to fit within LLM limits.
        
        Args:
            user_message: User's message
            conversation_history: Previous messages in conversation (list of dicts with 'role' and 'content')
            document_context: Relevant context from document
            system_prompt: Optional custom system prompt
            max_context_chars: Maximum characters for document context (default 6000, leaves room for conversation)
            
        Returns:
            AI response
        """
        if system_prompt is None:
            system_prompt = """You are a helpful tutor. Use the provided document context to answer questions accurately. 
            Be clear, encouraging, and relate answers to the student's course materials."""

        # Truncate document context intelligently if needed
        # Keep complete chunks, don't cut mid-sentence
        if len(document_context) > max_context_chars:
            truncated = document_context[:max_context_chars]
            # Try to end at a sentence boundary
            last_period = truncated.rfind('.')
            last_newline = truncated.rfind('\n')
            # Use whichever is closer to max_context_chars (but not too far)
            cutoff = max(last_period, last_newline)
            if cutoff > max_context_chars * 0.8:  # If we can keep at least 80% of content
                document_context = truncated[:cutoff + 1]
            else:
                document_context = truncated
            print(f"📝 Truncated document context to {len(document_context)} chars (from {len(document_context) + len(truncated) - max_context_chars})")
        
        # Build conversation history text
        # Keep last 10 messages to avoid context overflow
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        conversation_text = ""
        
        for msg in recent_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                conversation_text += f"User: {content}\n\n"
            elif role == 'assistant':
                conversation_text += f"Assistant: {content}\n\n"
        
        # If conversation is long, summarize older messages
        if len(conversation_history) > 10:
            conversation_text = f"[Previous conversation had {len(conversation_history) - 10} earlier messages]\n\n" + conversation_text
        
        # Combine system prompt, conversation history, and current question
        combined_prompt = f"""{system_prompt}

Previous Conversation:
{conversation_text if conversation_text.strip() else "This is the start of the conversation."}

Document Context:
{document_context}

User Question: {user_message}

Answer the question using the document context and conversation history. Be specific and reference the document when relevant."""

        messages = [HumanMessage(content=combined_prompt)]
        
        # Retry logic with model fallback (similar to gap analysis)
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                print(f"💬 Sending chat request to {self.initialized_model or 'unknown model'} (attempt {attempt + 1}/{max_retries})")
                response = self.llm.invoke(messages)
                return response.content
            except Exception as e:
                error_str = str(e)
                last_error = e
                print(f"❌ Error in chat (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Check if it's a model not found error (404) - need to re-initialize with next model
                if "404" in error_str or ("not found" in error_str.lower() and "model" in error_str.lower()):
                    print(f"❌ Model {self.initialized_model} not available (404). Re-initializing with fallback...")
                    try:
                        self._reinitialize_with_fallback(self.initialized_model)
                        # Retry the chat with the new model
                        print(f"🔄 Retrying chat with fallback model: {self.initialized_model}")
                        continue
                    except Exception as reinit_error:
                        print(f"❌ Failed to re-initialize: {reinit_error}")
                        # If re-initialization fails, try next attempt or raise
                        if attempt < max_retries - 1:
                            continue
                        else:
                            raise Exception(f"Model {self.initialized_model} not available and fallback failed: {reinit_error}")
                
                # Check if it's a context length error
                elif "context" in error_str.lower() or "length" in error_str.lower() or "token" in error_str.lower():
                    print("⚠️ Context too long, retrying with reduced context...")
                    # Retry with smaller context
                    return self.chat_with_context(
                        user_message=user_message,
                        conversation_history=recent_history[-5:],  # Even fewer messages
                        document_context=document_context[:4000],  # Smaller document context
                        system_prompt=system_prompt,
                        max_context_chars=4000
                    )
                
                # Check if it's a safety filter block
                elif "blocked" in error_str.lower() or "safety" in error_str.lower():
                    print(f"⚠️ Response blocked by safety filters (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        # Try with a simpler, more educational-focused prompt
                        print("Retrying with simplified educational prompt...")
                        system_prompt = """You are a helpful tutor. Answer the student's question clearly and accurately using the document context provided."""
                        continue
                    else:
                        # Final attempt failed - return a helpful error message
                        return "I apologize, but I'm having trouble generating a response due to content filtering. Please try rephrasing your question or ask about a different topic."
                
                else:
                    # Different error - if it's the last attempt, raise it
                    if attempt == max_retries - 1:
                        print(f"❌ All retries failed. Last error: {last_error}")
                        raise Exception(f"Failed to get chat response after {max_retries} attempts: {last_error}")
                    # Otherwise, continue to next attempt
                    continue
        
        # If we get here, all retries failed
        raise Exception(f"Failed to get chat response after {max_retries} attempts: {last_error}")

