"""
Example 09: Webhook Integration

Workflow that integrates with external services via webhooks.
Demonstrates async callbacks and external event handling.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
import time
import uuid


@step()
def initiate_external_process(request: dict) -> dict:
    """Start an external process that will callback via webhook."""
    print(f"Initiating external process: {request['type']}...")
    
    # Generate callback ID for tracking
    callback_id = str(uuid.uuid4())
    
    # In production: call external API with callback URL
    # POST https://external-service.com/process
    # {
    #   "data": request["data"],
    #   "callback_url": f"https://our-api.com/webhooks/{callback_id}"
    # }
    
    return {
        "callback_id": callback_id,
        "external_request_id": f"ext-{uuid.uuid4().hex[:8]}",
        "status": "pending",
        "initiated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step(StepConfig(savepoint=True))
def wait_for_webhook(callback_id: str, timeout_seconds: int = 120) -> dict:
    """
    Wait for webhook callback from external service.
    
    Creates savepoint while waiting so workflow state
    is preserved if the process restarts.
    """
    ctx = ExecutionContext.current()
    
    print(f"Waiting for webhook callback: {callback_id}...")
    
    # Create savepoint
    ctx.create_savepoint({
        "goal_summary": f"Waiting for external callback {callback_id}",
        "hypotheses": ["External service will respond within timeout"],
        "questions": ["Will the external process succeed?"],
        "decisions": [],
        "next_step": "process_webhook_response"
    })
    
    # Simulate waiting for webhook
    # In production: poll database for webhook receipt
    start = time.time()
    while time.time() - start < timeout_seconds:
        # Check if webhook received (simulated)
        # In production: query webhook_receipts table
        time.sleep(2)
        
        # Simulate webhook arrival after 5 seconds
        if time.time() - start > 5:
            return {
                "callback_id": callback_id,
                "received": True,
                "payload": {
                    "status": "completed",
                    "result": {"processed": True, "output": "External result data"},
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
    
    return {
        "callback_id": callback_id,
        "received": False,
        "error": "Timeout waiting for webhook"
    }


@step()
def process_webhook_response(webhook_data: dict) -> dict:
    """Process the webhook response."""
    print(f"Processing webhook response...")
    
    if not webhook_data.get("received"):
        return {
            "success": False,
            "error": webhook_data.get("error", "Unknown error")
        }
    
    payload = webhook_data["payload"]
    
    return {
        "success": True,
        "external_status": payload["status"],
        "result": payload["result"],
        "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step()
def send_acknowledgment(callback_id: str, result: dict) -> dict:
    """Send acknowledgment back to external service."""
    print(f"Sending acknowledgment for {callback_id}...")
    
    # In production: POST to external service
    return {
        "acknowledged": True,
        "callback_id": callback_id,
        "ack_sent_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step()
def update_internal_state(result: dict) -> dict:
    """Update internal systems based on webhook result."""
    print("Updating internal state...")
    
    return {
        "internal_updated": True,
        "updates": [
            {"system": "database", "status": "updated"},
            {"system": "cache", "status": "invalidated"},
            {"system": "search_index", "status": "queued"}
        ]
    }


@workflow()
def webhook_integration_workflow(request: dict) -> dict:
    """
    Workflow with external webhook integration:
    1. Initiate external process
    2. Wait for webhook callback
    3. Process webhook response
    4. Send acknowledgment
    5. Update internal state
    
    The workflow creates savepoints while waiting for
    webhooks, ensuring it can resume if interrupted.
    """
    # Initiate external process
    initiated = initiate_external_process(request)
    
    # Wait for webhook
    webhook_data = wait_for_webhook(
        initiated["callback_id"],
        timeout_seconds=60
    )
    
    # Process response
    processed = process_webhook_response(webhook_data)
    
    if not processed["success"]:
        return {
            "status": "failed",
            "error": processed.get("error"),
            "callback_id": initiated["callback_id"]
        }
    
    # Send acknowledgment
    ack = send_acknowledgment(initiated["callback_id"], processed)
    
    # Update internal state
    updated = update_internal_state(processed)
    
    return {
        "status": "completed",
        "callback_id": initiated["callback_id"],
        "external_request_id": initiated["external_request_id"],
        "result": processed["result"],
        "acknowledged": ack["acknowledged"],
        "internal_updates": updated["updates"]
    }


if __name__ == "__main__":
    request = {
        "type": "payment_verification",
        "data": {
            "transaction_id": "TXN-12345",
            "amount": 99.99,
            "currency": "USD"
        }
    }
    
    result = webhook_integration_workflow(request)
    print(f"\nWebhook Integration Result:")
    print(f"  Status: {result['status']}")
    print(f"  Callback ID: {result['callback_id']}")
    if result['status'] == 'completed':
        print(f"  Result: {result['result']}")
