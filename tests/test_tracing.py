"""
Tests for OpenTelemetry tracing integration.
"""

import pytest
from contd.observability.tracing import (
    setup_tracing,
    shutdown_tracing,
    get_tracer,
    trace_workflow,
    trace_step,
    trace_restore,
    traced,
    inject_trace_context,
    extract_trace_context,
    _OTEL_AVAILABLE,
)


class TestTracingSetup:
    """Test tracing setup and configuration."""
    
    def test_setup_tracing_returns_tracer_or_none(self):
        """Setup should return tracer if OTel available, None otherwise."""
        tracer = setup_tracing(service_name="test-service")
        if _OTEL_AVAILABLE:
            assert tracer is not None
        else:
            assert tracer is None
        shutdown_tracing()
    
    def test_get_tracer_consistent(self):
        """get_tracer should return consistent result."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        assert tracer1 is tracer2
        shutdown_tracing()
    
    def test_shutdown_tracing_clears_state(self):
        """Shutdown should clear tracer state."""
        setup_tracing()
        shutdown_tracing()
        # After shutdown, get_tracer will reinitialize
        # This just verifies no errors occur


class TestTracingContextManagers:
    """Test tracing context managers."""
    
    def test_trace_workflow_context_manager(self):
        """trace_workflow should work as context manager."""
        with trace_workflow("wf-123", "test_workflow") as span:
            # Should not raise
            span.set_attribute("test.key", "test_value")
    
    def test_trace_workflow_with_attributes(self):
        """trace_workflow should accept custom attributes."""
        with trace_workflow(
            "wf-123",
            "test_workflow",
            attributes={"custom.attr": "value"}
        ) as span:
            pass
    
    def test_trace_step_context_manager(self):
        """trace_step should work as context manager."""
        with trace_step("process_data", "wf-123", 1) as span:
            span.set_attribute("step.custom", "value")
    
    def test_trace_restore_context_manager(self):
        """trace_restore should work as context manager."""
        with trace_restore("wf-123", "test_workflow", has_snapshot=True) as span:
            pass
    
    def test_trace_workflow_handles_exception(self):
        """trace_workflow should handle exceptions properly."""
        with pytest.raises(ValueError):
            with trace_workflow("wf-123", "test_workflow") as span:
                raise ValueError("Test error")
    
    def test_trace_step_handles_exception(self):
        """trace_step should handle exceptions properly."""
        with pytest.raises(RuntimeError):
            with trace_step("failing_step", "wf-123", 1) as span:
                raise RuntimeError("Step failed")


class TestTracedDecorator:
    """Test the @traced decorator."""
    
    def test_traced_decorator_basic(self):
        """@traced should wrap function execution."""
        @traced()
        def my_function():
            return "result"
        
        result = my_function()
        assert result == "result"
    
    def test_traced_decorator_with_name(self):
        """@traced should accept custom span name."""
        @traced("custom_operation")
        def my_function():
            return 42
        
        result = my_function()
        assert result == 42
    
    def test_traced_decorator_preserves_args(self):
        """@traced should preserve function arguments."""
        @traced()
        def add(a, b):
            return a + b
        
        result = add(3, 4)
        assert result == 7
    
    def test_traced_decorator_handles_exception(self):
        """@traced should propagate exceptions."""
        @traced()
        def failing_function():
            raise ValueError("Expected error")
        
        with pytest.raises(ValueError, match="Expected error"):
            failing_function()


class TestTraceContextPropagation:
    """Test trace context propagation."""
    
    def test_inject_trace_context(self):
        """inject_trace_context should return carrier dict."""
        carrier = {}
        result = inject_trace_context(carrier)
        assert isinstance(result, dict)
    
    def test_extract_trace_context(self):
        """extract_trace_context should handle empty carrier."""
        carrier = {}
        result = extract_trace_context(carrier)
        # Result depends on OTel availability


class TestNoOpBehavior:
    """Test behavior when OpenTelemetry is not available."""
    
    def test_context_managers_work_without_otel(self):
        """Context managers should work even without OTel."""
        # These should not raise regardless of OTel availability
        with trace_workflow("wf-1", "test") as span:
            span.set_attribute("key", "value")
        
        with trace_step("step1", "wf-1", 1) as span:
            span.set_attribute("key", "value")
        
        with trace_restore("wf-1", "test") as span:
            span.set_attribute("key", "value")
    
    def test_traced_decorator_works_without_otel(self):
        """@traced decorator should work without OTel."""
        @traced()
        def simple_function():
            return "works"
        
        assert simple_function() == "works"
