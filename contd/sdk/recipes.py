"""
Context preservation recipes.

These are 10-line functions, not framework code.
The engine stays dumb. The recipes show what "smart" looks like.

Copy and modify these for your use case.
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from contd.sdk.context import ExecutionContext
    from contd.context.health import HealthSignals

logger = logging.getLogger(__name__)


def distill_on_decline(ctx: "ExecutionContext", health: "HealthSignals"):
    """
    Auto-distill when output trend is declining.

    Declining output often indicates the agent is losing detail
    as context degrades. Distilling preserves the reasoning.

    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            on_health_warning=distill_on_decline,
        ))
    """
    if health.output_trend == "declining" and health.buffer_bytes > 0:
        logger.info(
            f"Output declining ({health.output_decline_pct:.0%}), triggering distillation"
        )
        ctx.request_distill()


def savepoint_on_drift(ctx: "ExecutionContext", health: "HealthSignals"):
    """
    Auto-savepoint when retry rate spikes or multiple signals degrade.

    High retry rate suggests the agent is struggling.
    Creating a savepoint preserves the current reasoning state
    before things get worse.

    Usage:
        @workflow(WorkflowConfig(
            on_health_warning=savepoint_on_drift,
        ))
    """
    if health.recommendation in ("savepoint", "warning") or health.retry_rate > 0.2:
        logger.info(
            f"Health degraded (recommendation={health.recommendation}, "
            f"retry_rate={health.retry_rate:.1%}), creating savepoint"
        )
        ctx.create_savepoint(
            {
                "goal_summary": "Auto-savepoint due to health degradation",
                "hypotheses": [],
                "questions": ["Why is health degrading?"],
                "decisions": [
                    f"output_trend={health.output_trend}, "
                    f"retry_rate={health.retry_rate:.2f}, "
                    f"budget_used={health.budget_used:.1%}"
                ],
                "next_step": "Investigate and continue",
            }
        )
        # Also distill if there's buffered reasoning
        if health.buffer_bytes > 0:
            ctx.request_distill()


def warn_on_budget(ctx: "ExecutionContext", health: "HealthSignals"):
    """
    Log warning at 80% context budget.

    Gives the developer visibility into budget consumption
    without taking automatic action.

    Usage:
        @workflow(WorkflowConfig(
            context_budget=50_000,
            on_health_warning=warn_on_budget,
        ))
    """
    if health.budget_used > 0.8:
        pct = health.budget_used * 100
        logger.warning(f"Context budget at {pct:.0f}%")
        ctx.set_variable("_context_budget_warning", True)
        ctx.set_variable("_context_budget_used_pct", round(pct, 1))


def distill_and_annotate_on_budget(ctx: "ExecutionContext", health: "HealthSignals"):
    """
    Distill and annotate when approaching budget limit.

    More aggressive than warn_on_budget - actually takes action
    to compress context before hitting the limit.

    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            context_budget=50_000,
            on_health_warning=distill_and_annotate_on_budget,
        ))
    """
    if health.budget_used > 0.9:
        ctx.annotate("Approaching context budget limit, wrapping up")
        ctx.set_variable("should_conclude", True)
        if health.buffer_bytes > 0:
            ctx.request_distill()
    elif health.budget_used > 0.7:
        if health.buffer_bytes > 0:
            ctx.request_distill()


def combined_health_handler(ctx: "ExecutionContext", health: "HealthSignals"):
    """
    Combined handler that applies multiple strategies.

    - Distill on declining output
    - Savepoint on high retry rate
    - Warn on budget

    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            context_budget=50_000,
            on_health_warning=combined_health_handler,
        ))
    """
    # Distill on decline
    if health.output_trend == "declining" and health.buffer_bytes > 0:
        logger.info("Output declining, triggering distillation")
        ctx.request_distill()

    # Savepoint on drift
    if health.retry_rate > 0.2:
        logger.info(f"Retry rate {health.retry_rate:.1%}, creating savepoint")
        ctx.create_savepoint(
            {
                "goal_summary": "Auto-savepoint due to high retry rate",
            }
        )

    # Warn on budget
    if health.budget_used > 0.8:
        logger.warning(f"Context budget at {health.budget_used:.0%}")


# =============================================================================
# Example distill functions
# =============================================================================


def simple_distill(raw_chunks: list[str], previous_digest: dict | None) -> dict:
    """
    Simple distill that just keeps the last N chunks.

    No LLM call, cheap, lossy. Good for testing or when
    you don't need sophisticated summarization.
    """
    return {
        "raw_recent": raw_chunks[-3:],
        "previous": previous_digest,
        "total_chunks_seen": (
            (previous_digest.get("total_chunks_seen", 0) if previous_digest else 0)
            + len(raw_chunks)
        ),
    }


def structured_distill_prompt(
    raw_chunks: list[str], previous_digest: dict | None
) -> str:
    """
    Returns a prompt for LLM-based distillation.

    Use this with your LLM client:

        def my_distill_fn(chunks, prev):
            prompt = structured_distill_prompt(chunks, prev)
            response = my_llm.complete(prompt)
            return json.loads(response)
    """
    return f"""Distill this reasoning into structured context:

Previous context: {previous_digest or "None"}

New reasoning:
{chr(10).join(raw_chunks)}

Return JSON with:
- goal: Current goal being pursued
- hypotheses: List of working hypotheses
- decisions: List of decisions made with rationale
- open_questions: Unresolved questions
- key_findings: Important discoveries

Be concise. Preserve critical reasoning, discard noise."""


def llm_distill(llm_fn):
    """
    Wrap an LLM call function into a distill function.

    Usage:
        def call_llm(prompt):
            return my_client.complete(prompt)

        @workflow(WorkflowConfig(
            distill=llm_distill(call_llm),
        ))
        def my_agent(query):
            ...
    """
    import json

    def distill(chunks: list[str], previous: dict | None) -> dict:
        prompt = structured_distill_prompt(chunks, previous)
        response = llm_fn(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_failed": True}

    return distill
