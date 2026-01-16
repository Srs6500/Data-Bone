"""
Datadog monitoring and observability for LLM application.
Tracks LLM metrics, RAG performance, gap detection, and application health.
"""
import os
import time
from typing import Dict, Optional, Any, List
from functools import wraps
from datadog import initialize, api, statsd

# Load environment variables from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on system environment variables


class DatadogMonitor:
    """
    Comprehensive Datadog monitoring for LLM application.
    Tracks metrics, traces, and logs for observability.
    """
    
    def __init__(self):
        """Initialize Datadog monitoring."""
        # Read directly from environment variables (not from settings to avoid config issues)
        self.enabled = os.getenv('DD_API_KEY') is not None
        self.service_name = "databone-llm"
        self.env = os.getenv('DD_ENV', 'development')
        
        if self.enabled:
            try:
                # Initialize Datadog
                initialize(
                    api_key=os.getenv('DD_API_KEY'),
                    app_key=os.getenv('DD_APP_KEY'),  # Optional, for API calls
                    host_name=os.getenv('DD_HOST', 'localhost'),
                    statsd_host=os.getenv('DD_AGENT_HOST', 'localhost'),
                    statsd_port=int(os.getenv('DD_DOGSTATSD_PORT', 8125)),
                )
                print("✅ Datadog monitoring initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize Datadog: {e}")
                self.enabled = False
        else:
            print("⚠️ Datadog API key not found. Monitoring disabled.")
    
    # ==================== LLM Metrics ====================
    
    def track_llm_request(
        self,
        model: str,
        operation: str,  # 'gap_analysis', 'chat', 'explain'
        duration: float,
        success: bool,
        tokens_used: Optional[int] = None,
        error_type: Optional[str] = None,
        safety_blocked: bool = False,
        model_fallback: bool = False
    ):
        """Track LLM request metrics."""
        if not self.enabled:
            return
        
        tags = [
            f"model:{model}",
            f"operation:{operation}",
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"success:{str(success).lower()}",
        ]
        
        if error_type:
            tags.append(f"error_type:{error_type}")
        if safety_blocked:
            tags.append("safety_blocked:true")
        if model_fallback:
            tags.append("model_fallback:true")
        
        # Track latency
        statsd.distribution(
            'llm.request.duration',
            duration * 1000,  # Convert to milliseconds
            tags=tags
        )
        
        # Track success/failure
        statsd.increment(
            'llm.request.count',
            tags=tags
        )
        
        if not success:
            statsd.increment(
                'llm.request.error',
                tags=tags
            )
        
        # Track safety blocks
        if safety_blocked:
            statsd.increment(
                'llm.safety.blocked',
                tags=tags
            )
        
        # Track model fallbacks
        if model_fallback:
            statsd.increment(
                'llm.model.fallback',
                tags=tags
            )
        
        # Track token usage if available
        if tokens_used:
            statsd.distribution(
                'llm.tokens.used',
                tokens_used,
                tags=tags
            )
    
    def track_llm_model_usage(self, model: str, operation: str):
        """Track which models are being used."""
        if not self.enabled:
            return
        
        statsd.increment(
            'llm.model.usage',
            tags=[
                f"model:{model}",
                f"operation:{operation}",
                f"service:{self.service_name}",
                f"env:{self.env}",
            ]
        )
    
    # ==================== RAG Metrics ====================
    
    def track_rag_retrieval(
        self,
        document_id: str,
        query_concepts: List[str],
        chunks_retrieved: int,
        retrieval_time: float,
        total_chars: int,
        course_info_used: bool = False
    ):
        """Track RAG retrieval performance."""
        if not self.enabled:
            return
        
        tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"course_info_used:{str(course_info_used).lower()}",
        ]
        
        # Track retrieval time
        statsd.distribution(
            'rag.retrieval.duration',
            retrieval_time * 1000,  # milliseconds
            tags=tags
        )
        
        # Track chunk counts
        statsd.distribution(
            'rag.chunks.retrieved',
            chunks_retrieved,
            tags=tags
        )
        
        # Track context size
        statsd.distribution(
            'rag.context.size',
            total_chars,
            tags=tags
        )
        
        # Track retrieval count
        statsd.increment(
            'rag.retrieval.count',
            tags=tags
        )
    
    def track_embedding_generation(
        self,
        text_count: int,
        generation_time: float,
        model: str = "all-MiniLM-L6-v2"
    ):
        """Track embedding generation performance."""
        if not self.enabled:
            return
        
        tags = [
            f"model:{model}",
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        statsd.distribution(
            'embedding.generation.duration',
            generation_time * 1000,  # milliseconds
            tags=tags
        )
        
        statsd.distribution(
            'embedding.texts.processed',
            text_count,
            tags=tags
        )
    
    def track_vector_db_search(
        self,
        operation: str,  # 'rag_retrieval', 'gap_enhancement', 'chat_context'
        duration: float,
        success: bool,
        error_type: Optional[str] = None,
        retry_count: int = 0,
        used_post_filter: bool = False
    ):
        """Track Vector DB search operations and errors."""
        if not self.enabled:
            return
        
        tags = [
            f"operation:{operation}",
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"success:{str(success).lower()}",
            f"post_filter:{str(used_post_filter).lower()}",
        ]
        
        if error_type:
            tags.append(f"error_type:{error_type}")
        
        # Track search duration
        statsd.distribution(
            'vector_db.search.duration',
            duration * 1000,  # milliseconds
            tags=tags
        )
        
        # Track search count
        statsd.increment(
            'vector_db.search.count',
            tags=tags
        )
        
        # Track errors
        if not success:
            statsd.increment(
                'vector_db.search.error',
                tags=tags
            )
        
        # Track retries
        if retry_count > 0:
            statsd.distribution(
                'vector_db.search.retry_count',
                retry_count,
                tags=tags
            )
    
    # ==================== Gap Detection Metrics ====================
    
    def track_gap_analysis(
        self,
        document_id: str,
        total_gaps: int,
        critical_gaps: int,
        safe_gaps: int,
        analysis_duration: float,
        parsing_success: bool,
        rag_enhanced: bool = True
    ):
        """Track gap analysis metrics."""
        if not self.enabled:
            return
        
        tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"parsing_success:{str(parsing_success).lower()}",
            f"rag_enhanced:{str(rag_enhanced).lower()}",
        ]
        
        # Track analysis duration
        statsd.distribution(
            'gap.analysis.duration',
            analysis_duration * 1000,  # milliseconds
            tags=tags
        )
        
        # Track gap counts
        statsd.distribution(
            'gap.total.count',
            total_gaps,
            tags=tags
        )
        
        statsd.distribution(
            'gap.critical.count',
            critical_gaps,
            tags=tags
        )
        
        statsd.distribution(
            'gap.safe.count',
            safe_gaps,
            tags=tags
        )
        
        # Track parsing success
        if parsing_success:
            statsd.increment(
                'gap.parsing.success',
                tags=tags
            )
        else:
            statsd.increment(
                'gap.parsing.failure',
                tags=tags
            )
    
    # ==================== Application Health Metrics ====================
    
    def track_api_request(
        self,
        endpoint: str,
        method: str,
        duration: float,
        status_code: int,
        error: Optional[str] = None
    ):
        """Track API request metrics."""
        if not self.enabled:
            return
        
        tags = [
            f"endpoint:{endpoint}",
            f"method:{method}",
            f"status_code:{status_code}",
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        if error:
            tags.append(f"error:{error}")
        
        statsd.distribution(
            'api.request.duration',
            duration * 1000,  # milliseconds
            tags=tags
        )
        
        statsd.increment(
            'api.request.count',
            tags=tags
        )
        
        if status_code >= 400:
            statsd.increment(
                'api.request.error',
                tags=tags
            )
    
    def track_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Track application errors."""
        if not self.enabled:
            return
        
        tags = [
            f"error_type:{error_type}",
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        statsd.increment(
            'application.error',
            tags=tags
        )
        
        # Send error event to Datadog
        try:
            api.Event.create(
                title=f"Error: {error_type}",
                text=error_message,
                alert_type='error',
                tags=tags,
                aggregation_key=error_type
            )
        except Exception as e:
            print(f"⚠️ Failed to send error event to Datadog: {e}")
    
    # ==================== Decorators ====================
    
    def track_llm_call(self, operation: str):
        """Decorator to track LLM calls automatically."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = False
                error_type = None
                safety_blocked = False
                model_fallback = False
                model = "unknown"
                
                try:
                    # Try to get model from self if available
                    if args and hasattr(args[0], 'initialized_model'):
                        model = args[0].initialized_model or "unknown"
                    
                    result = func(*args, **kwargs)
                    success = True
                    duration = time.time() - start_time
                    
                    self.track_llm_request(
                        model=model,
                        operation=operation,
                        duration=duration,
                        success=success
                    )
                    
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    error_str = str(e).lower()
                    
                    if "blocked" in error_str or "safety" in error_str:
                        safety_blocked = True
                        error_type = "safety_filter"
                    elif "404" in error_str or "not found" in error_str:
                        error_type = "model_not_found"
                        model_fallback = True
                    else:
                        error_type = "unknown"
                    
                    self.track_llm_request(
                        model=model,
                        operation=operation,
                        duration=duration,
                        success=False,
                        error_type=error_type,
                        safety_blocked=safety_blocked,
                        model_fallback=model_fallback
                    )
                    
                    raise
            
            return wrapper
        return decorator
    
    # ==================== Custom Events ====================
    
    def send_custom_event(
        self,
        title: str,
        text: str,
        alert_type: str = 'info',  # 'info', 'success', 'warning', 'error'
        tags: Optional[List[str]] = None,
        aggregation_key: Optional[str] = None
    ):
        """Send custom event to Datadog."""
        if not self.enabled:
            return
        
        event_tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        if tags:
            event_tags.extend(tags)
        
        try:
            api.Event.create(
                title=title,
                text=text,
                alert_type=alert_type,
                tags=event_tags,
                aggregation_key=aggregation_key
            )
        except Exception as e:
            print(f"⚠️ Failed to send custom event to Datadog: {e}")
    
    # ==================== Chat Metrics ====================
    
    def track_chat_session(
        self,
        document_id: str,
        session_id: Optional[str] = None,
        has_gap_context: bool = False,
        gap_count: int = 0,
        filter_type: Optional[str] = None
    ):
        """Track chat session start."""
        if not self.enabled:
            return
        
        tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"has_gap_context:{str(has_gap_context).lower()}",
        ]
        
        if filter_type:
            tags.append(f"filter_type:{filter_type}")
        
        statsd.increment('chat.session.start', tags=tags)
    
    def track_chat_message(
        self,
        document_id: str,
        response_length: int,
        response_duration: float,
        context_size: int,
        message_count: int,
        is_incomplete: bool = False,
        is_exam_question_request: bool = False,
        has_gap_context: bool = False
    ):
        """Track individual chat message metrics."""
        if not self.enabled:
            return
        
        tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"is_incomplete:{str(is_incomplete).lower()}",
            f"is_exam_question:{str(is_exam_question_request).lower()}",
            f"has_gap_context:{str(has_gap_context).lower()}",
        ]
        
        # Track response duration
        statsd.distribution(
            'chat.response.duration',
            response_duration * 1000,  # milliseconds
            tags=tags
        )
        
        # Track response length
        statsd.distribution(
            'chat.response.length',
            response_length,
            tags=tags
        )
        
        # Track context size used
        statsd.distribution(
            'chat.context.size',
            context_size,
            tags=tags
        )
        
        # Track message count (conversation length)
        statsd.distribution(
            'chat.message.count',
            message_count,
            tags=tags
        )
        
        # Track incomplete responses
        if is_incomplete:
            statsd.increment('chat.response.incomplete', tags=tags)
        
        # Track exam question generation requests
        if is_exam_question_request:
            statsd.increment('chat.exam_question.request', tags=tags)
        
        # Track total chat messages
        statsd.increment('chat.message.count_total', tags=tags)
    
    def track_exam_question_generation(
        self,
        document_id: str,
        gap_concepts: List[str],
        question_count: int,
        generation_duration: float,
        success: bool
    ):
        """Track exam question generation metrics."""
        if not self.enabled:
            return
        
        tags = [
            f"service:{self.service_name}",
            f"env:{self.env}",
            f"success:{str(success).lower()}",
        ]
        
        # Track generation duration
        statsd.distribution(
            'exam_question.generation.duration',
            generation_duration * 1000,  # milliseconds
            tags=tags
        )
        
        # Track question count
        statsd.distribution(
            'exam_question.count',
            question_count,
            tags=tags
        )
        
        # Track generation requests
        statsd.increment('exam_question.generation.request', tags=tags)
        
        if success:
            statsd.increment('exam_question.generation.success', tags=tags)
        else:
            statsd.increment('exam_question.generation.failure', tags=tags)
    
    # ==================== Vector DB Error Frequency Metrics ====================
    
    def track_vector_db_error_frequency(
        self,
        error_type: str,
        operation: str,
        error_rate: float  # Percentage of searches that failed
    ):
        """Track Vector DB error frequency as a percentage metric."""
        if not self.enabled:
            return
        
        tags = [
            f"error_type:{error_type}",
            f"operation:{operation}",
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        # Track error rate as a gauge (percentage)
        statsd.gauge(
            'vector_db.error.rate',
            error_rate,  # Percentage (0-100)
            tags=tags
        )
        
        # Track if error rate exceeds threshold
        if error_rate > 5.0:  # More than 5% error rate
            statsd.increment('vector_db.error.rate.high', tags=tags)
    
    # ==================== Health Checks ====================
    
    def track_health_check(self, component: str, healthy: bool):
        """Track component health status."""
        if not self.enabled:
            return
        
        tags = [
            f"component:{component}",
            f"service:{self.service_name}",
            f"env:{self.env}",
        ]
        
        if healthy:
            statsd.increment('health.check.pass', tags=tags)
        else:
            statsd.increment('health.check.fail', tags=tags)
            
            # Send alert for unhealthy component
            self.send_custom_event(
                title=f"Health Check Failed: {component}",
                text=f"Component {component} is unhealthy",
                alert_type='error',
                tags=tags,
                aggregation_key=f"health_{component}"
            )

