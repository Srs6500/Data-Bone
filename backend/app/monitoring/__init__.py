"""
Datadog monitoring and observability module.
"""
from app.monitoring.datadog_monitor import DatadogMonitor

# Initialize global monitor instance
monitor = DatadogMonitor()

__all__ = ['monitor', 'DatadogMonitor']









