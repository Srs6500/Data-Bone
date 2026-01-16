# Datadog Observability Setup Guide

This guide explains how to set up and use Datadog observability monitoring for the DataBone LLM application.

## Overview

The Datadog integration provides comprehensive observability for:
- **LLM Metrics**: Request latency, success rates, token usage, safety filter blocks, model fallbacks
- **RAG Pipeline**: Retrieval performance, chunk counts, context sizes
- **Gap Detection**: Analysis duration, gap counts, parsing success rates
- **Application Health**: API metrics, error rates, component health checks

## Prerequisites

1. **Datadog Account**: Sign up at https://www.datadoghq.com/
2. **API Keys**: Get your Datadog API key and Application key from the Datadog UI
3. **Datadog Agent** (optional): For infrastructure monitoring, install the Datadog agent

## Setup Steps

### 1. Install Dependencies

The required Datadog packages are already in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Add these to your `.env` file or set as environment variables:

```bash
# Required: Datadog API Key
DD_API_KEY=your_datadog_api_key_here

# Optional: Datadog Application Key (for API calls like creating dashboards)
DD_APP_KEY=your_datadog_app_key_here

# Optional: Datadog Agent Host (default: localhost)
DD_AGENT_HOST=localhost

# Optional: DogStatsD Port (default: 8125)
DD_DOGSTATSD_PORT=8125

# Optional: Environment tag
DD_ENV=production  # or development, staging, etc.

# Optional: Host name
DD_HOST=databone-server-1
```

### 3. Initialize Datadog Monitoring

The monitoring module automatically initializes when the application starts. If `DD_API_KEY` is set, monitoring is enabled.

### 4. Create Dashboards and Alerts

Run the setup script to create dashboards, alerts, and detection rules:

```bash
cd backend
python -m app.monitoring.datadog_setup
```

This will:
- Create a comprehensive observability dashboard
- Set up detection rules for critical issues
- Configure alerts with appropriate thresholds

## Metrics Tracked

### LLM Metrics

- `llm.request.count`: Total LLM requests
- `llm.request.error`: Failed LLM requests
- `llm.request.duration`: Request latency (distribution)
- `llm.tokens.used`: Token usage (if available)
- `llm.safety.blocked`: Safety filter blocks
- `llm.model.fallback`: Model fallback events
- `llm.model.usage`: Model usage by model name

**Tags**: `model`, `operation`, `success`, `error_type`, `safety_blocked`, `model_fallback`

### RAG Metrics

- `rag.retrieval.count`: RAG retrieval operations
- `rag.retrieval.duration`: Retrieval latency
- `rag.chunks.retrieved`: Number of chunks retrieved
- `rag.context.size`: Size of retrieved context in characters

**Tags**: `service`, `env`, `course_info_used`

### Gap Detection Metrics

- `gap.analysis.duration`: Total analysis time
- `gap.total.count`: Total gaps detected
- `gap.critical.count`: Critical gaps detected
- `gap.safe.count`: Safe gaps detected
- `gap.parsing.success`: Successful parsing events
- `gap.parsing.failure`: Failed parsing events

**Tags**: `service`, `env`, `parsing_success`, `rag_enhanced`

### Embedding Metrics

- `embedding.generation.duration`: Embedding generation time
- `embedding.texts.processed`: Number of texts processed

**Tags**: `model`, `service`, `env`

### API Metrics

- `api.request.count`: Total API requests
- `api.request.error`: Failed API requests
- `api.request.duration`: Request latency

**Tags**: `endpoint`, `method`, `status_code`, `error`

### Health & Error Metrics

- `application.error`: Application errors
- `health.check.pass`: Successful health checks
- `health.check.fail`: Failed health checks

**Tags**: `error_type`, `component`, `service`, `env`

## Detection Rules

The following detection rules are configured:

1. **High LLM Error Rate** (Critical)
   - Triggers when error rate > 10% over 5 minutes
   - Indicates model availability or safety filter issues

2. **Safety Filter Block Spike** (Warning)
   - Triggers when > 5 blocks in 10 minutes
   - Indicates content triggering safety filters

3. **Model Fallback Spike** (Warning)
   - Triggers when > 3 fallbacks in 5 minutes
   - Indicates model availability issues

4. **High LLM Latency** (Warning)
   - Triggers when p95 latency > 10 seconds
   - Indicates performance degradation

5. **Gap Parsing Failure Rate** (Warning)
   - Triggers when failure rate > 20%
   - Indicates LLM response format issues

6. **High API Error Rate** (Critical)
   - Triggers when error rate > 5%
   - Indicates application-level issues

7. **Component Health Check Failure** (Critical)
   - Triggers when any component fails health check
   - Requires immediate investigation

## Dashboard

The dashboard includes:

- **LLM Metrics Section**: Request rates, latency, error rates, safety blocks, model usage, token usage
- **RAG Metrics Section**: Retrieval performance, context sizes, embedding generation
- **Gap Detection Section**: Analysis duration, gap counts, parsing success rates
- **API Metrics Section**: Request rates, latency by endpoint
- **Health & Errors Section**: Error rates, health check status

Access the dashboard in Datadog UI after running the setup script.

## Alerts & Incidents

When detection rules are triggered:

1. **Alert is created** in Datadog with appropriate severity
2. **Notification is sent** to configured channels (email, Slack, PagerDuty, etc.)
3. **Incident template** is available for creating incidents with:
   - Severity and priority
   - Recommended actions
   - Context about the issue
   - Links to relevant dashboards

### Configuring Alert Notifications

1. Go to Datadog UI → Monitors → Notification Settings
2. Configure notification channels:
   - Email
   - Slack
   - PagerDuty
   - Microsoft Teams
   - Webhooks
3. Assign notification channels to alert tags

## Usage in Code

### Automatic Instrumentation

Most metrics are tracked automatically:
- LLM requests are instrumented in `llm_service.py`
- RAG operations are instrumented in `gap_detector.py`
- API requests are tracked via middleware in `main.py`

### Manual Instrumentation

You can also track custom metrics:

```python
from app.monitoring import monitor

# Track custom event
monitor.send_custom_event(
    title="Custom Event",
    text="Description of the event",
    alert_type="info",  # or "success", "warning", "error"
    tags=["custom:tag"]
)

# Track error
monitor.track_error(
    error_type="custom_error",
    error_message="Error description",
    context={"additional": "context"}
)

# Track health check
monitor.track_health_check("component_name", healthy=True)
```

## Troubleshooting

### Monitoring Not Working

1. **Check API Key**: Ensure `DD_API_KEY` is set
2. **Check Agent**: If using DogStatsD, ensure agent is running
3. **Check Logs**: Look for Datadog initialization messages in application logs
4. **Check Network**: Ensure application can reach Datadog endpoints

### Metrics Not Appearing

1. **Wait**: Metrics may take 1-2 minutes to appear in Datadog
2. **Check Tags**: Ensure tags are correctly formatted
3. **Check Metric Names**: Verify metric names match dashboard queries
4. **Check Time Range**: Ensure dashboard time range includes recent data

### Alerts Not Triggering

1. **Check Thresholds**: Verify alert thresholds are appropriate
2. **Check Query**: Ensure alert query matches metric names and tags
3. **Check Time Window**: Verify time window is appropriate
4. **Test Alert**: Manually trigger conditions to test alerts

## Best Practices

1. **Tag Everything**: Use consistent tags for filtering and grouping
2. **Set Appropriate Thresholds**: Adjust alert thresholds based on baseline metrics
3. **Review Regularly**: Review dashboards and alerts regularly
4. **Document Incidents**: Use incident templates to document issues and resolutions
5. **Monitor Trends**: Watch for trends, not just spikes
6. **Set Up Runbooks**: Create runbooks for common issues

## Support

For issues or questions:
1. Check Datadog documentation: https://docs.datadoghq.com/
2. Review application logs for Datadog errors
3. Check Datadog status page: https://status.datadoghq.com/









