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
from contd.sdk.registry import WorkflowRegistry

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_metrics_collector = None

def _get_collector():
    global _metrics_collector
    if _metrics_collector is None:
        try:
            from contd.observability.metrics import collector
            _metrics_collector = collector
        except ImportError:
            _metrics_collector = None
    return _metrics_collector

P = ParamSpec('P')
R = TypeVar('R')

@dataclass
class WorkflowConfig:
    workflow_id: Optional[str] = None      # Auto-generate if None
    max_duration: Optional[timedelta] = None
    retry_policy: Optional[RetryPolicy] = None
    tags: Optional[dict[str, str]] = None
    org_id: Optional[str] = None

def workflow(config: WorkflowConfig | None = None):
    """
    Mark a function as a resumable workflow.
    """
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            workflow_start = time.time()
            collector = _get_collector()
            
            # Get or create workflow context
            ctx = ExecutionContext.get_or_create(
                workflow_id=config.workflow_id if config else None,
                org_id=config.org_id if config else None,
                workflow_name=fn.__name__,
                tags=config.tags if config else None
            )
            
            # Emit workflow start metric
            if collector:
                collector.record_workflow_start(
                    workflow_name=fn.__name__,
                    trigger=ctx.tags.get('trigger', 'api') if ctx.tags else 'api'
                )
            
            # Acquire lease
            lease_start = time.time()
            lease = ctx.engine.lease_manager.acquire(
                ctx.workflow_id,
                owner_id=ctx.executor_id
            )
            
            if not lease:
                if collector:
                    collector.record_lease_acquisition(
                        workflow_name=fn.__name__,
                        duration_ms=(time.time() - lease_start) * 1000,
                        result="locked"
                    )
                raise WorkflowLocked(f"Workflow {ctx.workflow_id} locked by another executor")
            
            if collector:
                collector.record_lease_acquisition(
                    workflow_name=fn.__name__,
                    duration_ms=(time.time() - lease_start) * 1000,
                    result="acquired",
                    owner_id=ctx.executor_id
                )
            
            try:
                # Start heartbeat background thread
                ctx.start_heartbeat(lease)
                
                # Check if resuming
                if ctx.is_resuming():
                    restore_start = time.time()
                    state = ctx.engine.restore(ctx.workflow_id)
                    restore_duration = (time.time() - restore_start) * 1000
                    
                    ctx.set_state(state)
                    logger.info(f"Resumed workflow {ctx.workflow_id} from step {state.step_number}")
                    
                    # Emit restore metrics
                    if collector:
                        # Count events replayed (approximate from step number)
                        events_replayed = state.step_number * 2  # Rough estimate
                        had_snapshot = hasattr(state, 'snapshot_id') and state.snapshot_id is not None
                        
                        collector.record_restore(
                            workflow_name=fn.__name__,
                            duration_ms=restore_duration,
                            events_replayed=events_replayed,
                            had_snapshot=had_snapshot
                        )
                
                # Execute workflow
                result = fn(*args, **kwargs)
                
                # Mark complete
                ctx.engine.complete_workflow(ctx.workflow_id)
                
                # Emit completion metric
                if collector:
                    duration = time.time() - workflow_start
                    collector.record_workflow_complete(
                        workflow_name=fn.__name__,
                        duration_seconds=duration,
                        status="completed"
                    )
                
                return result
                
            except Exception as e:
                # Emit failure metric
                if collector:
                    duration = time.time() - workflow_start
                    collector.record_workflow_complete(
                        workflow_name=fn.__name__,
                        duration_seconds=duration,
                        status="failed"
                    )
                raise
                
            finally:
                ctx.stop_heartbeat()
                ctx.engine.lease_manager.release(lease)
        
        # Attach metadata for introspection
        wrapper.__contd_workflow__ = True
        wrapper.__contd_config__ = config
        
        # Register workflow
        WorkflowRegistry.register(fn.__name__, wrapper)
        
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
            collector = _get_collector()
            
            # Generate step ID (deterministic from function name + position)
            step_id = ctx.generate_step_id(fn.__name__)
            
            # Check idempotency: already completed?
            if cached_result := ctx.engine.idempotency.check_completed(
                ctx.workflow_id, 
                step_id
            ):
                logger.info(f"Step {step_id} already completed, returning cached result")
                
                # Emit idempotency hit metric
                if collector:
                    collector.record_step_execution(
                        workflow_name=ctx.workflow_name,
                        step_name=fn.__name__,
                        duration_ms=0,
                        status="completed",
                        was_cached=True,
                        user_id=ctx.tags.get('user_id') if ctx.tags else None,
                        plan_type=ctx.tags.get('plan_type', 'free') if ctx.tags else 'free'
                    )
                
                ctx.set_state(cached_result)
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
                duration_ms = int((time.monotonic() - start_time) * 1000)
                
                # Log failure
                ctx.engine.journal.append(StepFailedEvent(
                    event_id=generate_id(),
                    workflow_id=ctx.workflow_id,
                    timestamp=utcnow(),
                    step_id=step_id,
                    attempt_id=attempt_id,
                    error=str(e),
                ))
                
                # Emit failure metric
                if collector:
                    collector.record_step_execution(
                        workflow_name=ctx.workflow_name,
                        step_name=fn.__name__,
                        duration_ms=duration_ms,
                        status="failed",
                        was_cached=False,
                        user_id=ctx.tags.get('user_id') if ctx.tags else None,
                        plan_type=ctx.tags.get('plan_type', 'free') if ctx.tags else 'free'
                    )
                
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
            ctx.engine.idempotency.mark_completed(
                ctx.workflow_id,
                step_id,
                attempt_id,
                new_state
            )
            
            # Update context state
            ctx.set_state(new_state)
            ctx.increment_step()
            
            # Emit success metric
            if collector:
                collector.record_step_execution(
                    workflow_name=ctx.workflow_name,
                    step_name=fn.__name__,
                    duration_ms=duration_ms,
                    status="completed",
                    was_cached=False,
                    user_id=ctx.tags.get('user_id') if ctx.tags else None,
                    plan_type=ctx.tags.get('plan_type', 'free') if ctx.tags else 'free'
                )
            
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
