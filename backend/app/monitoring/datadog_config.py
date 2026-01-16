"""
Datadog detection rules, dashboard configuration, and alert definitions.
"""
from typing import Dict, List, Any


# ==================== Detection Rules ====================

DETECTION_RULES = {
    "high_error_rate": {
        "name": "High LLM Error Rate",
        "description": "Alert when LLM error rate exceeds 10% over 5 minutes",
        "metric": "llm.request.error",
        "threshold": 0.1,  # 10% error rate
        "window": "5m",
        "condition": ">",
        "severity": "critical"
    },
    "safety_filter_spike": {
        "name": "Safety Filter Block Spike",
        "description": "Alert when safety filter blocks exceed 5 in 10 minutes",
        "metric": "llm.safety.blocked",
        "threshold": 5,
        "window": "10m",
        "condition": ">",
        "severity": "warning"
    },
    "model_fallback_spike": {
        "name": "Model Fallback Spike",
        "description": "Alert when model fallbacks exceed 3 in 5 minutes",
        "metric": "llm.model.fallback",
        "threshold": 3,
        "window": "5m",
        "condition": ">",
        "severity": "warning"
    },
    "high_latency": {
        "name": "High LLM Latency",
        "description": "Alert when p95 LLM latency exceeds 10 seconds",
        "metric": "llm.request.duration",
        "threshold": 10000,  # 10 seconds in milliseconds
        "window": "5m",
        "percentile": 95,
        "condition": ">",
        "severity": "warning"
    },
    "gap_parsing_failure": {
        "name": "Gap Parsing Failure Rate",
        "description": "Alert when gap parsing failure rate exceeds 20%",
        "metric": "gap.parsing.failure",
        "threshold": 0.2,
        "window": "10m",
        "condition": ">",
        "severity": "warning"
    },
    "rag_retrieval_slow": {
        "name": "Slow RAG Retrieval",
        "description": "Alert when p95 RAG retrieval time exceeds 2 seconds",
        "metric": "rag.retrieval.duration",
        "threshold": 2000,  # 2 seconds in milliseconds
        "window": "5m",
        "percentile": 95,
        "condition": ">",
        "severity": "info"
    },
    "api_error_rate": {
        "name": "High API Error Rate",
        "description": "Alert when API error rate exceeds 5%",
        "metric": "api.request.error",
        "threshold": 0.05,
        "window": "5m",
        "condition": ">",
        "severity": "critical"
    },
    "health_check_failure": {
        "name": "Component Health Check Failure",
        "description": "Alert when any component health check fails",
        "metric": "health.check.fail",
        "threshold": 1,
        "window": "1m",
        "condition": ">",
        "severity": "critical"
    }
}


# ==================== Dashboard Configuration ====================

DASHBOARD_CONFIG = {
    "title": "DataBone LLM Application - Observability Dashboard",
    "description": "Comprehensive observability dashboard for LLM-powered gap detection application",
    "widgets": [
        # LLM Metrics Section
        {
            "type": "timeseries",
            "title": "LLM Request Rate",
            "metrics": [
                {"query": "sum:llm.request.count{*}", "display_name": "Total Requests"},
                {"query": "sum:llm.request.error{*}", "display_name": "Errors"},
            ],
            "yaxis": {"label": "Requests/sec", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "LLM Request Latency (p50, p95, p99)",
            "metrics": [
                {"query": "avg:llm.request.duration{*}.as_rate()", "display_name": "Avg"},
                {"query": "p50:llm.request.duration{*}", "display_name": "p50"},
                {"query": "p95:llm.request.duration{*}", "display_name": "p95"},
                {"query": "p99:llm.request.duration{*}", "display_name": "p99"},
            ],
            "yaxis": {"label": "Latency (ms)", "scale": "log"}
        },
        {
            "type": "timeseries",
            "title": "LLM Error Rate by Type",
            "metrics": [
                {"query": "sum:llm.request.error{error_type:safety_filter}", "display_name": "Safety Filter"},
                {"query": "sum:llm.request.error{error_type:model_not_found}", "display_name": "Model Not Found"},
                {"query": "sum:llm.request.error{error_type:context_length_exceeded}", "display_name": "Context Length"},
                {"query": "sum:llm.request.error{error_type:unknown}", "display_name": "Unknown"},
            ],
            "yaxis": {"label": "Errors/min", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Safety Filter Blocks",
            "metrics": [
                {"query": "sum:llm.safety.blocked{*}.as_rate()", "display_name": "Blocks/min"},
            ],
            "yaxis": {"label": "Blocks", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Model Usage Distribution",
            "metrics": [
                {"query": "sum:llm.model.usage{model:gemini-2.5-pro}", "display_name": "Gemini 2.5 Pro"},
                {"query": "sum:llm.model.usage{model:gemini-2.5-flash}", "display_name": "Gemini 2.5 Flash"},
                {"query": "sum:llm.model.usage{model:gemini-1.5-flash}", "display_name": "Gemini 1.5 Flash"},
                {"query": "sum:llm.model.fallback{*}", "display_name": "Fallbacks"},
            ],
            "yaxis": {"label": "Usage", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Token Usage",
            "metrics": [
                {"query": "avg:llm.tokens.used{*}", "display_name": "Avg Tokens"},
                {"query": "sum:llm.tokens.used{*}", "display_name": "Total Tokens"},
            ],
            "yaxis": {"label": "Tokens", "scale": "linear"}
        },
        
        # RAG Metrics Section
        {
            "type": "timeseries",
            "title": "RAG Retrieval Performance",
            "metrics": [
                {"query": "avg:rag.retrieval.duration{*}", "display_name": "Avg Duration"},
                {"query": "p95:rag.retrieval.duration{*}", "display_name": "p95 Duration"},
                {"query": "avg:rag.chunks.retrieved{*}", "display_name": "Avg Chunks"},
            ],
            "yaxis": {"label": "Time (ms) / Chunks", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "RAG Context Size",
            "metrics": [
                {"query": "avg:rag.context.size{*}", "display_name": "Avg Context Size"},
                {"query": "max:rag.context.size{*}", "display_name": "Max Context Size"},
            ],
            "yaxis": {"label": "Characters", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Embedding Generation Performance",
            "metrics": [
                {"query": "avg:embedding.generation.duration{*}", "display_name": "Avg Duration"},
                {"query": "avg:embedding.texts.processed{*}", "display_name": "Texts Processed"},
            ],
            "yaxis": {"label": "Time (ms) / Count", "scale": "linear"}
        },
        
        # Gap Detection Metrics Section
        {
            "type": "timeseries",
            "title": "Gap Analysis Duration",
            "metrics": [
                {"query": "avg:gap.analysis.duration{*}", "display_name": "Avg Duration"},
                {"query": "p95:gap.analysis.duration{*}", "display_name": "p95 Duration"},
            ],
            "yaxis": {"label": "Time (ms)", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Gap Counts",
            "metrics": [
                {"query": "avg:gap.total.count{*}", "display_name": "Avg Total Gaps"},
                {"query": "avg:gap.critical.count{*}", "display_name": "Avg Critical Gaps"},
                {"query": "avg:gap.safe.count{*}", "display_name": "Avg Safe Gaps"},
            ],
            "yaxis": {"label": "Gaps", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Gap Parsing Success Rate",
            "metrics": [
                {"query": "sum:gap.parsing.success{*}.as_rate()", "display_name": "Success"},
                {"query": "sum:gap.parsing.failure{*}.as_rate()", "display_name": "Failure"},
            ],
            "yaxis": {"label": "Rate", "scale": "linear"}
        },
        
        # API Metrics Section
        {
            "type": "timeseries",
            "title": "API Request Rate",
            "metrics": [
                {"query": "sum:api.request.count{*}.as_rate()", "display_name": "Requests/sec"},
                {"query": "sum:api.request.error{*}.as_rate()", "display_name": "Errors/sec"},
            ],
            "yaxis": {"label": "Requests/sec", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "API Latency by Endpoint",
            "metrics": [
                {"query": "avg:api.request.duration{endpoint:/api/analyze/stream}", "display_name": "Analyze Stream"},
                {"query": "avg:api.request.duration{endpoint:/api/chat}", "display_name": "Chat"},
                {"query": "avg:api.request.duration{endpoint:/api/upload}", "display_name": "Upload"},
            ],
            "yaxis": {"label": "Latency (ms)", "scale": "linear"}
        },
        
        # Chat Metrics Section
        {
            "type": "timeseries",
            "title": "Chat Response Performance",
            "metrics": [
                {"query": "avg:chat.response.duration{*}", "display_name": "Avg Response Time"},
                {"query": "p95:chat.response.duration{*}", "display_name": "p95 Response Time"},
                {"query": "avg:chat.response.length{*}", "display_name": "Avg Response Length"},
            ],
            "yaxis": {"label": "Time (ms) / Length (chars)", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Chat Session Metrics",
            "metrics": [
                {"query": "sum:chat.session.start{*}.as_rate()", "display_name": "Sessions Started/min"},
                {"query": "sum:chat.message.count_total{*}.as_rate()", "display_name": "Messages/min"},
            ],
            "yaxis": {"label": "Count/min", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Chat Context Usage",
            "metrics": [
                {"query": "avg:chat.context.size{*}", "display_name": "Avg Context Size"},
                {"query": "avg:chat.message.count{*}", "display_name": "Avg Messages per Session"},
            ],
            "yaxis": {"label": "Size (chars) / Count", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Chat Quality Metrics",
            "metrics": [
                {"query": "sum:chat.response.incomplete{*}.as_rate()", "display_name": "Incomplete Responses/min"},
                {"query": "sum:chat.exam_question.request{*}.as_rate()", "display_name": "Exam Question Requests/min"},
            ],
            "yaxis": {"label": "Count/min", "scale": "linear"}
        },
        {
            "type": "timeseries",
            "title": "Exam Question Generation",
            "metrics": [
                {"query": "avg:exam_question.generation.duration{*}", "display_name": "Avg Generation Time"},
                {"query": "avg:exam_question.count{*}", "display_name": "Avg Questions Generated"},
                {"query": "sum:exam_question.generation.success{*}.as_rate()", "display_name": "Success/min"},
            ],
            "yaxis": {"label": "Time (ms) / Count", "scale": "linear"}
        },
        
        # Vector DB Error Frequency Section
        {
            "type": "timeseries",
            "title": "Vector DB Error Rate",
            "metrics": [
                {"query": "avg:vector_db.error.rate{error_type:all}", "display_name": "Overall Error Rate"},
                {"query": "avg:vector_db.error.rate{error_type:error_finding_id}", "display_name": "Error Finding ID Rate"},
                {"query": "avg:vector_db.error.rate{error_type:other}", "display_name": "Other Error Rate"},
            ],
            "yaxis": {"label": "Error Rate (%)", "scale": "linear"}
        },
        {
            "type": "query_value",
            "title": "Current Vector DB Error Rate",
            "metrics": [
                {"query": "avg:vector_db.error.rate{error_type:all}", "display_name": "Error Rate %"},
            ],
        },
        {
            "type": "timeseries",
            "title": "Vector DB Search Performance",
            "metrics": [
                {"query": "avg:vector_db.search.duration{*}", "display_name": "Avg Search Duration"},
                {"query": "p95:vector_db.search.duration{*}", "display_name": "p95 Search Duration"},
                {"query": "avg:vector_db.search.retry_count{*}", "display_name": "Avg Retry Count"},
            ],
            "yaxis": {"label": "Time (ms) / Retries", "scale": "linear"}
        },
        
        # Health & Errors Section
        {
            "type": "timeseries",
            "title": "Application Errors",
            "metrics": [
                {"query": "sum:application.error{*}.as_rate()", "display_name": "Errors/min"},
            ],
            "yaxis": {"label": "Errors", "scale": "linear"}
        },
        {
            "type": "query_value",
            "title": "Current Error Rate",
            "metrics": [
                {"query": "sum:application.error{*}.as_rate()", "display_name": "Errors/min"},
            ],
        },
        {
            "type": "timeseries",
            "title": "Health Check Status",
            "metrics": [
                {"query": "sum:health.check.pass{*}", "display_name": "Pass"},
                {"query": "sum:health.check.fail{*}", "display_name": "Fail"},
            ],
            "yaxis": {"label": "Checks", "scale": "linear"}
        },
    ]
}


# ==================== Alert Configuration ====================

ALERT_CONFIGS = [
    {
        "name": "Critical: High LLM Error Rate",
        "message": "LLM error rate has exceeded 10% over the last 5 minutes. This may indicate model availability issues or safety filter problems.",
        "query": "avg(last_5m):(sum:llm.request.error{*}.as_rate() / sum:llm.request.count{*}.as_rate()) * 100 > 10",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 60,
            "thresholds": {
                "critical": 10,
                "warning": 5
            }
        },
        "tags": ["service:databone-llm", "severity:critical", "team:ai-engineering"],
        "priority": "P1"
    },
    {
        "name": "Warning: Safety Filter Block Spike",
        "message": "Safety filter blocks have spiked. More than 5 blocks in the last 10 minutes. Review content being sent to LLM.",
        "query": "sum(last_10m):sum:llm.safety.blocked{*} > 5",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 120,
            "thresholds": {
                "warning": 5,
                "ok": 0
            }
        },
        "tags": ["service:databone-llm", "severity:warning", "team:ai-engineering"],
        "priority": "P2"
    },
    {
        "name": "Warning: Model Fallback Spike",
        "message": "Model fallbacks have spiked. More than 3 fallbacks in the last 5 minutes. Check model availability.",
        "query": "sum(last_5m):sum:llm.model.fallback{*} > 3",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 120,
            "thresholds": {
                "warning": 3,
                "ok": 0
            }
        },
        "tags": ["service:databone-llm", "severity:warning", "team:ai-engineering"],
        "priority": "P2"
    },
    {
        "name": "Warning: High LLM Latency",
        "message": "LLM p95 latency has exceeded 10 seconds. This may indicate performance degradation.",
        "query": "p95(last_5m):llm.request.duration{*} > 10000",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 180,
            "thresholds": {
                "warning": 10000,
                "ok": 5000
            }
        },
        "tags": ["service:databone-llm", "severity:warning", "team:ai-engineering"],
        "priority": "P3"
    },
    {
        "name": "Warning: Gap Parsing Failure Rate",
        "message": "Gap parsing failure rate has exceeded 20%. This may indicate LLM response format issues.",
        "query": "avg(last_10m):(sum:gap.parsing.failure{*}.as_rate() / (sum:gap.parsing.success{*}.as_rate() + sum:gap.parsing.failure{*}.as_rate())) * 100 > 20",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 180,
            "thresholds": {
                "warning": 20,
                "ok": 5
            }
        },
        "tags": ["service:databone-llm", "severity:warning", "team:ai-engineering"],
        "priority": "P3"
    },
    {
        "name": "Critical: High API Error Rate",
        "message": "API error rate has exceeded 5%. This indicates application-level issues.",
        "query": "avg(last_5m):(sum:api.request.error{*}.as_rate() / sum:api.request.count{*}.as_rate()) * 100 > 5",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 60,
            "thresholds": {
                "critical": 5,
                "warning": 2
            }
        },
        "tags": ["service:databone-llm", "severity:critical", "team:ai-engineering"],
        "priority": "P1"
    },
    {
        "name": "Critical: Component Health Check Failure",
        "message": "A component health check has failed. Immediate investigation required.",
        "query": "sum(last_1m):sum:health.check.fail{*} > 0",
        "options": {
            "notify_audit": True,
            "notify_no_data": False,
            "renotify_interval": 30,
            "thresholds": {
                "critical": 1,
                "ok": 0
            }
        },
        "tags": ["service:databone-llm", "severity:critical", "team:ai-engineering"],
        "priority": "P1"
    }
]


def get_incident_template(alert_name: str, alert_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an incident template for Datadog when an alert is triggered.
    
    Args:
        alert_name: Name of the alert
        alert_message: Alert message
        context: Additional context about the incident
        
    Returns:
        Incident template dictionary
    """
    return {
        "title": f"Incident: {alert_name}",
        "description": alert_message,
        "fields": {
            "severity": context.get("severity", "unknown"),
            "priority": context.get("priority", "P3"),
            "status": "investigating",
            "team": "ai-engineering",
            "service": "databone-llm",
            "environment": context.get("env", "production"),
            "detected_at": context.get("timestamp"),
            "metrics": context.get("metrics", {}),
            "recommended_actions": [
                "1. Review Datadog dashboard for detailed metrics",
                "2. Check LLM service logs for error patterns",
                "3. Verify model availability in Vertex AI",
                "4. Review recent code deployments",
                "5. Check system resource utilization"
            ]
        },
        "tags": [
            "incident",
            f"severity:{context.get('severity', 'unknown')}",
            "service:databone-llm",
            "team:ai-engineering"
        ]
    }









