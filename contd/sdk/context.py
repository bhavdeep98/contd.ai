from contextvars import ContextVar
from threading import Thread, Event
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
import uuid
import socket
import logging
from datetime import datetime

from contd.core.engine import ExecutionEngine
from contd.persistence.leases import Lease
from contd.models.state import WorkflowState
from contd.models.events import (
    SavepointCreatedEvent,
    AnnotationCreatedEvent,
    ReasoningIngestedEvent,
    ContextDigestCreatedEvent,
)
from contd.core.context_preservation import (
    ReasoningBuffer,
    HealthTracker,
    ContextHealth,
    RestoredContext,
    execute_distill,
)
from contd.sdk.errors import NoActiveWorkflow

logger = logging.getLogger(__name__)

_current_context: ContextVar["ExecutionContext"] = ContextVar(
    "contd_context", default=None
)


def generate_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


def generate_workflow_id():
    return f"wf-{generate_id()}"


def get_executor_id():
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def compute_checksum(state: WorkflowState) -> str:
    from contd.models.serialization import serialize
    import hashlib

    return hashlib.sha256(serialize(state).encode("utf-8")).hexdigest()


@dataclass
class ExecutionContext:
    """
    Execution context for a running workflow.

    Provides:
    - Thread-local context access via current()
    - State management and extraction
    - Background heartbeat for lease renewal
    - Savepoint creation with epistemic metadata
    - Context preservation: annotate(), ingest(), context_health()

    The context is automatically created by the @workflow decorator
    and accessed by @step decorated functions.
    """

    workflow_id: str
    org_id: str
    workflow_name: str
    executor_id: str
    engine: ExecutionEngine
    lease: Optional[Lease]
    tags: Optional[Dict[str, str]] = None

    _state: Optional[WorkflowState] = None
    _step_counter: int = 0
    _heartbeat_thread: Optional[Thread] = None
    _heartbeat_stop: Optional[Event] = None
    
    # Context preservation
    _reasoning_buffer: ReasoningBuffer = field(default_factory=ReasoningBuffer)
    _health_tracker: Optional[HealthTracker] = None
    _current_digest: Optional[dict] = None
    _digests_created: int = 0
    _last_digest_step: Optional[int] = None
    _distill_requested: bool = False
    
    # Workflow config for distillation
    _distill_fn: Optional[Callable[[List[str], Optional[dict]], dict]] = None
    _distill_every: Optional[int] = None
    _distill_threshold: Optional[int] = None
    _context_budget: Optional[int] = None
    _on_health_check: Optional[Callable[["ExecutionContext", ContextHealth], None]] = None
    
    # Restored context (populated on resume)
    _restored_context: Optional[RestoredContext] = None

    @classmethod
    def current(cls) -> "ExecutionContext":
        """
        Get current execution context (thread-local).

        Raises:
            NoActiveWorkflow: If called outside of a @workflow decorated function
        """
        ctx = _current_context.get()
        if ctx is None:
            raise NoActiveWorkflow(
                "No workflow context found. Did you forget @contd.workflow()?"
            )
        return ctx

    @classmethod
    def get_or_create(
        cls,
        workflow_id: str | None,
        workflow_name: str,
        org_id: str | None = None,
        tags: dict | None = None,
        # Context preservation config
        distill: Callable[[List[str], Optional[dict]], dict] | None = None,
        distill_every: int | None = None,
        distill_threshold: int | None = None,
        context_budget: int | None = None,
        on_health_check: Callable[["ExecutionContext", ContextHealth], None] | None = None,
    ) -> "ExecutionContext":
        """
        Create new context or prepare for resume.

        Args:
            workflow_id: Explicit ID (triggers resume if provided)
            workflow_name: Name of the workflow function
            org_id: Organization ID for multi-tenancy
            tags: Metadata tags for filtering/grouping
            distill: Developer-provided function to compress reasoning chunks
            distill_every: Trigger distillation every N steps
            distill_threshold: Trigger distillation when buffer exceeds N chars
            context_budget: Warn when total output exceeds N bytes
            on_health_check: Callback fired after each step with health signals

        Returns:
            ExecutionContext ready for workflow execution
        """
        # Check if resuming (if ID is provided, we try to resume)
        if workflow_id:
            resuming = True
        else:
            workflow_id = generate_workflow_id()
            resuming = False

        engine = ExecutionEngine.get_instance()

        if not org_id:
            org_id = "default"

        ctx = cls(
            workflow_id=workflow_id,
            org_id=org_id,
            workflow_name=workflow_name,
            executor_id=get_executor_id(),
            engine=engine,
            lease=None,
            tags=tags,
            _state=None,
            _reasoning_buffer=ReasoningBuffer(),
            _health_tracker=HealthTracker(context_budget=context_budget),
            _distill_fn=distill,
            _distill_every=distill_every,
            _distill_threshold=distill_threshold,
            _context_budget=context_budget,
            _on_health_check=on_health_check,
        )

        _current_context.set(ctx)

        if not resuming:
            # Create initial state
            ctx._state = WorkflowState(
                workflow_id=workflow_id,
                step_number=0,
                variables={},
                metadata={
                    "workflow_name": workflow_name,
                    "started_at": utcnow().isoformat(),
                    "tags": tags or {},
                },
                version="1.0",
                checksum="",
                org_id=org_id,
            )
            # Compute checksum (WorkflowState is frozen, so we need to recreate)
            checksum = compute_checksum(ctx._state)
            ctx._state = WorkflowState(
                workflow_id=ctx._state.workflow_id,
                step_number=ctx._state.step_number,
                variables=ctx._state.variables,
                metadata=ctx._state.metadata,
                version=ctx._state.version,
                checksum=checksum,
                org_id=ctx._state.org_id,
            )

        return ctx

    @classmethod
    def clear(cls):
        """Clear the current context (for testing)."""
        _current_context.set(None)

    def is_resuming(self) -> bool:
        """Check if workflow is being resumed from persistence."""
        return self._state is None

    def get_state(self) -> WorkflowState:
        """
        Get current workflow state.

        Raises:
            Exception: If state not initialized
        """
        if self._state is None:
            raise Exception("State not initialized. Call restore() or init.")
        return self._state

    def set_state(self, state: WorkflowState):
        """Set workflow state (used during restore and step completion)."""
        self._state = state
        self._step_counter = state.step_number

    def increment_step(self):
        """Increment step counter (state update handled by decorators)."""
        self._step_counter += 1

    def generate_step_id(self, step_name: str) -> str:
        """
        Generate deterministic step ID.

        Format: {step_name}_{counter}
        This ensures idempotent replay produces same step IDs.
        """
        return f"{step_name}_{self._step_counter}"

    def extract_state(self, result: Any) -> WorkflowState:
        """
        Extract new state from step result.

        Conventions:
        - If result is WorkflowState, use directly
        - If result is dict, merge into current state variables
        - Otherwise, ignore result for state purposes

        Args:
            result: Return value from step function

        Returns:
            New WorkflowState with updated variables
        """
        if isinstance(result, WorkflowState):
            return result

        current_vars = self._state.variables.copy()

        if isinstance(result, dict):
            current_vars.update(result)

        new_step_number = self._state.step_number + 1

        new_state = WorkflowState(
            workflow_id=self._state.workflow_id,
            step_number=new_step_number,
            variables=current_vars,
            metadata=self._state.metadata,
            version=self._state.version,
            checksum="",
            org_id=self.org_id,
        )

        # Compute checksum for new state
        checksum = compute_checksum(new_state)
        new_state = WorkflowState(
            workflow_id=new_state.workflow_id,
            step_number=new_state.step_number,
            variables=new_state.variables,
            metadata=new_state.metadata,
            version=new_state.version,
            checksum=checksum,
            org_id=new_state.org_id,
        )

        return new_state

    def start_heartbeat(self, lease: Lease):
        """
        Start background heartbeat thread for lease renewal.

        The heartbeat runs at the lease manager's configured interval
        and automatically stops if renewal fails.
        """
        self.lease = lease
        self._heartbeat_stop = Event()

        def heartbeat_loop():
            while not self._heartbeat_stop.is_set():
                try:
                    self.engine.lease_manager.heartbeat(lease)
                except Exception as e:
                    logger.error(f"Heartbeat failed for {self.workflow_id}: {e}")
                    self._heartbeat_stop.set()
                    break

                # Sleep for heartbeat interval
                interval = self.engine.lease_manager.HEARTBEAT_INTERVAL.total_seconds()
                self._heartbeat_stop.wait(timeout=interval)

        self._heartbeat_thread = Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.debug(f"Started heartbeat for {self.workflow_id}")

    def stop_heartbeat(self):
        """Stop the background heartbeat thread."""
        if self._heartbeat_stop:
            self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            logger.debug(f"Stopped heartbeat for {self.workflow_id}")

    def create_savepoint(self, metadata: Optional[Dict[str, Any]] = None):
        """
        Create rich savepoint with epistemic metadata.

        Savepoints capture not just state but reasoning context:
        - Goal summary
        - Current hypotheses
        - Open questions
        - Decision log
        - Next planned step

        Args:
            metadata: Optional override for savepoint metadata.
                     If not provided, reads from state["_savepoint_metadata"]
        """
        savepoint_id = generate_id()

        # Get metadata from argument or state
        if metadata is None:
            metadata = self._state.variables.get("_savepoint_metadata", {})

        self.engine.journal.append(
            SavepointCreatedEvent(
                event_id=generate_id(),
                workflow_id=self.workflow_id,
                org_id=self.org_id,
                timestamp=utcnow(),
                savepoint_id=savepoint_id,
                step_number=self._state.step_number,
                goal_summary=metadata.get("goal_summary", ""),
                current_hypotheses=metadata.get("hypotheses", []),
                open_questions=metadata.get("questions", []),
                decision_log=metadata.get("decisions", []),
                next_step=metadata.get("next_step", ""),
                snapshot_ref="",
            )
        )

        logger.info(
            f"Created savepoint {savepoint_id} at step {self._state.step_number}"
        )
        return savepoint_id

    def update_tags(self, new_tags: Dict[str, str]):
        """Update workflow tags (for runtime tagging)."""
        if self.tags is None:
            self.tags = {}
        self.tags.update(new_tags)

        # Also update in state metadata
        if self._state:
            current_metadata = dict(self._state.metadata)
            current_tags = current_metadata.get("tags", {})
            current_tags.update(new_tags)
            current_metadata["tags"] = current_tags

            self._state = WorkflowState(
                workflow_id=self._state.workflow_id,
                step_number=self._state.step_number,
                variables=self._state.variables,
                metadata=current_metadata,
                version=self._state.version,
                checksum=self._state.checksum,
                org_id=self._state.org_id,
            )

    # =========================================================================
    # Context Preservation Methods
    # =========================================================================

    def annotate(self, text: str):
        """
        Add a lightweight reasoning breadcrumb.
        
        One line. Optional. Developer decides what matters.
        The engine doesn't parse it, doesn't summarize it.
        It just stores it durably alongside the step event.
        
        Example:
            ctx.annotate("Chose regression because data is tabular")
        """
        step_number = self._state.step_number if self._state else 0
        step_name = f"step_{step_number}"  # Will be overwritten by step decorator
        
        self.engine.journal.append(
            AnnotationCreatedEvent(
                event_id=generate_id(),
                workflow_id=self.workflow_id,
                org_id=self.org_id,
                timestamp=utcnow(),
                step_number=step_number,
                step_name=step_name,
                text=text,
            )
        )
        logger.debug(f"Annotation created at step {step_number}: {text[:50]}...")

    def ingest(self, reasoning: str):
        """
        Ingest raw reasoning tokens into the buffer.
        
        When reasoning tokens are available (e.g., Claude's extended thinking),
        pass them in. When they're not, don't. Engine doesn't care.
        
        The engine accumulates these raw chunks in a buffer.
        Periodically, it calls the developer-provided distill function.
        
        Example:
            if response.thinking:
                ctx.ingest(response.thinking)
        """
        if not reasoning:
            return
            
        self._reasoning_buffer.add(reasoning)
        
        # Record the ingestion event
        self.engine.journal.append(
            ReasoningIngestedEvent(
                event_id=generate_id(),
                workflow_id=self.workflow_id,
                org_id=self.org_id,
                timestamp=utcnow(),
                step_number=self._state.step_number if self._state else 0,
                chunk=reasoning,
                chunk_size=len(reasoning),
            )
        )
        
        logger.debug(
            f"Ingested {len(reasoning)} chars, buffer now {self._reasoning_buffer.total_chars} chars"
        )

    def context_health(self) -> ContextHealth:
        """
        Get current context health signals.
        
        Queryable at any point during execution.
        The developer can use it programmatically to decide
        when to create savepoints or trigger distillation.
        
        Example:
            health = ctx.context_health()
            if health.recommendation == "distill":
                ctx.request_distill()
        """
        if self._health_tracker is None:
            self._health_tracker = HealthTracker(context_budget=self._context_budget)
        
        return self._health_tracker.compute_health(
            buffer=self._reasoning_buffer,
            digests_created=self._digests_created,
            last_digest_step=self._last_digest_step,
            current_step=self._state.step_number if self._state else 0,
        )

    def request_distill(self):
        """
        Request distillation before the next step.
        
        Use this to trigger distillation on-demand rather than
        waiting for the configured interval or threshold.
        
        Example:
            health = ctx.context_health()
            if health.output_trend == "declining":
                ctx.request_distill()
        """
        self._distill_requested = True
        logger.debug("Distillation requested")

    def get_restored_context(self) -> Optional[RestoredContext]:
        """
        Get the context that was restored on resume.
        
        Returns None if this is a fresh workflow (not resumed).
        
        The developer feeds context.digest back to their LLM prompt.
        The agent picks up where its reasoning was, not just where
        its data was.
        """
        return self._restored_context

    def set_restored_context(self, context: RestoredContext):
        """Set restored context (called by recovery)."""
        self._restored_context = context
        if context.digest:
            self._current_digest = context.digest
        self._digests_created = len(context.digest_history)
        if context.digest_history:
            self._last_digest_step = context.digest_history[-1].get("step")

    def _maybe_distill(self):
        """
        Check if distillation should be triggered and execute if so.
        
        Called after each step by the step decorator.
        """
        if self._distill_fn is None:
            return
        
        should_distill = False
        reason = ""
        
        # Check explicit request
        if self._distill_requested:
            should_distill = True
            reason = "requested"
            self._distill_requested = False
        
        # Check step interval
        elif self._distill_every and self._state:
            steps_since = (
                self._state.step_number - (self._last_digest_step or 0)
            )
            if steps_since >= self._distill_every:
                should_distill = True
                reason = f"interval ({steps_since} steps)"
        
        # Check threshold
        elif self._distill_threshold:
            if self._reasoning_buffer.total_chars >= self._distill_threshold:
                should_distill = True
                reason = f"threshold ({self._reasoning_buffer.total_chars} chars)"
        
        if not should_distill or len(self._reasoning_buffer) == 0:
            return
        
        logger.info(f"Triggering distillation: {reason}")
        self._execute_distill()

    def _execute_distill(self):
        """Execute the distillation and record the result."""
        chunks = self._reasoning_buffer.clear()
        
        # Execute developer's distill function
        digest = execute_distill(
            self._distill_fn,
            chunks,
            self._current_digest,
        )
        
        # Record the digest event
        distill_failed = digest.get("_distill_failed", False)
        
        self.engine.journal.append(
            ContextDigestCreatedEvent(
                event_id=generate_id(),
                workflow_id=self.workflow_id,
                org_id=self.org_id,
                timestamp=utcnow(),
                step_number=self._state.step_number if self._state else 0,
                digest=digest if not distill_failed else {},
                chunks_processed=len(chunks),
                distill_failed=distill_failed,
                error=digest.get("error", "") if distill_failed else "",
                raw_chunks=digest.get("raw_chunks", []) if distill_failed else [],
            )
        )
        
        # Update state
        self._current_digest = digest
        self._digests_created += 1
        self._last_digest_step = self._state.step_number if self._state else 0
        
        if distill_failed:
            logger.warning(f"Distillation failed: {digest.get('error')}")
        else:
            logger.info(f"Distillation complete at step {self._last_digest_step}")

    def _fire_health_check(self, output_size: int, duration_ms: int, was_retry: bool = False):
        """
        Record step metrics and fire health check callback.
        
        Called after each step by the step decorator.
        """
        if self._health_tracker:
            self._health_tracker.record_step(output_size, duration_ms, was_retry)
        
        if self._on_health_check:
            health = self.context_health()
            try:
                self._on_health_check(self, health)
            except Exception as e:
                logger.warning(f"Health check callback failed: {e}")

    def set_variable(self, key: str, value: Any):
        """
        Set a workflow variable.
        
        Useful for health check handlers to signal state changes.
        
        Example:
            def my_handler(ctx, health):
                if health.budget_used > 0.9:
                    ctx.set_variable("should_conclude", True)
        """
        if self._state is None:
            return
        
        new_vars = dict(self._state.variables)
        new_vars[key] = value
        
        self._state = WorkflowState(
            workflow_id=self._state.workflow_id,
            step_number=self._state.step_number,
            variables=new_vars,
            metadata=self._state.metadata,
            version=self._state.version,
            checksum=self._state.checksum,
            org_id=self._state.org_id,
        )
