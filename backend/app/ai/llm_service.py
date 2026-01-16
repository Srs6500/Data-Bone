"""
LLM service using Google Vertex AI (Gemini Pro).
Handles all LLM interactions for gap detection, explanations, and chat.
"""
import os
import time
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, AIMessage
from app.config import settings
from app.monitoring import monitor

# Import safety settings types from langchain_google_vertexai
try:
    from langchain_google_vertexai import HarmCategory, HarmBlockThreshold
    HAS_SAFETY_TYPES = True
except ImportError:
    HAS_SAFETY_TYPES = False
    HarmCategory = None
    HarmBlockThreshold = None


class LLMService:
    """Service for interacting with Gemini Pro via Vertex AI."""
    
    def __init__(self):
        """Initialize the LLM service."""
        self.llm = None
        self.chat_llm = None  # Separate LLM instance for chat with higher token limit
        self.initialized_model = None  # Track which model was successfully initialized
        self._safety_settings = None  # Store safety settings if parameter not supported
        self._initialize_llm()
        self._initialize_chat_llm()  # Initialize chat LLM with higher token limit
    
    def _get_safety_settings(self):
        """
        Get safety settings configured to allow educational content.
        Sets all 4 safety categories to BLOCK_NONE to prevent false positives
        for educational content (mathematics, computer science, etc.).
        
        Returns:
            Dictionary mapping HarmCategory to HarmBlockThreshold (format required by LangChain 1.0+)
        """
        # In LangChain 1.0+, safety_settings must be a Dict[HarmCategory, HarmBlockThreshold]
        if HAS_SAFETY_TYPES and HarmCategory and HarmBlockThreshold:
            try:
                return {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            except Exception as e:
                print(f"⚠️ Could not use safety types: {e}")
                return None
        
        # If types not available, return None (will initialize without safety settings)
        print("⚠️ Safety settings types not available, initializing without safety_settings")
        return None
    
    def _extract_content(self, response) -> str:
        """
        Extract string content from LangChain response.
        In LangChain 1.0+, response.content can be a list (multimodal) or string.
        
        Args:
            response: LangChain AIMessage or response object
            
        Returns:
            String content (joined if list)
        """
        content = response.content if hasattr(response, 'content') else response
        
        # Handle list content (LangChain 1.0+ multimodal support)
        if isinstance(content, list):
            # Join list items into string
            return " ".join(str(item) for item in content)
        elif isinstance(content, str):
            return content
        else:
            # Fallback: convert to string
            return str(content)
    
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
    
    def _sanitize_user_message(self, message: str) -> str:
        """
        Sanitize user message to reduce safety filter triggers.
        Replaces potentially problematic terms with educational alternatives.
        
        Args:
            message: User's message to sanitize
            
        Returns:
            Sanitized message
        """
        if not message:
            return ""
        
        # Create a mapping of potentially problematic terms to educational alternatives
        # Focus on terms that might be misinterpreted by safety filters
        sanitization_map = {
            # Mathematical terms that might trigger filters
            "boundary conditions": "boundary value conditions",
            "dirichlet boundary": "dirichlet boundary value",
            "incorporation of": "implementation of",
            "incorporating": "implementing",
        }
        
        message_lower = message.lower()
        sanitized_message = message
        
        # Apply sanitization only if the term appears in a potentially problematic context
        for problematic, replacement in sanitization_map.items():
            if problematic in message_lower:
                # Replace with educational alternative
                sanitized_message = sanitized_message.replace(problematic, replacement)
                print(f"🛡️ Sanitized message: replaced '{problematic}' with '{replacement}'")
        
        return sanitized_message.strip()
    
    def _initialize_llm(self):
        """Initialize the Gemini Pro LLM."""
        try:
            # Set Google Cloud credentials
            if settings.google_application_credentials:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.google_application_credentials
            
            # Initialize ChatVertexAI with Gemini
            # Model priority: Use gemini-2.5-pro directly (fast, reliable, excellent quality)
            # Removed gemini-3-pro models (don't exist, waste 20-30s per request)
            models_to_try = [
                # Primary: Gemini 2.5 Pro (excellent quality, widely available, fast)
                "gemini-2.5-pro",      # Gemini 2.5 Pro (best quality for complex analysis)
                
                # Fallback: Gemini 2.5 Flash (fast, good quality)
                "gemini-2.5-flash",    # Gemini 2.5 Flash (fast, efficient fallback)
                
                # Additional fallbacks (if above models unavailable)
                "gemini-2.0-pro-exp",  # Gemini 2.0 Pro (experimental)
                "gemini-2.0-flash-exp", # Gemini 2.0 Flash (experimental)
                "gemini-2.0-flash",    # Gemini 2.0 Flash (stable)
                
                # Final fallback (widely available)
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
                    # Initialize with safety settings explicitly set to BLOCK_NONE
                    # This prevents false positives for educational content
                    safety_settings = self._get_safety_settings()
                    
                    # Initialize with safety settings (dictionary format for LangChain 1.0+)
                    # Build initialization kwargs
                    init_kwargs = {
                        "model_name": model_name,
                        "temperature": settings.temperature,
                        "max_output_tokens": settings.max_tokens,
                        "project": settings.google_cloud_project,
                        "location": settings.google_cloud_location,
                    }
                    
                    # Add safety settings if available (dictionary format: Dict[HarmCategory, HarmBlockThreshold])
                    if safety_settings is not None:
                        init_kwargs["safety_settings"] = safety_settings
                    
                    self.llm = ChatVertexAI(**init_kwargs)
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
    
    def _initialize_chat_llm(self):
        """Initialize a separate LLM instance for chat with higher token limit."""
        try:
            # Use the same model that was successfully initialized for analysis
            # But with higher token limit for complete chat responses
            if self.initialized_model is None:
                # If main LLM failed, try to initialize chat LLM anyway
                model_name = settings.gemini_model
            else:
                model_name = self.initialized_model
            
            safety_settings = self._get_safety_settings()
            
            # Initialize chat LLM with higher token limit
            init_kwargs = {
                "model_name": model_name,
                "temperature": settings.temperature,
                "max_output_tokens": settings.max_tokens_chat,  # Higher limit for chat
                "project": settings.google_cloud_project,
                "location": settings.google_cloud_location,
            }
            
            if safety_settings is not None:
                init_kwargs["safety_settings"] = safety_settings
            
            self.chat_llm = ChatVertexAI(**init_kwargs)
            print(f"✅ Chat LLM initialized with {settings.max_tokens_chat} token limit (model: {model_name})")
        except Exception as e:
            print(f"⚠️ Failed to initialize chat LLM, will use main LLM: {e}")
            # Fallback: use main LLM if chat LLM fails
            self.chat_llm = None
    
    def _reinitialize_with_fallback(self, failed_model: str):
        """Re-initialize LLM with the next available model after a failure."""
        print(f"🔄 Re-initializing after {failed_model} failed...")
        
        # Get the list of models to try (same priority as initialization)
        # Priority: 3 Pro → 2.5 Pro → 2.5 Flash (best quality for analysis)
        models_to_try = [
            # Primary: Gemini 2.5 Pro (excellent quality, widely available)
            "gemini-2.5-pro",
            
            # Fallback: Gemini 2.5 Flash (fast, good quality)
            "gemini-2.5-flash",
            
            # Additional fallbacks (if above models unavailable)
            "gemini-2.0-pro-exp",
            "gemini-2.0-flash-exp", "gemini-2.0-flash",
            
            # Final fallback (widely available)
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
                # Use same safety settings for fallback models
                safety_settings = self._get_safety_settings()
                
                # Initialize with safety settings (dictionary format for LangChain 1.0+)
                init_kwargs = {
                    "model_name": model_name,
                    "temperature": settings.temperature,
                    "max_output_tokens": settings.max_tokens,
                    "project": settings.google_cloud_project,
                    "location": settings.google_cloud_location,
                }
                
                # Add safety settings if available
                if safety_settings is not None:
                    init_kwargs["safety_settings"] = safety_settings
                
                self.llm = ChatVertexAI(**init_kwargs)
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

IMPORTANT: The "Why Needed" section MUST be SPECIFIC and COMPLETE:
- DO NOT use generic phrases like "This concept is important for understanding the course material"
- DO NOT use vague statements like "This is important to understand"
- DO use specific references: "Required for Question 3", "Needed to solve Assignment 2, Problem 1", "Without this you cannot understand SVD decomposition"
- DO mention specific question numbers, assignment numbers, or problem numbers when available
- DO explain the specific consequence: "Without X, you cannot Y" or "Missing X prevents completing Z"
- DO ensure the sentence is COMPLETE (ends with proper punctuation, not cut off mid-sentence)
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
   - Partially explained but missing key details
   - Referenced but not defined
   - Used in examples but not taught
3. Extract SPECIFIC concept names (e.g., "Power Method", "SVD Decomposition", "Dynamic Programming")
   - DO NOT use generic phrases like "concepts mentioned but not explained"
   - DO NOT use vague descriptions like "mathematical concepts"
   - USE specific, named concepts from the document
4. BE THOROUGH: For short documents (< 2000 chars), aim to find 5-10 gaps. For longer documents, find 10-20+ gaps.
   - Look for every concept that is mentioned, referenced, or implied but not fully explained
   - Don't stop at 2-3 gaps - continue analyzing until you've found all knowledge gaps
   - Even if a concept is briefly mentioned, if it lacks explanation, it's a gap

CRITICAL CATEGORIZATION RULES (STRICT - Only for Essential Problem-Solving):
- A gap is CRITICAL ONLY if it is EXPLICITLY required to solve specific problems in the document
- A gap is CRITICAL if a concept is directly asked in assignment questions with NO explanation provided
- A gap is CRITICAL if missing it would PREVENT completing core assignment tasks (not just helpful, but essential)
- A gap is CRITICAL if it appears in exam-style questions and is NOT explained in the notes
- A gap is CRITICAL if it's a prerequisite concept that MUST be understood before solving problems
- DO NOT mark a gap as CRITICAL just because it's mentioned - it must be EXPLICITLY required for problem-solving
- DO NOT mark a gap as CRITICAL if it's just helpful or enhances understanding - those are SAFE
- Student level does NOT affect categorization - CRITICAL gaps are CRITICAL regardless of level

SAFE CATEGORIZATION RULES (DEFAULT - Be Very Generous):
- DEFAULT TO SAFE: When in doubt between CRITICAL and SAFE, ALWAYS choose SAFE
- A gap is SAFE if it's helpful for deeper understanding but not directly required for problem-solving
- A gap is SAFE if it enhances knowledge but isn't explicitly tested or required in assignments
- A gap is SAFE if it provides background knowledge that improves comprehension but isn't essential
- A gap is SAFE if it's an advanced topic that deepens understanding but isn't needed for passing
- A gap is SAFE if it's an implementation detail when the core concept is already understood
- A gap is SAFE if it's a related concept that helps connect ideas but isn't directly required
- A gap is SAFE if it's mentioned in the document but not explicitly needed for any problems
- A gap is SAFE if it would be "nice to know" or "helpful to understand" - these are NOT critical
- A gap is SAFE if understanding it improves quality but isn't strictly necessary to complete tasks
- MOST gaps should be SAFE - only mark as CRITICAL if absolutely essential for problem-solving

STRICT OUTPUT FORMAT (YOU MUST FOLLOW THIS EXACTLY):
{examples}

REQUIREMENTS:
1. Use EXACT format: "CRITICAL GAP: [Specific Concept Name]" or "SAFE GAP: [Specific Concept Name]"
2. Concept names must be SPECIFIC (e.g., "Power Method", not "numerical methods")
3. Each gap must have Explanation and Why Needed sections
   - Explanation: Complete, full sentences explaining what the concept is and why it's missing. DO NOT cut off mid-sentence.
   - Why Needed: SPECIFIC reason with question/assignment numbers when available. Examples:
     * "Required for Question 3 from the document"
     * "Needed to solve Assignment 2, Problem 1"
     * "Without this you cannot understand SVD decomposition"
     * "Missing this knowledge prevents completing the assignment"
     * DO NOT use: "This concept is important for understanding" (too generic)
     * DO NOT use: "This is important to understand" (too vague)
     * DO ensure complete sentences (no cutoff)
4. Identify ALL knowledge gaps you find in the document. Be thorough and comprehensive:
   - If you identify 5 gaps, list all 5
   - If you identify 20 gaps, list all 20
   - If you identify 30 gaps, list all 30
   - Do NOT limit yourself to any specific number
   - Quality over quantity: only include gaps that are genuinely missing or insufficiently explained
   - Be exhaustive in your analysis - leave no stone unturned
5. BALANCE (MANDATORY): You MUST have a mix of both CRITICAL and SAFE gaps
   - If document has assignments/questions: 30-50% should be CRITICAL, 50-70% should be SAFE
   - If document is notes only: 10-30% CRITICAL, 70-90% SAFE
   - DEFAULT TO SAFE: Be very generous with SAFE categorization - only mark as CRITICAL if absolutely essential
   - If you find 3 gaps and all are CRITICAL, you are being too strict - re-evaluate and mark at least 1-2 as SAFE
   - If you find 5 gaps, at least 2-3 should be SAFE
   - If you find 10 gaps, at least 5-7 should be SAFE
   - REMEMBER: Most gaps are SAFE - only concepts that PREVENT problem-solving are CRITICAL
6. DO NOT use generic fallback text - extract real, specific concepts from the document

Begin your analysis now. Extract specific concepts and format them exactly as shown in the examples."""

        # Use RAG context if available and sufficient, otherwise use full document text
        # Check if RAG context is sufficient (has enough chunks and content)
        # ADAPTIVE THRESHOLD: Adjust based on document size for better accuracy
        rag_is_sufficient = False
        if rag_context:
            # Count chunks by splitting on double newlines (chunk separator)
            rag_chunks = [c.strip() for c in rag_context.split('\n\n') if c.strip()]
            rag_chunk_count = len(rag_chunks)
            rag_char_count = len(rag_context)
            document_char_count = len(document_text)
            
            # Adaptive threshold based on document size:
            # - Short documents (< 2000 chars): Lower threshold (1000 chars) - RAG is very useful even if smaller
            # - Medium documents (2000-5000 chars): Medium threshold (1500 chars)
            # - Large documents (> 5000 chars): Higher threshold (2000 chars) - need more context
            if document_char_count < 2000:
                min_chars_threshold = 1000  # For short docs, 1000 chars of RAG is excellent
            elif document_char_count < 5000:
                min_chars_threshold = 1500  # For medium docs, 1500 chars is good
            else:
                min_chars_threshold = 2000  # For large docs, need more context
            
            # Always require at least 5 chunks for quality
            min_chunks_threshold = 5
            
            if rag_chunk_count >= min_chunks_threshold and rag_char_count >= min_chars_threshold:
                rag_is_sufficient = True
                print(f"📚 Using RAG context for focused analysis ({rag_chunk_count} chunks, {rag_char_count} chars, doc size: {document_char_count} chars)")
            else:
                print(f"⚠️ RAG context insufficient: {rag_chunk_count} chunks, {rag_char_count} chars (need {min_chunks_threshold}+ chunks, {min_chars_threshold}+ chars for {document_char_count} char document)")
                print(f"📄 Falling back to full document text for comprehensive analysis")
        
        if rag_is_sufficient:
            analysis_text = rag_context
        else:
            # Use full document text for comprehensive analysis
            analysis_text = document_text
            print(f"📄 Using full document text ({len(document_text)} chars) for comprehensive gap analysis")
        
        # Sanitize text to reduce safety filter issues
        # Increased context window to support comprehensive gap analysis (20+ gaps)
        sanitized_text = self._sanitize_text(analysis_text, max_length=12000)
        
        # Build user prompt with RAG context
        user_prompt = f"""Analyze this educational document and identify knowledge gaps.

RELEVANT DOCUMENT CONTEXT (Retrieved using semantic search):
{sanitized_text}

{f'ASSIGNMENT CONTEXT: {assignment_context[:2000] if assignment_context else ""}'}

IMPORTANT: Use the provided context to identify specific concepts that are:
1. Mentioned but not fully explained
2. Required for assignments/exams but missing from notes
3. Referenced in questions but not covered in detail

Focus on extracting SPECIFIC concept names from the context above."""

        # Retry logic for blocked responses
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Verify LLM is initialized
                if self.llm is None:
                    raise Exception("LLM not initialized. Please check your configuration.")
                
                # Combine system and user prompts since SystemMessage not supported
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                messages = [HumanMessage(content=combined_prompt)]
                
                model_name = self.initialized_model or 'unknown'
                print(f"📤 Sending analysis request to model: {model_name}")
                
                # Track model usage
                monitor.track_llm_model_usage(model_name, 'gap_analysis')
                
                response = self.llm.invoke(messages)
                duration = time.time() - start_time
                
                # Track successful request
                monitor.track_llm_request(
                    model=model_name,
                    operation='gap_analysis',
                    duration=duration,
                    success=True
                )
                
                return {
                    "analysis": self._extract_content(response),
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

CRITICAL: Answer ONLY using the provided document context. If the information is not in the context, say "I couldn't find that information in the document" or "Not found in the provided materials." Do not make up information or use knowledge outside the provided context.

Your explanation should identify and fill knowledge gaps:
1. Be clear and simple
2. Explain the "why" - why does this concept/formula work?
3. Explain the "when" - when does it apply? When does it fail? What are exceptions?
4. Explain important details that are easy to miss
5. Provide geometric/visual interpretations when helpful
6. Use examples from their course materials when possible
7. Relate to their specific assignment/exam context
8. Build understanding step by step
9. Be encouraging and supportive

Your goal is to help them truly understand the concept, not just memorize it."""

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
            return self._extract_content(response)
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
            system_prompt = """You are a helpful tutor focused on identifying and filling knowledge gaps. 

CRITICAL: Answer ONLY using the provided document context. If the answer is not in the context, say "I couldn't find that information in the document" or "Not found in the provided materials." Do not make up information or use knowledge outside the provided context.

Use the provided document context to answer questions accurately. Be clear, encouraging, and relate answers to the student's course materials. When explaining concepts, help them understand the "why", "when", exceptions, and important details - not just the formula."""

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
                # Use chat_llm if available (higher token limit), otherwise fallback to main llm
                llm_to_use = self.chat_llm if self.chat_llm is not None else self.llm
                model_name = self.initialized_model or 'unknown'
                start_time = time.time()
                print(f"💬 Sending chat request to {model_name} (attempt {attempt + 1}/{max_retries})")
                
                # Track model usage
                monitor.track_llm_model_usage(model_name, 'chat')
                
                response = llm_to_use.invoke(messages)
                duration = time.time() - start_time
                
                # Track successful chat request
                monitor.track_llm_request(
                    model=model_name,
                    operation='chat',
                    duration=duration,
                    success=True
                )
                
                return self._extract_content(response)
            except Exception as e:
                duration = time.time() - start_time
                error_str = str(e)
                last_error = e
                model_name = self.initialized_model or 'unknown'
                print(f"❌ Error in chat (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Check if it's a model not found error (404) - need to re-initialize with next model
                if "404" in error_str or ("not found" in error_str.lower() and "model" in error_str.lower()):
                    print(f"❌ Model {model_name} not available (404). Re-initializing with fallback...")
                    
                    # Track model fallback
                    monitor.track_llm_request(
                        model=model_name,
                        operation='chat',
                        duration=duration,
                        success=False,
                        error_type='model_not_found',
                        model_fallback=True
                    )
                    
                    try:
                        self._reinitialize_with_fallback(model_name)
                        # Retry the chat with the new model
                        print(f"🔄 Retrying chat with fallback model: {self.initialized_model}")
                        continue
                    except Exception as reinit_error:
                        print(f"❌ Failed to re-initialize: {reinit_error}")
                        # If re-initialization fails, try next attempt or raise
                        if attempt < max_retries - 1:
                            continue
                        else:
                            raise Exception(f"Model {model_name} not available and fallback failed: {reinit_error}")
                
                # Check if it's a context length error
                elif "context" in error_str.lower() or "length" in error_str.lower() or "token" in error_str.lower():
                    print("⚠️ Context too long, retrying with reduced context...")
                    
                    # Track context length error
                    monitor.track_llm_request(
                        model=model_name,
                        operation='chat',
                        duration=duration,
                        success=False,
                        error_type='context_length_exceeded'
                    )
                    
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
                    
                    # Track safety block
                    monitor.track_llm_request(
                        model=model_name,
                        operation='chat',
                        duration=duration,
                        success=False,
                        error_type='safety_filter',
                        safety_blocked=True
                    )
                    if attempt < max_retries - 1:
                        # Try with improved sanitization and more explicit educational prompt
                        print("Retrying with sanitized message and explicit educational prompt...")
                        
                        # Sanitize the user message to reduce filter triggers
                        sanitized_user_message = self._sanitize_user_message(user_message)
                        
                        # Create a more explicit educational system prompt
                        system_prompt = """You are an expert educational tutor helping a student understand mathematical and computational concepts from their course materials.

CRITICAL: Answer ONLY using the provided document context. If the answer is not in the context, say "I couldn't find that information in the document" or "Not found in the provided materials." Do not make up information or use knowledge outside the provided context.

Your role:
- Explain concepts clearly and accurately using educational terminology
- Use the document context to provide specific, relevant explanations
- Focus on helping the student understand the underlying principles
- Be thorough and educational in your explanations
- This is purely educational content for academic learning

Answer the student's question using the document context provided. Be specific and educational."""
                        
                        # Rebuild the prompt with sanitized message
                        combined_prompt = f"""{system_prompt}

Previous Conversation:
{conversation_text if conversation_text.strip() else "This is the start of the conversation."}

Document Context:
{document_context}

User Question: {sanitized_user_message}

Answer the question using the document context and conversation history. Be specific, educational, and reference the document when relevant."""
                        
                        messages = [HumanMessage(content=combined_prompt)]
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

