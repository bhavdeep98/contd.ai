from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
import uuid


def generate_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


class EventType(Enum):
    WORKFLOW_STARTED = "workflow.started"
    STEP_INTENTION = "step.intention"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    SAVEPOINT_CREATED = "savepoint.created"
    WORKFLOW_SUSPENDED = "workflow.suspended"
    WORKFLOW_RESTORED = "workflow.restored"
    WORKFLOW_COMPLETED = "workflow.completed"
    # Context preservation events
    ANNOTATION_CREATED = "context.annotation"
    REASONING_INGESTED = "context.reasoning"
    CONTEXT_DIGEST_CREATED = "context.digest"


@dataclass(frozen=True)
class BaseEvent:
    event_id: str
    workflow_id: str
    org_id: str  # Multi-tenancy
    timestamp: datetime
    schema_version: str = "1.0"
    # producer_version and checksum are added by the Journal at append time


@dataclass(frozen=True)
class StepIntentionEvent(BaseEvent):
    step_id: str = ""
    step_name: str = ""
    attempt_id: int = 0
    event_type: Literal[EventType.STEP_INTENTION] = EventType.STEP_INTENTION


@dataclass(frozen=True)
class StepCompletedEvent(BaseEvent):
    step_id: str = ""
    attempt_id: int = 0
    state_delta: dict = None  # Only changes
    duration_ms: int = 0
    event_type: Literal[EventType.STEP_COMPLETED] = EventType.STEP_COMPLETED

    def __post_init__(self):
        if self.state_delta is None:
            object.__setattr__(self, "state_delta", {})


@dataclass(frozen=True)
class StepFailedEvent(BaseEvent):
    step_id: str = ""
    attempt_id: int = 0
    error: str = ""
    event_type: Literal[EventType.STEP_FAILED] = EventType.STEP_FAILED


@dataclass(frozen=True)
class SavepointCreatedEvent(BaseEvent):
    savepoint_id: str = ""
    step_number: int = 0
    # Epistemic metadata
    goal_summary: str = ""
    current_hypotheses: list = None
    open_questions: list = None
    decision_log: list = None
    next_step: str = ""
    # State reference
    snapshot_ref: str = ""  # S3 key or inline
    event_type: Literal[EventType.SAVEPOINT_CREATED] = EventType.SAVEPOINT_CREATED

    def __post_init__(self):
        if self.current_hypotheses is None:
            object.__setattr__(self, "current_hypotheses", [])
        if self.open_questions is None:
            object.__setattr__(self, "open_questions", [])
        if self.decision_log is None:
            object.__setattr__(self, "decision_log", [])


# =============================================================================
# Context Preservation Events
# =============================================================================


@dataclass(frozen=True)
class AnnotationCreatedEvent(BaseEvent):
    """
    Lightweight reasoning breadcrumb created by developer via ctx.annotate().
    Step-associated for filtering on restore.
    """
    step_number: int = 0
    step_name: str = ""
    text: str = ""
    event_type: Literal[EventType.ANNOTATION_CREATED] = EventType.ANNOTATION_CREATED


@dataclass(frozen=True)
class ReasoningIngestedEvent(BaseEvent):
    """
    Raw reasoning tokens ingested via ctx.ingest().
    Accumulated in buffer until distillation.
    """
    step_number: int = 0
    chunk: str = ""
    chunk_size: int = 0
    event_type: Literal[EventType.REASONING_INGESTED] = EventType.REASONING_INGESTED


@dataclass(frozen=True)
class ContextDigestCreatedEvent(BaseEvent):
    """
    Distilled context created by developer-provided distill function.
    Contains compressed reasoning from accumulated chunks.
    """
    step_number: int = 0
    digest: dict = None  # Developer-defined structure
    chunks_processed: int = 0
    distill_failed: bool = False
    error: str = ""
    # Raw chunks included if distill failed (fallback)
    raw_chunks: list = None
    event_type: Literal[EventType.CONTEXT_DIGEST_CREATED] = EventType.CONTEXT_DIGEST_CREATED

    def __post_init__(self):
        if self.digest is None:
            object.__setattr__(self, "digest", {})
        if self.raw_chunks is None:
            object.__setattr__(self, "raw_chunks", [])
