"""
OpenTelemetry Tracing Integration for Contd.ai

Provides distributed tracing for workflow execution, step operations,
and cross-service communication.

Note: OpenTelemetry is an optional dependency. If not installed,
tracing functions become no-ops.
"""

from contextlib import contextmanager
from typing import Optional, Dict, Any
import functools

# Try to import OpenTelemetry, gracefully degrade if not available
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    _OTEL_AVAILABLE = True
except ImportError:
    # OpenTelemetry not installed - provide stubs
    trace = None
    TracerProvider = None
    Resource = None
    ResourceAttributes = None
    Status = None
    StatusCode = None
    TraceContextTextMapPropagator = None


# Global tracer provider
_tracer_provider = None
_tracer = None


def setup_tracing(
    service_name: str = "contd",
    service_version: str = "0.1.0",
    environment: str = "development",
    otlp_endpoint: Optional[str] = None,
    enable_console: bool = False,
):
    """
    Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service for trace identification
        service_version: Version of the service
        environment: Deployment environment (development, staging, production)
        otlp_endpoint: OTLP exporter endpoint (e.g., "http://localhost:4317")
        enable_console: Enable console span exporter for debugging

    Returns:
        Configured tracer instance, or None if OpenTelemetry not available
    """
    global _tracer_provider, _tracer

    if not _OTEL_AVAILABLE:
        print("Warning: OpenTelemetry not installed. Tracing disabled.")
        return None

    # Create resource with service info
    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: environment,
        }
    )

    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            print(
                "Warning: OTLP exporter not available. Install opentelemetry-exporter-otlp"
            )

    # Add console exporter for debugging
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        _tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(_tracer_provider)

    # Get tracer
    _tracer = trace.get_tracer(service_name, service_version)

    return _tracer


def get_tracer():
    """Get the configured tracer, initializing with defaults if needed."""
    global _tracer
    if not _OTEL_AVAILABLE:
        return None
    if _tracer is None:
        setup_tracing()
    return _tracer


def shutdown_tracing():
    """Shutdown tracing and flush pending spans."""
    global _tracer_provider, _tracer
    if _tracer_provider and _OTEL_AVAILABLE:
        _tracer_provider.shutdown()
        _tracer_provider = None
        _tracer = None


class _NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def set_attribute(self, key, value):
        pass

    def set_status(self, status):
        pass

    def record_exception(self, exception):
        pass

    def add_event(self, name, attributes=None):
        pass


@contextmanager
def trace_workflow(
    workflow_id: str, workflow_name: str, attributes: Optional[Dict[str, Any]] = None
):
    """
    Context manager for tracing workflow execution.

    Usage:
        with trace_workflow("wf-123", "order_processing") as span:
            # workflow execution
            span.set_attribute("custom.key", "value")
    """
    tracer = get_tracer()
    if not tracer:
        yield _NoOpSpan()
        return

    attrs = {
        "workflow.id": workflow_id,
        "workflow.name": workflow_name,
        "workflow.type": "contd",
    }
    if attributes:
        attrs.update(attributes)

    with tracer.start_as_current_span(
        f"workflow:{workflow_name}", attributes=attrs, kind=trace.SpanKind.INTERNAL
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_step(
    step_name: str,
    workflow_id: str,
    step_number: int,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for tracing step execution.

    Usage:
        with trace_step("process_payment", "wf-123", 3) as span:
            # step execution
    """
    tracer = get_tracer()
    if not tracer:
        yield _NoOpSpan()
        return

    attrs = {
        "step.name": step_name,
        "step.number": step_number,
        "workflow.id": workflow_id,
    }
    if attributes:
        attrs.update(attributes)

    with tracer.start_as_current_span(
        f"step:{step_name}", attributes=attrs, kind=trace.SpanKind.INTERNAL
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_restore(workflow_id: str, workflow_name: str, has_snapshot: bool = False):
    """
    Context manager for tracing restore operations.
    """
    tracer = get_tracer()
    if not tracer:
        yield _NoOpSpan()
        return

    attrs = {
        "workflow.id": workflow_id,
        "workflow.name": workflow_name,
        "restore.has_snapshot": has_snapshot,
    }

    with tracer.start_as_current_span(
        "restore", attributes=attrs, kind=trace.SpanKind.INTERNAL
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_persistence_operation(
    operation: str, storage_type: str, workflow_id: Optional[str] = None
):
    """
    Context manager for tracing persistence operations (journal, snapshot).
    """
    tracer = get_tracer()
    if not tracer:
        yield _NoOpSpan()
        return

    attrs = {
        "persistence.operation": operation,
        "persistence.storage_type": storage_type,
    }
    if workflow_id:
        attrs["workflow.id"] = workflow_id

    with tracer.start_as_current_span(
        f"persistence:{operation}", attributes=attrs, kind=trace.SpanKind.CLIENT
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def traced(span_name: Optional[str] = None):
    """
    Decorator for tracing function execution.

    Usage:
        @traced("custom_operation")
        def my_function():
            pass

        @traced()  # Uses function name as span name
        def another_function():
            pass
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)

            name = span_name or func.__name__

            with tracer.start_as_current_span(name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


# Trace context propagation for distributed tracing
_propagator = TraceContextTextMapPropagator() if _OTEL_AVAILABLE else None


def inject_trace_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """
    Inject current trace context into a carrier dict for propagation.

    Usage:
        headers = {}
        inject_trace_context(headers)
        # headers now contains traceparent, tracestate
    """
    if _propagator:
        _propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Extract trace context from carrier and set as current context.

    Usage:
        context = extract_trace_context(request.headers)
        with trace.use_span(context):
            # operations continue the trace
    """
    if _propagator:
        return _propagator.extract(carrier)
    return None


__all__ = [
    "setup_tracing",
    "get_tracer",
    "shutdown_tracing",
    "trace_workflow",
    "trace_step",
    "trace_restore",
    "trace_persistence_operation",
    "traced",
    "inject_trace_context",
    "extract_trace_context",
]
