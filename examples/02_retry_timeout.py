"""
Example 02: Retry and Timeout Patterns

Demonstrates error handling with retry policies and timeouts.
"""

from datetime import timedelta
from contd.sdk import workflow, step, StepConfig, RetryPolicy


@step(StepConfig(
    retry=RetryPolicy(
        max_attempts=3,
        backoff_base=2.0,
        backoff_max=30.0,
        backoff_jitter=0.5
    )
))
def flaky_api_call(endpoint: str) -> dict:
    """
    Call an unreliable API with automatic retry.
    
    Will retry up to 3 times with exponential backoff:
    - Attempt 1: immediate
    - Attempt 2: ~2 seconds delay
    - Attempt 3: ~4 seconds delay
    """
    import random
    
    # Simulate 50% failure rate
    if random.random() < 0.5:
        print(f"API call to {endpoint} failed, will retry...")
        raise ConnectionError("API temporarily unavailable")
    
    print(f"API call to {endpoint} succeeded!")
    return {"data": "success", "endpoint": endpoint}


@step(StepConfig(timeout=timedelta(seconds=5)))
def slow_operation() -> dict:
    """
    Operation with timeout protection.
    
    Raises StepTimeout if execution exceeds 5 seconds.
    """
    import time
    
    print("Starting slow operation...")
    # Simulate work (completes in 2 seconds)
    time.sleep(2)
    print("Slow operation completed!")
    
    return {"status": "done"}


@step(StepConfig(
    timeout=timedelta(seconds=10),
    retry=RetryPolicy(
        max_attempts=2,
        retryable_exceptions=[TimeoutError, ConnectionError]
    )
))
def robust_external_call(url: str) -> dict:
    """
    Combined timeout and retry for external calls.
    
    - Times out after 10 seconds
    - Retries on TimeoutError or ConnectionError
    - Max 2 attempts
    """
    import random
    
    # Simulate occasional timeout
    if random.random() < 0.3:
        raise TimeoutError("Request timed out")
    
    return {"response": "OK", "url": url}


@workflow()
def resilient_workflow(api_endpoint: str) -> dict:
    """
    Workflow demonstrating resilient patterns.
    
    Handles transient failures gracefully with retries
    and protects against hanging operations with timeouts.
    """
    # Step with retry
    api_result = flaky_api_call(api_endpoint)
    
    # Step with timeout
    slow_result = slow_operation()
    
    # Step with both
    external_result = robust_external_call("https://api.example.com")
    
    return {
        "api": api_result,
        "slow": slow_result,
        "external": external_result
    }


if __name__ == "__main__":
    result = resilient_workflow("https://api.example.com/data")
    print(f"\nWorkflow completed: {result}")
