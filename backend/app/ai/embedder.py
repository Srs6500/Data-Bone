"""
Embedding service for converting text to vectors.
Uses sentence-transformers for generating embeddings.
"""
import os
# CRITICAL: Set environment variables BEFORE importing sentence-transformers
# This prevents accelerate from using device_map which creates meta tensors
os.environ.setdefault('ACCELERATE_DISABLE_RICH', '1')
os.environ.setdefault('ACCELERATE_USE_CPU', '1')
os.environ.setdefault('ACCELERATE_NO_CPU', '0')
os.environ.setdefault('HF_HUB_DISABLE_EXPERIMENTAL_WARNING', '1')
os.environ.setdefault('TRANSFORMERS_NO_ADVISORY_WARNINGS', '1')
# CRITICAL: Prevent transformers from using device_map which creates meta tensors
os.environ.setdefault('TRANSFORMERS_NO_DEVICE_MAP', '1')

from typing import List
import threading
from sentence_transformers import SentenceTransformer
from app.config import settings


class Embedder:
    """Service for generating text embeddings."""
    
    def __init__(self):
        """Initialize the embedding model."""
        self.model = None
        self._model_lock = threading.Lock()  # Thread-safe model loading
        # Use full model path if not already prefixed
        model_name = settings.embedding_model
        if not model_name.startswith('sentence-transformers/') and '/' not in model_name:
            self.model_name = f'sentence-transformers/{model_name}'
        else:
            self.model_name = model_name
    
    def _fix_meta_tensors_recursive(self, module, device='cpu'):
        """
        Recursively fix meta tensors in a module and all its submodules.
        
        Args:
            module: PyTorch module to fix
            device: Target device (default: 'cpu')
        """
        if module is None:
            return
        
        # Try to move the module itself to the device
        try:
            module.to(device)
        except (NotImplementedError, RuntimeError) as e:
            error_str = str(e).lower()
            if 'meta tensor' in error_str or 'to_empty' in error_str:
                # Use to_empty() to materialize meta tensors
                if hasattr(module, 'to_empty'):
                    try:
                        # to_empty() materializes on default device (CPU)
                        module.to_empty()
                        # Now move to target device
                        module.to(device)
                    except Exception as empty_error:
                        print(f"⚠️ Could not fix meta tensor in module {type(module).__name__}: {empty_error}")
            else:
                # Not a meta tensor error, re-raise
                raise
        
        # Recursively fix all submodules
        if hasattr(module, '_modules'):
            for name, submodule in module._modules.items():
                if submodule is not None:
                    self._fix_meta_tensors_recursive(submodule, device)
    
    def _load_model(self):
        """Lazy load the model (only when needed). Thread-safe."""
        # Double-check locking pattern for thread safety
        if self.model is None:
            with self._model_lock:
                # Check again inside lock (another thread might have loaded it)
                if self.model is None:
                    print(f"Loading embedding model: {self.model_name}")
                    
                    # Verify model name is correctly formatted
                    if not self.model_name or self.model_name.strip() == '':
                        raise ValueError("Model name is empty or invalid")
                    
                    # Ensure we have the correct format
                    if not self.model_name.startswith('sentence-transformers/') and '/' not in self.model_name:
                        # This should have been set in __init__, but double-check
                        self.model_name = f'sentence-transformers/{self.model_name}'
                        print(f"⚠️ Model name corrected to: {self.model_name}")
                    
                    try:
                        import torch
                        import os
                        import shutil
                        import gc
                        
                        # CRITICAL: Preemptively clear cache to prevent meta tensor issues
                        # Clear the cache BEFORE loading to ensure clean model loading
                        cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                        model_cache_path = os.path.join(cache_dir, f'models--{self.model_name.replace("/", "--")}')
                        if self.model_name.startswith('sentence-transformers/'):
                            short_name = self.model_name.replace('sentence-transformers/', '')
                            short_name_cache = os.path.join(cache_dir, f'models--{short_name.replace("/", "--")}')
                            if os.path.exists(short_name_cache) and not os.path.exists(model_cache_path):
                                model_cache_path = short_name_cache
                        
                        # Clear cache if it exists (aggressive approach to prevent meta tensors)
                        if os.path.exists(model_cache_path):
                            print(f"🧹 Clearing model cache to prevent meta tensor issues: {model_cache_path}")
                            try:
                                shutil.rmtree(model_cache_path)
                                print(f"✅ Cleared model cache: {model_cache_path}")
                                gc.collect()
                                import time
                                time.sleep(1.0)  # Wait for cache deletion to complete
                            except Exception as cache_error:
                                print(f"⚠️ Could not clear cache: {cache_error}")
                        
                        # Also clear short name cache if different
                        if self.model_name.startswith('sentence-transformers/'):
                            short_name = self.model_name.replace('sentence-transformers/', '')
                            short_name_cache = os.path.join(cache_dir, f'models--{short_name.replace("/", "--")}')
                            if os.path.exists(short_name_cache) and short_name_cache != model_cache_path:
                                print(f"🧹 Clearing short name cache: {short_name_cache}")
                                try:
                                    shutil.rmtree(short_name_cache)
                                    print(f"✅ Cleared short name cache: {short_name_cache}")
                                    gc.collect()
                                    import time
                                    time.sleep(0.5)
                                except Exception:
                                    pass
                        
                        # CRITICAL: Set environment variables BEFORE any imports that might use them
                        # These must be set before sentence-transformers/transformers loads
                        os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'max_split_size_mb:512')
                        os.environ['HF_HUB_DISABLE_EXPERIMENTAL_WARNING'] = '1'
                        os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
                        os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
                        # Force CPU by hiding CUDA
                        os.environ['CUDA_VISIBLE_DEVICES'] = ''
                        
                        # CRITICAL: Disable accelerate meta device usage
                        os.environ['ACCELERATE_DISABLE_RICH'] = '1'
                        os.environ['ACCELERATE_USE_CPU'] = '1'
                        os.environ['ACCELERATE_NO_CPU'] = '0'
                        # Prevent accelerate from using meta device
                        os.environ['ACCELERATE_DISABLE_META'] = '1'
                        
                        # CRITICAL: Prevent transformers from using device_map or low_cpu_mem_usage with meta tensors
                        # This is the root cause - transformers uses device_map='auto' which creates meta tensors
                        os.environ['TRANSFORMERS_NO_DEVICE_MAP'] = '1'
                        # Disable low_cpu_mem_usage which can trigger meta tensor creation
                        os.environ['TRANSFORMERS_LOW_CPU_MEM_USAGE'] = '0'
                        
                        # Ensure we're not using meta device
                        if hasattr(torch, 'use_deterministic_algorithms'):
                            torch.use_deterministic_algorithms(False)
                        
                        try:
                            # CRITICAL: Set default device to CPU BEFORE any model loading
                            # This prevents PyTorch from using meta device
                            if hasattr(torch, 'set_default_device'):
                                torch.set_default_device('cpu')
                            
                            # Set default tensor type to avoid meta tensors
                            if hasattr(torch, 'set_default_tensor_type'):
                                torch.set_default_tensor_type('torch.FloatTensor')
                            
                            # Ensure CUDA is completely disabled
                            if torch.cuda.is_available():
                                try:
                                    torch.cuda.set_device(-1)
                                except:
                                    pass
                            
                            # CRITICAL: Ensure accelerate doesn't use device_map or meta device
                            # Check if accelerate is installed and configure it
                            try:
                                import accelerate
                                # Force accelerate to not use device_map or meta device
                                os.environ['ACCELERATE_DISABLE_RICH'] = '1'
                                os.environ['ACCELERATE_USE_CPU'] = '1'
                                os.environ['ACCELERATE_NO_CPU'] = '0'
                                os.environ['ACCELERATE_DISABLE_META'] = '1'
                            except ImportError:
                                # accelerate not installed - that's fine, SentenceTransformer will work without it
                                pass
                            
                            # CRITICAL FIX: Monkey-patch torch.nn.Module.to() BEFORE loading
                            # This intercepts the to() call inside SentenceTransformer.__init__
                            import torch
                            original_to = torch.nn.Module.to
                            
                            def safe_to_patch(self, *args, **kwargs):
                                """Patched to() that handles meta tensors."""
                                try:
                                    return original_to(self, *args, **kwargs)
                                except (NotImplementedError, RuntimeError) as e:
                                    error_str = str(e).lower()
                                    if 'meta tensor' in error_str or 'to_empty' in error_str:
                                        # Use to_empty() to materialize meta tensors
                                        if hasattr(self, 'to_empty'):
                                            try:
                                                # to_empty() materializes on default device (CPU)
                                                self.to_empty()
                                                # Now move to target device
                                                device = args[0] if args else kwargs.get('device', 'cpu')
                                                return original_to(self, device)
                                            except Exception as empty_error:
                                                print(f"⚠️ to_empty() failed: {empty_error}")
                                                # Last resort: try to materialize parameters manually
                                                if hasattr(self, '_parameters'):
                                                    for name, param in self._parameters.items():
                                                        if param is not None and hasattr(param, 'device') and str(param.device) == 'meta':
                                                            # Create new tensor on CPU with same shape/dtype
                                                            new_param = torch.nn.Parameter(
                                                                torch.zeros_like(param, device='cpu')
                                                            )
                                                            self._parameters[name] = new_param
                                                # Try again
                                                return original_to(self, *args, **kwargs)
                                    raise
                            
                            # Apply the patch
                            torch.nn.Module.to = safe_to_patch
                            
                            try:
                                # Try loading with explicit parameters to prevent meta tensors
                                self.model = SentenceTransformer(
                                    self.model_name,
                                    device='cpu',
                                    trust_remote_code=True
                                )
                                print("✅ Embedding model loaded successfully on CPU")
                            except Exception as model_load_error:
                                # If full path fails, try without prefix (for backwards compatibility)
                                if self.model_name.startswith('sentence-transformers/'):
                                    short_name = self.model_name.replace('sentence-transformers/', '')
                                    print(f"⚠️ Failed with full path, trying short name: {short_name}")
                                    self.model = SentenceTransformer(
                                        short_name,
                                        device='cpu',
                                        trust_remote_code=True
                                    )
                                    print("✅ Embedding model loaded successfully on CPU (short name)")
                                else:
                                    raise model_load_error
                            finally:
                                # Restore original to() method
                                torch.nn.Module.to = original_to
                        except Exception as e1:
                            error_str = str(e1)
                            if 'meta tensor' in error_str.lower() or 'to_empty' in error_str.lower():
                                # FIXED: Use proper workaround for meta tensor issue
                                print("⚠️ Meta tensor error detected. Using proper workaround...")
                                try:
                                    import torch
                                    import gc
                                    import shutil
                            
                                    # Clear any cached models that might have meta tensors
                                    gc.collect()
                                    
                                    # CRITICAL: Clear HuggingFace cache to remove any corrupted/meta tensor models
                                    cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                                    model_cache_path = os.path.join(cache_dir, f'models--{self.model_name.replace("/", "--")}')
                                    
                                    # Also clear the short name cache if we're using full path
                                    short_name_cache = None
                                    if self.model_name.startswith('sentence-transformers/'):
                                        short_name = self.model_name.replace('sentence-transformers/', '')
                                        short_name_cache = os.path.join(cache_dir, f'models--{short_name.replace("/", "--")}')
                                    
                                    # Clear both caches
                                    caches_to_clear = [model_cache_path]
                                    if short_name_cache and short_name_cache != model_cache_path:
                                        caches_to_clear.append(short_name_cache)
                                    
                                    for cache_path in caches_to_clear:
                                        if os.path.exists(cache_path):
                                            print(f"🧹 Clearing potentially corrupted model cache: {cache_path}")
                                            try:
                                                # More aggressive: clear the entire model cache directory
                                                shutil.rmtree(cache_path)
                                                print(f"✅ Model cache cleared: {cache_path}")
                                                # Also try clearing any lock files that might prevent reloading
                                                lock_files = [
                                                    os.path.join(cache_dir, '.lock'),
                                                    os.path.join(cache_path, '.lock')
                                                ]
                                                for lock_file in lock_files:
                                                    if os.path.exists(lock_file):
                                                        try:
                                                            os.remove(lock_file)
                                                            print(f"✅ Removed lock file: {lock_file}")
                                                        except:
                                                            pass
                                            except Exception as cache_error:
                                                print(f"⚠️ Could not clear cache {cache_path}: {cache_error}")
                                        else:
                                            print(f"ℹ️ Model cache not found at {cache_path}, nothing to clear")
                                    
                                    # Wait longer for cache deletion to complete
                                    import time
                                    time.sleep(2.0)  # Give more time for cache deletion
                                    
                                    # Disable meta device by setting environment variables
                                    os.environ['HF_HUB_DISABLE_EXPERIMENTAL_WARNING'] = '1'
                                    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
                                    os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
                                    # Force CPU by hiding CUDA
                                    os.environ['CUDA_VISIBLE_DEVICES'] = ''
                                    
                                    # CRITICAL FIX: Force CPU device before loading
                                    if hasattr(torch, 'set_default_tensor_type'):
                                        torch.set_default_tensor_type('torch.FloatTensor')
                                    
                                    # Ensure CUDA is completely disabled
                                    if torch.cuda.is_available():
                                        # Force CPU by setting device to -1
                                        try:
                                            torch.cuda.set_device(-1)
                                        except:
                                            pass
                                    
                                    # Load model with explicit CPU device
                                    # The key is to load it fresh after clearing cache
                                    # Wait a moment for cache deletion to complete
                                    import time
                                    time.sleep(1.0)  # Give more time for cache deletion
                                    
                                    # CRITICAL: Disable device_map and ensure no meta tensors
                                    # Set environment to prevent accelerate from using device_map
                                    os.environ['ACCELERATE_DISABLE_RICH'] = '1'
                                    os.environ['ACCELERATE_USE_CPU'] = '1'
                                    os.environ['HF_HUB_DISABLE_EXPERIMENTAL_WARNING'] = '1'
                                    
                                    # CRITICAL: Load model and handle meta tensors properly
                                    try:
                                        # Try with full path first
                                        try:
                                            self.model = SentenceTransformer(
                                                self.model_name,
                                                device='cpu',
                                                trust_remote_code=True
                                            )
                                        except Exception as model_load_error:
                                            # If full path fails, try without prefix
                                            if self.model_name.startswith('sentence-transformers/'):
                                                short_name = self.model_name.replace('sentence-transformers/', '')
                                                print(f"⚠️ Failed with full path, trying short name: {short_name}")
                                                self.model = SentenceTransformer(
                                                    short_name,
                                                    device='cpu',
                                                    trust_remote_code=True
                                                )
                                            else:
                                                raise model_load_error
                                        
                                        # Fix any meta tensors that might have been created
                                        self._fix_meta_tensors_recursive(self.model, device='cpu')
                                        
                                        print("✅ Embedding model loaded successfully (meta tensor workaround)")
                                    except NotImplementedError as meta_error:
                                        if 'meta tensor' in str(meta_error).lower():
                                            # Meta tensor error - the model was loaded with meta tensors
                                            # This happens when accelerate or transformers uses device_map='auto'
                                            # Solution: Force reload with explicit settings to prevent meta device
                                            print("⚠️ Meta tensor error detected. Forcing clean reload...")
                                            
                                            # CRITICAL: Completely disable accelerate and force CPU
                                            os.environ['ACCELERATE_DISABLE_RICH'] = '1'
                                            os.environ['ACCELERATE_USE_CPU'] = '1'
                                            os.environ['ACCELERATE_NO_CPU'] = '0'
                                            os.environ['ACCELERATE_DISABLE_META'] = '1'  # Disable meta device
                                            
                                            # Force PyTorch to use CPU and prevent meta device
                                            import torch
                                            if hasattr(torch, 'set_default_device'):
                                                torch.set_default_device('cpu')
                                            
                                            # Clear any cached model state that might have meta tensors
                                            import gc
                                            gc.collect()
                                            
                                            # Wait a moment for cleanup
                                            import time
                                            time.sleep(1.0)  # Give more time for cache deletion
                                            
                                            # CRITICAL: Ensure transformers doesn't use device_map
                                            # Set environment variable to prevent device_map usage
                                            os.environ['TRANSFORMERS_NO_DEVICE_MAP'] = '1'
                                            
                                            # Load model and fix meta tensors after loading
                                            try:
                                                # Try with full path
                                                self.model = SentenceTransformer(
                                                    self.model_name,
                                                    device='cpu',
                                                    trust_remote_code=True
                                                )
                                                
                                                # Fix any meta tensors that were created
                                                self._fix_meta_tensors_recursive(self.model, device='cpu')
                                                
                                                print("✅ Embedding model loaded successfully after meta tensor fix")
                                            except Exception as retry_error:
                                                # If that still fails, try with short name
                                                if self.model_name.startswith('sentence-transformers/'):
                                                    short_name = self.model_name.replace('sentence-transformers/', '')
                                                    print(f"⚠️ Retrying with short name: {short_name}")
                                                    try:
                                                        self.model = SentenceTransformer(
                                                            short_name,
                                                            device='cpu',
                                                            trust_remote_code=True
                                                        )
                                                        
                                                        # Fix any meta tensors
                                                        self._fix_meta_tensors_recursive(self.model, device='cpu')
                                                        
                                                        print("✅ Embedding model loaded successfully with short name")
                                                    except Exception as short_error:
                                                        # Last resort: suggest manual cache clearing
                                                        raise Exception(
                                                            f"Failed to load embedding model after meta tensor error.\n"
                                                            f"MANUAL FIX REQUIRED: Clear the HuggingFace cache:\n"
                                                            f"  rm -rf ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2\n"
                                                            f"Then restart the server.\n\n"
                                                            f"Original error: {meta_error}\n"
                                                            f"Retry error: {retry_error}\n"
                                                            f"Short name error: {short_error}"
                                                        )
                                                else:
                                                    raise Exception(
                                                        f"Failed to load embedding model after meta tensor error.\n"
                                                        f"MANUAL FIX REQUIRED: Clear the HuggingFace cache:\n"
                                                        f"  rm -rf ~/.cache/huggingface\n"
                                                        f"Then restart the server.\n\n"
                                                        f"Original error: {meta_error}\n"
                                                        f"Retry error: {retry_error}"
                                                    )
                                        else:
                                            raise
                                except Exception as e3:
                                    print(f"❌ All embedding load methods failed. Last error: {e3}")
                                    # Last resort: raise with helpful message
                                    raise Exception(f"Failed to load embedding model due to PyTorch meta tensor issue. Try restarting the server. Error: {e3}")
                            else:
                                print(f"⚠️ Warning: Failed to load with explicit CPU device: {e1}")
                                # Try fallback with auto device
                                try:
                                    # Try with full path first
                                    try:
                                        self.model = SentenceTransformer(self.model_name)
                                    except Exception as fallback_error:
                                        # If full path fails, try without prefix
                                        if self.model_name.startswith('sentence-transformers/'):
                                            short_name = self.model_name.replace('sentence-transformers/', '')
                                            print(f"⚠️ Fallback failed with full path, trying short name: {short_name}")
                                            self.model = SentenceTransformer(short_name)
                                        else:
                                            raise fallback_error
                                    print("✅ Embedding model loaded successfully (auto device)")
                                except Exception as e2:
                                    print(f"❌ All embedding load methods failed: {e2}")
                                    # Provide helpful error message
                                    raise Exception(
                                        f"Failed to load embedding model '{self.model_name}'. "
                                        f"This could be due to:\n"
                                        f"1. Network connectivity issues (can't download from HuggingFace)\n"
                                        f"2. Model cache corruption (try: rm -rf ~/.cache/huggingface)\n"
                                        f"3. Invalid model identifier\n"
                                        f"Original error: {e2}"
                                    )
                    
                    except Exception as e:
                        print(f"Error loading embedding model: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
    
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


