from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
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
    timestamp: datetime
    schema_version: str = "1.0"
    # producer_version and checksum are added by the Journal at append time


@dataclass(frozen=True)
class StepIntentionEvent(BaseEvent):
    step_id: str
    step_name: str
    attempt_id: int
    event_type: Literal[EventType.STEP_INTENTION] = EventType.STEP_INTENTION

@dataclass(frozen=True)
class StepCompletedEvent(BaseEvent):
    step_id: str
    attempt_id: int
    state_delta: dict  # Only changes
    duration_ms: int
    event_type: Literal[EventType.STEP_COMPLETED] = EventType.STEP_COMPLETED

@dataclass(frozen=True)
class StepFailedEvent(BaseEvent):
    step_id: str
    attempt_id: int
    error: str
    event_type: Literal[EventType.STEP_FAILED] = EventType.STEP_FAILED

@dataclass(frozen=True)
class SavepointCreatedEvent(BaseEvent):
    savepoint_id: str
    step_number: int
    # Epistemic metadata
    goal_summary: str
    current_hypotheses: list[str]
    open_questions: list[str]
    decision_log: list[dict]
    next_step: str
    # State reference
    snapshot_ref: str  # S3 key or inline
    event_type: Literal[EventType.SAVEPOINT_CREATED] = EventType.SAVEPOINT_CREATED
