"""
Runtime executor for workflow step execution with full durability guarantees.
"""

import time
import logging
from typing import Any, Callable, Tuple
from datetime import datetime
import uuid

from contd.core.engine import ExecutionEngine
from contd.persistence.leases import Lease
from contd.models.state import WorkflowState
from contd.models.events import StepIntentionEvent, StepCompletedEvent, StepFailedEvent
from contd.models.serialization import compute_delta

logger = logging.getLogger(__name__)


def generate_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


class StepExecutor:
    """
    Executes workflow steps with full durability guarantees:
    - Idempotent execution (exactly-once semantics)
    - Event sourcing (all state changes recorded)
    - Lease-based coordination (prevents split-brain)
    - Automatic retry with attempt tracking
    """

    def __init__(self, engine: ExecutionEngine):
        self.engine = engine

    def execute_step(
        self,
        workflow_id: str,
        org_id: str,
        step_name: str,
        step_fn: Callable[[WorkflowState], Any],
        current_state: WorkflowState,
        lease: Lease,
        last_event_seq: int,
    ) -> Tuple[WorkflowState, int]:
        """
        Execute a single workflow step with full durability.

        Returns:
            Tuple of (new_state, new_event_seq)
        """
        step_id = self._generate_step_id(step_name, current_state.step_number)

        # 1. Check if already completed (idempotency)
        cached_result = self.engine.idempotency.check_completed(
            workflow_id, step_id, org_id
        )
        if cached_result:
            logger.info(f"Step {step_id} already completed, returning cached result")
            return cached_result, last_event_seq

        # 2. Allocate attempt (atomic, with fencing token)
        attempt_id = self.engine.idempotency.allocate_attempt(
            workflow_id, step_id, lease, org_id
        )

        # 3. Record intention event
        self._record_intention(workflow_id, org_id, step_id, step_name, attempt_id)

        # 4. Execute step function
        start_time = time.time()
        try:
            result = step_fn(current_state)
            duration_ms = int((time.time() - start_time) * 1000)

            # 5. Compute new state
            new_state = self._compute_new_state(current_state, result)

            # 6. Compute delta (JSON Patch)
            delta = compute_delta(current_state, new_state)

            # 7. Record completion event
            completion_seq = self._record_completion(
                workflow_id, org_id, step_id, attempt_id, delta, duration_ms
            )

            # 8. Mark step completed (idempotent)
            self.engine.idempotency.mark_completed(
                workflow_id, step_id, attempt_id, new_state, completion_seq, org_id
            )

            # 9. Maybe create snapshot
            self.engine.maybe_snapshot(new_state, completion_seq)

            logger.info(f"Step {step_id} completed in {duration_ms}ms")
            return new_state, completion_seq

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            # Record failure event
            self._record_failure(workflow_id, org_id, step_id, attempt_id, str(e))

            logger.error(f"Step {step_id} failed: {e}")
            raise

    def _generate_step_id(self, step_name: str, step_number: int) -> str:
        """Generate deterministic step ID."""
        return f"{step_name}_{step_number}"

    def _compute_new_state(
        self, current_state: WorkflowState, result: Any
    ) -> WorkflowState:
        """Compute new state from step result."""
        if isinstance(result, WorkflowState):
            return result

        # Merge result into variables
        new_vars = dict(current_state.variables)
        if isinstance(result, dict):
            new_vars.update(result)
        elif result is not None:
            new_vars["_last_result"] = result

        # Create new state with incremented step number
        return WorkflowState(
            workflow_id=current_state.workflow_id,
            step_number=current_state.step_number + 1,
            variables=new_vars,
            metadata=current_state.metadata,
            version=current_state.version,
            checksum="",  # Will be computed by recovery
            org_id=current_state.org_id,
        )

    def _record_intention(
        self,
        workflow_id: str,
        org_id: str,
        step_id: str,
        step_name: str,
        attempt_id: int,
    ) -> int:
        """Record step intention event."""
        event = StepIntentionEvent(
            event_id=generate_id(),
            workflow_id=workflow_id,
            org_id=org_id,
            timestamp=utcnow(),
            step_id=step_id,
            step_name=step_name,
            attempt_id=attempt_id,
        )
        return self.engine.journal.append(event)

    def _record_completion(
        self,
        workflow_id: str,
        org_id: str,
        step_id: str,
        attempt_id: int,
        delta: list,
        duration_ms: int,
    ) -> int:
        """Record step completion event."""
        event = StepCompletedEvent(
            event_id=generate_id(),
            workflow_id=workflow_id,
            org_id=org_id,
            timestamp=utcnow(),
            step_id=step_id,
            attempt_id=attempt_id,
            state_delta=delta,
            duration_ms=duration_ms,
        )
        return self.engine.journal.append(event)

    def _record_failure(
        self, workflow_id: str, org_id: str, step_id: str, attempt_id: int, error: str
    ) -> int:
        """Record step failure event."""
        event = StepFailedEvent(
            event_id=generate_id(),
            workflow_id=workflow_id,
            org_id=org_id,
            timestamp=utcnow(),
            step_id=step_id,
            attempt_id=attempt_id,
            error=error,
        )
        return self.engine.journal.append(event)


class WorkflowExecutor:
    """
    High-level workflow executor that manages the full lifecycle:
    - Lease acquisition
    - State restoration
    - Step execution
    - Heartbeat management
    - Cleanup
    """

    def __init__(self, engine: ExecutionEngine = None):
        self.engine = engine or ExecutionEngine.get_instance()
        self.step_executor = StepExecutor(self.engine)

    def run_workflow(
        self,
        workflow_id: str,
        org_id: str,
        owner_id: str,
        steps: list,  # List of (name, fn) tuples
    ) -> WorkflowState:
        """
        Run a complete workflow with all steps.
        """
        # Acquire lease
        lease = self.engine.acquire_lease(workflow_id, owner_id, org_id)
        if not lease:
            raise LeaseAcquisitionError(f"Could not acquire lease for {workflow_id}")

        try:
            # Restore state
            try:
                state, last_seq = self.engine.restore(workflow_id, org_id)
            except Exception:
                # New workflow - create initial state
                state = WorkflowState(
                    workflow_id=workflow_id,
                    step_number=0,
                    variables={},
                    metadata={"started_at": utcnow().isoformat()},
                    version="1.0",
                    checksum="",
                    org_id=org_id,
                )
                last_seq = 0

            # Execute steps
            for step_name, step_fn in steps:
                state, last_seq = self.step_executor.execute_step(
                    workflow_id, org_id, step_name, step_fn, state, lease, last_seq
                )

                # Heartbeat to maintain lease
                self.engine.lease_manager.heartbeat(lease)

            # Complete workflow
            self.engine.complete_workflow(workflow_id, state, last_seq)

            return state

        finally:
            # Release lease
            self.engine.release_lease(lease)


class LeaseAcquisitionError(Exception):
    """Raised when lease cannot be acquired."""

    pass
