"""
Default handler recipes for context rot response.

These are simple, opinionated functions that developers can use directly
as on_health_warning callbacks, or copy and modify. The engine doesn't
require any of these — they're patterns, not framework code.

Usage:
    @workflow(WorkflowConfig(
        on_health_warning=distill_on_decline,
    ))
    def my_agent(query):
        ...
"""

import logging

logger = logging.getLogger(__name__)


def distill_on_decline(ctx, health) -> None:
    """
    Auto-trigger distillation when output trend is declining.

    Simple recipe: if the agent's outputs are getting shorter
    (possible context rot symptom), force a distill to compress
    accumulated reasoning before it gets worse.
    """
    if health.output_trend == "declining" and health.buffer_bytes > 0:
        logger.info(
            f"[recipe:distill_on_decline] Output declining "
            f"({health.output_decline_pct:.0%}), triggering distill"
        )
        ctx.request_distill()


def savepoint_on_drift(ctx, health) -> None:
    """
    Auto-create savepoint when multiple health signals degrade.

    When the recommendation is 'savepoint' or 'warning', create
    an epistemic savepoint to preserve the current reasoning state
    before it degrades further.
    """
    if health.recommendation in ("savepoint", "warning"):
        logger.info(
            f"[recipe:savepoint_on_drift] Health degraded "
            f"(recommendation={health.recommendation}), creating savepoint"
        )
        ctx.create_savepoint({
            "goal_summary": "Auto-savepoint: context health degraded",
            "hypotheses": [],
            "questions": [],
            "decisions": [
                f"Auto-savepoint triggered: output_trend={health.output_trend}, "
                f"retry_rate={health.retry_rate:.2f}, "
                f"budget_used={health.budget_used:.1%}"
            ],
            "next_step": "continue_with_degraded_context",
        })

        # Also distill if there's buffered reasoning
        if health.buffer_bytes > 0:
            ctx.request_distill()


def warn_on_budget(ctx, health) -> None:
    """
    Log warning when context budget is running low.

    Sets a workflow variable that the developer can check
    in their step logic to decide whether to wrap up.
    """
    if health.budget_used > 0.8:
        pct = health.budget_used * 100
        logger.warning(
            f"[recipe:warn_on_budget] Context budget at {pct:.0f}%"
        )
        ctx.set_variable("_context_budget_warning", True)
        ctx.set_variable("_context_budget_used_pct", round(pct, 1))
