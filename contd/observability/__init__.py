"""
Contd.ai Observability Module

Complete observability stack including:
- Prometheus metrics exporters
- OpenTelemetry tracing integration
- Structured JSON logging
- Health check endpoints
- Alert definitions
"""

from .metrics import collector, MetricsCollector
from .exporter import start_metrics_server, stop_metrics_server
from .background import start_background_collection, stop_background_collection
from .push import MetricsPusher
from .tracing import (
    setup_tracing,
    shutdown_tracing,
    get_tracer,
    trace_workflow,
    trace_step,
    trace_restore,
    traced,
)
from .logging import (
    setup_json_logging,
    get_logger,
    set_workflow_context,
    clear_workflow_context,
    JSONFormatter,
    StructuredLogger,
)
from .health import router as health_router


def setup_observability(
    metrics_port: int = 9090,
    enable_background: bool = True,
    background_interval: int = 15,
    enable_tracing: bool = True,
    tracing_endpoint: str = None,
    enable_json_logging: bool = True,
    service_name: str = "contd",
):
    """
    Setup complete observability stack.
    
    Args:
        metrics_port: Port for Prometheus metrics endpoint
        enable_background: Enable background system metrics collection
        background_interval: Interval for background collection (seconds)
        enable_tracing: Enable OpenTelemetry tracing
        tracing_endpoint: OTLP endpoint for trace export
        enable_json_logging: Enable structured JSON logging
        service_name: Service name for tracing
    """
    # Start metrics server
    start_metrics_server(port=metrics_port)
    
    # Start background collection
    if enable_background:
        start_background_collection(interval_seconds=background_interval)
    
    # Setup tracing
    if enable_tracing:
        setup_tracing(
            service_name=service_name,
            otlp_endpoint=tracing_endpoint,
        )
    
    # Setup JSON logging
    if enable_json_logging:
        setup_json_logging()


def teardown_observability():
    """Cleanup observability resources"""
    stop_metrics_server()
    stop_background_collection()
    shutdown_tracing()


__all__ = [
    # Metrics
    'collector',
    'MetricsCollector',
    'start_metrics_server',
    'stop_metrics_server',
    'start_background_collection',
    'stop_background_collection',
    'MetricsPusher',
    # Tracing
    'setup_tracing',
    'shutdown_tracing',
    'get_tracer',
    'trace_workflow',
    'trace_step',
    'trace_restore',
    'traced',
    # Logging
    'setup_json_logging',
    'get_logger',
    'set_workflow_context',
    'clear_workflow_context',
    'JSONFormatter',
    'StructuredLogger',
    # Health
    'health_router',
    # Setup
    'setup_observability',
    'teardown_observability',
]
