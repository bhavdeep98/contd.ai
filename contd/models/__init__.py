"""
Contd Models

Data models for workflow state, events, and persistence.
"""
from .state import WorkflowState, StateMigration
from .events import (
    EventType,
    BaseEvent,
    StepIntentionEvent,
    StepCompletedEvent,
    StepFailedEvent,
    SavepointCreatedEvent,
)
from .savepoint import Savepoint
from .serialization import serialize, deserialize, compute_delta, apply_delta

__all__ = [
    # State
    "WorkflowState",
    "StateMigration",
    # Events
    "EventType",
    "BaseEvent",
    "StepIntentionEvent",
    "StepCompletedEvent",
    "StepFailedEvent",
    "SavepointCreatedEvent",
    # Savepoint
    "Savepoint",
    # Serialization
    "serialize",
    "deserialize",
    "compute_delta",
    "apply_delta",
]

# Auth models are optional (require email-validator)
try:
    from .auth import (
        UserRole,
        UserBase,
        UserCreate,
        UserInDB,
        User,
        OrganizationBase,
        OrganizationCreate,
        Organization,
        OrganizationMemberBase,
        OrganizationMemberCreate,
        OrganizationMember,
        ApiKeyCreate,
        ApiKey,
        Token,
        TokenData,
    )
    __all__.extend([
        "UserRole",
        "UserBase",
        "UserCreate",
        "UserInDB",
        "User",
        "OrganizationBase",
        "OrganizationCreate",
        "Organization",
        "OrganizationMemberBase",
        "OrganizationMemberCreate",
        "OrganizationMember",
        "ApiKeyCreate",
        "ApiKey",
        "Token",
        "TokenData",
    ])
except ImportError:
    # email-validator not installed, auth models unavailable
    pass
