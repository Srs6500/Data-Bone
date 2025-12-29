"""
Vector database service using ChromaDB.
Stores and retrieves document embeddings for semantic search.
"""
import os
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings


class VectorDB:
    """Service for managing vector database operations."""
    
    def __init__(self):
        """Initialize ChromaDB client and collection."""
        self.client = None
        self.collection = None
        self.collection_name = settings.collection_name
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize ChromaDB client and create/get collection."""
        try:
            # Create persistent client
            self.client = chromadb.PersistentClient(
                path=settings.chroma_db_path,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            
            print(f"Vector database initialized: {self.collection_name}")
        except Exception as e:
            print(f"Error initializing vector database: {e}")
            raise
    
    def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector database.
        
        Args:
            documents: List of text documents
            embeddings: List of embedding vectors
            metadatas: Optional list of metadata dictionaries
            ids: Optional list of document IDs (auto-generated if not provided)
            
        Returns:
            List of document IDs
        """
        if not documents or not embeddings:
            raise ValueError("Documents and embeddings cannot be empty")
        
        if len(documents) != len(embeddings):
            raise ValueError("Documents and embeddings must have the same length")
        
        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Prepare metadatas
        if metadatas is None:
            metadatas = [{}] * len(documents)
        
        try:
            # Check which IDs already exist to avoid duplicates
            existing_ids = set()
            try:
                # Try to get existing documents with these IDs
                existing = self.collection.get(ids=ids)
                if existing and 'ids' in existing:
                    existing_ids = set(existing['ids'])
            except Exception:
                # If get fails, assume no existing documents
                pass
            
            # Filter out documents that already exist
            new_docs = []
            new_embeddings = []
            new_metadatas = []
            new_ids = []
            
            for i, doc_id in enumerate(ids):
                if doc_id not in existing_ids:
                    new_docs.append(documents[i])
                    new_embeddings.append(embeddings[i])
                    new_metadatas.append(metadatas[i])
                    new_ids.append(doc_id)
            
            # Only add new documents
            if new_docs:
                self.collection.add(
                    documents=new_docs,
                    embeddings=new_embeddings,
                    metadatas=new_metadatas,
                    ids=new_ids
                )
                print(f"Added {len(new_docs)} new documents to vector DB (skipped {len(existing_ids)} existing)")
            else:
                print(f"All {len(ids)} documents already exist in vector DB, skipping add")
            
            return ids
        except Exception as e:
            # If add fails, try upsert (update or insert)
            try:
                print(f"Add failed, trying upsert: {e}")
                self.collection.upsert(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                print(f"Successfully upserted {len(documents)} documents")
                return ids
            except Exception as upsert_error:
                print(f"Error adding/upserting documents to vector DB: {upsert_error}")
                raise
    
    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Search for similar documents using embedding.
        
        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            Dictionary with results (ids, documents, distances, metadatas)
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            
            return results
        except Exception as e:
            print(f"Error searching vector DB: {e}")
            raise
    
    def get_context(
        self,
        query_text: str,
        query_embedding: List[float],
        n_results: int = 3
    ) -> List[str]:
        """
        Get relevant context for a query.
        
        Args:
            query_text: Query text
            query_embedding: Query embedding
            n_results: Number of context chunks to return
            
        Returns:
            List of relevant text chunks
        """
        results = self.search_similar(query_embedding, n_results=n_results)
        
        if results and 'documents' in results and results['documents']:
            # Flatten the results (ChromaDB returns nested lists)
            documents = results['documents'][0] if results['documents'] else []
            return documents
        
        return []
    
    def delete_documents(self, ids: List[str]):
        """
        Delete documents from the vector database.
        
        Args:
            ids: List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
        except Exception as e:
            print(f"Error deleting documents: {e}")
            raise
    
    def get_collection_count(self) -> int:
        """
        Get the number of documents in the collection.
        
        Returns:
            Number of documents
        """
        return self.collection.count()


