"""
Tests for structured JSON logging.
"""

import pytest
import json
import logging
import io
from contd.observability.logging import (
    JSONFormatter,
    StructuredLogger,
    setup_json_logging,
    get_logger,
    set_workflow_context,
    clear_workflow_context,
    set_request_context,
    clear_request_context,
)


class TestJSONFormatter:
    """Test JSON log formatter."""
    
    def test_format_basic_message(self):
        """Formatter should produce valid JSON."""
        formatter = JSONFormatter(include_trace=False)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
    
    def test_format_includes_source_location(self):
        """Formatter should include source location."""
        formatter = JSONFormatter(include_trace=False)
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Debug message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "source" in parsed
        assert parsed["source"]["line"] == 42
    
    def test_format_with_exception(self):
        """Formatter should include exception info."""
        formatter = JSONFormatter(include_trace=False)
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "Test error" in parsed["exception"]["message"]


class TestStructuredLogger:
    """Test structured logger wrapper."""
    
    def setup_method(self):
        """Setup test logger."""
        self.logger = get_logger("test.structured")
    
    def test_info_logging(self):
        """Logger should support info level."""
        # Should not raise
        self.logger.info("Test info message", key="value")
    
    def test_error_logging(self):
        """Logger should support error level."""
        self.logger.error("Test error", error_code=500)
    
    def test_workflow_started(self):
        """Logger should have workflow_started method."""
        self.logger.workflow_started("wf-123", "test_workflow", user_id="user-1")
    
    def test_workflow_completed(self):
        """Logger should have workflow_completed method."""
        self.logger.workflow_completed("wf-123", "test_workflow", duration_ms=1500.5)
    
    def test_workflow_failed(self):
        """Logger should have workflow_failed method."""
        self.logger.workflow_failed("wf-123", "test_workflow", error="Connection timeout")
    
    def test_step_started(self):
        """Logger should have step_started method."""
        self.logger.step_started("wf-123", "process_data", step_number=1)
    
    def test_step_completed(self):
        """Logger should have step_completed method."""
        self.logger.step_completed("wf-123", "process_data", step_number=1, duration_ms=250.0)
    
    def test_step_failed(self):
        """Logger should have step_failed method."""
        self.logger.step_failed("wf-123", "process_data", step_number=1, error="Invalid input")
    
    def test_restore_started(self):
        """Logger should have restore_started method."""
        self.logger.restore_started("wf-123", from_snapshot=True)
    
    def test_restore_completed(self):
        """Logger should have restore_completed method."""
        self.logger.restore_completed("wf-123", events_replayed=50, duration_ms=120.0)


class TestContextFunctions:
    """Test context setting functions."""
    
    def teardown_method(self):
        """Clear context after each test."""
        clear_workflow_context()
        clear_request_context()
    
    def test_set_workflow_context(self):
        """set_workflow_context should not raise."""
        set_workflow_context("wf-123", "test_workflow")
    
    def test_clear_workflow_context(self):
        """clear_workflow_context should not raise."""
        set_workflow_context("wf-123")
        clear_workflow_context()
    
    def test_set_request_context(self):
        """set_request_context should not raise."""
        set_request_context("req-123", user_id="user-1", org_id="org-1")
    
    def test_clear_request_context(self):
        """clear_request_context should not raise."""
        set_request_context("req-123")
        clear_request_context()


class TestSetupJsonLogging:
    """Test JSON logging setup."""
    
    def test_setup_json_logging_returns_logger(self):
        """setup_json_logging should return configured logger."""
        logger = setup_json_logging(level=logging.DEBUG, include_trace=False)
        assert logger is not None
    
    def test_setup_json_logging_specific_logger(self):
        """setup_json_logging should configure specific logger."""
        logger = setup_json_logging(
            level=logging.WARNING,
            logger_name="specific.logger"
        )
        assert logger.name == "specific.logger"
        assert logger.level == logging.WARNING


class TestGetLogger:
    """Test get_logger function."""
    
    def test_get_logger_returns_structured_logger(self):
        """get_logger should return StructuredLogger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, StructuredLogger)
    
    def test_get_logger_different_names(self):
        """get_logger should return different loggers for different names."""
        logger1 = get_logger("module.one")
        logger2 = get_logger("module.two")
        assert logger1.logger.name != logger2.logger.name
