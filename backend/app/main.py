"""
Main FastAPI application entry point.
"""
import os
# Disable ddtrace auto-instrumentation if not needed (we use datadog package directly)
os.environ.setdefault('DD_TRACE_ENABLED', 'false')

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import time
from app.config import settings
from app.monitoring import monitor

# Create FastAPI app instance
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered tool to help students identify knowledge gaps and prepare for exams",
    debug=settings.debug
)

# Configure CORS (Cross-Origin Resource Sharing)
# This allows the frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add middleware for API request tracking
@app.middleware("http")
async def track_api_requests(request: Request, call_next):
    """Middleware to track API requests in Datadog."""
    start_time = time.time()
    path = request.url.path
    method = request.method
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Track API request
        monitor.track_api_request(
            endpoint=path,
            method=method,
            duration=duration,
            status_code=response.status_code
        )
        
        return response
    except Exception as e:
        duration = time.time() - start_time
        monitor.track_api_request(
            endpoint=path,
            method=method,
            duration=duration,
            status_code=500,
            error=str(e)
        )
        raise


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "message": "Student Performance Enhancer API",
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with component status."""
    from app.ai.vector_db import VectorDB
    from app.ai.llm_service import LLMService
    
    health_status = {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "components": {}
    }
    
    all_healthy = True
    
    # Check Vector DB
    try:
        vector_db = VectorDB()
        if vector_db.collection is not None:
            health_status["components"]["vector_db"] = "healthy"
            monitor.track_health_check("vector_db", True)
        else:
            health_status["components"]["vector_db"] = "unhealthy"
            monitor.track_health_check("vector_db", False)
            all_healthy = False
    except Exception as e:
        health_status["components"]["vector_db"] = f"error: {str(e)}"
        monitor.track_health_check("vector_db", False)
        all_healthy = False
    
    # Check LLM Service
    try:
        llm_service = LLMService()
        if llm_service.llm is not None or llm_service.chat_llm is not None:
            health_status["components"]["llm_service"] = "healthy"
            monitor.track_health_check("llm_service", True)
        else:
            health_status["components"]["llm_service"] = "unhealthy"
            monitor.track_health_check("llm_service", False)
            all_healthy = False
    except Exception as e:
        health_status["components"]["llm_service"] = f"error: {str(e)}"
        monitor.track_health_check("llm_service", False)
        all_healthy = False
    
    if not all_healthy:
        health_status["status"] = "degraded"
        return Response(
            content=str(health_status),
            status_code=503,  # Service Unavailable
            media_type="application/json"
        )
    
    return health_status


# Import API routes
from app.api import upload, analyze, chat
# from app.api import gaps, questions

# Include routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
# app.include_router(gaps.router, prefix="/api", tags=["gaps"])
# app.include_router(questions.router, prefix="/api", tags=["questions"])

