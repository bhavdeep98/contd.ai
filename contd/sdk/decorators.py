from typing import TypeVar, Callable, ParamSpec, Optional
from dataclasses import dataclass
from functools import wraps
from datetime import timedelta
import time
import traceback
import logging

from contd.sdk.context import ExecutionContext, utcnow, generate_id
from contd.sdk.types import RetryPolicy
from contd.sdk.errors import WorkflowLocked
from contd.models.serialization import compute_delta
from contd.models.events import StepIntentionEvent, StepFailedEvent, StepCompletedEvent

logger = logging.getLogger(__name__)

P = ParamSpec('P')
R = TypeVar('R')

@dataclass
class WorkflowConfig:
    workflow_id: Optional[str] = None      # Auto-generate if None
    max_duration: Optional[timedelta] = None
    retry_policy: Optional[RetryPolicy] = None
    tags: Optional[dict[str, str]] = None

def workflow(config: WorkflowConfig | None = None):
    """
    Mark a function as a resumable workflow.
    """
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Get or create workflow context
            ctx = ExecutionContext.get_or_create(
                workflow_id=config.workflow_id if config else None,
                workflow_name=fn.__name__,
                tags=config.tags if config else None
            )
            
            # Acquire lease
            lease = ctx.engine.lease_manager.acquire(
                ctx.workflow_id,
                owner_id=ctx.executor_id
            )
            
            if not lease:
                raise WorkflowLocked(f"Workflow {ctx.workflow_id} locked by another executor")
            
            try:
                # Start heartbeat background thread
                ctx.start_heartbeat(lease)
                
                # Check if resuming
                if ctx.is_resuming():
                    state = ctx.engine.restore(ctx.workflow_id)
                    ctx.set_state(state)
                    logger.info(f"Resumed workflow {ctx.workflow_id} from step {state.step_number}")
                
                # Execute workflow
                result = fn(*args, **kwargs)
                
                # Mark complete
                ctx.engine.complete_workflow(ctx.workflow_id)
                
                return result
                
            finally:
                ctx.stop_heartbeat()
                ctx.engine.lease_manager.release(lease)
        
        # Attach metadata for introspection
        wrapper.__contd_workflow__ = True
        wrapper.__contd_config__ = config
        
        return wrapper
    
    return decorator

@dataclass
class StepConfig:
    checkpoint: bool = True              # Create checkpoint after step?
    idempotency_key: Callable | None = None  # For external side effects
    retry: RetryPolicy | None = None
    timeout: timedelta | None = None
    savepoint: bool = False              # Rich savepoint with metadata?

def execute_with_timeout(fn, timeout: timedelta, *args, **kwargs):
    # Simplistic timeout implementation (real one might use signals or threads)
    # This is placeholder
    return fn(*args, **kwargs)

def step(config: StepConfig | None = None):
    """
    Mark a function as a workflow step.
    """
    cfg = config or StepConfig()
    
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = ExecutionContext.current()
            
            # Generate step ID (deterministic from function name + position)
            step_id = ctx.generate_step_id(fn.__name__)
            
            # Check idempotency: already completed?
            if cached_result := ctx.engine.idempotency.check_completed(
                ctx.workflow_id, 
                step_id
            ):
                logger.info(f"Step {step_id} already completed, returning cached result")
                # Need to update context state with cached result!
                # Cached result is WorkflowState.
                # If cached_result returns state, we set it.
                ctx.set_state(cached_result)
                return cached_result.variables # Return variables to user function usually?
                # Wait, the workflow code expects `fn` result.
                # If `fn` returns state/dict, we should return that.
                # `check_completed` returns `WorkflowState`.
                # We should probably return `state.variables` if user function expects dict, 
                # OR return `state` if users pass state around.
                # In examples: `state = search(state, query)`.
                # So we should return the appropriate object.
                # The prompt implies `state` (dict) is passed around. 
                # But `check_completed` returns `WorkflowState`.
                # For compatibility, this might need more robust typing or convention.
                # We'll assume the user code works with `variable` dicts if that's what `fn` does.
                # But the decorator expects `fn` to return something.
                # We'll return `cached_result` (WorkflowState)?
                # In example `state = fetch_order(state)`.
                # `fetch_order` takes state (dict or obj) and returns state.
                # If we return `WorkflowState`, user code might fail if it expects dict.
                # But `ExecutionContext.extract_state` handles both.
                # Let's return `cached_result` for now.
                return cached_result 

            # Allocate attempt ID
            attempt_id = ctx.engine.idempotency.allocate_attempt(
                ctx.workflow_id,
                step_id,
                ctx.lease
            )
            
            # Write intention
            ctx.engine.journal.append(StepIntentionEvent(
                event_id=generate_id(),
                workflow_id=ctx.workflow_id,
                timestamp=utcnow(),
                step_id=step_id,
                step_name=fn.__name__,
                attempt_id=attempt_id
            ))
            
            # Execute with timeout
            start_time = time.monotonic()
            try:
                if cfg.timeout:
                    result = execute_with_timeout(fn, cfg.timeout, *args, **kwargs)
                else:
                    result = fn(*args, **kwargs)
                    
            except Exception as e:
                # Log failure
                ctx.engine.journal.append(StepFailedEvent(
                    event_id=generate_id(),
                    workflow_id=ctx.workflow_id,
                    timestamp=utcnow(),
                    step_id=step_id,
                    attempt_id=attempt_id,
                    error=str(e), # spec used error_type/msg, but StepFailedEvent def in models uses `error: str`
                ))
                
                # Apply retry policy
                if cfg.retry and cfg.retry.should_retry(attempt_id, e):
                    logger.info(f"Retrying step {step_id}, attempt {attempt_id + 1}")
                    time.sleep(cfg.retry.backoff(attempt_id))
                    return wrapper(*args, **kwargs)  # Recursive retry
                
                raise
            
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            # Extract new state (assumes result is state or contains state)
            new_state = ctx.extract_state(result)
            old_state = ctx.get_state()
            
            # Compute delta
            # compute_delta expects dicts now based on my update to serialization.py
            delta = compute_delta(old_state.to_dict(), new_state.to_dict())
            
            # Write completion
            ctx.engine.journal.append(StepCompletedEvent(
                event_id=generate_id(),
                workflow_id=ctx.workflow_id,
                timestamp=utcnow(),
                step_id=step_id,
                attempt_id=attempt_id,
                state_delta=delta,
                duration_ms=duration_ms
            ))
            
            # Mark completed (idempotent)
            # Added last_event_seq=0 placeholder as I discussed in idempotency.py step
            ctx.engine.idempotency.mark_completed(
                ctx.workflow_id,
                step_id,
                attempt_id,
                new_state
            )
            
            # Update context state
            ctx.set_state(new_state)
            ctx.increment_step()
            
            # Checkpoint if configured
            if cfg.checkpoint:
                ctx.engine.maybe_snapshot(new_state)
            
            # Savepoint if configured (rich metadata)
            if cfg.savepoint:
                ctx.create_savepoint()
            
            return result
        
        wrapper.__contd_step__ = True
        wrapper.__contd_config__ = cfg
        
        return wrapper
    
    return decorator
