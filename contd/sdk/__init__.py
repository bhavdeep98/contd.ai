"""
Contd SDK - Developer Experience Layer

Provides decorators, context management, and utilities for building
resumable workflows with exactly-once execution semantics.
"""

from .decorators import workflow, step, WorkflowConfig, StepConfig
from .context import ExecutionContext
from .client import ContdClient
from .types import (
    # Enums
    WorkflowStatus,
    StepStatus,
    # TypedDicts (backward compat)
    State,
    SavepointMetadataDict,
    # Pydantic models
    RetryPolicy,
    SavepointMetadata,
    WorkflowInput,
    WorkflowResult,
    StepResult,
    SavepointInfo,
    WorkflowStatusResponse,
    HealthCheck,
    WorkflowConfigModel,
    StepConfigModel,
)
from .errors import (
    # Base
    ContdError,
    # Workflow lifecycle
    WorkflowLocked,
    NoActiveWorkflow,
    WorkflowNotFound,
    WorkflowAlreadyCompleted,
    # Step execution
    StepError,
    StepTimeout,
    TooManyAttempts,
    StepExecutionFailed,
    # Data integrity
    IntegrityError,
    ChecksumMismatch,
    EventSequenceGap,
    SnapshotCorrupted,
    # Persistence
    PersistenceError,
    JournalWriteError,
    LeaseAcquisitionFailed,
    SnapshotStorageError,
    # Recovery
    RecoveryError,
    RecoveryFailed,
    InvalidSavepoint,
    # Configuration
    ConfigurationError,
    InvalidRetryPolicy,
    # Testing
    WorkflowInterrupted,
)
from .testing import (
    ContdTestCase,
    MockExecutionEngine,
    WorkflowTestBuilder,
    mock_workflow_context,
    StepExecution,
    WorkflowExecution,
)
from .registry import WorkflowRegistry

# Context preservation types (from new location)
from contd.context import (
    ContextHealth,
    HealthSignals,
    ReasoningLedger,
    ContextEntry,
    ContextDigest,
    distill_on_decline,
    savepoint_on_drift,
    warn_on_budget,
)

__all__ = [
    # Decorators
    "workflow",
    "step",
    "WorkflowConfig",
    "StepConfig",
    # Context
    "ExecutionContext",
    # Client
    "ContdClient",
    # Enums
    "WorkflowStatus",
    "StepStatus",
    # Types (TypedDict)
    "State",
    "SavepointMetadataDict",
    # Types (Pydantic)
    "RetryPolicy",
    "SavepointMetadata",
    "WorkflowInput",
    "WorkflowResult",
    "StepResult",
    "SavepointInfo",
    "WorkflowStatusResponse",
    "HealthCheck",
    "WorkflowConfigModel",
    "StepConfigModel",
    # Context Preservation
    "ContextHealth",
    "HealthSignals",
    "ReasoningLedger",
    "ContextEntry",
    "ContextDigest",
    # Context Recipes
    "distill_on_decline",
    "savepoint_on_drift",
    "warn_on_budget",
    # Errors - Base
    "ContdError",
    # Errors - Workflow
    "WorkflowLocked",
    "NoActiveWorkflow",
    "WorkflowNotFound",
    "WorkflowAlreadyCompleted",
    # Errors - Step
    "StepError",
    "StepTimeout",
    "TooManyAttempts",
    "StepExecutionFailed",
    # Errors - Integrity
    "IntegrityError",
    "ChecksumMismatch",
    "EventSequenceGap",
    "SnapshotCorrupted",
    # Errors - Persistence
    "PersistenceError",
    "JournalWriteError",
    "LeaseAcquisitionFailed",
    "SnapshotStorageError",
    # Errors - Recovery
    "RecoveryError",
    "RecoveryFailed",
    "InvalidSavepoint",
    # Errors - Config
    "ConfigurationError",
    "InvalidRetryPolicy",
    # Errors - Testing
    "WorkflowInterrupted",
    # Testing utilities
    "ContdTestCase",
    "MockExecutionEngine",
    "WorkflowTestBuilder",
    "mock_workflow_context",
    "StepExecution",
    "WorkflowExecution",
    # Registry
    "WorkflowRegistry",
]
