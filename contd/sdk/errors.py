"""
Contd SDK Error Hierarchy

All exceptions inherit from ContdError for easy catching.
Each error includes contextual information for debugging.
"""

from typing import Optional


class ContdError(Exception):
    """
    Base exception for all Contd SDK errors.

    Attributes:
        message: Human-readable error description
        workflow_id: Associated workflow ID if applicable
        details: Additional context for debugging
    """

    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.workflow_id = workflow_id
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.workflow_id:
            parts.append(f"[workflow={self.workflow_id}]")
        if self.details:
            parts.append(f"details={self.details}")
        return " ".join(parts)


# ============================================================================
# Workflow Lifecycle Errors
# ============================================================================


class WorkflowLocked(ContdError):
    """
    Workflow is locked by another executor.

    This occurs when attempting to execute a workflow that is already
    being processed by another executor instance.
    """

    def __init__(
        self,
        workflow_id: str,
        owner_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ):
        details = {}
        if owner_id:
            details["current_owner"] = owner_id
        if expires_at:
            details["expires_at"] = expires_at
        super().__init__(
            "Workflow is locked by another executor",
            workflow_id=workflow_id,
            details=details,
        )


class NoActiveWorkflow(ContdError):
    """
    No workflow context found in current execution.

    This typically means a @step decorated function was called
    outside of a @workflow decorated function.
    """

    def __init__(self, message: str = "No active workflow context"):
        super().__init__(message)


class WorkflowNotFound(ContdError):
    """Workflow does not exist in persistence."""

    def __init__(self, workflow_id: str):
        super().__init__("Workflow not found", workflow_id=workflow_id)


class WorkflowAlreadyCompleted(ContdError):
    """Attempted operation on a completed workflow."""

    def __init__(self, workflow_id: str, completed_at: Optional[str] = None):
        details = {"completed_at": completed_at} if completed_at else {}
        super().__init__(
            "Workflow has already completed", workflow_id=workflow_id, details=details
        )


# ============================================================================
# Step Execution Errors
# ============================================================================


class StepError(ContdError):
    """Base class for step-related errors."""

    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        attempt: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        self.step_id = step_id
        self.step_name = step_name
        self.attempt = attempt

        full_details = details or {}
        if step_id:
            full_details["step_id"] = step_id
        if step_name:
            full_details["step_name"] = step_name
        if attempt is not None:
            full_details["attempt"] = attempt

        super().__init__(message, workflow_id=workflow_id, details=full_details)


class StepTimeout(StepError):
    """Step exceeded configured timeout."""

    def __init__(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        timeout_seconds: float,
        elapsed_seconds: float,
    ):
        super().__init__(
            f"Step timed out after {elapsed_seconds:.2f}s (limit: {timeout_seconds}s)",
            workflow_id=workflow_id,
            step_id=step_id,
            step_name=step_name,
            details={
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": elapsed_seconds,
            },
        )


class TooManyAttempts(StepError):
    """Step exceeded maximum retry attempts."""

    def __init__(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        max_attempts: int,
        last_error: Optional[str] = None,
    ):
        details = {"max_attempts": max_attempts}
        if last_error:
            details["last_error"] = last_error
        super().__init__(
            f"Step exceeded {max_attempts} retry attempts",
            workflow_id=workflow_id,
            step_id=step_id,
            step_name=step_name,
            details=details,
        )


class StepExecutionFailed(StepError):
    """Step execution failed with an unrecoverable error."""

    def __init__(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        attempt: int,
        original_error: Exception,
    ):
        super().__init__(
            f"Step execution failed: {original_error}",
            workflow_id=workflow_id,
            step_id=step_id,
            step_name=step_name,
            attempt=attempt,
            details={"original_error_type": type(original_error).__name__},
        )
        self.__cause__ = original_error


# ============================================================================
# Data Integrity Errors
# ============================================================================


class IntegrityError(ContdError):
    """Base class for data integrity errors."""

    pass


class ChecksumMismatch(IntegrityError):
    """Data checksum validation failed."""

    def __init__(
        self, workflow_id: str, resource_type: str, expected: str, actual: str
    ):
        super().__init__(
            f"{resource_type} checksum mismatch",
            workflow_id=workflow_id,
            details={
                "resource_type": resource_type,
                "expected_checksum": expected[:16] + "...",
                "actual_checksum": actual[:16] + "...",
            },
        )


class EventSequenceGap(IntegrityError):
    """Gap detected in event sequence numbers."""

    def __init__(self, workflow_id: str, expected_seq: int, actual_seq: int):
        super().__init__(
            f"Event sequence gap: expected {expected_seq}, got {actual_seq}",
            workflow_id=workflow_id,
            details={
                "expected_sequence": expected_seq,
                "actual_sequence": actual_seq,
                "gap_size": actual_seq - expected_seq,
            },
        )


class SnapshotCorrupted(IntegrityError):
    """Snapshot data is corrupted or invalid."""

    def __init__(self, workflow_id: str, snapshot_ref: str, reason: str):
        super().__init__(
            f"Snapshot corrupted: {reason}",
            workflow_id=workflow_id,
            details={"snapshot_ref": snapshot_ref, "reason": reason},
        )


# ============================================================================
# Persistence Errors
# ============================================================================


class PersistenceError(ContdError):
    """Base class for persistence layer errors."""

    pass


class JournalWriteError(PersistenceError):
    """Failed to write event to journal."""

    def __init__(self, workflow_id: str, event_type: str, reason: str):
        super().__init__(
            f"Failed to write {event_type} event: {reason}",
            workflow_id=workflow_id,
            details={"event_type": event_type},
        )


class LeaseAcquisitionFailed(PersistenceError):
    """Failed to acquire workflow lease."""

    def __init__(self, workflow_id: str, reason: str):
        super().__init__(f"Lease acquisition failed: {reason}", workflow_id=workflow_id)


class SnapshotStorageError(PersistenceError):
    """Failed to store or retrieve snapshot."""

    def __init__(self, workflow_id: str, operation: str, reason: str):
        super().__init__(
            f"Snapshot {operation} failed: {reason}",
            workflow_id=workflow_id,
            details={"operation": operation},
        )


# ============================================================================
# Recovery Errors
# ============================================================================


class RecoveryError(ContdError):
    """Base class for recovery-related errors."""

    pass


class RecoveryFailed(RecoveryError):
    """Workflow recovery failed."""

    def __init__(self, workflow_id: str, reason: str, recoverable: bool = False):
        super().__init__(
            f"Recovery failed: {reason}",
            workflow_id=workflow_id,
            details={"recoverable": recoverable},
        )
        self.recoverable = recoverable


class InvalidSavepoint(RecoveryError):
    """Savepoint is invalid or cannot be restored."""

    def __init__(self, workflow_id: str, savepoint_id: str, reason: str):
        super().__init__(
            f"Invalid savepoint: {reason}",
            workflow_id=workflow_id,
            details={"savepoint_id": savepoint_id},
        )


# ============================================================================
# Configuration Errors
# ============================================================================


class ConfigurationError(ContdError):
    """Invalid SDK configuration."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, details=details)


class InvalidRetryPolicy(ConfigurationError):
    """Retry policy configuration is invalid."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid retry policy: {reason}", config_key="retry_policy")


# ============================================================================
# LLM Errors
# ============================================================================


class TokenBudgetExceeded(ContdError):
    """
    Token or cost budget exceeded for LLM operations.

    Raised when an LLM step or workflow exceeds configured limits.
    """

    def __init__(
        self,
        workflow_id: str,
        budget_type: str,  # "tokens", "cost", "step_tokens", "step_cost"
        budget_limit: float,
        current_usage: float,
    ):
        if "cost" in budget_type:
            message = f"LLM {budget_type} budget exceeded: ${current_usage:.4f} > ${budget_limit:.4f}"
        else:
            message = f"LLM {budget_type} budget exceeded: {int(current_usage)} > {int(budget_limit)}"

        super().__init__(
            message,
            workflow_id=workflow_id,
            details={
                "budget_type": budget_type,
                "budget_limit": budget_limit,
                "current_usage": current_usage,
                "overage": current_usage - budget_limit,
            },
        )
        self.budget_type = budget_type
        self.budget_limit = budget_limit
        self.current_usage = current_usage


# ============================================================================
# Testing Errors
# ============================================================================


class WorkflowInterrupted(ContdError):
    """
    Workflow was intentionally interrupted (test utility).

    Used by ContdTestCase to simulate failures at specific steps.
    """

    def __init__(self, workflow_id: str, step_number: int):
        super().__init__(
            f"Workflow interrupted at step {step_number} for testing",
            workflow_id=workflow_id,
            details={"interrupted_at_step": step_number},
        )
