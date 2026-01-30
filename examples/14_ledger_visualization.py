"""
Example 14: Ledger Visualization & Human-in-the-Loop Review

This example demonstrates how to:
1. Use the ReasoningLedger to track agent reasoning
2. Annotate steps with developer breadcrumbs
3. Ingest raw reasoning from LLM responses
4. View the ledger via API and web UI
5. Submit human reviews for reasoning steps

The ledger provides transparency into agent decision-making,
enabling human oversight of autonomous workflows.
"""

import time
from datetime import datetime
from contd.sdk import workflow, step
from contd.context import ReasoningLedger, ContextDigest


# Simulated LLM response with reasoning
def simulate_llm_response(prompt: str) -> dict:
    """Simulate an LLM response with extended thinking."""
    return {
        "reasoning": f"""
        Analyzing the request: "{prompt}"
        
        Step 1: Understanding the context
        - The user wants to process data
        - Need to validate inputs first
        
        Step 2: Evaluating options
        - Option A: Direct processing (faster, less safe)
        - Option B: Staged processing (slower, more reliable)
        
        Decision: Choosing Option B because reliability is critical
        for production workflows.
        """,
        "response": "I'll process this using the staged approach.",
        "confidence": 0.85
    }


@workflow(name="ledger_demo")
def ledger_demo_workflow(data: dict, config=None):
    """
    Workflow demonstrating ledger usage for human-in-the-loop review.
    
    Run this workflow, then:
    1. Open http://localhost:8000/ledger-viewer
    2. Enter the workflow ID
    3. Review the reasoning timeline
    4. Approve/reject reasoning steps
    """
    
    # Initialize the reasoning ledger
    ledger = ReasoningLedger()
    ledger.distill_every = 5  # Distill every 5 steps
    ledger.distill_threshold = 10000  # Or when buffer exceeds 10KB
    
    # Step 1: Data validation
    result = validate_data(data, ledger)
    
    # Step 2: Analysis with LLM
    analysis = analyze_with_llm(result, ledger)
    
    # Step 3: Decision making
    decision = make_decision(analysis, ledger)
    
    # Step 4: Execute action
    final_result = execute_action(decision, ledger)
    
    # Store ledger in workflow metadata for API access
    # In production, this is handled by ExecutionContext
    print("\n=== Ledger Summary ===")
    print(f"Total annotations: {len(ledger.annotations)}")
    print(f"Total digests: {len(ledger.digests)}")
    print(f"Context bytes: {ledger.total_context_bytes}")
    print(f"Undigested buffer: {ledger.raw_buffer_bytes} bytes")
    
    return {
        "result": final_result,
        "ledger_context": ledger.get_restore_context()
    }


@step(name="validate_data")
def validate_data(data: dict, ledger: ReasoningLedger) -> dict:
    """Validate input data with reasoning annotation."""
    
    # Developer annotation - always available
    ledger.annotate(
        step_number=1,
        step_name="validate_data",
        text="Validating input data structure and required fields"
    )
    
    # Simulate validation logic
    required_fields = ["id", "type", "payload"]
    missing = [f for f in required_fields if f not in data]
    
    if missing:
        ledger.annotate(
            step_number=1,
            step_name="validate_data",
            text=f"Validation failed: missing fields {missing}"
        )
        raise ValueError(f"Missing required fields: {missing}")
    
    ledger.annotate(
        step_number=1,
        step_name="validate_data",
        text="Validation passed - all required fields present"
    )
    
    # Record step signal (observable metrics)
    ledger.record_step_signal(
        step_number=1,
        step_name="validate_data",
        output_bytes=len(str(data)),
        duration_ms=50,
        was_retry=False
    )
    
    return {"validated": True, "data": data}


@step(name="analyze_with_llm")
def analyze_with_llm(input_data: dict, ledger: ReasoningLedger) -> dict:
    """Analyze data using LLM with reasoning capture."""
    
    ledger.annotate(
        step_number=2,
        step_name="analyze_with_llm",
        text="Sending data to LLM for analysis"
    )
    
    # Simulate LLM call
    llm_response = simulate_llm_response(
        f"Analyze this data: {input_data['data']}"
    )
    
    # Ingest raw reasoning from LLM (when available)
    # This captures the model's thinking process
    ledger.ingest(llm_response["reasoning"])
    
    ledger.annotate(
        step_number=2,
        step_name="analyze_with_llm",
        text=f"LLM analysis complete. Confidence: {llm_response['confidence']}"
    )
    
    ledger.record_step_signal(
        step_number=2,
        step_name="analyze_with_llm",
        output_bytes=len(llm_response["response"]),
        duration_ms=1500,  # LLM calls take longer
        was_retry=False
    )
    
    return {
        "analysis": llm_response["response"],
        "confidence": llm_response["confidence"],
        "raw_data": input_data
    }


@step(name="make_decision")
def make_decision(analysis: dict, ledger: ReasoningLedger) -> dict:
    """Make a decision based on analysis."""
    
    ledger.annotate(
        step_number=3,
        step_name="make_decision",
        text=f"Evaluating analysis with confidence {analysis['confidence']}"
    )
    
    # Decision logic
    if analysis["confidence"] >= 0.8:
        decision = "proceed"
        reason = "High confidence analysis supports proceeding"
    elif analysis["confidence"] >= 0.5:
        decision = "review"
        reason = "Medium confidence - flagging for human review"
    else:
        decision = "reject"
        reason = "Low confidence - rejecting to prevent errors"
    
    ledger.annotate(
        step_number=3,
        step_name="make_decision",
        text=f"Decision: {decision}. Reason: {reason}"
    )
    
    # Check if we should distill accumulated reasoning
    if ledger.should_distill():
        # In production, this would call a developer-provided distill function
        digest = ContextDigest(
            digest_id=f"digest-{datetime.utcnow().timestamp()}",
            step_number=3,
            timestamp=datetime.utcnow(),
            payload={
                "summary": "Validated data, analyzed with LLM, made decision",
                "key_decisions": [decision],
                "confidence_level": analysis["confidence"]
            },
            raw_chunk_count=len(ledger.raw_buffer),
            raw_byte_count=ledger.raw_buffer_bytes
        )
        ledger.accept_digest(digest)
        print("  [Distilled reasoning into digest]")
    
    ledger.record_step_signal(
        step_number=3,
        step_name="make_decision",
        output_bytes=len(decision),
        duration_ms=10,
        was_retry=False
    )
    
    return {
        "decision": decision,
        "reason": reason,
        "analysis": analysis
    }


@step(name="execute_action")
def execute_action(decision_data: dict, ledger: ReasoningLedger) -> dict:
    """Execute the decided action."""
    
    decision = decision_data["decision"]
    
    ledger.annotate(
        step_number=4,
        step_name="execute_action",
        text=f"Executing action for decision: {decision}"
    )
    
    if decision == "proceed":
        result = {"status": "completed", "action": "processed"}
    elif decision == "review":
        result = {"status": "pending_review", "action": "queued"}
    else:
        result = {"status": "rejected", "action": "none"}
    
    ledger.annotate(
        step_number=4,
        step_name="execute_action",
        text=f"Action result: {result['status']}"
    )
    
    ledger.record_step_signal(
        step_number=4,
        step_name="execute_action",
        output_bytes=len(str(result)),
        duration_ms=100,
        was_retry=False
    )
    
    return result


def demo_api_usage():
    """
    Demonstrate how to use the ledger API endpoints.
    
    After running a workflow, you can:
    """
    print("""
    === Ledger API Endpoints ===
    
    GET  /v1/workflows/{id}/ledger/summary
         Get high-level stats (steps, annotations, digests, pending reviews)
    
    GET  /v1/workflows/{id}/ledger/timeline
         Get chronological timeline of all reasoning entries
    
    GET  /v1/workflows/{id}/ledger/traces
         Get detailed reasoning traces per step
    
    GET  /v1/workflows/{id}/ledger/traces/{step}
         Get trace for a specific step
    
    POST /v1/workflows/{id}/ledger/traces/{step}/review
         Submit human review (approve/reject/needs_revision)
         Body: {"status": "approved", "feedback": "Looks good"}
    
    GET  /v1/workflows/{id}/ledger/reviews
         Get all reviews for a workflow
    
    GET  /v1/workflows/{id}/ledger/undigested
         Get raw undigested reasoning buffer
    
    === Web UI ===
    
    Open http://localhost:8000/ledger-viewer in your browser
    for an interactive visualization of the reasoning ledger.
    """)


if __name__ == "__main__":
    print("=== Ledger Visualization Demo ===\n")
    
    # Run the workflow
    result = ledger_demo_workflow(
        data={
            "id": "test-123",
            "type": "analysis",
            "payload": {"value": 42, "category": "important"}
        }
    )
    
    print(f"\nWorkflow result: {result['result']}")
    
    # Show API usage
    demo_api_usage()
