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
