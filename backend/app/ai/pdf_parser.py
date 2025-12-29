"""
PDF Parser for extracting text and structure from PDF documents.
Handles various PDF formats including notes, assignments, and slides.
"""
import os
from typing import Dict, List, Optional
import pdfplumber
import PyPDF2
from pathlib import Path


class PDFParser:
    """Parser for extracting text and structure from PDF files."""
    
    def __init__(self):
        """Initialize the PDF parser."""
        self.supported_formats = ['.pdf']
    
    def extract_text(self, pdf_path: str) -> Dict[str, any]:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing:
                - text: Full extracted text
                - pages: List of page texts
                - metadata: PDF metadata
                - total_pages: Number of pages
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Try pdfplumber first (better for structured text)
        try:
            return self._extract_with_pdfplumber(pdf_path)
        except Exception as e:
            # Fallback to PyPDF2 if pdfplumber fails
            print(f"pdfplumber failed, trying PyPDF2: {e}")
            return self._extract_with_pypdf2(pdf_path)
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Dict[str, any]:
        """Extract text using pdfplumber (better for structured content)."""
        full_text = []
        pages_text = []
        metadata = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            metadata = {
                'title': pdf.metadata.get('Title', ''),
                'author': pdf.metadata.get('Author', ''),
                'subject': pdf.metadata.get('Subject', ''),
                'total_pages': len(pdf.pages)
            }
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    pages_text.append({
                        'page_number': page_num,
                        'text': page_text
                    })
                    full_text.append(page_text)
        
        return {
            'text': '\n\n'.join(full_text),
            'pages': pages_text,
            'metadata': metadata,
            'total_pages': len(pages_text)
        }
    
    def _extract_with_pypdf2(self, pdf_path: str) -> Dict[str, any]:
        """Extract text using PyPDF2 (fallback method)."""
        full_text = []
        pages_text = []
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            metadata = {
                'title': pdf_reader.metadata.get('/Title', '') if pdf_reader.metadata else '',
                'author': pdf_reader.metadata.get('/Author', '') if pdf_reader.metadata else '',
                'subject': pdf_reader.metadata.get('/Subject', '') if pdf_reader.metadata else '',
                'total_pages': len(pdf_reader.pages)
            }
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append({
                            'page_number': page_num,
                            'text': page_text
                        })
                        full_text.append(page_text)
                except Exception as e:
                    print(f"Error extracting page {page_num}: {e}")
                    continue
        
        return {
            'text': '\n\n'.join(full_text),
            'pages': pages_text,
            'metadata': metadata,
            'total_pages': len(pages_text)
        }
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into chunks for embedding.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < text_length:
                # Look for sentence endings near the end
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.7:  # If break point is reasonable
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            
            # Move start position with overlap
            start = end - overlap
            if start >= text_length:
                break
        
        return [chunk for chunk in chunks if chunk]  # Remove empty chunks
    
    def extract_structure(self, pdf_path: str) -> Dict[str, any]:
        """
        Extract document structure (headings, sections).
        This is a basic implementation.
        For more advanced structure detection, we'd use ML models.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with structure information
        """
        extraction_result = self.extract_text(pdf_path)
        text = extraction_result['text']
        
        # Basic structure detection
        lines = text.split('\n')
        potential_headings = []
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Simple heuristic: short lines, all caps, or numbered
            if (len(line_stripped) < 100 and 
                len(line_stripped) > 3 and
                (line_stripped.isupper() or 
                 line_stripped[0].isdigit() or
                 line_stripped.startswith('Chapter') or
                 line_stripped.startswith('Section'))):
                potential_headings.append({
                    'text': line_stripped,
                    'position': i,
                    'level': self._estimate_heading_level(line_stripped)
                })
        
        return {
            'headings': potential_headings,
            'total_sections': len(potential_headings)
        }
    
    def _estimate_heading_level(self, text: str) -> int:
        """Estimate heading level (1-3) based on text characteristics."""
        if text.isupper() and len(text) < 50:
            return 1  # Main heading
        elif text[0].isdigit() or text.startswith('Chapter'):
            return 1  # Main heading
        elif text.startswith(('Section', 'Part')):
            return 2  # Sub-heading
        else:
            return 3  # Minor heading


