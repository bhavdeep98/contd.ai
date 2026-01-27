"""
Example 07: Multi-Step Approval Workflow

Human-in-the-loop workflow with approval gates.
Demonstrates waiting for external signals.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
import time


@step()
def submit_request(request: dict) -> dict:
    """Submit a request for approval."""
    print(f"Submitting request: {request['title']}")
    
    request_id = f"REQ-{int(time.time())}"
    
    return {
        "request_id": request_id,
        "title": request["title"],
        "amount": request["amount"],
        "requester": request["requester"],
        "status": "pending",
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step()
def determine_approvers(request: dict) -> dict:
    """Determine required approvers based on request."""
    print(f"Determining approvers for ${request['amount']}...")
    
    approvers = []
    
    # Approval rules based on amount
    if request["amount"] < 1000:
        approvers = ["manager"]
    elif request["amount"] < 10000:
        approvers = ["manager", "director"]
    else:
        approvers = ["manager", "director", "vp"]
    
    return {
        "approvers": approvers,
        "approval_chain": [{"role": a, "status": "pending"} for a in approvers]
    }


@step()
def notify_approver(approver: str, request: dict) -> dict:
    """Send notification to approver."""
    print(f"Notifying {approver} about request {request['request_id']}...")
    
    # Simulate sending email/Slack notification
    return {
        "notified": approver,
        "notification_sent_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@step(StepConfig(savepoint=True))
def wait_for_approval(approver: str, request: dict, timeout_seconds: int = 60) -> dict:
    """
    Wait for approval from an approver.
    
    In production, this would poll a database or wait for
    a webhook callback. For demo, we simulate approval.
    """
    ctx = ExecutionContext.current()
    
    print(f"Waiting for {approver} to approve request {request['request_id']}...")
    
    # Create savepoint while waiting
    ctx.create_savepoint({
        "goal_summary": f"Waiting for {approver} approval",
        "hypotheses": ["Approver will respond within timeout"],
        "questions": [f"Will {approver} approve?"],
        "decisions": [],
        "next_step": "process_approval_response"
    })
    
    # Simulate waiting (in production: poll database)
    start = time.time()
    while time.time() - start < timeout_seconds:
        # Check for approval (simulated)
        # In production: query database for approval status
        time.sleep(2)
        
        # Simulate approval after 5 seconds
        if time.time() - start > 5:
            return {
                "approver": approver,
                "decision": "approved",
                "decided_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "comments": "Looks good!"
            }
    
    return {
        "approver": approver,
        "decision": "timeout",
        "decided_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comments": "No response within timeout"
    }


@step()
def process_approval_result(request: dict, approvals: list) -> dict:
    """Process the final approval result."""
    print("Processing approval results...")
    
    all_approved = all(a["decision"] == "approved" for a in approvals)
    
    if all_approved:
        status = "approved"
        message = "Request approved by all approvers"
    else:
        status = "rejected"
        rejections = [a for a in approvals if a["decision"] != "approved"]
        message = f"Request rejected by: {[r['approver'] for r in rejections]}"
    
    return {
        "request_id": request["request_id"],
        "final_status": status,
        "message": message,
        "approvals": approvals
    }


@step()
def execute_approved_request(request: dict) -> dict:
    """Execute the approved request."""
    print(f"Executing approved request {request['request_id']}...")
    
    return {
        "executed": True,
        "execution_id": f"EXE-{request['request_id']}",
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@workflow()
def approval_workflow(request: dict) -> dict:
    """
    Multi-step approval workflow:
    1. Submit request
    2. Determine required approvers
    3. For each approver:
       a. Send notification
       b. Wait for approval
    4. Process final result
    5. Execute if approved
    
    Savepoints are created while waiting for approvals,
    allowing the workflow to be inspected and resumed.
    """
    # Submit
    submitted = submit_request(request)
    
    # Determine approvers
    approval_config = determine_approvers(submitted)
    
    # Collect approvals
    approvals = []
    for approver_info in approval_config["approval_chain"]:
        approver = approver_info["role"]
        
        # Notify
        notify_approver(approver, submitted)
        
        # Wait for approval
        approval = wait_for_approval(approver, submitted, timeout_seconds=30)
        approvals.append(approval)
        
        # Short-circuit on rejection
        if approval["decision"] != "approved":
            break
    
    # Process result
    result = process_approval_result(submitted, approvals)
    
    # Execute if approved
    if result["final_status"] == "approved":
        execution = execute_approved_request(submitted)
        result["execution"] = execution
    
    return result


if __name__ == "__main__":
    request = {
        "title": "New Server Purchase",
        "amount": 5000,
        "requester": "alice@example.com",
        "description": "Need new server for ML training",
        "justification": "Current servers at capacity"
    }
    
    result = approval_workflow(request)
    print(f"\nApproval Result:")
    print(f"  Status: {result['final_status']}")
    print(f"  Message: {result['message']}")
