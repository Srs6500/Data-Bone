"""
Data models for documents and related entities.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class CourseType(str, Enum):
    """Course type enumeration."""
    PREREQUISITE = "prerequisite"
    CORE = "core"
    ELECTIVE = "elective"
    ADVANCED = "advanced"


class LearningGoal(str, Enum):
    """Learning goal enumeration."""
    PASS_EXAM = "pass_exam"
    ACE_ASSIGNMENT = "ace_assignment"
    UNDERSTAND = "understand"
    ALL = "all"


class CurrentLevel(str, Enum):
    """Current student level enumeration."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class CourseInfo(BaseModel):
    """Course information model."""
    course_code: str = Field(..., description="Course code (e.g., CS 101)")
    institution: str = Field(..., description="Institution name")
    course_name: Optional[str] = Field(None, description="Course name (e.g., Introduction to Computer Science) - optional for better RAG semantic matching")
    course_type: CourseType = Field(..., description="Type of course")
    learning_goal: LearningGoal = Field(..., description="Primary learning goal")
    current_level: CurrentLevel = Field(..., description="Student's current level")


class DocumentMetadata(BaseModel):
    """PDF document metadata."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    total_pages: int = 0


class DocumentExtraction(BaseModel):
    """Extracted document content."""
    text: str = Field(..., description="Full extracted text")
    pages: List[Dict] = Field(default_factory=list, description="Page-by-page text")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    total_pages: int = 0
    chunks: List[str] = Field(default_factory=list, description="Text chunks for embedding")
    chunk_data: List[Dict] = Field(default_factory=list, description="Chunk data with page numbers")


class Document(BaseModel):
    """Document model."""
    id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to stored file")
    file_size: int = Field(..., description="File size in bytes")
    course_info: CourseInfo = Field(..., description="Course information")
    extraction: Optional[DocumentExtraction] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed: bool = Field(default=False, description="Whether document has been processed")
    analysis_id: Optional[str] = Field(None, description="ID of analysis result")


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str
    filename: str
    message: str
    status: str = "uploaded"


