"""
Core engine components for workflow execution.
"""

from .engine import ExecutionEngine, EngineConfig
from .idempotency import IdempotencyGuard, TooManyAttempts, AttemptConflict
from .recovery import HybridRecovery, WorkflowNotFoundError, StateCorruptionError
from .version import __version__

# Re-export context preservation from new location for backward compatibility
from contd.context import (
    ContextHealth,
    HealthSignals,
    ReasoningLedger,
    ContextEntry,
    ContextDigest,
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
    # Context preservation (re-exported from contd.context)
    "ContextHealth",
    "HealthSignals",
    "ReasoningLedger",
    "ContextEntry",
    "ContextDigest",
]
