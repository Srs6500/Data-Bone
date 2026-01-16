"""
Document service for handling document uploads and processing.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.models.document import Document, DocumentExtraction, DocumentMetadata, CourseInfo
from app.ai.pdf_parser import PDFParser
from app.config import settings


class DocumentService:
    """Service for managing documents."""
    
    def __init__(self):
        """Initialize the document service."""
        self.parser = PDFParser()
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def save_uploaded_file(self, file, filename: str) -> str:
        """
        Save uploaded file to disk.
        
        Args:
            file: Uploaded file object
            filename: Original filename
            
        Returns:
            Path to saved file
        """
        # Generate unique filename to avoid conflicts
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = self.upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return str(file_path)
    
    def create_document(
        self,
        filename: str,
        file_path: str,
        course_info: CourseInfo,
        file_size: int
    ) -> Document:
        """
        Create a document record.
        
        Args:
            filename: Original filename
            file_path: Path to saved file
            course_info: Course information
            file_size: File size in bytes
            
        Returns:
            Document object
        """
        document_id = str(uuid.uuid4())
        
        document = Document(
            id=document_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            course_info=course_info,
            uploaded_at=datetime.now(),
            processed=False
        )
        
        return document
    
    def process_document(self, document: Document) -> Document:
        """
        Process document: extract text and create chunks.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document with extraction data
        """
        try:
            # Extract text from PDF
            extraction_result = self.parser.extract_text(document.file_path)
            
            # Create chunks with page numbers preserved
            chunk_data = self.parser.chunk_text_with_pages(
                extraction_result['pages'],
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap
            )
            
            # Extract just the text for backward compatibility
            chunks = [chunk['text'] for chunk in chunk_data]
            
            # Create metadata
            metadata = DocumentMetadata(
                title=extraction_result['metadata'].get('title'),
                author=extraction_result['metadata'].get('author'),
                subject=extraction_result['metadata'].get('subject'),
                total_pages=extraction_result['total_pages']
            )
            
            # Create extraction object
            extraction = DocumentExtraction(
                text=extraction_result['text'],
                pages=extraction_result['pages'],
                metadata=metadata,
                total_pages=extraction_result['total_pages'],
                chunks=chunks,
                chunk_data=chunk_data  # Store chunk data with page numbers
            )
            
            document.extraction = extraction
            document.processed = True
            
            return document
            
        except Exception as e:
            print(f"Error processing document: {e}")
            raise Exception(f"Failed to process document: {str(e)}")
    
    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID.
        In a real app, this would query a database.
        For now, we'll use in-memory storage (simple dict).
        
        Args:
            document_id: Document ID
            
        Returns:
            Document if found, None otherwise
        """
        # TODO: Implement database storage
        # For now, return None (will be implemented with database)
        return None
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete document and its file.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if deleted, False otherwise
        """
        # TODO: Implement with database
        return False


