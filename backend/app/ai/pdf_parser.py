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
        Split text into chunks for embedding with improved sentence boundary detection.
        Uses recursive approach: tries paragraph breaks, then sentence endings, then word boundaries.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters (recommended: 100-200)
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        # Define separators in order of preference (most preferred first)
        # These help break at natural boundaries
        separators = [
            '\n\n',      # Paragraph breaks (highest priority)
            '\n',        # Line breaks
            '. ',        # Sentence endings with space
            '! ',        # Exclamation with space
            '? ',        # Question mark with space
            '.',         # Period without space
            '!',         # Exclamation without space
            '?',         # Question mark without space
            ' ',         # Word boundaries
        ]
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            # If we haven't reached the end of text, try to find a good break point
            if end < text_length:
                best_break = -1
                
                # Try each separator in order of preference
                for separator in separators:
                    # Look for separator near the end of the chunk (within last 30% of chunk)
                    search_start = max(0, int(chunk_size * 0.7))
                    break_pos = chunk.rfind(separator, search_start)
                    
                    if break_pos > search_start:
                        # Found a good break point
                        best_break = break_pos + len(separator)
                        break
                
                # If we found a good break point, use it
                if best_break > 0:
                    chunk = chunk[:best_break]
                    end = start + best_break
                # Otherwise, try to break at the last space (word boundary)
                else:
                    last_space = chunk.rfind(' ', int(chunk_size * 0.8))
                    if last_space > int(chunk_size * 0.7):
                        chunk = chunk[:last_space + 1]
                        end = start + last_space + 1
            
            chunk_text = chunk.strip()
            if chunk_text:  # Only add non-empty chunks
                chunks.append(chunk_text)
            
            # Move start position with overlap
            # Ensure we don't go backwards or skip too much
            start = max(start + 1, end - overlap)
            if start >= text_length:
                break
        
        return chunks
    
    def chunk_text_with_pages(
        self, 
        pages: List[Dict[str, any]], 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[Dict[str, any]]:
        """
        Split text into chunks while preserving page numbers.
        IMPROVED: Chunks across all pages (not per-page) to ensure better coverage
        and minimum chunk count for short documents.
        
        Args:
            pages: List of page dictionaries with 'page_number' and 'text' keys
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of chunk dictionaries with 'text' and 'page' keys
        """
        if not pages:
            return []
        
        # Step 1: Combine all pages into a single text with page markers
        # This allows chunking across page boundaries for better coverage
        combined_text_parts = []
        page_boundaries = []  # Track where each page starts in combined text
        
        current_position = 0
        for page_data in pages:
            page_number = page_data.get('page_number', 0)
            page_text = page_data.get('text', '')
            
            if not page_text or not page_text.strip():
                continue
            
            # Store page boundary: (start_position, page_number)
            page_boundaries.append((current_position, page_number))
            
            # Add page text with separator
            combined_text_parts.append(page_text)
            current_position += len(page_text) + 2  # +2 for separator
            
        # Combine all pages
        combined_text = '\n\n'.join(combined_text_parts)
        total_length = len(combined_text)
        
        # Step 2: Adaptive chunk sizing for short documents
        # Ensure we get at least 10 chunks for better RAG coverage
        min_chunks = 10
        if total_length > 0:
            # Calculate optimal chunk size to get minimum chunks
            # For short documents, reduce chunk size to ensure we get enough chunks
            if total_length < 2000:
                # Very short documents: use 100-150 char chunks to get 10+ chunks
                optimal_chunk_size = max(100, total_length // min_chunks)
                optimal_overlap = max(20, optimal_chunk_size // 5)
            elif total_length < 5000:
                # Short documents: use 300-500 char chunks
                optimal_chunk_size = min(500, max(300, total_length // min_chunks))
                optimal_overlap = min(overlap, optimal_chunk_size // 5)
            elif total_length < 10000:
                # Medium documents: use 500-700 char chunks
                optimal_chunk_size = min(700, max(500, total_length // min_chunks))
                optimal_overlap = min(overlap, optimal_chunk_size // 5)
            else:
                # Normal documents: use configured chunk size
                optimal_chunk_size = chunk_size
                optimal_overlap = overlap
        else:
            optimal_chunk_size = chunk_size
            optimal_overlap = overlap
        
        # Step 3: Chunk the combined text across all pages
        chunks = []
        start = 0
        text_length = len(combined_text)
        
        # Define separators in order of preference
        separators = [
            '\n\n',      # Paragraph breaks (highest priority)
            '\n',        # Line breaks
            '. ',        # Sentence endings with space
            '! ',        # Exclamation with space
            '? ',        # Question mark with space
            '.',         # Period without space
            '!',         # Exclamation without space
            '?',         # Question mark without space
            ' ',         # Word boundaries
        ]
        
        while start < text_length:
            end = start + optimal_chunk_size
            chunk = combined_text[start:end]
            
            # If we haven't reached the end of text, try to find a good break point
            if end < text_length:
                best_break = -1
                
                # Try each separator in order of preference
                for separator in separators:
                    # Look for separator near the end of the chunk (within last 30% of chunk)
                    search_start = max(0, int(optimal_chunk_size * 0.7))
                    break_pos = chunk.rfind(separator, search_start)
                    
                    if break_pos > search_start:
                        # Found a good break point
                        best_break = break_pos + len(separator)
                        break
                
                # If we found a good break point, use it
                if best_break > 0:
                    chunk = chunk[:best_break]
                    end = start + best_break
                # Otherwise, try to break at the last space (word boundary)
                else:
                    last_space = chunk.rfind(' ', int(optimal_chunk_size * 0.8))
                    if last_space > int(optimal_chunk_size * 0.7):
                        chunk = chunk[:last_space + 1]
                        end = start + last_space + 1
            
            chunk_text = chunk.strip()
            if chunk_text:  # Only add non-empty chunks
                # Determine which page this chunk belongs to
                # Find the page boundary that's closest but not after this chunk's start
                chunk_page = 0
                for boundary_pos, page_num in page_boundaries:
                    if boundary_pos <= start:
                        chunk_page = page_num
                    else:
                        break
            
                chunks.append({
                    'text': chunk_text,
                    'page': chunk_page
                })
            
            # Move start position with overlap
            # Ensure we don't go backwards or skip too much
            start = max(start + 1, end - optimal_overlap)
            if start >= text_length:
                break
        
        # Log chunking statistics for diagnostics
        print(f"📊 Chunking stats: {len(pages)} pages, {total_length} chars total, {len(chunks)} chunks created (target: {min_chunks} min)")
        if len(chunks) < min_chunks and total_length > 0:
            print(f"⚠️ Warning: Only {len(chunks)} chunks created for {total_length} char document. Consider reducing chunk_size.")
        
        return chunks
    
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


