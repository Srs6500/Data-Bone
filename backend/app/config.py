"""
Configuration settings for the application.
Handles environment variables and API keys.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys - LLM Provider
    # For Gemini/Vertex AI (recommended for free tier)
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "us-central1"  # Default Vertex AI location
    google_application_credentials: Optional[str] = None  # Path to service account JSON
    
    # For OpenAI (alternative)
    openai_api_key: Optional[str] = None
    
    # LLM Provider Selection
    llm_provider: str = "gemini"  # Options: "gemini" or "openai"
    
    # Application Settings
    app_name: str = "Student Performance Enhancer"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # File Upload Settings
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list = [".pdf"]
    upload_dir: str = "uploads"
    
    # Vector Database Settings
    chroma_db_path: str = "./chroma_db"
    collection_name: str = "documents"
    
    # AI/ML Settings
    embedding_model: str = "all-MiniLM-L6-v2"  # Lightweight, fast model
    chunk_size: int = 1000  # Characters per chunk
    chunk_overlap: int = 200  # Overlap between chunks
    
    # Gemini/Vertex AI Settings
    gemini_model: str = "gemini-2.5-pro"  # Default model
    # Model priority optimized for analysis quality (Pro models first):
    # 1. Gemini 3 Pro (highest quality for gap analysis)
    # 2. Gemini 2.5 Pro (excellent quality, widely available)
    # 3. Gemini 2.5 Flash (fast, good quality fallback)
    # 4. Additional fallbacks (Gemini 3 Flash, 2.0 models, etc.)
    # 5. Gemini 1.5 Flash (final fallback)
    # This prioritizes quality for accurate gap detection and analysis
    temperature: float = 0.3  # Lower for more focused, accurate analysis
    max_tokens: int = 4096  # Higher limit for longer document analysis
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create global settings instance
settings = Settings()

