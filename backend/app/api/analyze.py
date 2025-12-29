"""
API routes for document analysis and gap detection.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.gap_service import GapService
from app.services.document_service import DocumentService
from app.models.document import Document

router = APIRouter()
# Initialize services lazily to avoid import-time errors
gap_service = None
document_service = DocumentService()

def get_gap_service():
    """Get gap service instance (lazy initialization)."""
    global gap_service
    if gap_service is None:
        gap_service = GapService()
    return gap_service


class AnalysisRequest(BaseModel):
    """Request model for analysis."""
    document_id: str


class GapResponse(BaseModel):
    """Response model for a gap."""
    id: str
    concept: str
    category: str  # "critical" or "safe"
    explanation: str
    whyNeeded: str


class AnalysisResponse(BaseModel):
    """Response model for analysis."""
    document_id: str = Field(..., alias="documentId")
    gaps: List[GapResponse]
    total_gaps: int = Field(..., alias="totalGaps")
    critical_gaps: int = Field(..., alias="criticalGaps")
    safe_gaps: int = Field(..., alias="safeGaps")
    status: str = "completed"
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat(), alias="analyzedAt")
    
    model_config = {
        "populate_by_name": True,  # Allow both snake_case and camelCase
    }


# In-memory storage for documents (temporary - replace with database later)
documents_store: Dict[str, Document] = {}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(request: AnalysisRequest):
    """
    Analyze a document and detect knowledge gaps.
    
    Args:
        request: Analysis request with document ID
        
    Returns:
        Analysis response with detected gaps
    """
    try:
        document_id = request.document_id
        
        # Get document from store (temporary - should be from database)
        document = documents_store.get(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        # Detect gaps
        gaps = get_gap_service().get_gaps_for_document(document)
        
        # Categorize gaps
        critical_gaps = [g for g in gaps if g.get("category") == "critical"]
        safe_gaps = [g for g in gaps if g.get("category") == "safe"]
        
        # Convert to response format
        gap_responses = [
            GapResponse(
                id=gap.get("id", ""),
                concept=gap.get("concept", ""),
                category=gap.get("category", "safe"),
                explanation=gap.get("explanation", ""),
                whyNeeded=gap.get("whyNeeded", "")
            )
            for gap in gaps
        ]
        
        # Create response with camelCase for frontend compatibility
        response = AnalysisResponse(
            document_id=document_id,
            gaps=gap_responses,
            total_gaps=len(gaps),
            critical_gaps=len(critical_gaps),
            safe_gaps=len(safe_gaps),
            status="completed",
            analyzed_at=datetime.now().isoformat()
        )
        
        # Return with camelCase aliases (Pydantic v2)
        return response.model_dump(by_alias=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing document: {str(e)}"
        )


# Helper function to store document (called from upload endpoint)
def store_document(document: Document):
    """Store document in temporary storage."""
    documents_store[document.id] = document


# Helper function to get document
def get_document(document_id: str) -> Document:
    """Get document from temporary storage."""
    return documents_store.get(document_id)


@router.get("/analyze/debug")
async def debug_documents():
    """Debug endpoint to see stored documents."""
    return {
        "total_documents": len(documents_store),
        "document_ids": list(documents_store.keys())
    }

