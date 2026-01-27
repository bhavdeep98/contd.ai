from typing import TypedDict, NotRequired, List, Dict, Any, Tuple
from dataclasses import dataclass
import random
import time

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

class SavepointMetadata(TypedDict):
    """Metadata for rich savepoints"""
    goal_summary: str
    hypotheses: List[str]
    questions: List[str]
    decisions: List[Dict[str, Any]]
    next_step: str

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    retryable_exceptions: Tuple[type[Exception], ...] = (Exception,)
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        return (
            attempt < self.max_attempts 
            and isinstance(error, self.retryable_exceptions)
        )
    
    def backoff(self, attempt: int) -> float:
        """Exponential backoff with jitter"""
        delay = min(self.backoff_base ** attempt, self.backoff_max)
        return delay * (0.5 + random.random() * 0.5)  # ±50% jitter
