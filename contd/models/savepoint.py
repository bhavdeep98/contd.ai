from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any
from .state import WorkflowState


@dataclass
class Savepoint:
    """Rich savepoint beyond raw state"""

    savepoint_id: str
    workflow_id: str
    step_number: int
    timestamp: datetime

    # Core state
    state: WorkflowState

    # Epistemic context (for reasoning workflows)
    goal_summary: str
    current_hypotheses: List[str]
    open_questions: List[str]
    decision_log: List[Dict[str, Any]]
    next_step: str

    # Performance
    token_usage: int
    duration_ms: int
