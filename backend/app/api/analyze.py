"""
API routes for document analysis and gap detection.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, List, Callable, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
import time

from app.models.document import Document
from app.monitoring import monitor

router = APIRouter()
# Initialize services lazily to avoid heavy import-time work
gap_service = None

def get_gap_service():
    """Get gap service instance (lazy initialization)."""
    global gap_service
    if gap_service is None:
        from app.services.gap_service import GapService
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


@router.post("/analyze/stream")
async def analyze_document_stream(request: AnalysisRequest):
    """
    Analyze a document with real-time progress updates via Server-Sent Events (SSE).
    
    Args:
        request: Analysis request with document ID
        
    Returns:
        StreamingResponse with SSE events for progress updates
    """
    start_time = time.time()
    
    async def event_generator():
        """Generator function that yields SSE events."""
        document_id = request.document_id
        
        try:
            # Get document from store
            document = documents_store.get(document_id)
            if not document:
                yield f"data: {json.dumps({'stage': 'error', 'message': f'Document {document_id} not found'})}\n\n"
                return
            
            # Use a queue to collect progress events from sync code
            import queue
            progress_queue = queue.Queue()
            
            # Progress callback function (called from sync code)
            def progress_callback(stage: str, message: str = "", data: Optional[Dict] = None):
                """Collect progress events in queue."""
                event_data = {
                    "stage": stage,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
                if data:
                    event_data.update(data)
                progress_queue.put(event_data)
            
            # Emit initial progress stages (already completed during upload)
            yield f"data: {json.dumps({'stage': 'uploaded', 'message': 'Document uploaded', 'timestamp': datetime.now().isoformat()})}\n\n"
            await asyncio.sleep(0.05)
            
            yield f"data: {json.dumps({'stage': 'extracted', 'message': 'Text extracted from PDF', 'timestamp': datetime.now().isoformat()})}\n\n"
            await asyncio.sleep(0.05)
            
            # Run gap detection in background thread with progress callback
            import concurrent.futures
            import threading
            
            gaps_result = [None]  # Use list to store result from thread
            error_result = [None]
            
            def run_analysis():
                """Run analysis in background thread."""
                try:
                    # Create a custom progress callback that filters out the basic "completed" event
                    # from gap_detector and replaces it with our properly formatted one
                    def filtered_progress_callback(stage: str, message: str = "", data: Optional[Dict] = None):
                        """Progress callback that filters out basic completed events."""
                        # Skip the basic "completed" event from gap_detector - we'll send our own
                        if stage == "completed":
                            return  # Don't queue the basic completed event
                        # Queue all other events normally
                        progress_callback(stage, message, data)
                    
                    gaps = get_gap_service().get_gaps_for_document(
                        document, progress_callback=filtered_progress_callback
                    )
                    gaps_result[0] = gaps
                    
                    # QUICK FIX: If 0 gaps and analysis likely failed, send error instead of completed
                    if len(gaps) == 0:
                        # Check if this is likely an error (safety filter block, etc.)
                        error_event = {
                            "stage": "error",
                            "message": "Analysis failed: Safety filters blocked the analysis or no gaps could be detected. Please try uploading a different document.",
                            "timestamp": datetime.now().isoformat()
                        }
                        progress_queue.put(error_event)
                        print(f"⚠️ Queued error event (0 gaps detected - likely analysis failure)")
                    else:
                        # Normal completion with gaps found
                        critical_gaps = [g for g in gaps if g.get("category") == "critical"]
                        safe_gaps = [g for g in gaps if g.get("category") == "safe"]
                        gap_responses = [
                            {
                                "id": gap.get("id", ""),
                                "concept": gap.get("concept", ""),
                                "category": gap.get("category", "safe"),
                                "explanation": gap.get("explanation", ""),
                                "whyNeeded": gap.get("whyNeeded", "")
                            }
                            for gap in gaps
                        ]
                        # Put a properly formatted completed event in the queue
                        completed_event = {
                            "stage": "completed",
                            "message": "Analysis completed",
                            "data": {
                                "documentId": document_id,
                                "gaps": gap_responses,
                                "totalGaps": len(gaps),
                                "criticalGaps": len(critical_gaps),
                                "safeGaps": len(safe_gaps),
                                "analyzedAt": datetime.now().isoformat()
                            },
                            "timestamp": datetime.now().isoformat()
                        }
                        progress_queue.put(completed_event)
                        print(f"✅ Queued completed event with {len(gaps)} gaps")
                except Exception as e:
                    print(f"❌ Error in run_analysis: {e}")
                    import traceback
                    traceback.print_exc()
                    error_result[0] = str(e)
            
            # Start analysis in background thread
            analysis_thread = threading.Thread(target=run_analysis, daemon=True)
            analysis_thread.start()
            
            # Monitor progress queue and emit events
            completed_event_received = False
            max_iterations = 1000  # Safety limit to prevent infinite loop
            iteration = 0
            
            while (analysis_thread.is_alive() or not progress_queue.empty()) and iteration < max_iterations:
                iteration += 1
                # Check for new progress events
                events_emitted = False
                try:
                    while True:
                        event = progress_queue.get_nowait()
                        # Check if this is the completed event
                        if event.get("stage") == "completed":
                            completed_event_received = True
                            print(f"📤 Emitting completed event with data: {bool(event.get('data'))}")
                        yield f"data: {json.dumps(event)}\n\n"
                        events_emitted = True
                except queue.Empty:
                    pass
                
                # If we received completed event, break early
                if completed_event_received:
                    print("✅ Completed event emitted, breaking loop")
                    break
                
                # Only sleep if no events were emitted (to avoid unnecessary delays)
                if not events_emitted:
                    await asyncio.sleep(0.1)  # Check every 100ms
            
            # Wait for thread to finish (with timeout)
            analysis_thread.join(timeout=5.0)  # Wait up to 5 seconds
            
            # Emit any remaining events (including the completed event we added)
            try:
                while True:
                    event = progress_queue.get_nowait()
                    if event.get("stage") == "completed":
                        completed_event_received = True
                        print(f"📤 Emitting final completed event with data: {bool(event.get('data'))}")
                    yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                pass
            
            # Check for errors
            if error_result[0]:
                yield f"data: {json.dumps({'stage': 'error', 'message': error_result[0], 'timestamp': datetime.now().isoformat()})}\n\n"
                return
            
            # Get final result
            gaps = gaps_result[0]
            if gaps is None:
                yield f"data: {json.dumps({'stage': 'error', 'message': 'Analysis failed', 'timestamp': datetime.now().isoformat()})}\n\n"
                return
            
            # If completed event wasn't received, emit it now as fallback
            if not completed_event_received:
                # Categorize gaps
                critical_gaps = [g for g in gaps if g.get("category") == "critical"]
                safe_gaps = [g for g in gaps if g.get("category") == "safe"]
                
                # Convert to response format
                gap_responses = [
                    {
                        "id": gap.get("id", ""),
                        "concept": gap.get("concept", ""),
                        "category": gap.get("category", "safe"),
                        "explanation": gap.get("explanation", ""),
                        "whyNeeded": gap.get("whyNeeded", "")
                    }
                    for gap in gaps
                ]
                
                # Emit final result
                final_result = {
                    "stage": "completed",
                    "message": "Analysis completed",
                    "data": {
                        "documentId": document_id,
                        "gaps": gap_responses,
                        "totalGaps": len(gaps),
                        "criticalGaps": len(critical_gaps),
                        "safeGaps": len(safe_gaps),
                        "analyzedAt": datetime.now().isoformat()
                    },
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(final_result)}\n\n"
            
        except Exception as e:
            duration = time.time() - start_time
            error_message = str(e)
            
            # Track API error
            monitor.track_api_request(
                endpoint="/api/analyze/stream",
                method="POST",
                duration=duration,
                status_code=500,
                error=error_message
            )
            
            monitor.track_error(
                error_type='analysis_stream_error',
                error_message=error_message,
                context={'document_id': request.document_id}
            )
            
            error_event = {
                "stage": "error",
                "message": error_message,
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    # Track API request start
    monitor.track_api_request(
        endpoint="/api/analyze/stream",
        method="POST",
        duration=0,  # Will be updated on completion
        status_code=200
    )
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )

