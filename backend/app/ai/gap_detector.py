"""
Gap detection service.
Orchestrates embeddings, vector database, and LLM to detect knowledge gaps.
"""
from typing import List, Dict, Optional, Callable
import json
import re
import time

from app.ai.embedder import Embedder
from app.ai.vector_db import VectorDB
from app.ai.llm_service import LLMService
from app.models.document import Document, CourseInfo
from app.monitoring import monitor


class GapDetector:
    """Service for detecting knowledge gaps in documents."""
    
    def __init__(self):
        """Initialize gap detection service."""
        self.embedder = Embedder()
        self.vector_db = VectorDB()
        self.llm_service = LLMService()
    
    def detect_gaps(
        self,
        document: Document,
        course_info: CourseInfo,
        progress_callback: Optional[Callable[[str, str, Optional[Dict]], None]] = None
    ) -> List[Dict]:
        """
        Detect knowledge gaps in a document.
        
        Args:
            document: Document object with extracted text
            course_info: Course information
            progress_callback: Optional callback function(stage, message, data) for progress updates
            
        Returns:
            List of gap dictionaries with concept, category, explanation, etc.
        """
        if not document.extraction or not document.extraction.text:
            raise ValueError("Document must have extracted text")
        
        analysis_start_time = time.time()
        
        def emit(stage: str, message: str = "", data: Optional[Dict] = None):
            """Helper to emit progress events."""
            if progress_callback:
                progress_callback(stage, message, data)
            print(f"[{stage}] {message}")
        
        # Step 1: Generate embeddings for document chunks
        emit("embeddings_generating", "Generating embeddings for document chunks...")
        embedding_start = time.time()
        chunks = document.extraction.chunks
        chunk_data = getattr(document.extraction, 'chunk_data', [])
        
        # Diagnostic logging
        doc_length = len(document.extraction.text) if document.extraction.text else 0
        page_count = document.extraction.total_pages if hasattr(document.extraction, 'total_pages') else 0
        print(f"📊 Document stats: {page_count} pages, {doc_length} chars, {len(chunks)} chunks")
        
        if not chunks:
            # Fallback: create chunks if not already created
            from app.ai.pdf_parser import PDFParser
            parser = PDFParser()
            chunks = parser.chunk_text(document.extraction.text)
            # Create chunk_data with default page 0 for fallback chunks
            chunk_data = [{"text": chunk, "page": 0} for chunk in chunks]
            print(f"⚠️ Created fallback chunks: {len(chunks)} chunks from {doc_length} chars")
        
        embeddings = self.embedder.generate_embeddings_batch(chunks)
        embedding_duration = time.time() - embedding_start
        
        # Track embedding generation
        monitor.track_embedding_generation(
            text_count=len(chunks),
            generation_time=embedding_duration
        )
        
        emit("embeddings_generated", f"Generated embeddings for {len(chunks)} chunks", {"chunk_count": len(chunks)})
        
        # Step 2: Store in vector database with page numbers
        emit("vector_db_storing", "Storing chunks in vector database...")
        # Create metadata with actual page numbers from chunk_data
        metadatas = []
        for i, chunk in enumerate(chunks):
            page_num = chunk_data[i].get('page', 0) if i < len(chunk_data) else 0
            metadatas.append({
                "document_id": document.id,
                "page": page_num
            })
        
        document_ids = self.vector_db.add_documents(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=[f"{document.id}_chunk_{i}" for i in range(len(chunks))]
        )
        emit("vector_db_stored", f"Stored {len(chunks)} chunks in vector database", {"chunk_count": len(chunks)})
        
        # Step 3: Retrieve relevant context using RAG (vector search)
        emit("rag_retrieving", "Retrieving relevant context using RAG...")
        rag_start = time.time()
        rag_context = self._retrieve_rag_context(document.extraction.text, document.id, course_info)
        rag_duration = time.time() - rag_start
        
        # Track RAG retrieval (approximate - actual chunk count tracked in _retrieve_rag_context)
        monitor.track_rag_retrieval(
            document_id=document.id,
            query_concepts=[],  # Will be tracked in get_context_for_gaps
            chunks_retrieved=len(rag_context.split('\n\n')) if rag_context else 0,
            retrieval_time=rag_duration,
            total_chars=len(rag_context),
            course_info_used=bool(course_info.course_code)
        )
        
        emit("rag_retrieved", "Retrieved relevant context using RAG", {"context_length": len(rag_context)})
        
        # Step 4: Use LLM to analyze and detect gaps with RAG context
        emit("llm_analyzing", "Analyzing document with AI to detect gaps...")
        course_info_dict = {
            "course_code": course_info.course_code,
            "institution": course_info.institution,
            "course_name": course_info.course_name,  # Optional field - None if not provided
            "course_type": course_info.course_type.value,
            "current_level": course_info.current_level.value,
            "learning_goal": course_info.learning_goal.value
        }
        
        analysis_result = self.llm_service.analyze_document_for_gaps(
            document_text=document.extraction.text,
            course_info=course_info_dict,
            rag_context=rag_context  # Inject RAG context
        )
        emit("llm_analyzed", "AI analysis completed")
        
        # Step 5: Parse LLM response to extract gaps
        emit("gaps_parsing", "Parsing detected gaps...")
        gaps = self._parse_gaps_from_analysis(analysis_result["analysis"], document)
        emit("gaps_parsed", f"Parsed {len(gaps)} gaps from analysis", {"gap_count": len(gaps)})
        
        # Step 6: Enhance gaps with RAG context (retrieve specific context for each gap)
        emit("gaps_enhancing", "Enhancing gaps with RAG context...")
        gaps = self._enhance_gaps_with_rag(gaps, document.id, course_info)
        emit("gaps_enhanced", "Enhanced gaps with RAG context")
        
        # Step 7: Extract assignment context and force CRITICAL gaps if needed
        assignment_context = self._extract_assignment_context(document.extraction.text)
        if assignment_context and not any(g.get("category") == "critical" for g in gaps):
            emit("gaps_force_critical", "Forcing CRITICAL gap detection based on assignment context...")
            gaps = self._force_critical_gaps(gaps, document.extraction.text, assignment_context)
        
        # Step 8: Final validation - ensure specific concepts
        gaps = self._ensure_specific_concepts(gaps, document.extraction.text)
        
        # Emit completion
        critical_count = len([g for g in gaps if g.get("category") == "critical"])
        safe_count = len([g for g in gaps if g.get("category") == "safe"])
        analysis_duration = time.time() - analysis_start_time
        
        # Track gap analysis metrics
        parsing_success = len(gaps) > 0
        monitor.track_gap_analysis(
            document_id=document.id,
            total_gaps=len(gaps),
            critical_gaps=critical_count,
            safe_gaps=safe_count,
            analysis_duration=analysis_duration,
            parsing_success=parsing_success,
            rag_enhanced=True
        )
        
        emit("completed", "Gap analysis completed", {
            "total_gaps": len(gaps),
            "critical_gaps": critical_count,
            "safe_gaps": safe_count
        })
        
        return gaps
    
    def _parse_gaps_from_analysis(self, analysis_text: str, document: Document) -> List[Dict]:
        """
        Parse gaps from LLM analysis response.
        Improved parsing to extract multiple specific gaps.
        
        Args:
            analysis_text: LLM analysis text
            document: Document object
            
        Returns:
            List of parsed gap dictionaries
        """
        # CRITICAL: Check if this is an error/fallback message - reject it immediately
        if self._is_error_or_fallback_message(analysis_text):
            print("❌ Detected error/fallback message in analysis. Rejecting to prevent parsing generic gaps.")
            return []  # Return empty list - don't parse error messages as gaps
        
        gaps = []
        
        # Strategy 1: Try to find structured gaps with clear markers
        # Look for patterns like "CRITICAL GAP: Concept Name" or "SAFE GAP: Concept Name"
        
        # Split text into sections (by double newlines or clear separators)
        sections = re.split(r'\n\s*\n+', analysis_text)
        
        current_gap = None
        current_section = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Check if this section starts a new gap
            # Pattern 1: "CRITICAL GAP: [Concept Name]"
            critical_match = re.search(
                r'CRITICAL\s+GAP\s*:?\s*(.+?)(?:\n|$|Explanation|Why)',
                section,
                re.IGNORECASE | re.DOTALL
            )
            
            # Pattern 2: "CRITICAL: [Concept Name]"
            if not critical_match:
                critical_match = re.search(
                    r'CRITICAL\s*:?\s*(.+?)(?:\n|$|Explanation|Why)',
                    section,
                    re.IGNORECASE | re.DOTALL
                )
            
            # Pattern 3: "SAFE GAP: [Concept Name]"
            safe_match = re.search(
                r'SAFE\s+GAP\s*:?\s*(.+?)(?:\n|$|Explanation|Why)',
                section,
                re.IGNORECASE | re.DOTALL
            )
            
            # Pattern 4: "SAFE: [Concept Name]"
            if not safe_match:
                safe_match = re.search(
                    r'SAFE\s*:?\s*(.+?)(?:\n|$|Explanation|Why)',
                    section,
                    re.IGNORECASE | re.DOTALL
                )
            
            # If we found a new gap marker, save previous gap and start new one
            if critical_match or safe_match:
                # Save previous gap if exists
                if current_gap:
                    gaps.append(current_gap)
                
                # Extract concept name
                if critical_match:
                    concept = critical_match.group(1).strip()
                    # Clean up concept name (remove extra formatting)
                    concept = re.sub(r'^\d+[\.\)]\s*', '', concept)  # Remove numbering
                    concept = re.sub(r'^[-•*]\s*', '', concept)  # Remove bullets
                    concept = concept.split('\n')[0].strip()  # Take first line only
                    
                    current_gap = {
                        "concept": concept,
                        "category": "critical",
                        "explanation": "",
                        "whyNeeded": ""
                    }
                elif safe_match:
                    concept = safe_match.group(1).strip()
                    # Clean up concept name
                    concept = re.sub(r'^\d+[\.\)]\s*', '', concept)
                    concept = re.sub(r'^[-•*]\s*', '', concept)
                    concept = concept.split('\n')[0].strip()
                    
                    current_gap = {
                        "concept": concept,
                        "category": "safe",
                        "explanation": "",
                        "whyNeeded": ""
                    }
                
                # Extract explanation and why needed from this section
                self._extract_gap_details(section, current_gap)
            
            # If we have a current gap and this section doesn't start a new gap,
            # it might be continuation of current gap details
            elif current_gap:
                self._extract_gap_details(section, current_gap)
        
        # Add final gap if exists
        if current_gap:
            gaps.append(current_gap)
        
        # Strategy 2: If no structured gaps found, try alternative patterns
        if not gaps:
            gaps = self._parse_alternative_format(analysis_text)
        
        # Strategy 3: If still no gaps, try to extract from numbered/bulleted lists
        if not gaps:
            gaps = self._parse_list_format(analysis_text)
        
        # Clean up and validate gaps
        gaps = self._cleanup_gaps(gaps, document)
        
        # Validate gaps - check if they're generic/fallback
        is_generic = self._is_generic_gaps(gaps)
        if is_generic:
            print("⚠️ Warning: Detected generic/fallback gaps. Attempting improved extraction...")
            # Try more aggressive extraction
            improved_gaps = self._extract_concepts_aggressively(analysis_text)
            if improved_gaps and len(improved_gaps) > len(gaps):
                print(f"✅ Improved extraction found {len(improved_gaps)} gaps vs {len(gaps)} generic gaps")
                gaps = self._cleanup_gaps(improved_gaps, document)
        
        # Final validation - ensure we have specific concepts
        gaps = self._validate_and_fix_gaps(gaps, analysis_text)
        
        # Final validation pass: Ensure all gaps have complete sentences and specific "Why Needed"
        gaps = self._validate_completeness_and_specificity(gaps, document)
        
        # If still no gaps, create a minimal fallback (but try to extract something useful)
        if not gaps:
            # Try to extract at least one meaningful gap from the text
            fallback_gap = self._create_fallback_gap(analysis_text)
            if fallback_gap:
                gaps.append(fallback_gap)
        
        return gaps
    
    def _extract_gap_details(self, text: str, gap: Dict):
        """
        Extract explanation and whyNeeded from text section.
        Improved to capture complete sentences and multi-line sections.
        
        Args:
            text: Text section to parse
            gap: Gap dictionary to populate
        """
        # Use regex to find Explanation and Why Needed sections more robustly
        # This handles cases where sections span multiple lines or have various formats
        
        # Pattern 1: Find Explanation section (may span multiple lines)
        explanation_pattern = r'Explanation\s*:?\s*(.+?)(?=Why\s+(Needed|Important|Required)\s*:|CRITICAL\s+GAP|SAFE\s+GAP|$)'
        explanation_match = re.search(explanation_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if explanation_match:
            explanation_text = explanation_match.group(1).strip()
            # Clean up: remove extra whitespace, ensure complete sentences
            explanation_text = re.sub(r'\s+', ' ', explanation_text)  # Normalize whitespace
            gap["explanation"] = self._ensure_complete_sentence(explanation_text)
        else:
            # Fallback: try to find explanation without explicit marker
            # Look for text before "Why Needed" that doesn't contain gap markers
            why_pattern = r'Why\s+(Needed|Important|Required)\s*:'
            why_pos = re.search(why_pattern, text, re.IGNORECASE)
            if why_pos:
                # Text before "Why Needed" might be explanation
                potential_explanation = text[:why_pos.start()].strip()
                # Remove concept name if present at start
                concept = gap.get("concept", "")
                if concept and potential_explanation.lower().startswith(concept.lower()):
                    potential_explanation = potential_explanation[len(concept):].strip()
                    potential_explanation = re.sub(r'^[:\-]\s*', '', potential_explanation)  # Remove leading colon/dash
                if potential_explanation and len(potential_explanation) > 20:
                    gap["explanation"] = self._ensure_complete_sentence(potential_explanation)
        
        # Pattern 2: Find Why Needed section (may span multiple lines)
        why_needed_pattern = r'Why\s+(Needed|Important|Required)\s*:?\s*(.+?)(?=CRITICAL\s+GAP|SAFE\s+GAP|Explanation\s*:|$)'
        why_needed_match = re.search(why_needed_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if why_needed_match:
            why_needed_text = why_needed_match.group(2).strip()
            # Clean up: remove extra whitespace, ensure specific and complete
            why_needed_text = re.sub(r'\s+', ' ', why_needed_text)  # Normalize whitespace
            gap["whyNeeded"] = self._ensure_specific_and_complete(why_needed_text, gap.get("concept", ""))
        else:
            # Fallback: look for lines that contain "why", "needed", "important", "required" keywords
            lines = text.split('\n')
            why_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Check if line contains why/needed keywords and isn't a gap marker
                if re.search(r'\b(why|needed|important|required|prevents|without|cannot|missing)\b', line, re.IGNORECASE):
                    if not re.search(r'(CRITICAL|SAFE)\s+(GAP)?\s*:', line, re.IGNORECASE):
                        why_lines.append(line)
            
            if why_lines:
                why_needed_text = " ".join(why_lines).strip()
                gap["whyNeeded"] = self._ensure_specific_and_complete(why_needed_text, gap.get("concept", ""))
        
        # If explanation is still empty, try to extract from first paragraph after concept
        if not gap.get("explanation"):
            # Look for first substantial paragraph after concept name
            concept = gap.get("concept", "")
            if concept:
                # Find concept position
                concept_pos = text.lower().find(concept.lower())
                if concept_pos >= 0:
                    # Get text after concept (first 300 chars)
                    after_concept = text[concept_pos + len(concept):concept_pos + len(concept) + 300]
                    # Remove gap markers and section headers
                    after_concept = re.sub(r'(CRITICAL|SAFE)\s+(GAP)?\s*:', '', after_concept, flags=re.IGNORECASE)
                    after_concept = re.sub(r'Explanation\s*:?\s*', '', after_concept, flags=re.IGNORECASE)
                    after_concept = re.sub(r'Why\s+(Needed|Important|Required)\s*:?\s*', '', after_concept, flags=re.IGNORECASE)
                    after_concept = after_concept.strip()
                    if after_concept and len(after_concept) > 20:
                        # Take first sentence or first 200 chars
                        first_sentence = re.split(r'[.!?]', after_concept)[0]
                        if len(first_sentence) > 20:
                            gap["explanation"] = self._ensure_complete_sentence(first_sentence + '.')
                        else:
                            gap["explanation"] = self._ensure_complete_sentence(after_concept[:200])
    
    def _parse_alternative_format(self, text: str) -> List[Dict]:
        """
        Parse gaps from alternative formats (numbered lists, bullet points).
        
        Args:
            text: Analysis text
            
        Returns:
            List of gap dictionaries
        """
        gaps = []
        
        # Look for numbered or bulleted lists with gap indicators
        # Pattern: "1. CRITICAL: Concept Name" or "- SAFE: Concept Name"
        patterns = [
            r'(\d+[\.\)])\s*(CRITICAL|SAFE)\s*:?\s*(.+?)(?:\n|$)',
            r'([-•*])\s*(CRITICAL|SAFE)\s*:?\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                category = match.group(2).lower()
                concept = match.group(3).strip()
                
                # Clean up concept name
                concept = re.sub(r'^\d+[\.\)]\s*', '', concept)
                concept = concept.split('\n')[0].strip()
                
                if len(concept) > 3 and len(concept) < 100:  # Reasonable length
                    gap = {
                        "concept": concept,
                        "category": "critical" if "critical" in category else "safe",
                        "explanation": "",
                        "whyNeeded": ""
                    }
                    gaps.append(gap)
        
        return gaps
    
    def _parse_list_format(self, text: str) -> List[Dict]:
        """
        Parse gaps from simple list format.
        
        Args:
            text: Analysis text
            
        Returns:
            List of gap dictionaries
        """
        gaps = []
        
        # Look for lines that start with numbers or bullets and contain concept-like text
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if line looks like a gap item
            # Pattern: "1. Concept Name" or "- Concept Name"
            match = re.match(r'^(\d+[\.\)]|[-•*])\s*(.+?)(?:\s*:|\s*$)', line)
            if match:
                concept = match.group(2).strip()
                
                # Check if next few lines contain gap-related keywords
                context = " ".join(lines[max(0, i-2):min(len(lines), i+5)])
                
                # Determine category based on context
                category = "safe"  # Default
                if re.search(r'\b(critical|must|required|essential|necessary|exam|assignment)\b', context, re.IGNORECASE):
                    category = "critical"
                
                if len(concept) > 5 and len(concept) < 100:
                    gap = {
                        "concept": concept,
                        "category": category,
                        "explanation": "",
                        "whyNeeded": ""
                    }
                    gaps.append(gap)
        
        return gaps
    
    def _cleanup_gaps(self, gaps: List[Dict], document: Optional[Document] = None) -> List[Dict]:
        """
        Clean up and validate gaps.
        
        Args:
            gaps: List of gap dictionaries
            document: Optional document object for context
            
        Returns:
            Cleaned list of gaps
        """
        cleaned_gaps = []
        seen_concepts = set()
        
        for gap in gaps:
            # Validate gap has required fields
            if not gap.get("concept") or len(gap.get("concept", "").strip()) < 3:
                continue
            
            # Remove duplicates (same concept)
            concept_lower = gap["concept"].lower().strip()
            if concept_lower in seen_concepts:
                continue
            seen_concepts.add(concept_lower)
            
            # Clean up concept name
            gap["concept"] = gap["concept"].strip()
            
            # Ensure category is valid
            if gap.get("category") not in ["critical", "safe"]:
                gap["category"] = "safe"  # Default to safe
            
            # Clean up explanation - ensure complete sentences
            gap["explanation"] = gap.get("explanation", "").strip()
            if not gap["explanation"]:
                gap["explanation"] = f"Concept: {gap['concept']} needs to be understood for this course."
            else:
                # Ensure explanation ends with complete sentence (no cutoff)
                gap["explanation"] = self._ensure_complete_sentence(gap["explanation"])
            
            # Clean up whyNeeded - ensure specific and complete
            gap["whyNeeded"] = gap.get("whyNeeded", "").strip()
            if not gap["whyNeeded"]:
                # Don't use generic fallback - try to extract from explanation or document
                if document:
                    gap["whyNeeded"] = self._generate_specific_why_needed(gap, document)
                else:
                    # Fallback if no document available
                    concept = gap.get("concept", "")
                    if gap.get("category") == "critical":
                        gap["whyNeeded"] = f"Required to solve problems in the document. Without understanding {concept}, you cannot complete essential tasks."
                    else:
                        gap["whyNeeded"] = f"Enhances understanding of related topics. Learning {concept} improves comprehension but is not strictly required for core tasks."
            else:
                # Ensure whyNeeded is specific (not generic) and complete
                gap["whyNeeded"] = self._ensure_specific_and_complete(gap["whyNeeded"], gap["concept"])
            
            # Limit explanation and whyNeeded length - but at complete sentences, not mid-word
            if len(gap["explanation"]) > 500:
                gap["explanation"] = self._truncate_at_sentence(gap["explanation"], max_length=500)
            if len(gap["whyNeeded"]) > 300:
                gap["whyNeeded"] = self._truncate_at_sentence(gap["whyNeeded"], max_length=300)
            
            cleaned_gaps.append(gap)
        
        return cleaned_gaps
    
    def _ensure_complete_sentence(self, text: str) -> str:
        """
        Ensure text ends with a complete sentence (no cutoff).
        
        Args:
            text: Text to validate
            
        Returns:
            Text with complete sentence ending
        """
        if not text:
            return text
        
        text = text.strip()
        
        # Check if text ends with sentence-ending punctuation
        if text.endswith(('.', '!', '?')):
            return text
        
        # If text ends with "..." it's likely truncated
        if text.endswith('...'):
            # Remove the "..." and try to find last complete sentence
            text = text[:-3].strip()
            # Find last sentence-ending punctuation
            last_period = text.rfind('.')
            last_exclamation = text.rfind('!')
            last_question = text.rfind('?')
            last_sentence_end = max(last_period, last_exclamation, last_question)
            
            if last_sentence_end > 0:
                # Return up to last complete sentence
                return text[:last_sentence_end + 1]
            # If no sentence ending found, return as-is (might be intentional)
            return text
        
        # If text doesn't end with punctuation, check if it's a complete thought
        # Look for common incomplete patterns
        incomplete_patterns = [
            r'\b(and|or|but|because|since|when|if|while|although)\s*$',
            r'\b(the|a|an|this|that|these|those)\s*$',
            r'\b(is|are|was|were|has|have|had|will|would|should|could)\s*$',
        ]
        
        for pattern in incomplete_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Text appears incomplete, try to find last complete sentence
                last_period = text.rfind('.')
                last_exclamation = text.rfind('!')
                last_question = text.rfind('?')
                last_sentence_end = max(last_period, last_exclamation, last_question)
                
                if last_sentence_end > 0:
                    return text[:last_sentence_end + 1]
                # If no sentence found, add period to make it complete
                return text + '.'
        
        # Text appears complete, return as-is
        return text
    
    def _truncate_at_sentence(self, text: str, max_length: int) -> str:
        """
        Truncate text at a complete sentence boundary, not mid-sentence.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            
        Returns:
            Truncated text ending at complete sentence
        """
        if len(text) <= max_length:
            return text
        
        # Truncate to max_length
        truncated = text[:max_length]
        
        # Find last complete sentence within truncated text
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        # If we found a sentence ending within reasonable distance (within 50 chars of max)
        if last_sentence_end > max_length - 50:
            return truncated[:last_sentence_end + 1]
        
        # If no sentence ending found, look for last space to avoid cutting words
        last_space = truncated.rfind(' ')
        if last_space > max_length - 30:
            return truncated[:last_space] + '.'
        
        # Fallback: return truncated with ellipsis (but this should be rare)
        return truncated + "..."
    
    def _ensure_specific_and_complete(self, why_needed: str, concept: str) -> str:
        """
        Ensure 'Why Needed' is specific (not generic) and complete.
        
        Args:
            why_needed: Current "Why Needed" text
            concept: Gap concept name
            
        Returns:
            Specific and complete "Why Needed" text
        """
        if not why_needed:
            return why_needed
        
        why_needed = why_needed.strip()
        
        # Check if it's generic (common generic phrases)
        generic_phrases = [
            "this concept is important for understanding",
            "this concept is important to understand",
            "important for understanding the course material",
            "important to understand the course material",
            "this concept is important",
            "needs to be understood",
            "important for the course",
            "essential for learning",
        ]
        
        is_generic = any(phrase in why_needed.lower() for phrase in generic_phrases)
        
        # Check if it's specific (mentions question numbers, assignment numbers, specific topics)
        specific_indicators = [
            r'\b(question|q\.?)\s*\d+',
            r'\b(assignment|assn\.?|hw\.?|homework)\s*\d+',
            r'\b(problem|prob\.?)\s*\d+',
            r'\b(exam|test|quiz)\s*\d+',
            r'\b(section|chapter|lecture)\s*\d+',
            r'\b(required|needed|necessary)\s+(for|to|in)',
            r'\b(without|missing|lack)\s+(this|understanding|knowledge)',
            r'\b(cannot|cannot|unable)\s+(to|solve|complete|understand)',
            r'\b(prevents|blocks|stops)\s+(you|student|completing)',
        ]
        
        is_specific = any(re.search(pattern, why_needed, re.IGNORECASE) for pattern in specific_indicators)
        
        # If generic and not specific, try to improve it
        if is_generic and not is_specific:
            # Try to extract more specific information from the text
            # Look for any references to questions, assignments, etc.
            improved = self._extract_specific_reason(why_needed, concept)
            if improved and improved != why_needed:
                return self._ensure_complete_sentence(improved)
        
        # Ensure it's complete (no cutoff)
        return self._ensure_complete_sentence(why_needed)
    
    def _extract_specific_reason(self, text: str, concept: str) -> str:
        """
        Try to extract or improve specific reason from text.
        
        Args:
            text: Current text
            concept: Concept name
            
        Returns:
            Improved specific text if possible, otherwise original
        """
        # Look for any specific references in the text
        # Pattern: "required for X" or "needed to Y"
        patterns = [
            r'(required|needed|necessary)\s+(for|to|in)\s+([^.]+)',
            r'(without|missing)\s+([^.]+)',
            r'(prevents|blocks|stops)\s+([^.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Found a specific reference, use it
                if len(match.groups()) >= 2:
                    reason_part = match.group(0)
                    # Try to make it more specific
                    if 'question' not in reason_part.lower() and 'assignment' not in reason_part.lower():
                        # Add concept context
                        return f"Required for {concept} understanding. {reason_part.capitalize()}."
                    return reason_part.capitalize()
        
        # If no specific reference found, return original
        return text
    
    def _generate_specific_why_needed(self, gap: Dict, document: Document) -> str:
        """
        Generate a specific "Why Needed" when LLM didn't provide one.
        Tries to extract from explanation or document context.
        
        Args:
            gap: Gap dictionary
            document: Document object
            
        Returns:
            Specific "Why Needed" text
        """
        concept = gap.get("concept", "")
        explanation = gap.get("explanation", "")
        
        # Try to extract from explanation
        if explanation:
            # Look for question/assignment references in explanation
            question_match = re.search(r'\b(question|q\.?)\s*(\d+)', explanation, re.IGNORECASE)
            assignment_match = re.search(r'\b(assignment|assn\.?)\s*(\d+)', explanation, re.IGNORECASE)
            
            if question_match:
                q_num = question_match.group(2)
                return f"Required to solve Question {q_num}. Without understanding {concept}, you cannot complete this question."
            
            if assignment_match:
                a_num = assignment_match.group(2)
                return f"Required for Assignment {a_num}. Missing knowledge of {concept} prevents completing the assignment."
        
        # Try to extract from document text
        doc_text = document.extraction.text if document and document.extraction else ""
        if doc_text:
            # Look for concept mentions near question/assignment references
            concept_lower = concept.lower()
            doc_lower = doc_text.lower()
            
            # Find concept position
            concept_pos = doc_lower.find(concept_lower)
            if concept_pos >= 0:
                # Look for nearby question/assignment references (within 200 chars)
                context_start = max(0, concept_pos - 200)
                context_end = min(len(doc_text), concept_pos + len(concept) + 200)
                context = doc_text[context_start:context_end]
                
                question_match = re.search(r'\b(question|q\.?)\s*(\d+)', context, re.IGNORECASE)
                assignment_match = re.search(r'\b(assignment|assn\.?)\s*(\d+)', context, re.IGNORECASE)
                
                if question_match:
                    q_num = question_match.group(2)
                    return f"Required to solve Question {q_num} from the document. Without {concept}, you cannot answer this question."
                
                if assignment_match:
                    a_num = assignment_match.group(2)
                    return f"Required for Assignment {a_num} in the document. Missing {concept} knowledge prevents completing this assignment."
        
        # Last resort: Check if it's a CRITICAL gap (should have specific reason)
        if gap.get("category") == "critical":
            return f"Required to solve problems in the document. Without understanding {concept}, you cannot complete essential tasks."
        
        # For SAFE gaps, be more general but still specific
        return f"Enhances understanding of related topics. Learning {concept} improves comprehension but is not strictly required for core tasks."
    
    def _validate_completeness_and_specificity(self, gaps: List[Dict], document: Document) -> List[Dict]:
        """
        Final validation pass: Ensure all gaps have complete sentences and specific "Why Needed".
        
        Args:
            gaps: List of gap dictionaries
            document: Document object for context
            
        Returns:
            Validated and improved gaps
        """
        validated_gaps = []
        
        for gap in gaps:
            # Validate explanation is complete
            explanation = gap.get("explanation", "")
            if explanation:
                gap["explanation"] = self._ensure_complete_sentence(explanation)
            else:
                # If no explanation, create a basic one
                concept = gap.get("concept", "")
                gap["explanation"] = f"{concept} is mentioned in the document but not fully explained."
            
            # Validate "Why Needed" is specific and complete
            why_needed = gap.get("whyNeeded", "")
            concept = gap.get("concept", "")
            
            if why_needed:
                # Check if it's generic
                generic_phrases = [
                    "this concept is important for understanding",
                    "this concept is important to understand",
                    "important for understanding the course material",
                    "important to understand the course material",
                ]
                
                is_generic = any(phrase in why_needed.lower() for phrase in generic_phrases)
                
                if is_generic:
                    # Try to generate a more specific one
                    improved = self._generate_specific_why_needed(gap, document)
                    if improved and improved != why_needed:
                        gap["whyNeeded"] = improved
                    else:
                        # Ensure it's at least complete
                        gap["whyNeeded"] = self._ensure_complete_sentence(why_needed)
                else:
                    # Ensure it's complete
                    gap["whyNeeded"] = self._ensure_specific_and_complete(why_needed, concept)
            else:
                # Generate specific "Why Needed" if missing
                gap["whyNeeded"] = self._generate_specific_why_needed(gap, document)
            
            validated_gaps.append(gap)
        
        return validated_gaps
    
    def _is_error_or_fallback_message(self, text: str) -> bool:
        """
        Check if the analysis text is an error/fallback message.
        These should NOT be parsed as gaps.
        
        Args:
            text: Analysis text to check
            
        Returns:
            True if text appears to be an error/fallback message
        """
        if not text or len(text.strip()) < 50:
            return False
        
        text_lower = text.lower()
        
        # Error message indicators (from llm_service.py fallback responses)
        error_indicators = [
            "for best results, try uploading",
            "contact support if this persists",
            "due to content filtering",
            "please review your document manually",
            "a detailed analysis could not be generated",
            "could not be generated automatically",
            "try uploading a different document",
            "please review your document",
            "manually and identify",
        ]
        
        # Check if text contains multiple error indicators (more reliable)
        error_count = sum(1 for indicator in error_indicators if indicator in text_lower)
        
        # If 2+ error indicators found, it's definitely an error message
        if error_count >= 2:
            print(f"⚠️ Detected error message with {error_count} error indicators")
            return True
        
        # Also check for the specific fallback pattern structure
        if "gap analysis for" in text_lower and "due to content filtering" in text_lower:
            return True
        
        return False
    
    def _is_generic_gaps(self, gaps: List[Dict]) -> bool:
        """
        Check if gaps are generic/fallback gaps.
        
        Args:
            gaps: List of gap dictionaries
            
        Returns:
            True if gaps appear to be generic/fallback
        """
        if not gaps:
            return True
        
        # Generic concept patterns
        generic_patterns = [
            r'concepts?\s+mentioned',
            r'topics?\s+that\s+appear',
            r'mathematical\s+or\s+computational\s+concepts?',
            r'concepts?\s+that\s+need',
            r'knowledge\s+gaps?',
            r'unexplained\s+concepts?',
            r'missing\s+information',
            r'concepts?\s+not\s+fully\s+explained',
        ]
        
        # Single-word generic concepts (extracted from error messages)
        single_word_generics = {
            'mathematical', 'topics', 'concepts', 'please', 'due', 'gap', 'analysis',
            'review', 'document', 'manually', 'identify', 'uploading', 'different',
            'contact', 'support', 'persists', 'results', 'best', 'try', 'filtering',
            'content', 'detailed', 'generated', 'automatically', 'appear', 'covered',
            'notes', 'assignments', 'computational', 'mentioned', 'explained', 'unexplained',
            'missing', 'information', 'knowledge', 'needs', 'needed', 'understanding'
        }
        
        generic_count = 0
        for gap in gaps:
            concept = gap.get("concept", "").strip().lower()
            
            # Check 1: Single-word generic concepts
            if concept in single_word_generics:
                generic_count += 1
                continue
            
            # Check 2: Very short concepts (likely generic)
            if len(concept) <= 3:
                generic_count += 1
                continue
            
            # Check 3: Concepts that are just common words
            if concept in ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can']:
                generic_count += 1
                continue
            
            # Check 4: Concept matches generic phrase patterns
            for pattern in generic_patterns:
                if re.search(pattern, concept):
                    generic_count += 1
                    break
        
        # If more than 50% are generic, consider them generic
        return generic_count > len(gaps) * 0.5
    
    def _extract_concepts_aggressively(self, text: str) -> List[Dict]:
        """
        More aggressive concept extraction from text.
        Looks for specific concepts mentioned in the document.
        
        Args:
            text: Analysis text
            
        Returns:
            List of gap dictionaries
        """
        gaps = []
        
        # Pattern 1: Look for capitalized concept names (e.g., "Power Method", "SVD Decomposition")
        concept_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
        concepts = re.findall(concept_pattern, text)
        
        # Pattern 2: Look for acronyms (e.g., "SVD", "PCA", "SVM")
        acronym_pattern = r'\b([A-Z]{2,5})\b'
        acronyms = re.findall(acronym_pattern, text)
        
        # Combine and deduplicate
        all_concepts = list(set(concepts + acronyms))
        
        # Filter out common words and generic terms
        common_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his',
            'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who',
            'boy', 'did', 'has', 'let', 'put', 'say', 'she', 'too', 'use', 'why',
            'CRITICAL', 'SAFE', 'GAP', 'Explanation', 'Needed', 'Important'
        }
        
        for concept in all_concepts:
            concept_clean = concept.strip()
            if (len(concept_clean) > 2 and 
                len(concept_clean) < 50 and 
                concept_clean.lower() not in common_words and
                not re.search(r'^\d+', concept_clean)):  # Not starting with number
                
                # Determine category based on context around concept
                context_start = max(0, text.find(concept) - 100)
                context_end = min(len(text), text.find(concept) + 100)
                context = text[context_start:context_end].lower()
                
                category = "safe"  # Default
                if re.search(r'\b(critical|must|required|essential|necessary|exam|assignment|question|problem)\b', context):
                    category = "critical"
                
                gaps.append({
                    "concept": concept_clean,
                    "category": category,
                    "explanation": f"Concept: {concept_clean} needs to be understood for this course.",
                    "whyNeeded": "This concept appears in the document and requires understanding."
                })
        
        return gaps
    
    def _validate_and_fix_gaps(self, gaps: List[Dict], analysis_text: str) -> List[Dict]:
        """
        Final validation and fixing of gaps.
        Ensures gaps have specific concepts, not generic descriptions.
        
        Args:
            gaps: List of gap dictionaries
            analysis_text: Original analysis text for reference
            
        Returns:
            Validated and fixed list of gaps
        """
        validated_gaps = []
        
        for gap in gaps:
            concept = gap.get("concept", "").strip()
            
            # Skip if concept is too generic
            if self._is_generic_concept(concept):
                # Try to extract a better concept name from explanation
                better_concept = self._extract_concept_from_explanation(gap.get("explanation", ""))
                if better_concept:
                    gap["concept"] = better_concept
                else:
                    # Skip this gap if we can't find a better concept
                    continue
            
            # Ensure explanation and whyNeeded are not generic
            if gap.get("explanation", "").strip() in [
                "This concept is important for understanding the course material.",
                "Concept: {} needs to be understood for this course.".format(concept),
                "Review the analysis above for specific gaps."
            ]:
                # Try to extract better explanation from analysis text
                better_explanation = self._extract_explanation_for_concept(concept, analysis_text)
                if better_explanation:
                    gap["explanation"] = better_explanation
            
            validated_gaps.append(gap)
        
        return validated_gaps
    
    def _is_generic_concept(self, concept: str) -> bool:
        """Check if a concept name is generic."""
        generic_patterns = [
            r'concepts?\s+mentioned',
            r'topics?\s+that\s+appear',
            r'mathematical\s+or\s+computational',
            r'concepts?\s+that\s+need',
            r'knowledge\s+gaps?',
            r'unexplained',
            r'missing',
        ]
        
        concept_lower = concept.lower()
        for pattern in generic_patterns:
            if re.search(pattern, concept_lower):
                return True
        return False
    
    def _extract_concept_from_explanation(self, explanation: str) -> Optional[str]:
        """Try to extract a specific concept name from explanation text."""
        # Look for capitalized phrases
        matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', explanation)
        for match in matches:
            if len(match) > 3 and len(match) < 50:
                return match
        return None
    
    def _extract_explanation_for_concept(self, concept: str, analysis_text: str) -> Optional[str]:
        """Extract explanation for a concept from analysis text."""
        # Find context around concept mention
        concept_lower = concept.lower()
        text_lower = analysis_text.lower()
        
        idx = text_lower.find(concept_lower)
        if idx == -1:
            return None
        
        # Extract surrounding context
        start = max(0, idx - 200)
        end = min(len(analysis_text), idx + 300)
        context = analysis_text[start:end]
        
        # Try to find explanation pattern
        explanation_match = re.search(
            r'(?:explanation|description|definition)[\s:]+(.+?)(?:\n\n|Why|CRITICAL|SAFE|$)',
            context,
            re.IGNORECASE | re.DOTALL
        )
        
        if explanation_match:
            explanation = explanation_match.group(1).strip()
            if len(explanation) > 20:  # Meaningful length
                return explanation[:500]  # Limit length
        
        return None
    
    def _create_fallback_gap(self, analysis_text: str) -> Optional[Dict]:
        """
        Create a fallback gap if no gaps were extracted.
        Tries to extract at least one meaningful concept.
        
        Args:
            analysis_text: Analysis text
            
        Returns:
            Fallback gap dictionary or None
        """
        # Try to find at least one concept mentioned in the text
        # Look for capitalized phrases that might be concepts
        concept_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b',  # "Power Method", "Dynamic Programming"
            r'([A-Z]{2,})',  # Acronyms like "SVD", "DFS", "BFS"
        ]
        
        for pattern in concept_patterns:
            matches = re.finditer(pattern, analysis_text)
            for match in matches:
                concept = match.group(1).strip()
                if len(concept) > 3 and len(concept) < 50:
                    return {
                        "concept": concept,
                        "category": "safe",
                        "explanation": analysis_text[:400] + "..." if len(analysis_text) > 400 else analysis_text,
                        "whyNeeded": "Review the analysis above for specific gaps."
                    }
        
        return None
    
    def _filter_results_by_distance(
        self,
        results: Dict,
        max_distance: float = 1.5
    ) -> tuple[List[str], List[float], List[int]]:
        """
        Filter RAG retrieval results by distance threshold.
        Only returns chunks with distance <= max_distance to prevent hallucinations.
        
        Args:
            results: Dictionary with 'documents', 'distances', and 'metadatas' keys from vector search
            max_distance: Maximum allowed distance (default 1.5 for cosine similarity)
                          Lower distance = better match. 1.5 is a reasonable threshold.
        
        Returns:
            Tuple of (filtered_chunks, filtered_distances, filtered_pages)
        """
        if not results or 'documents' not in results:
            return [], [], []
        
        documents = results['documents'][0] if results['documents'] else []
        distances = results.get('distances', [])
        distance_list = distances[0] if distances and len(distances) > 0 else []
        metadatas = results.get('metadatas', [])
        metadata_list = metadatas[0] if metadatas and len(metadatas) > 0 else []
        
        filtered_chunks = []
        filtered_distances = []
        filtered_pages = []
        
        for idx, chunk in enumerate(documents):
            if not chunk or not chunk.strip():
                continue
            
            # Get distance for this chunk (default to max_distance + 1 if not available)
            distance = distance_list[idx] if idx < len(distance_list) else (max_distance + 1.0)
            
            # Get page number from metadata (default to 0 if not available)
            page_num = 0
            if idx < len(metadata_list) and metadata_list[idx]:
                page_num = metadata_list[idx].get('page', 0)
            
            # Only include chunks with distance <= threshold
            if distance <= max_distance:
                filtered_chunks.append(chunk)
                filtered_distances.append(distance)
                filtered_pages.append(page_num)
            else:
                print(f"⚠️ Filtered out chunk with distance {distance:.3f} (threshold: {max_distance:.3f})")
        
        return filtered_chunks, filtered_distances, filtered_pages
    
    def _retrieve_rag_context(self, document_text: str, document_id: str, course_info: Optional['CourseInfo'] = None, n_chunks: int = 20) -> str:
        """
        Retrieve relevant context chunks using RAG (vector search).
        Uses multiple query strategies to get comprehensive context.
        Now includes course info for enhanced semantic matching.
        
        Args:
            document_text: Full document text
            document_id: Document ID for filtering
            course_info: Optional course information for enhanced RAG queries
            n_chunks: Number of chunks to retrieve (increased to 20 to support comprehensive gap analysis)
            
        Returns:
            Concatenated relevant context chunks
        """
        try:
            all_chunks = []
            seen_chunks = set()
            
            # Strategy 1: Query using document title/intro (first part)
            try:
                query_text_1 = document_text[:500]
                query_embedding_1 = self.embedder.generate_embedding(query_text_1)
                results_1 = self.vector_db.search_similar(
                    query_embedding=query_embedding_1,
                    n_results=n_chunks // 3,
                    where={"document_id": document_id}
                )
                # Filter by distance threshold to prevent hallucinations
                chunks_1, _, _ = self._filter_results_by_distance(results_1, max_distance=1.5)
                for chunk in chunks_1:
                    if chunk not in seen_chunks:
                        all_chunks.append(chunk)
                        seen_chunks.add(chunk)
            except Exception as e:
                print(f"⚠️ Strategy 1 RAG retrieval failed: {e}")
            
            # Strategy 2: Query using assignment/question keywords
            try:
                assignment_keywords = "assignment question problem exercise task solve find compute calculate"
                query_embedding_2 = self.embedder.generate_embedding(assignment_keywords)
                results_2 = self.vector_db.search_similar(
                    query_embedding=query_embedding_2,
                    n_results=n_chunks // 3,
                    where={"document_id": document_id}
                )
                # Filter by distance threshold to prevent hallucinations
                chunks_2, _, _ = self._filter_results_by_distance(results_2, max_distance=1.5)
                for chunk in chunks_2:
                    if chunk not in seen_chunks:
                        all_chunks.append(chunk)
                        seen_chunks.add(chunk)
            except Exception as e:
                print(f"⚠️ Strategy 2 RAG retrieval failed: {e}")
            
            # Strategy 3: Query using middle section (often contains core content)
            if len(document_text) > 1000:
                try:
                    query_text_3 = document_text[len(document_text)//2:len(document_text)//2 + 500]
                    query_embedding_3 = self.embedder.generate_embedding(query_text_3)
                    results_3 = self.vector_db.search_similar(
                        query_embedding=query_embedding_3,
                        n_results=n_chunks // 4,
                        where={"document_id": document_id}
                    )
                    # Filter by distance threshold to prevent hallucinations
                    chunks_3, _, _ = self._filter_results_by_distance(results_3, max_distance=1.5)
                    for chunk in chunks_3:
                        if chunk not in seen_chunks:
                            all_chunks.append(chunk)
                            seen_chunks.add(chunk)
                except Exception as e:
                    print(f"⚠️ Strategy 3 RAG retrieval failed: {e}")
            
            # Strategy 4: Enhanced course info queries (multiple approaches for better coverage)
            # This provides powerful semantic enhancement for course-specific content retrieval
            if course_info:
                try:
                    # Build multiple course context queries for better semantic matching
                    course_queries = []
                    
                    # Query 4a: Basic course info (course_code + institution + course_name)
                    course_parts = [course_info.course_code, course_info.institution]
                    if course_info.course_name:
                        course_parts.append(course_info.course_name)
                    basic_query = " ".join(filter(None, course_parts))
                    if basic_query.strip():
                        course_queries.append(("basic", basic_query))
                    
                    # Query 4b: Course code + institution (for institution-specific content)
                    if course_info.course_code and course_info.institution:
                        institution_query = f"{course_info.course_code} {course_info.institution}"
                        course_queries.append(("institution", institution_query))
                    
                    # Query 4c: Course name + institution (for semantic matching on course topics)
                    if course_info.course_name and course_info.institution:
                        semantic_query = f"{course_info.course_name} {course_info.institution}"
                        course_queries.append(("semantic", semantic_query))
                    
                    # Query 4d: Combined with document context (first 200 chars for topic relevance)
                    if document_text and len(document_text) > 100:
                        doc_preview = document_text[:200].strip()
                        if course_info.course_code:
                            combined_query = f"{course_info.course_code} {doc_preview}"
                            course_queries.append(("combined", combined_query))
                    
                    # Execute all course queries and aggregate results
                    course_chunks_found = 0
                    for query_type, course_query in course_queries:
                        try:
                            print(f"📚 Using course info for RAG ({query_type}): {course_query[:100]}...")
                            query_embedding = self.embedder.generate_embedding(course_query)
                            results = self.vector_db.search_similar(
                                query_embedding=query_embedding,
                                n_results=max(3, n_chunks // (len(course_queries) + 1)),  # Distribute chunks across queries
                                where={"document_id": document_id}
                            )
                            # Filter by distance threshold to prevent hallucinations
                            chunks, _, _ = self._filter_results_by_distance(results, max_distance=1.5)
                            for chunk in chunks:
                                if chunk not in seen_chunks:
                                    all_chunks.append(chunk)
                                    seen_chunks.add(chunk)
                                    course_chunks_found += 1
                        except Exception as query_error:
                            print(f"⚠️ Course query ({query_type}) failed: {query_error}")
                            continue  # Continue with other queries
                    
                    if course_chunks_found > 0:
                        print(f"✅ Course info RAG retrieved {course_chunks_found} additional relevant chunks (from {len(course_queries)} queries)")
                except Exception as e:
                    print(f"⚠️ Strategy 4 (course info) RAG retrieval failed: {e}")
            
            if all_chunks:
                # Combine chunks into context
                context = "\n\n".join(all_chunks[:n_chunks])  # Limit to n_chunks
                context_chars = len(context)
                print(f"✅ Retrieved {len(all_chunks)} relevant chunks using RAG ({context_chars} chars, multi-strategy with course info)")
                
                # Diagnostic: Log if we got fewer chunks than expected
                if len(all_chunks) < 5:
                    print(f"⚠️ Warning: RAG retrieved only {len(all_chunks)} chunks. System will fall back to full document if insufficient.")
                
                return context
            else:
                print("⚠️ No chunks found in vector DB for RAG. Returning empty string (will trigger fallback to full document).")
                return ""  # Return empty to trigger fallback in llm_service
                
        except Exception as e:
            print(f"⚠️ Error retrieving RAG context: {e}, using full document text")
            return document_text[:3000]  # Fallback on error
    
    def _enhance_gaps_with_rag(self, gaps: List[Dict], document_id: str, course_info: Optional['CourseInfo'] = None) -> List[Dict]:
        """
        Enhance each gap with relevant RAG context.
        Uses course info to improve semantic matching for gap concepts.
        
        Args:
            gaps: List of gap dictionaries
            document_id: Document ID for filtering
            course_info: Optional course information for enhanced semantic matching
            
        Returns:
            Enhanced gaps with RAG context
        """
        enhanced_gaps = []
        
        for gap in gaps:
            concept = gap.get("concept", "")
            if not concept:
                enhanced_gaps.append(gap)
                continue
            
            try:
                # Build enhanced query: concept + course context for better semantic matching
                query_text = concept
                if course_info:
                    # Add course context to improve matching
                    course_context_parts = []
                    if course_info.course_code:
                        course_context_parts.append(course_info.course_code)
                    if course_info.institution:
                        course_context_parts.append(course_info.institution)
                    
                    if course_context_parts:
                        course_context = " ".join(course_context_parts)
                        query_text = f"{concept} {course_context}"  # Combine concept with course context
                
                # Retrieve specific context for this gap concept
                concept_embedding = self.embedder.generate_embedding(query_text)
                results = self.vector_db.search_similar(
                    query_embedding=concept_embedding,
                    n_results=5,  # Increased from 3 to 5 for better coverage
                    where={"document_id": document_id}
                )
                
                # Filter by distance threshold to prevent hallucinations
                relevant_chunks, _, relevant_pages = self._filter_results_by_distance(results, max_distance=1.5)
                if relevant_chunks:
                    # Add RAG context to gap metadata (for future use in chat)
                    gap["rag_context"] = "\n\n".join(relevant_chunks[:2])  # Top 2 chunks
                # Add page references for credibility
                if relevant_pages:
                    unique_pages = sorted(set(relevant_pages[:2]))  # Get unique pages from top 2 chunks
                    gap["page_references"] = unique_pages
                print(f"✅ Enhanced gap '{concept}' with RAG context (pages: {relevant_pages[:2] if relevant_pages else 'N/A'})")
                
            except Exception as e:
                print(f"⚠️ Error enhancing gap '{concept}' with RAG: {e}")
            
            enhanced_gaps.append(gap)
        
        return enhanced_gaps
    
    def _extract_assignment_context(self, text: str) -> Optional[str]:
        """
        Extract assignment/question context from document text.
        
        Args:
            text: Document text
            
        Returns:
            Assignment context string or None
        """
        # Look for assignment/question indicators
        assignment_patterns = [
            r'(?:assignment|homework|problem set|question|exercise|task)\s*\d+[:\-]?\s*(.+?)(?:\n\n|$)',
            r'question\s*\d+[:\-]?\s*(.+?)(?:\n\n|$)',
            r'problem\s*\d+[:\-]?\s*(.+?)(?:\n\n|$)',
        ]
        
        assignment_contexts = []
        for pattern in assignment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                context = match.group(1).strip()[:200]  # Limit length
                if len(context) > 20:
                    assignment_contexts.append(context)
        
        if assignment_contexts:
            return "\n".join(assignment_contexts[:5])  # Max 5 questions
        return None
    
    def _force_critical_gaps(self, gaps: List[Dict], document_text: str, assignment_context: str) -> List[Dict]:
        """
        Force detection of CRITICAL gaps by analyzing assignments.
        
        Args:
            gaps: Existing gaps
            document_text: Full document text
            assignment_context: Assignment/question context
            
        Returns:
            Updated gaps with CRITICAL gaps added
        """
        # Extract concepts mentioned in assignments but not in notes
        assignment_concepts = self._extract_concepts_from_assignments(assignment_context, document_text)
        
        # Convert assignment concepts to CRITICAL gaps
        for concept in assignment_concepts:
            # Check if concept already exists in gaps
            concept_lower = concept.lower()
            existing = any(g.get("concept", "").lower() == concept_lower for g in gaps)
            
            if not existing:
                gaps.append({
                    "concept": concept,
                    "category": "critical",
                    "explanation": f"{concept} is required to solve assignment problems but is not fully explained in the notes.",
                    "whyNeeded": f"This concept appears in assignment questions and is essential for completing the work."
                })
        
        return gaps
    
    def _extract_concepts_from_assignments(self, assignment_context: str, document_text: str) -> List[str]:
        """
        Extract specific concepts mentioned in assignments.
        
        Args:
            assignment_context: Assignment/question text
            document_text: Full document text
            
        Returns:
            List of concept names
        """
        concepts = []
        
        # Look for capitalized concept names in assignments
        concept_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
        matches = re.findall(concept_pattern, assignment_context)
        
        # Filter out common words and check if concept is mentioned in assignment but not explained
        common_words = {'Assignment', 'Question', 'Problem', 'Exercise', 'Task', 'Solve', 'Find', 'Compute', 'Calculate'}
        
        for concept in matches:
            if concept not in common_words and len(concept) > 3:
                # Check if concept appears in assignment but might not be explained
                concept_lower = concept.lower()
                if concept_lower in assignment_context.lower():
                    # Check if it's explained in document (simple heuristic)
                    explanation_keywords = ['explain', 'definition', 'is', 'are', 'method', 'algorithm', 'technique']
                    context_around = document_text.lower()
                    if concept_lower in context_around:
                        # Check if there's explanation nearby
                        idx = context_around.find(concept_lower)
                        surrounding = context_around[max(0, idx-50):min(len(context_around), idx+200)]
                        has_explanation = any(kw in surrounding for kw in explanation_keywords)
                        if not has_explanation or len(surrounding) < 100:
                            concepts.append(concept)
        
        return list(set(concepts))[:5]  # Max 5 concepts
    
    def _ensure_specific_concepts(self, gaps: List[Dict], document_text: str) -> List[Dict]:
        """
        Ensure gaps have specific concepts, not generic descriptions.
        
        Args:
            gaps: List of gaps
            document_text: Document text for reference
            
        Returns:
            Gaps with specific concepts
        """
        improved_gaps = []
        
        for gap in gaps:
            concept = gap.get("concept", "").strip()
            
            # If concept is generic, try to find specific concept
            if self._is_generic_concept(concept):
                # Try to extract from explanation
                better_concept = self._extract_concept_from_explanation(gap.get("explanation", ""))
                if better_concept:
                    gap["concept"] = better_concept
                else:
                    # Try to find concept in document text
                    concepts_in_doc = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', document_text)
                    if concepts_in_doc:
                        gap["concept"] = concepts_in_doc[0]  # Use first found concept
            
            improved_gaps.append(gap)
        
        return improved_gaps
    
    def get_context_for_gap(self, gap_concept: str, document_id: str, n_results: int = 3) -> str:
        """
        Get relevant context from document for a specific gap.
        
        Args:
            gap_concept: Concept name
            document_id: Document ID
            n_results: Number of context chunks to retrieve
            
        Returns:
            Relevant context text
        """
        # Generate embedding for the gap concept
        try:
            gap_embedding = self.embedder.generate_embedding(gap_concept)
            
            # Search for similar content
            results = self.vector_db.search_similar(
                gap_embedding,
                n_results=n_results,
                where={"document_id": document_id}
            )
        except Exception as e:
            print(f"⚠️ Error retrieving context for gap '{gap_concept}': {e}")
            # Return empty results for graceful degradation
            return []
        
        # Filter by distance threshold to prevent hallucinations
        context_chunks, _, _ = self._filter_results_by_distance(results, max_distance=1.5)
        
        if context_chunks:
            return "\n\n".join(context_chunks)
        
        return ""
    
    def get_context_for_gaps(
        self, 
        gap_concepts: List[str], 
        document_id: str, 
        n_results_per_concept: int = 5,  # Increased from 3 to 5 for better context per gap
        max_total_chars: int = 15000  # Increased from 8000 to 15000 to support 20+ gaps
    ) -> str:
        """
        Get relevant context from document for multiple gap concepts.
        Uses multi-query RAG strategy: retrieves context for each concept,
        then intelligently merges and deduplicates chunks.
        
        Args:
            gap_concepts: List of concept names to retrieve context for
            document_id: Document ID
            n_results_per_concept: Number of context chunks to retrieve per concept
            max_total_chars: Maximum total characters in returned context (for context window management)
            
        Returns:
            Merged and deduplicated relevant context text, prioritized by relevance
        """
        if not gap_concepts:
            return ""
        
        rag_start = time.time()
        try:
            all_chunks = []
            seen_chunks = set()  # For deduplication (exact match)
            chunk_scores = {}  # Track relevance scores for prioritization
            
            print(f"🔍 Retrieving RAG context for {len(gap_concepts)} gap concepts: {gap_concepts[:3]}...")
            
            # Strategy: Multi-query RAG - retrieve context for each gap concept
            for concept in gap_concepts:
                if not concept or not concept.strip():
                    continue
                
                try:
                    # Generate embedding for this gap concept
                    concept_embedding = self.embedder.generate_embedding(concept)
                    
                    # Search for similar content
                    results = self.vector_db.search_similar(
                        query_embedding=concept_embedding,
                        n_results=n_results_per_concept,
                        where={"document_id": document_id}
                    )
                except Exception as e:
                    print(f"⚠️ Error retrieving context for concept '{concept}': {e}")
                    continue
                
                # Filter by distance threshold to prevent hallucinations
                chunks, distances_filtered, pages_filtered = self._filter_results_by_distance(results, max_distance=1.5)
                
                # Add chunks with their relevance scores
                for idx, chunk in enumerate(chunks):
                    if chunk and chunk.strip():
                        # Use distance as relevance score (lower distance = higher relevance)
                        # Convert distance to score (0-1 scale, higher is better)
                        distance = distances_filtered[idx] if idx < len(distances_filtered) else 1.0
                        relevance_score = 1.0 / (1.0 + distance)  # Inverse distance as score
                        
                        # Deduplicate: check if we've seen this exact chunk
                        chunk_normalized = chunk.strip().lower()
                        if chunk_normalized not in seen_chunks:
                            all_chunks.append({
                                'text': chunk,
                                'concept': concept,
                                'score': relevance_score
                            })
                            seen_chunks.add(chunk_normalized)
                            chunk_scores[chunk] = relevance_score
                        else:
                            # If duplicate, keep the one with higher score
                            existing_chunk = next((c for c in all_chunks if c['text'].strip().lower() == chunk_normalized), None)
                            if existing_chunk and relevance_score > existing_chunk['score']:
                                existing_chunk['score'] = relevance_score
                                existing_chunk['concept'] = concept
            
            # Sort chunks by relevance score (highest first)
            all_chunks.sort(key=lambda x: x['score'], reverse=True)
            
            # Build context string, respecting max_total_chars limit
            context_parts = []
            total_chars = 0
            
            for chunk_data in all_chunks:
                chunk_text = chunk_data['text']
                chunk_length = len(chunk_text)
                
                # Check if adding this chunk would exceed limit
                if total_chars + chunk_length > max_total_chars:
                    # Try to add partial chunk if we have space
                    remaining_space = max_total_chars - total_chars
                    if remaining_space > 200:  # Only if meaningful space remains
                        # Add truncated chunk (keep complete sentences)
                        truncated = chunk_text[:remaining_space]
                        last_period = truncated.rfind('.')
                        if last_period > remaining_space * 0.7:  # If we can keep most of it
                            context_parts.append(truncated[:last_period + 1])
                    break
                
                context_parts.append(chunk_text)
                total_chars += chunk_length
            
            combined_context = "\n\n".join(context_parts)
            rag_duration = time.time() - rag_start
            
            # Track RAG retrieval for chat/gap explanations
            monitor.track_rag_retrieval(
                document_id=document_id,
                query_concepts=gap_concepts,
                chunks_retrieved=len(context_parts),
                retrieval_time=rag_duration,
                total_chars=total_chars,
                course_info_used=False  # This method doesn't use course info
            )
            
            print(f"✅ Retrieved {len(context_parts)} unique context chunks ({total_chars} chars) for {len(gap_concepts)} concepts")
            
            return combined_context
            
        except Exception as e:
            print(f"❌ Error retrieving context for gaps: {e}")
            monitor.track_error(
                error_type='rag_retrieval_error',
                error_message=str(e),
                context={'document_id': document_id, 'gap_concepts': gap_concepts}
            )
            # Fallback: return empty string, let caller handle fallback to full document
            return ""


