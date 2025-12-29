"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name
    }


# Import API routes
from app.api import upload, analyze, chat
# from app.api import gaps, questions

# Include routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
# app.include_router(gaps.router, prefix="/api", tags=["gaps"])
# app.include_router(questions.router, prefix="/api", tags=["questions"])

