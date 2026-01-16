"""
Vector database service using ChromaDB.
Stores and retrieves document embeddings for semantic search.
"""
import os
import time
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings

# Import monitor for tracking (optional, won't break if not available)
try:
    from app.monitoring import monitor
    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False
    monitor = None


class VectorDB:
    """Service for managing vector database operations."""
    
    def __init__(self):
        """Initialize ChromaDB client and collection."""
        self.client = None
        self.collection = None
        self.collection_name = settings.collection_name
        # Error tracking for frequency metrics
        self._search_count = 0
        self._error_count = 0
        self._error_count_by_type = {}  # Track errors by type
        self._last_error_rate_calculation = time.time()
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize ChromaDB client and create/get collection."""
        try:
            # Create persistent client
            # Handle tenant/database errors by allowing reset
            self.client = chromadb.PersistentClient(
                path=settings.chroma_db_path,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            # ChromaDB 1.4.0: Handle HNSW parameters carefully to avoid parsing errors
            try:
                # Try to get existing collection
                self.collection = self.client.get_collection(name=self.collection_name)
                print(f"Found existing collection: {self.collection_name}")
                
                # Check if collection has parsing errors - if so, delete and recreate
                try:
                    # Test if collection is accessible
                    _ = self.collection.count()
                except Exception as test_error:
                    error_str = str(test_error).lower()
                    if "parse" in error_str or "hnsw" in error_str or "metadata" in error_str:
                        print(f"⚠️ Collection has metadata parsing errors, deleting and recreating...")
                        try:
                            self.client.delete_collection(name=self.collection_name)
                            print(f"✅ Deleted collection with parsing errors: {self.collection_name}")
                            raise Exception("Collection deleted, will recreate")  # Force recreation
                        except Exception:
                            pass
            except Exception as get_error:
                # Collection doesn't exist or needs recreation
                error_str = str(get_error).lower()
                if "parse" in error_str or "hnsw" in error_str or "metadata" in error_str:
                    # Collection exists but has parsing errors, delete it
                    try:
                        self.client.delete_collection(name=self.collection_name)
                        print(f"✅ Deleted collection with parsing errors: {self.collection_name}")
                    except Exception:
                        pass  # Collection might not exist
                
                # Create new collection
                # For ChromaDB 1.4.0, use minimal metadata to avoid parsing issues
                # HNSW parameters may need to be set differently or use defaults
                try:
                    # Try with minimal metadata first (just space)
                    self.collection = self.client.create_collection(
                name=self.collection_name,
                        metadata={"hnsw:space": "cosine"}  # Minimal metadata to avoid parsing errors
                    )
                    print(f"✅ Created new collection: {self.collection_name}")
                except Exception as create_error:
                    error_str = str(create_error).lower()
                    # Handle race condition: collection was created by another thread/request
                    if "already exists" in error_str or "internalerror" in error_str:
                        # Collection exists (race condition), just get it
                        try:
                            self.collection = self.client.get_collection(name=self.collection_name)
                            print(f"✅ Collection already exists (race condition), retrieved: {self.collection_name}")
                        except Exception as get_retry_error:
                            print(f"❌ Failed to get collection after race condition: {get_retry_error}")
                            raise
                    else:
                        # If even minimal metadata fails, try with no metadata
                        print(f"⚠️ Failed with metadata, trying without: {create_error}")
                        try:
                            self.collection = self.client.create_collection(
                                name=self.collection_name
                            )
                            print(f"✅ Created new collection without metadata: {self.collection_name}")
                        except Exception as final_error:
                            final_error_str = str(final_error).lower()
                            # Handle race condition in fallback too
                            if "already exists" in final_error_str or "internalerror" in final_error_str:
                                try:
                                    self.collection = self.client.get_collection(name=self.collection_name)
                                    print(f"✅ Collection already exists (race condition), retrieved: {self.collection_name}")
                                except Exception as get_retry_error:
                                    print(f"❌ Failed to get collection after race condition: {get_retry_error}")
                                    raise
                            else:
                                print(f"❌ Failed to create collection: {final_error}")
                                raise
            
            print(f"Vector database initialized: {self.collection_name}")
        except Exception as e:
            print(f"Error initializing vector database: {e}")
            # If initialization fails due to database corruption or parsing errors, suggest deleting chroma_db
            error_str = str(e).lower()
            if "tenant" in error_str or "corrupted" in error_str or "no such table" in error_str or "parse" in error_str or "hnsw" in error_str:
                print("💡 Tip: Database has parsing/corruption issues. Delete ChromaDB directory:")
                print(f"   rm -rf {settings.chroma_db_path}")
                print("   Then restart the server to recreate with clean metadata.")
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
            where: Optional metadata filter (if provided, uses post-filtering to avoid "Error finding id")
            
        Returns:
            Dictionary with results (ids, documents, distances, metadatas)
        """
        import time
        
        # OPTIMIZATION: Use post-filtering for document_id filters to avoid "Error finding id" issues
        # This prevents ChromaDB metadata index errors that occur with where clauses
        post_filter_document_id = None
        if where and "document_id" in where:
            post_filter_document_id = where["document_id"]
            # Query more results to account for post-filtering
            query_n_results = min(n_results * 3, 50)  # Get 3x results, max 50
            where = None  # Remove where clause, we'll filter in Python
        else:
            query_n_results = n_results
        
        max_retries = 3
        retry_delay = 0.5  # Start with 0.5 seconds
        search_start_time = time.time()
        retry_count = 0
        
        # Track search attempt
        self._search_count += 1
        operation_type = operation if hasattr(self, '_current_operation') else 'search'
        
        for attempt in range(max_retries):
            try:
                # Query without where clause if we're using post-filtering
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=query_n_results,
                    where=where,
                )
                
                # Post-filter by document_id if needed
                if post_filter_document_id and results:
                    filtered_results = self._post_filter_by_document_id(
                        results, post_filter_document_id, n_results
                    )
                    
                    # Track successful search with post-filtering
                    if MONITORING_ENABLED and monitor:
                        search_duration = time.time() - search_start_time
                        monitor.track_vector_db_search(
                            operation="search",
                            duration=search_duration,
                            success=True,
                            retry_count=retry_count,
                            used_post_filter=True
                        )
                    
                    return filtered_results
                
                # Track successful search
                if MONITORING_ENABLED and monitor:
                    search_duration = time.time() - search_start_time
                    monitor.track_vector_db_search(
                        operation=operation_type,
                        duration=search_duration,
                        success=True,
                        retry_count=retry_count,
                        used_post_filter=(post_filter_document_id is not None)
                    )
                
                # Calculate and track error rate periodically (every 10 searches or 30 seconds)
                self._calculate_and_track_error_rate(operation_type)
                
                return results
                
            except Exception as e:
                error_str = str(e).lower()
                retry_count = attempt + 1
                
                # Track error for frequency calculation
                error_type = "error_finding_id" if ("error finding id" in error_str or "internal error" in error_str) else "other"
                if error_type not in self._error_count_by_type:
                    self._error_count_by_type[error_type] = 0
                self._error_count_by_type[error_type] += 1
                self._error_count += 1
                
                # Handle "Error finding id" - ChromaDB internal error, often transient
                if "error finding id" in error_str or "internal error" in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait before retrying
                        wait_time = retry_delay * (2 ** attempt)
                        print(f"⚠️ Vector DB 'Error finding id' (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        
                        # Track retry attempt
                        if MONITORING_ENABLED and monitor:
                            monitor.track_vector_db_search(
                                operation=operation_type,
                                duration=time.time() - search_start_time,
                                success=False,
                                error_type="error_finding_id",
                                retry_count=retry_count,
                                used_post_filter=(post_filter_document_id is not None)
                            )
                        
                        # On second attempt, try without where filter (might be causing the issue)
                        if attempt == 1 and where is not None:
                            print(f"⚠️ Retrying without metadata filter...")
                            try:
                                results = self.collection.query(
                                    query_embeddings=[query_embedding],
                                    n_results=n_results,
                                    where=None  # Remove filter
                                )
                                print(f"✅ Retry successful without filter")
                                return results
                            except Exception as no_filter_error:
                                # If that also fails, continue to next retry
                                continue
                        continue
                    else:
                        # Last attempt failed - try without where filter as final fallback
                        if where is not None:
                            print(f"⚠️ All retries failed, trying without metadata filter as final fallback...")
                            try:
                                results = self.collection.query(
                                    query_embeddings=[query_embedding],
                                    n_results=n_results,
                                    where=None  # Remove filter
                                )
                                print(f"✅ Final fallback successful without filter")
                                return results
                            except Exception as final_error:
                                print(f"❌ Final fallback also failed: {final_error}")
                                # Return empty results instead of raising - graceful degradation
                                return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
                        else:
                            # No where filter to remove, return empty results
                            print(f"❌ All retries failed, returning empty results for graceful degradation")
                            
                            # Track final failure
                            if MONITORING_ENABLED and monitor:
                                search_duration = time.time() - search_start_time
                                monitor.track_vector_db_search(
                                    operation=operation_type,
                                    duration=search_duration,
                                    success=False,
                                    error_type="error_finding_id",
                                    retry_count=retry_count,
                                    used_post_filter=(post_filter_document_id is not None)
                                )
                            
                            # Calculate and track error rate
                            self._calculate_and_track_error_rate(operation_type)
                            
                            return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
                
                # Handle "ef or M is too small" error
                elif "ef or M is too small" in error_str or "contigious" in error_str:
                    print(f"⚠️ Vector DB search error (ef/M too small), retrying with fewer results...")
                    try:
                        # Retry with fewer results (reduces ef requirement)
                        reduced_n = max(1, n_results // 2)
                        results = self.collection.query(
                            query_embeddings=[query_embedding],
                            n_results=reduced_n,
                            where=where
                        )
                        print(f"✅ Retry successful with {reduced_n} results (requested {n_results})")
                        return results
                    except Exception as retry_error:
                        print(f"❌ Retry also failed: {retry_error}")
                        # If retry fails, try without where filter
                        if where is not None:
                            try:
                                results = self.collection.query(
                                    query_embeddings=[query_embedding],
                                    n_results=reduced_n,
                                    where=None
                                )
                                print(f"✅ Retry successful without filter")
                                return results
                            except:
                                pass
                        # Return empty results for graceful degradation
                        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
                
                # Other errors - raise on first attempt, retry on subsequent attempts
                else:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        print(f"⚠️ Vector DB search error (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.1f}s: {e}")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Error searching vector DB: {e}")
                        # Return empty results instead of raising - graceful degradation
                        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
        
        # Should never reach here, but just in case
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
    
    def _post_filter_by_document_id(
        self,
        results: Dict,
        document_id: str,
        n_results: int
    ) -> Dict:
        """
        Post-filter results by document_id to avoid ChromaDB "Error finding id" issues.
        
        Args:
            results: Query results from ChromaDB
            document_id: Document ID to filter by
            n_results: Maximum number of results to return
            
        Returns:
            Filtered results dictionary
        """
        if not results or 'ids' not in results or not results['ids']:
            return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
        
        # Extract all result lists (ChromaDB returns nested lists)
        all_ids = results['ids'][0] if results['ids'] else []
        all_documents = results['documents'][0] if results.get('documents') else []
        all_distances = results['distances'][0] if results.get('distances') else []
        all_metadatas = results['metadatas'][0] if results.get('metadatas') else []
        
        # Filter by document_id
        filtered_ids = []
        filtered_documents = []
        filtered_distances = []
        filtered_metadatas = []
        
        for idx, result_id in enumerate(all_ids):
            # Extract document_id from metadata or ID format
            metadata = all_metadatas[idx] if idx < len(all_metadatas) else {}
            result_doc_id = metadata.get('document_id', '')
            
            # Also check if ID format is "{document_id}_chunk_{i}"
            if not result_doc_id and '_chunk_' in str(result_id):
                result_doc_id = str(result_id).split('_chunk_')[0]
            
            # Match document_id
            if result_doc_id == document_id:
                filtered_ids.append(result_id)
                if idx < len(all_documents):
                    filtered_documents.append(all_documents[idx])
                if idx < len(all_distances):
                    filtered_distances.append(all_distances[idx])
                if idx < len(all_metadatas):
                    filtered_metadatas.append(all_metadatas[idx])
                
                # Stop when we have enough results
                if len(filtered_ids) >= n_results:
                    break
        
        # Return in ChromaDB format (nested lists)
        return {
            "ids": [filtered_ids],
            "documents": [filtered_documents],
            "distances": [filtered_distances],
            "metadatas": [filtered_metadatas]
        }
    
    def _calculate_and_track_error_rate(self, operation: str):
        """Calculate and track Vector DB error rate periodically."""
        current_time = time.time()
        time_since_last_calc = current_time - self._last_error_rate_calculation
        
        # Calculate error rate every 10 searches or every 30 seconds
        if self._search_count % 10 == 0 or time_since_last_calc >= 30:
            if self._search_count > 0:
                error_rate = (self._error_count / self._search_count) * 100
                
                # Track overall error rate
                if MONITORING_ENABLED and monitor:
                    monitor.track_vector_db_error_frequency(
                        error_type="all",
                        operation=operation,
                        error_rate=error_rate
                    )
                
                # Track error rate by type
                for error_type, error_count in self._error_count_by_type.items():
                    if self._search_count > 0:
                        type_error_rate = (error_count / self._search_count) * 100
                        if MONITORING_ENABLED and monitor:
                            monitor.track_vector_db_error_frequency(
                                error_type=error_type,
                                operation=operation,
                                error_rate=type_error_rate
                            )
            
            # Reset counters for next period (keep last 100 searches in memory)
            if self._search_count >= 100:
                # Reset but keep recent history
                self._search_count = self._search_count % 50
                self._error_count = 0
                self._error_count_by_type = {}
            
            self._last_error_rate_calculation = current_time
    
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


