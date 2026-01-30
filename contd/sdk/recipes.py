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
    from contd.core.context_preservation import ContextHealth

logger = logging.getLogger(__name__)


def distill_on_decline(ctx: "ExecutionContext", health: "ContextHealth"):
    """
    Auto-distill when output trend is declining.
    
    Declining output often indicates the agent is losing detail
    as context degrades. Distilling preserves the reasoning.
    
    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            on_health_check=distill_on_decline,
        ))
    """
    if health.output_trend == "declining" and health.reasoning_buffer_size > 0:
        logger.info("Output declining, triggering distillation")
        ctx.request_distill()


def savepoint_on_drift(ctx: "ExecutionContext", health: "ContextHealth"):
    """
    Auto-savepoint when retry rate spikes.
    
    High retry rate suggests the agent is struggling.
    Creating a savepoint preserves the current reasoning state
    before things get worse.
    
    Usage:
        @workflow(WorkflowConfig(
            on_health_check=savepoint_on_drift,
        ))
    """
    if health.retry_rate > 0.2:
        logger.info(f"Retry rate {health.retry_rate:.1%}, creating savepoint")
        ctx.create_savepoint({
            "goal_summary": "Auto-savepoint due to high retry rate",
            "hypotheses": [],
            "questions": ["Why is retry rate elevated?"],
            "decisions": [],
            "next_step": "Investigate failures",
        })


def warn_on_budget(ctx: "ExecutionContext", health: "ContextHealth"):
    """
    Log warning at 80% context budget.
    
    Gives the developer visibility into budget consumption
    without taking automatic action.
    
    Usage:
        @workflow(WorkflowConfig(
            context_budget=50_000,
            on_health_check=warn_on_budget,
        ))
    """
    if health.budget_used > 0.8:
        logger.warning(
            f"Context budget at {health.budget_used:.0%} "
            f"({health.total_output_bytes} / {health.budget_limit} bytes)"
        )


def distill_and_annotate_on_budget(ctx: "ExecutionContext", health: "ContextHealth"):
    """
    Distill and annotate when approaching budget limit.
    
    More aggressive than warn_on_budget - actually takes action
    to compress context before hitting the limit.
    
    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            context_budget=50_000,
            on_health_check=distill_and_annotate_on_budget,
        ))
    """
    if health.budget_used > 0.9:
        ctx.annotate("Approaching context budget limit, wrapping up")
        ctx.set_variable("should_conclude", True)
        if health.reasoning_buffer_size > 0:
            ctx.request_distill()
    elif health.budget_used > 0.7:
        if health.reasoning_buffer_size > 0:
            ctx.request_distill()


def combined_health_handler(ctx: "ExecutionContext", health: "ContextHealth"):
    """
    Combined handler that applies multiple strategies.
    
    - Distill on declining output
    - Savepoint on high retry rate  
    - Warn on budget
    
    Usage:
        @workflow(WorkflowConfig(
            distill=my_distill_fn,
            context_budget=50_000,
            on_health_check=combined_health_handler,
        ))
    """
    # Distill on decline
    if health.output_trend == "declining" and health.reasoning_buffer_size > 0:
        logger.info("Output declining, triggering distillation")
        ctx.request_distill()
    
    # Savepoint on drift
    if health.retry_rate > 0.2:
        logger.info(f"Retry rate {health.retry_rate:.1%}, creating savepoint")
        ctx.create_savepoint({
            "goal_summary": "Auto-savepoint due to high retry rate",
        })
    
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


def structured_distill_prompt(raw_chunks: list[str], previous_digest: dict | None) -> str:
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
