"""
Context health scoring from observable signals.

Detects symptoms of context rot without understanding the content.
Uses side effects: output size trends, retry rates, duration spikes.
No LLM calls. No embeddings. Just statistics the engine already has.
"""

from dataclasses import dataclass
from typing import List, Optional
import logging

from .ledger import StepSignal

logger = logging.getLogger(__name__)

# Minimum steps before health scoring is meaningful
MIN_STEPS_FOR_HEALTH = 3

# Thresholds
OUTPUT_DECLINE_THRESHOLD = 0.3  # 30% decline from rolling average
RETRY_RATE_WARNING = 0.2  # 20% of recent steps had retries
DURATION_SPIKE_THRESHOLD = 2.0  # 2x the rolling average


@dataclass
class HealthSignals:
    """Observable health signals computed from step metrics."""

    output_trend: str  # "stable", "declining", "increasing"
    output_decline_pct: float  # Negative = declining
    retry_rate: float  # Fraction of recent steps that retried
    duration_trend: str  # "stable", "spiking", "normal"
    duration_spike_factor: float  # Current vs rolling average
    budget_used: float  # Fraction of context budget used (0.0-1.0)
    steps_since_distill: int  # Steps since last distillation
    buffer_bytes: int  # Undigested reasoning bytes
    recommendation: str  # "ok", "distill", "savepoint", "warning"

    def to_dict(self) -> dict:
        return {
            "output_trend": self.output_trend,
            "output_decline_pct": round(self.output_decline_pct, 3),
            "retry_rate": round(self.retry_rate, 3),
            "duration_trend": self.duration_trend,
            "duration_spike_factor": round(self.duration_spike_factor, 2),
            "budget_used": round(self.budget_used, 3),
            "steps_since_distill": self.steps_since_distill,
            "buffer_bytes": self.buffer_bytes,
            "recommendation": self.recommendation,
        }


class ContextHealth:
    """
    Computes context health from observable step signals.

    No semantic understanding. Just trends:
    - Output getting shorter? Agent may be losing detail.
    - Retry rate climbing? Agent may be producing invalid output.
    - Duration spiking? Agent may be struggling with degraded context.
    - Buffer growing? Time to distill.
    """

    @staticmethod
    def compute(
        signals: List[StepSignal],
        buffer_bytes: int,
        total_context_bytes: int,
        context_budget: int,
        steps_since_distill: int,
        window: int = 5,
    ) -> HealthSignals:
        """
        Compute health from the last `window` steps of signals.

        Args:
            signals: Step execution signals
            buffer_bytes: Current undigested reasoning buffer size
            total_context_bytes: Total context accumulated
            context_budget: Budget limit in bytes (0 = unlimited)
            steps_since_distill: Steps since last distillation
            window: Rolling window size for trend detection
        """
        if len(signals) < MIN_STEPS_FOR_HEALTH:
            return HealthSignals(
                output_trend="unknown",
                output_decline_pct=0.0,
                retry_rate=0.0,
                duration_trend="unknown",
                duration_spike_factor=1.0,
                budget_used=0.0,
                steps_since_distill=steps_since_distill,
                buffer_bytes=buffer_bytes,
                recommendation="ok",
            )

        recent = signals[-window:]
        older = signals[-(window * 2) : -window] if len(signals) > window else signals[: len(signals) // 2]

        # Output trend
        output_trend, output_decline = _compute_output_trend(recent, older)

        # Retry rate
        retry_rate = sum(1 for s in recent if s.was_retry) / len(recent)

        # Duration trend
        duration_trend, duration_factor = _compute_duration_trend(recent, older)

        # Budget usage
        budget_used = (total_context_bytes / context_budget) if context_budget > 0 else 0.0

        # Recommendation
        recommendation = _compute_recommendation(
            output_trend, output_decline, retry_rate, duration_factor,
            budget_used, buffer_bytes, steps_since_distill,
        )

        return HealthSignals(
            output_trend=output_trend,
            output_decline_pct=output_decline,
            retry_rate=retry_rate,
            duration_trend=duration_trend,
            duration_spike_factor=duration_factor,
            budget_used=budget_used,
            steps_since_distill=steps_since_distill,
            buffer_bytes=buffer_bytes,
            recommendation=recommendation,
        )


def _compute_output_trend(
    recent: List[StepSignal], older: List[StepSignal]
) -> tuple:
    """Compare recent output sizes to older output sizes."""
    if not older:
        return "unknown", 0.0

    recent_avg = sum(s.output_bytes for s in recent) / len(recent)
    older_avg = sum(s.output_bytes for s in older) / len(older)

    if older_avg == 0:
        return "stable", 0.0

    change_pct = (recent_avg - older_avg) / older_avg

    if change_pct < -OUTPUT_DECLINE_THRESHOLD:
        return "declining", change_pct
    elif change_pct > OUTPUT_DECLINE_THRESHOLD:
        return "increasing", change_pct
    else:
        return "stable", change_pct


def _compute_duration_trend(
    recent: List[StepSignal], older: List[StepSignal]
) -> tuple:
    """Detect duration spikes (agent struggling)."""
    if not older:
        return "unknown", 1.0

    recent_avg = sum(s.duration_ms for s in recent) / len(recent)
    older_avg = sum(s.duration_ms for s in older) / len(older)

    if older_avg == 0:
        return "normal", 1.0

    factor = recent_avg / older_avg

    if factor > DURATION_SPIKE_THRESHOLD:
        return "spiking", factor
    else:
        return "normal", factor


def _compute_recommendation(
    output_trend: str,
    output_decline: float,
    retry_rate: float,
    duration_factor: float,
    budget_used: float,
    buffer_bytes: int,
    steps_since_distill: int,
) -> str:
    """
    Compute a recommendation based on health signals.

    Priority: warning > savepoint > distill > ok
    """
    # Hard warnings
    if budget_used > 0.9:
        return "warning"
    if retry_rate > RETRY_RATE_WARNING and output_trend == "declining":
        return "warning"

    # Savepoint recommended (multiple bad signals)
    bad_signals = 0
    if output_trend == "declining":
        bad_signals += 1
    if retry_rate > RETRY_RATE_WARNING:
        bad_signals += 1
    if duration_factor > DURATION_SPIKE_THRESHOLD:
        bad_signals += 1
    if bad_signals >= 2:
        return "savepoint"

    # Distill recommended (buffer growing)
    if buffer_bytes > 0 and steps_since_distill > 3:
        return "distill"
    if budget_used > 0.7:
        return "distill"

    return "ok"
