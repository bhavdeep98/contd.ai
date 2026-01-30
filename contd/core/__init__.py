"""
Core engine components for workflow execution.
"""

from .engine import ExecutionEngine, EngineConfig
from .idempotency import IdempotencyGuard, TooManyAttempts, AttemptConflict
from .recovery import HybridRecovery, WorkflowNotFoundError, StateCorruptionError
from .version import __version__
from .context_preservation import (
    ContextHealth,
    RestoredContext,
    ReasoningBuffer,
    HealthTracker,
    execute_distill,
)

__all__ = [
    "ExecutionEngine",
    "EngineConfig",
    "IdempotencyGuard",
    "TooManyAttempts",
    "AttemptConflict",
    "HybridRecovery",
    "WorkflowNotFoundError",
    "StateCorruptionError",
    "__version__",
    # Context preservation
    "ContextHealth",
    "RestoredContext",
    "ReasoningBuffer",
    "HealthTracker",
    "execute_distill",
]
