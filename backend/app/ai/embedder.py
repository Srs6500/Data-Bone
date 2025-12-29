"""
Embedding service for converting text to vectors.
Uses sentence-transformers for generating embeddings.
"""
from typing import List
from sentence_transformers import SentenceTransformer
from app.config import settings


class Embedder:
    """Service for generating text embeddings."""
    
    def __init__(self):
        """Initialize the embedding model."""
        self.model = None
        self.model_name = settings.embedding_model
    
    def _load_model(self):
        """Lazy load the model (only when needed)."""
        if self.model is None:
            print(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print("Embedding model loaded successfully")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        self._load_model()
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        return embedding.tolist()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).
        More efficient than calling generate_embedding multiple times.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            return []
        
        self._load_model()
        
        # Generate embeddings in batch
        embeddings = self.model.encode(
            valid_texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        return embeddings.tolist()
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings.
        
        Returns:
            Dimension of the embedding vector
        """
        self._load_model()
        # Get dimension from model
        return self.model.get_sentence_embedding_dimension()


