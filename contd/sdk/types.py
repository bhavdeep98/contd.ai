"""
Contd SDK Types

Pydantic models for validation and serialization.
"""
from typing import TypedDict, NotRequired, List, Dict, Any, Tuple, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import timedelta
from enum import Enum
import random


# ============================================================================
# Enums
# ============================================================================

class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================================
# TypedDict (for backward compatibility)
# ============================================================================

class State(TypedDict):
    """
    User-facing state container.
    Reserved keys start with underscore.
    """
    # User variables (any keys without underscore prefix)
    
    # Reserved for SDK
    _workflow_id: NotRequired[str]
    _step_number: NotRequired[int]
    _savepoint_metadata: NotRequired[dict]


class SavepointMetadataDict(TypedDict):
    """Metadata for rich savepoints (TypedDict version)."""
    goal_summary: str
    hypotheses: List[str]
    questions: List[str]
    decisions: List[Dict[str, Any]]
    next_step: str


# ============================================================================
# Pydantic Models
# ============================================================================

class RetryPolicy(BaseModel):
    """
    Configurable retry policy with exponential backoff.
    
    Attributes:
        max_attempts: Maximum number of retry attempts (1 = no retries)
        backoff_base: Base for exponential backoff calculation
        backoff_max: Maximum backoff delay in seconds
        backoff_jitter: Jitter factor (0.0-1.0) to randomize delays
        retryable_exceptions: Tuple of exception types that trigger retry
    
    Example:
        >>> policy = RetryPolicy(max_attempts=5, backoff_base=2.0)
        >>> policy.should_retry(attempt=2, error=ConnectionError())
        True
        >>> policy.backoff(attempt=3)  # ~8 seconds with jitter
    """
    max_attempts: int = Field(default=3, ge=1, le=100)
    backoff_base: float = Field(default=2.0, ge=1.0, le=10.0)
    backoff_max: float = Field(default=60.0, ge=1.0, le=3600.0)
    backoff_jitter: float = Field(default=0.5, ge=0.0, le=1.0)
    retryable_exceptions: Tuple[type, ...] = Field(default=(Exception,))
    
    model_config = {"arbitrary_types_allowed": True}
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if retry should be attempted."""
        return (
            attempt < self.max_attempts 
            and isinstance(error, self.retryable_exceptions)
        )
    
    def backoff(self, attempt: int) -> float:
        """
        Calculate backoff delay with exponential growth and jitter.
        
        Formula: min(base^attempt, max) * (1 - jitter/2 + random*jitter)
        """
        delay = min(self.backoff_base ** attempt, self.backoff_max)
        jitter_range = delay * self.backoff_jitter
        return delay - jitter_range / 2 + random.random() * jitter_range


class SavepointMetadata(BaseModel):
    """
    Rich metadata for workflow savepoints.
    
    Captures epistemic context for reasoning workflows,
    enabling meaningful time-travel and debugging.
    """
    goal_summary: str = Field(
        default="",
        description="Brief summary of current workflow goal"
    )
    hypotheses: List[str] = Field(
        default_factory=list,
        description="Current working hypotheses"
    )
    questions: List[str] = Field(
        default_factory=list,
        description="Open questions to be resolved"
    )
    decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Decision log with rationale"
    )
    next_step: str = Field(
        default="",
        description="Planned next action"
    )
    
    def add_decision(self, decision: str, rationale: str, alternatives: List[str] = None):
        """Add a decision to the log."""
        self.decisions.append({
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives or []
        })


class WorkflowInput(BaseModel):
    """Input parameters for starting a workflow."""
    workflow_name: str = Field(..., min_length=1, max_length=256)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=256)
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Ensure tag keys and values are reasonable length."""
        for key, value in v.items():
            if len(key) > 64:
                raise ValueError(f"Tag key too long: {key[:20]}...")
            if len(value) > 256:
                raise ValueError(f"Tag value too long for key {key}")
        return v


class WorkflowResult(BaseModel):
    """Result of a workflow execution."""
    workflow_id: str
    status: WorkflowStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    step_count: int = 0


class StepResult(BaseModel):
    """Result of a step execution."""
    step_id: str
    step_name: str
    status: StepStatus
    attempt: int = 1
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: int = 0
    was_cached: bool = False


class SavepointInfo(BaseModel):
    """Information about a workflow savepoint."""
    savepoint_id: str
    workflow_id: str
    step_number: int
    created_at: str
    metadata: SavepointMetadata = Field(default_factory=SavepointMetadata)
    snapshot_size_bytes: Optional[int] = None


class WorkflowStatusResponse(BaseModel):
    """Response for workflow status queries."""
    workflow_id: str
    org_id: str
    status: WorkflowStatus
    current_step: int = 0
    total_steps: Optional[int] = None
    has_lease: bool = False
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[str] = None
    event_count: int = 0
    snapshot_count: int = 0
    latest_snapshot_step: Optional[int] = None
    savepoints: List[SavepointInfo] = Field(default_factory=list)


class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    components: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Configuration Models
# ============================================================================

class WorkflowConfigModel(BaseModel):
    """
    Pydantic model for workflow configuration.
    
    Use this for API requests; the dataclass WorkflowConfig
    is used internally by decorators.
    """
    workflow_id: Optional[str] = Field(default=None, max_length=256)
    max_duration_seconds: Optional[int] = Field(default=None, ge=1, le=86400)
    retry_policy: Optional[RetryPolicy] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    org_id: Optional[str] = Field(default=None, max_length=64)
    
    @model_validator(mode='after')
    def validate_config(self):
        """Cross-field validation."""
        if self.workflow_id and not self.workflow_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("workflow_id must be alphanumeric with dashes/underscores")
        return self


class StepConfigModel(BaseModel):
    """Pydantic model for step configuration."""
    checkpoint: bool = True
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    retry: Optional[RetryPolicy] = None
    savepoint: bool = False
    idempotency_key: Optional[str] = Field(default=None, max_length=256)
