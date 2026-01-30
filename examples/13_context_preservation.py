"""
Example: Context Preservation for LLM Agent Workflows

This example demonstrates how to use contd.ai's context preservation
features to combat context rot in long-running LLM agent workflows.

Key features demonstrated:
1. ctx.annotate() - Lightweight reasoning breadcrumbs
2. ctx.ingest() - Capture reasoning tokens when available
3. Distillation - Periodic compression of reasoning context
4. ctx.context_health() - Monitor for context degradation
5. Restore with context - Resume with reasoning, not just data

The engine is plumbing. You bring the intelligence.
"""

import json
from typing import Optional

import contd
from contd import workflow, step, WorkflowConfig, StepConfig, ExecutionContext


# =============================================================================
# Your distill function - you decide how to compress reasoning
# =============================================================================

def my_distill_fn(raw_chunks: list[str], previous_digest: dict | None) -> dict:
    """
    Developer-provided distillation function.
    
    Options:
    A) Use an LLM to summarize (shown here as pseudocode)
    B) Simple heuristic (keep last N chunks)
    C) Domain-specific extraction
    
    The engine doesn't care which you choose.
    """
    # Option A: LLM-based summarization (pseudocode)
    # In production, you'd call your LLM here:
    #
    # response = anthropic.messages.create(
    #     model="claude-haiku-4-20250414",  # Cheap model for distillation
    #     messages=[{
    #         "role": "user",
    #         "content": f'''Distill this reasoning into structured context:
    #         
    #         Previous context: {json.dumps(previous_digest)}
    #         
    #         New reasoning:
    #         {chr(10).join(raw_chunks)}
    #         
    #         Return JSON with: goal, hypotheses, decisions, open_questions'''
    #     }]
    # )
    # return json.loads(response.content)
    
    # Option B: Simple heuristic (for this example)
    return {
        "goal": previous_digest.get("goal", "Unknown") if previous_digest else "Research task",
        "recent_reasoning": raw_chunks[-3:],  # Keep last 3 chunks
        "total_chunks_processed": (
            (previous_digest.get("total_chunks_processed", 0) if previous_digest else 0)
            + len(raw_chunks)
        ),
        "key_decisions": (
            (previous_digest.get("key_decisions", []) if previous_digest else [])
            + [f"Processed {len(raw_chunks)} reasoning chunks"]
        )[-5:],  # Keep last 5 decisions
    }


# =============================================================================
# Health check handler - you decide what to do about degradation
# =============================================================================

def my_health_handler(ctx: ExecutionContext, health):
    """
    Called after each step with health signals.
    
    The engine doesn't interpret these - it just measures.
    You decide what constitutes a "warning" and what to do.
    """
    # Log health for observability
    print(f"  Health: output_trend={health.output_trend}, "
          f"retry_rate={health.retry_rate:.1%}, "
          f"budget_used={health.budget_used:.0%}")
    
    # React to declining output (agent losing detail)
    if health.output_trend == "declining":
        print("  ⚠️  Output declining - triggering distillation")
        ctx.request_distill()
    
    # React to high retry rate (agent struggling)
    if health.retry_rate > 0.2:
        print("  ⚠️  High retry rate - creating savepoint")
        ctx.create_savepoint({
            "goal_summary": "Auto-savepoint due to degradation",
            "hypotheses": [],
            "questions": ["Why is the agent struggling?"],
        })
    
    # React to budget exhaustion
    if health.budget_used > 0.9:
        print("  ⚠️  Near budget limit - signaling to wrap up")
        ctx.annotate("Approaching context budget, should conclude soon")
        ctx.set_variable("should_conclude", True)


# =============================================================================
# The workflow - with context preservation enabled
# =============================================================================

@workflow(WorkflowConfig(
    # Context preservation configuration
    distill=my_distill_fn,           # Your compression function
    distill_every=5,                  # Distill every 5 steps
    distill_threshold=10_000,         # Or when buffer exceeds 10k chars
    context_budget=50_000,            # Warn at 50k bytes total output
    on_health_check=my_health_handler,  # Your health handler
    
    # Standard workflow config
    tags={"type": "research_agent"},
))
def research_agent(query: str):
    """
    A research agent that preserves its reasoning context.
    
    On crash recovery, the agent resumes with:
    - Its data state (variables, step outputs)
    - Its reasoning context (digest, annotations, undigested chunks)
    """
    ctx = ExecutionContext.current()
    
    # Check if we're resuming
    restored = ctx.get_restored_context()
    if restored:
        print(f"\n📚 Resumed with context:")
        print(f"   - {len(restored.annotations)} annotations")
        print(f"   - {len(restored.digest_history)} digests")
        print(f"   - {len(restored.undigested)} undigested chunks")
        if restored.digest:
            print(f"   - Latest digest: {json.dumps(restored.digest, indent=2)}")
        
        # Feed the digest back to your LLM on resume
        # This is where the agent picks up its reasoning thread
        # context_for_llm = restored.digest
    
    # Run research steps
    for i in range(10):
        result = research_step(query, i)
        
        # Check if we should wrap up (set by health handler)
        if ctx.get_state().variables.get("should_conclude"):
            print("\n🏁 Concluding due to budget limit")
            break
    
    return synthesize_findings()


@step(StepConfig(checkpoint=True))
def research_step(query: str, iteration: int) -> dict:
    """
    A single research step that demonstrates context preservation.
    """
    ctx = ExecutionContext.current()
    
    print(f"\n📖 Research step {iteration}")
    
    # Simulate LLM call with reasoning
    # In production, this would be your actual LLM call
    reasoning = f"""
    Iteration {iteration}: Analyzing query '{query}'
    
    Considering approach: {'deep analysis' if iteration < 5 else 'synthesis'}
    Key insight: Found relevant information about {query}
    Decision: {'Continue gathering' if iteration < 7 else 'Start synthesizing'}
    """
    
    result = f"Finding {iteration}: Relevant data about {query}"
    
    # === Context Preservation ===
    
    # 1. Annotate: One-line breadcrumb (always available)
    ctx.annotate(f"Step {iteration}: {'Gathering' if iteration < 7 else 'Synthesizing'}")
    
    # 2. Ingest: Capture reasoning tokens (when available)
    # In production, you'd check if your LLM exposes reasoning:
    #   if response.thinking:
    #       ctx.ingest(response.thinking)
    ctx.ingest(reasoning)
    
    # 3. Health check: Query current health (optional)
    health = ctx.context_health()
    if health.reasoning_buffer_chars > 5000:
        print(f"  Buffer getting large ({health.reasoning_buffer_chars} chars)")
    
    return {
        f"finding_{iteration}": result,
        "iteration": iteration,
    }


@step()
def synthesize_findings() -> dict:
    """Synthesize all findings into a final result."""
    ctx = ExecutionContext.current()
    
    print("\n🔬 Synthesizing findings")
    
    # Access the current digest for synthesis
    # This contains the compressed reasoning from all previous steps
    health = ctx.context_health()
    
    ctx.annotate("Final synthesis complete")
    
    return {
        "synthesis": "Research complete",
        "total_steps": ctx.get_state().step_number,
        "digests_created": health.digests_created,
    }


# =============================================================================
# Demo: Show the context preservation in action
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Context Preservation Demo")
    print("=" * 60)
    
    print("""
This demo shows how contd.ai preserves reasoning context:

1. ctx.annotate("...") - Lightweight breadcrumbs
2. ctx.ingest(reasoning) - Capture reasoning tokens  
3. Automatic distillation - Compress accumulated reasoning
4. ctx.context_health() - Monitor for degradation
5. Restore with context - Resume with reasoning intact

The engine is plumbing. You bring the intelligence.
""")
    
    # Note: This example requires the full contd.ai infrastructure
    # (Postgres, S3, etc.) to actually run. It's meant to demonstrate
    # the API and patterns.
    
    print("\nTo run this example with real infrastructure:")
    print("  1. Set up Postgres and S3 (see docker/)")
    print("  2. Configure CONTD_POSTGRES_* and CONTD_S3_* env vars")
    print("  3. Run: python examples/13_context_preservation.py")
    
    print("\n" + "=" * 60)
    print("API Summary")
    print("=" * 60)
    
    print("""
# Workflow configuration
@workflow(WorkflowConfig(
    distill=my_distill_fn,      # Your compression function
    distill_every=5,            # Distill every N steps
    distill_threshold=10_000,   # Or when buffer exceeds N chars
    context_budget=50_000,      # Warn at N bytes total output
    on_health_check=handler,    # Your health callback
))

# Inside steps
ctx.annotate("Chose X because Y")           # Breadcrumb
ctx.ingest(response.thinking)               # Capture reasoning
health = ctx.context_health()               # Check health
ctx.request_distill()                       # Force distillation

# On resume
restored = ctx.get_restored_context()
if restored:
    # Feed restored.digest back to your LLM
    pass
""")
