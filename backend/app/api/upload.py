"""
API routes for document upload.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import json

from app.services.document_service import DocumentService
from app.models.document import CourseInfo, CourseType, LearningGoal, CurrentLevel, DocumentUploadResponse
from app.config import settings
from app.api.analyze import store_document

router = APIRouter()
document_service = DocumentService()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    course_info_json: str = Form(..., description="Course information as JSON string")
):
    """
    Upload a PDF document for analysis.
    
    Args:
        file: PDF file to upload
        course_info_json: Course information as JSON string
        
    Returns:
        Document upload response with document ID
    """
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > settings.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {settings.max_upload_size / (1024*1024):.1f}MB"
            )
        
        # Parse course info
        try:
            course_info_dict = json.loads(course_info_json)
            course_info = CourseInfo(
                course_code=course_info_dict.get('courseCode', ''),
                institution=course_info_dict.get('institution', ''),
                course_name=course_info_dict.get('courseName'),  # Optional field - None if not provided
                course_type=CourseType(course_info_dict.get('courseType', 'prerequisite')),
                learning_goal=LearningGoal(course_info_dict.get('learningGoal', 'pass_exam')),
                current_level=CurrentLevel(course_info_dict.get('currentLevel', 'intermediate'))
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid course information: {str(e)}"
            )
        
        # Save uploaded file
        file_path = document_service.save_uploaded_file(file, file.filename)
        
        # Create document record
        document = document_service.create_document(
            filename=file.filename,
            file_path=file_path,
            course_info=course_info,
            file_size=file_size
        )
        
        # Process document (extract text)
        document = document_service.process_document(document)
        
        # Store document for analysis (temporary - should be in database)
        store_document(document)
        
        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            message="Document uploaded and processed successfully",
            status="processed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading document: {str(e)}"
        )


@router.get("/upload/test")
async def test_upload():
    """Test endpoint for upload route."""
    return {"message": "Upload endpoint is working"}

