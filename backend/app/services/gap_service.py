"""
Gap service for managing gap detection and analysis.
"""
from typing import List, Dict, Optional, Callable
from app.ai.gap_detector import GapDetector
from app.models.document import Document
from app.services.document_service import DocumentService


class GapService:
    """Service for gap detection operations."""
    
    def __init__(self):
        """Initialize gap service."""
        self.gap_detector = GapDetector()
        self.document_service = DocumentService()
    
    def analyze_document(self, document_id: str) -> Dict:
        """
        Analyze a document and detect gaps.
        
        Args:
            document_id: Document ID to analyze
            
        Returns:
            Dictionary with gaps and analysis results
        """
        # TODO: In a real app, fetch document from database
        # For now, we'll need to pass document directly
        # This will be called from the API with the document
        
        # This is a placeholder - actual implementation will fetch from DB
        pass
    
    def get_gaps_for_document(self, document: Document, progress_callback: Optional[Callable[[str, str, Optional[Dict]], None]] = None) -> List[Dict]:
        """
        Get gaps for a specific document.
        
        Args:
            document: Document object
            progress_callback: Optional callback function(stage, message, data) for progress updates
            
        Returns:
            List of gap dictionaries
        """
        if not document.processed:
            raise ValueError("Document must be processed before gap detection")
        
        # Detect gaps with progress callback
        gaps = self.gap_detector.detect_gaps(
            document=document,
            course_info=document.course_info,
            progress_callback=progress_callback
        )
        
        # Add IDs to gaps
        for i, gap in enumerate(gaps):
            gap["id"] = f"{document.id}_gap_{i}"
        
        return gaps
    
    def get_gap_context(self, gap_concept: str, document_id: str) -> str:
        """
        Get relevant context for a gap.
        
        Args:
            gap_concept: Concept name
            document_id: Document ID
            
        Returns:
            Relevant context text
        """
        return self.gap_detector.get_context_for_gap(
            gap_concept=gap_concept,
            document_id=document_id
        )
    
    def get_gaps_context(self, gap_concepts: List[str], document_id: str, max_chars: int = 8000) -> str:
        """
        Get relevant context for multiple gap concepts.
        Uses multi-query RAG to retrieve and merge context for all concepts.
        
        Args:
            gap_concepts: List of concept names
            document_id: Document ID
            max_chars: Maximum characters in returned context
            
        Returns:
            Merged and deduplicated relevant context text
        """
        return self.gap_detector.get_context_for_gaps(
            gap_concepts=gap_concepts,
            document_id=document_id,
            max_total_chars=max_chars
        )


