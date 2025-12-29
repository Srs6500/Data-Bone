"""
Gap detection service.
Orchestrates embeddings, vector database, and LLM to detect knowledge gaps.
"""
from typing import List, Dict, Optional
import json
import re

from app.ai.embedder import Embedder
from app.ai.vector_db import VectorDB
from app.ai.llm_service import LLMService
from app.models.document import Document, CourseInfo


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
        course_info: CourseInfo
    ) -> List[Dict]:
        """
        Detect knowledge gaps in a document.
        
        Args:
            document: Document object with extracted text
            course_info: Course information
            
        Returns:
            List of gap dictionaries with concept, category, explanation, etc.
        """
        if not document.extraction or not document.extraction.text:
            raise ValueError("Document must have extracted text")
        
        # Step 1: Generate embeddings for document chunks
        print("Generating embeddings...")
        chunks = document.extraction.chunks
        if not chunks:
            # Fallback: create chunks if not already created
            from app.ai.pdf_parser import PDFParser
            parser = PDFParser()
            chunks = parser.chunk_text(document.extraction.text)
        
        embeddings = self.embedder.generate_embeddings_batch(chunks)
        
        # Step 2: Store in vector database
        print("Storing in vector database...")
        document_ids = self.vector_db.add_documents(
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"document_id": document.id, "page": i} for i in range(len(chunks))],
            ids=[f"{document.id}_chunk_{i}" for i in range(len(chunks))]
        )
        
        # Step 3: Retrieve relevant context using RAG (vector search)
        print("Retrieving relevant context using RAG...")
        rag_context = self._retrieve_rag_context(document.extraction.text, document.id)
        
        # Step 4: Use LLM to analyze and detect gaps with RAG context
        print("Analyzing with LLM using RAG context...")
        course_info_dict = {
            "course_code": course_info.course_code,
            "institution": course_info.institution,
            "course_type": course_info.course_type.value,
            "current_level": course_info.current_level.value,
            "learning_goal": course_info.learning_goal.value
        }
        
        analysis_result = self.llm_service.analyze_document_for_gaps(
            document_text=document.extraction.text,
            course_info=course_info_dict,
            rag_context=rag_context  # Inject RAG context
        )
        
        # Step 5: Parse LLM response to extract gaps
        print("Parsing gaps...")
        gaps = self._parse_gaps_from_analysis(analysis_result["analysis"], document)
        
        # Step 6: Enhance gaps with RAG context (retrieve specific context for each gap)
        print("Enhancing gaps with RAG context...")
        gaps = self._enhance_gaps_with_rag(gaps, document.id)
        
        # Step 7: Extract assignment context and force CRITICAL gaps if needed
        assignment_context = self._extract_assignment_context(document.extraction.text)
        if assignment_context and not any(g.get("category") == "critical" for g in gaps):
            print("⚠️ Warning: No CRITICAL gaps found despite assignment context. Forcing CRITICAL detection...")
            gaps = self._force_critical_gaps(gaps, document.extraction.text, assignment_context)
        
        # Step 8: Final validation - ensure specific concepts
        gaps = self._ensure_specific_concepts(gaps, document.extraction.text)
        
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
        gaps = self._cleanup_gaps(gaps)
        
        # Validate gaps - check if they're generic/fallback
        is_generic = self._is_generic_gaps(gaps)
        if is_generic:
            print("⚠️ Warning: Detected generic/fallback gaps. Attempting improved extraction...")
            # Try more aggressive extraction
            improved_gaps = self._extract_concepts_aggressively(analysis_text)
            if improved_gaps and len(improved_gaps) > len(gaps):
                print(f"✅ Improved extraction found {len(improved_gaps)} gaps vs {len(gaps)} generic gaps")
                gaps = self._cleanup_gaps(improved_gaps)
        
        # Final validation - ensure we have specific concepts
        gaps = self._validate_and_fix_gaps(gaps, analysis_text)
        
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
        
        Args:
            text: Text section to parse
            gap: Gap dictionary to populate
        """
        lines = text.split('\n')
        
        explanation_lines = []
        why_needed_lines = []
        in_explanation = False
        in_why_needed = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for explanation marker
            if re.search(r'Explanation\s*:?\s*', line, re.IGNORECASE):
                in_explanation = True
                in_why_needed = False
                # Extract text after "Explanation:"
                explanation_text = re.sub(r'Explanation\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if explanation_text:
                    explanation_lines.append(explanation_text)
                continue
            
            # Check for why needed marker
            if re.search(r'Why\s+(Needed|Important|Required)\s*:?\s*', line, re.IGNORECASE):
                in_why_needed = True
                in_explanation = False
                # Extract text after "Why Needed:"
                why_text = re.sub(r'Why\s+(Needed|Important|Required)\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if why_text:
                    why_needed_lines.append(why_text)
                continue
            
            # Check if we hit a new gap marker (stop collecting)
            if re.search(r'(CRITICAL|SAFE)\s+(GAP)?\s*:?\s*', line, re.IGNORECASE):
                in_explanation = False
                in_why_needed = False
                break
            
            # Collect lines based on current state
            if in_explanation:
                explanation_lines.append(line)
            elif in_why_needed:
                why_needed_lines.append(line)
            # If neither marker found yet, assume it's explanation until we see "Why"
            elif not gap["explanation"] and not gap["whyNeeded"]:
                # Check if line contains "why" or "needed" keywords
                if re.search(r'\b(why|needed|important|required|appears|needed for)\b', line, re.IGNORECASE):
                    why_needed_lines.append(line)
                else:
                    explanation_lines.append(line)
        
        # Update gap with extracted information
        if explanation_lines:
            gap["explanation"] = " ".join(explanation_lines).strip()
        if why_needed_lines:
            gap["whyNeeded"] = " ".join(why_needed_lines).strip()
    
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
    
    def _cleanup_gaps(self, gaps: List[Dict]) -> List[Dict]:
        """
        Clean up and validate gaps.
        
        Args:
            gaps: List of gap dictionaries
            
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
            
            # Clean up explanation
            gap["explanation"] = gap.get("explanation", "").strip()
            if not gap["explanation"]:
                gap["explanation"] = f"Concept: {gap['concept']} needs to be understood for this course."
            
            # Clean up whyNeeded
            gap["whyNeeded"] = gap.get("whyNeeded", "").strip()
            if not gap["whyNeeded"]:
                gap["whyNeeded"] = f"This concept is important for understanding the course material."
            
            # Limit explanation and whyNeeded length
            if len(gap["explanation"]) > 500:
                gap["explanation"] = gap["explanation"][:500] + "..."
            if len(gap["whyNeeded"]) > 300:
                gap["whyNeeded"] = gap["whyNeeded"][:300] + "..."
            
            cleaned_gaps.append(gap)
        
        return cleaned_gaps
    
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
    
    def _retrieve_rag_context(self, document_text: str, document_id: str, n_chunks: int = 10) -> str:
        """
        Retrieve relevant context chunks using RAG (vector search).
        Uses multiple query strategies to get comprehensive context.
        
        Args:
            document_text: Full document text
            document_id: Document ID for filtering
            n_chunks: Number of chunks to retrieve
            
        Returns:
            Concatenated relevant context chunks
        """
        try:
            all_chunks = []
            seen_chunks = set()
            
            # Strategy 1: Query using document title/intro (first part)
            query_text_1 = document_text[:500]
            query_embedding_1 = self.embedder.generate_embedding(query_text_1)
            results_1 = self.vector_db.search_similar(
                query_embedding=query_embedding_1,
                n_results=n_chunks // 2,
                where={"document_id": document_id}
            )
            if results_1 and 'documents' in results_1 and results_1['documents']:
                chunks_1 = results_1['documents'][0] if results_1['documents'] else []
                for chunk in chunks_1:
                    if chunk not in seen_chunks:
                        all_chunks.append(chunk)
                        seen_chunks.add(chunk)
            
            # Strategy 2: Query using assignment/question keywords
            assignment_keywords = "assignment question problem exercise task solve find compute calculate"
            query_embedding_2 = self.embedder.generate_embedding(assignment_keywords)
            results_2 = self.vector_db.search_similar(
                query_embedding=query_embedding_2,
                n_results=n_chunks // 2,
                where={"document_id": document_id}
            )
            if results_2 and 'documents' in results_2 and results_2['documents']:
                chunks_2 = results_2['documents'][0] if results_2['documents'] else []
                for chunk in chunks_2:
                    if chunk not in seen_chunks:
                        all_chunks.append(chunk)
                        seen_chunks.add(chunk)
            
            # Strategy 3: Query using middle section (often contains core content)
            if len(document_text) > 1000:
                query_text_3 = document_text[len(document_text)//2:len(document_text)//2 + 500]
                query_embedding_3 = self.embedder.generate_embedding(query_text_3)
                results_3 = self.vector_db.search_similar(
                    query_embedding=query_embedding_3,
                    n_results=n_chunks // 3,
                    where={"document_id": document_id}
                )
                if results_3 and 'documents' in results_3 and results_3['documents']:
                    chunks_3 = results_3['documents'][0] if results_3['documents'] else []
                    for chunk in chunks_3:
                        if chunk not in seen_chunks:
                            all_chunks.append(chunk)
                            seen_chunks.add(chunk)
            
            if all_chunks:
                # Combine chunks into context
                context = "\n\n".join(all_chunks[:n_chunks])  # Limit to n_chunks
                print(f"✅ Retrieved {len(all_chunks)} relevant chunks using RAG (multi-strategy)")
                return context
            else:
                print("⚠️ No chunks found in vector DB, using full document text")
                return document_text[:3000]  # Fallback: use first 3000 chars
                
        except Exception as e:
            print(f"⚠️ Error retrieving RAG context: {e}, using full document text")
            return document_text[:3000]  # Fallback on error
    
    def _enhance_gaps_with_rag(self, gaps: List[Dict], document_id: str) -> List[Dict]:
        """
        Enhance each gap with relevant RAG context.
        
        Args:
            gaps: List of gap dictionaries
            document_id: Document ID for filtering
            
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
                # Retrieve specific context for this gap concept
                concept_embedding = self.embedder.generate_embedding(concept)
                results = self.vector_db.search_similar(
                    query_embedding=concept_embedding,
                    n_results=3,  # Get top 3 relevant chunks for this concept
                    where={"document_id": document_id}
                )
                
                if results and 'documents' in results and results['documents']:
                    relevant_chunks = results['documents'][0] if results['documents'] else []
                    if relevant_chunks:
                        # Add RAG context to gap metadata (for future use in chat)
                        gap["rag_context"] = "\n\n".join(relevant_chunks[:2])  # Top 2 chunks
                        print(f"✅ Enhanced gap '{concept}' with RAG context")
                
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
        gap_embedding = self.embedder.generate_embedding(gap_concept)
        
        # Search for similar content
        results = self.vector_db.search_similar(
            gap_embedding,
            n_results=n_results,
            where={"document_id": document_id}
        )
        
        if results and 'documents' in results and results['documents']:
            context_chunks = results['documents'][0] if results['documents'] else []
            return "\n\n".join(context_chunks)
        
        return ""
    
    def get_context_for_gaps(
        self, 
        gap_concepts: List[str], 
        document_id: str, 
        n_results_per_concept: int = 3,
        max_total_chars: int = 8000
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
        
        try:
            all_chunks = []
            seen_chunks = set()  # For deduplication (exact match)
            chunk_scores = {}  # Track relevance scores for prioritization
            
            print(f"🔍 Retrieving RAG context for {len(gap_concepts)} gap concepts: {gap_concepts[:3]}...")
            
            # Strategy: Multi-query RAG - retrieve context for each gap concept
            for concept in gap_concepts:
                if not concept or not concept.strip():
                    continue
                
                # Generate embedding for this gap concept
                concept_embedding = self.embedder.generate_embedding(concept)
                
                # Search for similar content
                results = self.vector_db.search_similar(
                    query_embedding=concept_embedding,
                    n_results=n_results_per_concept,
                    where={"document_id": document_id}
                )
                
                if results and 'documents' in results and results['documents']:
                    chunks = results['documents'][0] if results['documents'] else []
                    distances = results.get('distances', [])
                    
                    # Add chunks with their relevance scores
                    for idx, chunk in enumerate(chunks):
                        if chunk and chunk.strip():
                            # Use distance as relevance score (lower distance = higher relevance)
                            # Convert distance to score (0-1 scale, higher is better)
                            distance = distances[0][idx] if distances and len(distances) > 0 and idx < len(distances[0]) else 1.0
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
            
            print(f"✅ Retrieved {len(context_parts)} unique context chunks ({total_chars} chars) for {len(gap_concepts)} concepts")
            
            return combined_context
            
        except Exception as e:
            print(f"❌ Error retrieving context for gaps: {e}")
            # Fallback: return empty string, let caller handle fallback to full document
            return ""


