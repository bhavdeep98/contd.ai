"""
Context preservation for LLM agent workflows.

Provides:
- Reasoning buffer management (ingest/distill cycle)
- Health signal tracking (output size, duration, retry trends)
- Context reconstruction on restore

The engine is plumbing. The developer brings intelligence.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)


@dataclass
class ContextHealth:
    """
    Health signals computed from step execution metrics.
    
    The engine doesn't interpret these - it just measures.
    The developer decides what constitutes a "warning".
    """
    # Output trends
    output_sizes: List[int] = field(default_factory=list)
    output_trend: str = "stable"  # "stable", "declining", "increasing"
    
    # Duration trends
    step_durations: List[int] = field(default_factory=list)  # ms
    duration_trend: str = "stable"
    
    # Retry signals
    retry_count: int = 0
    retry_rate: float = 0.0  # retries / total steps
    
    # Context budget
    total_output_bytes: int = 0
    budget_limit: Optional[int] = None
    budget_used: float = 0.0  # 0.0 - 1.0
    
    # Buffer state
    reasoning_buffer_size: int = 0
    reasoning_buffer_chars: int = 0
    
    # Distillation state
    digests_created: int = 0
    last_digest_step: Optional[int] = None
    steps_since_digest: int = 0
    
    # Computed recommendation (not an opinion, just a signal)
    recommendation: Optional[str] = None  # "distill", "savepoint", None
    
    def to_dict(self) -> dict:
        return {
            "output_trend": self.output_trend,
            "duration_trend": self.duration_trend,
            "retry_rate": self.retry_rate,
            "budget_used": self.budget_used,
            "reasoning_buffer_size": self.reasoning_buffer_size,
            "steps_since_digest": self.steps_since_digest,
            "recommendation": self.recommendation,
        }


@dataclass
class ReasoningBuffer:
    """
    Accumulates raw reasoning chunks between distillations.
    """
    chunks: List[str] = field(default_factory=list)
    total_chars: int = 0
    
    def add(self, chunk: str):
        self.chunks.append(chunk)
        self.total_chars += len(chunk)
    
    def clear(self) -> List[str]:
        """Clear buffer and return chunks."""
        chunks = self.chunks
        self.chunks = []
        self.total_chars = 0
        return chunks
    
    def __len__(self):
        return len(self.chunks)


@dataclass 
class RestoredContext:
    """
    Context returned alongside state on restore.
    
    The engine doesn't reconstruct a context window.
    It hands the developer the raw materials.
    """
    # Latest distilled context (if any)
    digest: Optional[Dict[str, Any]] = None
    
    # Raw chunks since last distill
    undigested: List[str] = field(default_factory=list)
    
    # Step-associated annotations
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Full digest history for audit trail
    digest_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Savepoint chain (epistemic metadata from savepoints)
    savepoints: List[Dict[str, Any]] = field(default_factory=list)
    
    # Execution stats
    steps_completed: int = 0
    total_output_bytes: int = 0
    step_durations: List[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "digest": self.digest,
            "undigested": self.undigested,
            "annotations": self.annotations,
            "digest_history": self.digest_history,
            "savepoints": self.savepoints,
            "steps_completed": self.steps_completed,
            "total_output_bytes": self.total_output_bytes,
            "step_durations": self.step_durations,
        }


class HealthTracker:
    """
    Tracks health signals from step execution.
    
    Computes trends without interpreting them.
    """
    
    # Window size for trend calculation
    TREND_WINDOW = 10
    
    def __init__(self, context_budget: Optional[int] = None):
        self.output_sizes: List[int] = []
        self.step_durations: List[int] = []
        self.retry_count: int = 0
        self.total_steps: int = 0
        self.total_output_bytes: int = 0
        self.context_budget = context_budget
        
    def record_step(self, output_size: int, duration_ms: int, was_retry: bool = False):
        """Record metrics from a completed step."""
        self.output_sizes.append(output_size)
        self.step_durations.append(duration_ms)
        self.total_output_bytes += output_size
        self.total_steps += 1
        if was_retry:
            self.retry_count += 1
    
    def compute_health(
        self, 
        buffer: ReasoningBuffer,
        digests_created: int,
        last_digest_step: Optional[int],
        current_step: int,
    ) -> ContextHealth:
        """Compute current health signals."""
        health = ContextHealth(
            output_sizes=self.output_sizes[-self.TREND_WINDOW:],
            step_durations=self.step_durations[-self.TREND_WINDOW:],
            retry_count=self.retry_count,
            retry_rate=self.retry_count / max(self.total_steps, 1),
            total_output_bytes=self.total_output_bytes,
            budget_limit=self.context_budget,
            reasoning_buffer_size=len(buffer),
            reasoning_buffer_chars=buffer.total_chars,
            digests_created=digests_created,
            last_digest_step=last_digest_step,
            steps_since_digest=(
                current_step - last_digest_step 
                if last_digest_step is not None 
                else current_step
            ),
        )
        
        # Compute trends
        health.output_trend = self._compute_trend(self.output_sizes)
        health.duration_trend = self._compute_trend(self.step_durations)
        
        # Compute budget usage
        if self.context_budget:
            health.budget_used = self.total_output_bytes / self.context_budget
        
        # Compute recommendation (signal, not opinion)
        health.recommendation = self._compute_recommendation(health)
        
        return health
    
    def _compute_trend(self, values: List[int]) -> str:
        """Compute trend from recent values."""
        if len(values) < 3:
            return "stable"
        
        recent = values[-self.TREND_WINDOW:]
        if len(recent) < 3:
            return "stable"
        
        # Simple linear regression slope
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n
        
        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Normalize slope by mean to get relative change
        if y_mean == 0:
            return "stable"
        
        relative_slope = slope / y_mean
        
        if relative_slope < -0.1:
            return "declining"
        elif relative_slope > 0.1:
            return "increasing"
        return "stable"
    
    def _compute_recommendation(self, health: ContextHealth) -> Optional[str]:
        """
        Compute recommendation signal.
        
        This is NOT the engine making decisions.
        It's surfacing signals the developer can act on.
        """
        # High buffer = suggest distill
        if health.reasoning_buffer_chars > 5000:
            return "distill"
        
        # Declining output + high retry = suggest savepoint
        if health.output_trend == "declining" and health.retry_rate > 0.2:
            return "savepoint"
        
        # Near budget limit = suggest distill
        if health.budget_used > 0.8:
            return "distill"
        
        return None


def execute_distill(
    distill_fn: Callable[[List[str], Optional[dict]], dict],
    chunks: List[str],
    previous_digest: Optional[dict],
) -> dict:
    """
    Execute developer's distill function with error handling.
    
    On failure, returns a failed digest containing the raw chunks.
    The engine doesn't lose data, doesn't block execution.
    """
    try:
        result = distill_fn(chunks, previous_digest)
        return result
    except Exception as e:
        logger.warning(f"Distill function failed: {e}")
        return {
            "_distill_failed": True,
            "raw_chunks": chunks,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
