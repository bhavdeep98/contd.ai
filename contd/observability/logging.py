"""
Structured JSON Logging for Contd.ai

Provides consistent, machine-parseable log output for production environments.
"""

import logging
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextvars import ContextVar


# Context variables for request/workflow correlation
_workflow_context: ContextVar[Optional[Dict[str, str]]] = ContextVar('workflow_context', default=None)
_request_context: ContextVar[Optional[Dict[str, str]]] = ContextVar('request_context', default=None)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    
    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "logger": "contd.core.engine",
        "message": "Workflow started",
        "workflow_id": "wf-123",
        "workflow_name": "order_processing",
        "trace_id": "abc123",
        "span_id": "def456",
        "extra": {...}
    }
    """
    
    def __init__(self, include_trace: bool = True):
        super().__init__()
        self.include_trace = include_trace
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add workflow context if available
        wf_ctx = _workflow_context.get()
        if wf_ctx:
            log_entry.update(wf_ctx)
        
        # Add request context if available
        req_ctx = _request_context.get()
        if req_ctx:
            log_entry.update(req_ctx)
        
        # Add trace context if available and enabled
        if self.include_trace:
            try:
                from opentelemetry import trace
                span = trace.get_current_span()
                if span and span.is_recording():
                    ctx = span.get_span_context()
                    log_entry["trace_id"] = format(ctx.trace_id, '032x')
                    log_entry["span_id"] = format(ctx.span_id, '016x')
            except ImportError:
                pass
        
        # Add extra fields from record
        if hasattr(record, 'extra') and record.extra:
            log_entry["extra"] = record.extra
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else None
            }
        
        # Add source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }
        
        return json.dumps(log_entry, default=str)


class StructuredLogger:
    """
    Wrapper around standard logger with structured logging support.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Internal log method with extra data support."""
        record_extra = extra or {}
        record_extra.update(kwargs)
        
        # Create a custom LogRecord with extra data
        self.logger.log(level, message, extra={'extra': record_extra} if record_extra else None)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        self.logger.error(message, exc_info=exc_info, extra={'extra': kwargs} if kwargs else None)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        self.logger.critical(message, exc_info=exc_info, extra={'extra': kwargs} if kwargs else None)
    
    # Workflow-specific logging methods
    def workflow_started(self, workflow_id: str, workflow_name: str, **kwargs):
        self.info(
            "Workflow started",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            event="workflow.started",
            **kwargs
        )
    
    def workflow_completed(self, workflow_id: str, workflow_name: str, duration_ms: float, **kwargs):
        self.info(
            "Workflow completed",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            duration_ms=duration_ms,
            event="workflow.completed",
            **kwargs
        )
    
    def workflow_failed(self, workflow_id: str, workflow_name: str, error: str, **kwargs):
        self.error(
            "Workflow failed",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            error=error,
            event="workflow.failed",
            **kwargs
        )
    
    def step_started(self, workflow_id: str, step_name: str, step_number: int, **kwargs):
        self.info(
            f"Step started: {step_name}",
            workflow_id=workflow_id,
            step_name=step_name,
            step_number=step_number,
            event="step.started",
            **kwargs
        )
    
    def step_completed(self, workflow_id: str, step_name: str, step_number: int, duration_ms: float, **kwargs):
        self.info(
            f"Step completed: {step_name}",
            workflow_id=workflow_id,
            step_name=step_name,
            step_number=step_number,
            duration_ms=duration_ms,
            event="step.completed",
            **kwargs
        )
    
    def step_failed(self, workflow_id: str, step_name: str, step_number: int, error: str, **kwargs):
        self.error(
            f"Step failed: {step_name}",
            workflow_id=workflow_id,
            step_name=step_name,
            step_number=step_number,
            error=error,
            event="step.failed",
            **kwargs
        )
    
    def restore_started(self, workflow_id: str, **kwargs):
        self.info(
            "Restore started",
            workflow_id=workflow_id,
            event="restore.started",
            **kwargs
        )
    
    def restore_completed(self, workflow_id: str, events_replayed: int, duration_ms: float, **kwargs):
        self.info(
            "Restore completed",
            workflow_id=workflow_id,
            events_replayed=events_replayed,
            duration_ms=duration_ms,
            event="restore.completed",
            **kwargs
        )


def set_workflow_context(workflow_id: str, workflow_name: Optional[str] = None):
    """Set workflow context for log correlation."""
    ctx = {"workflow_id": workflow_id}
    if workflow_name:
        ctx["workflow_name"] = workflow_name
    _workflow_context.set(ctx)


def clear_workflow_context():
    """Clear workflow context."""
    _workflow_context.set(None)


def set_request_context(request_id: str, user_id: Optional[str] = None, org_id: Optional[str] = None):
    """Set request context for log correlation."""
    ctx = {"request_id": request_id}
    if user_id:
        ctx["user_id"] = user_id
    if org_id:
        ctx["org_id"] = org_id
    _request_context.set(ctx)


def clear_request_context():
    """Clear request context."""
    _request_context.set(None)


def setup_json_logging(
    level: int = logging.INFO,
    include_trace: bool = True,
    logger_name: Optional[str] = None
):
    """
    Configure JSON structured logging.
    
    Args:
        level: Logging level (default: INFO)
        include_trace: Include OpenTelemetry trace context (default: True)
        logger_name: Specific logger to configure (default: root logger)
    """
    formatter = JSONFormatter(include_trace=include_trace)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.handlers = []  # Clear existing handlers
    logger.addHandler(handler)
    
    return logger


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


__all__ = [
    'JSONFormatter',
    'StructuredLogger',
    'setup_json_logging',
    'get_logger',
    'set_workflow_context',
    'clear_workflow_context',
    'set_request_context',
    'clear_request_context',
]
