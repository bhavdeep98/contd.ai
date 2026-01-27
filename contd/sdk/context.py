from contextvars import ContextVar
from threading import Thread, Event
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time
import uuid
import socket
import logging
from datetime import datetime

from contd.core.engine import ExecutionEngine
from contd.persistence.leases import Lease
from contd.models.state import WorkflowState
from contd.models.events import SavepointCreatedEvent
from contd.sdk.errors import NoActiveWorkflow, WorkflowLocked

logger = logging.getLogger(__name__)

_current_context: ContextVar['ExecutionContext'] = ContextVar('contd_context', default=None)

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
    return hashlib.sha256(serialize(state).encode('utf-8')).hexdigest()

@dataclass
class ExecutionContext:
    workflow_id: str
    workflow_name: str
    executor_id: str
    engine: ExecutionEngine
    lease: Optional[Lease]
    
    _state: Optional[WorkflowState]
    _step_counter: int = 0
    _heartbeat_thread: Optional[Thread] = None
    _heartbeat_stop: Optional[Event] = None
    
    @classmethod
    def current(cls) -> 'ExecutionContext':
        """Get current execution context (thread-local)"""
        ctx = _current_context.get()
        if ctx is None:
            raise NoActiveWorkflow("No workflow context found. Did you forget @contd.workflow()?")
        return ctx
    
    @classmethod
    def get_or_create(
        cls,
        workflow_id: str | None,
        workflow_name: str,
        tags: dict | None = None
    ) -> 'ExecutionContext':
        """Create new context or resume existing"""
        
        # Check if resuming (Placeholder logic - in real app, check DB if ID provided)
        # Here we assume if ID is provided, we try to resume.
        if workflow_id:
            # Check existence via engine?
            # engine.exists(workflow_id)
            resuming = True
        else:
            workflow_id = workflow_id or generate_workflow_id()
            resuming = False
        
        engine = ExecutionEngine.get_instance()
        
        ctx = cls(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            executor_id=get_executor_id(),
            engine=engine,
            lease=None,  # Set by workflow decorator
            _state=None
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
                    "tags": tags or {}
                },
                version="1.0",
                checksum=""
            )
            ctx._state.checksum = compute_checksum(ctx._state)
        
        return ctx
        
    @classmethod
    def _workflow_exists(cls, workflow_id: str) -> bool:
        # Mock check
        return True
    
    def is_resuming(self) -> bool:
        """Check if workflow is being resumed"""
        return self._state is None
    
    def get_state(self) -> WorkflowState:
        if self._state is None:
             raise Exception("State not initialized. Call restore() or init.")
        return self._state
    
    def set_state(self, state: WorkflowState):
        self._state = state
        self._step_counter = state.step_number
    
    def increment_step(self):
        self._step_counter += 1
        # Updating state object directly (it's frozen, so replace)
        # But wait, python dataclasses frozen=True means we can't update.
        # So we should be creating NEW state objects.
        # decorators.py handles creating new state from result.
        pass
    
    def generate_step_id(self, step_name: str) -> str:
        """Deterministic step ID from name + counter"""
        return f"{step_name}_{self._step_counter}"
    
    def extract_state(self, result: Any) -> WorkflowState:
        """
        Extract state from step result.
        Convention: result is either the state itself or a dict to merge.
        """
        if isinstance(result, WorkflowState):
            return result
        
        current_vars = self._state.variables
        new_vars = current_vars.copy()
        
        if isinstance(result, dict):
            # Merge into existing state
            new_vars.update(result)
        
        # Determine new step number (increment)
        new_step_number = self._state.step_number + 1
        
        new_state = WorkflowState(
            workflow_id=self._state.workflow_id,
            step_number=new_step_number,
            variables=new_vars,
            metadata=self._state.metadata,
            version=self._state.version,
            checksum="" # Will be computed later
        )
        new_state.checksum = compute_checksum(new_state)
        return new_state
    
    def start_heartbeat(self, lease: Lease):
        """Start background heartbeat thread"""
        self.lease = lease
        self._heartbeat_stop = Event()
        
        def heartbeat_loop():
            while not self._heartbeat_stop.is_set():
                try:
                    self.engine.lease_manager.heartbeat(lease)
                except Exception as e:
                    logger.error(f"Heartbeat failed: {e}")
                    self._heartbeat_stop.set()
                    break
                
                # Check less frequently than interval
                time.sleep(self.engine.lease_manager.HEARTBEAT_INTERVAL.total_seconds())
        
        self._heartbeat_thread = Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def stop_heartbeat(self):
        """Stop heartbeat thread"""
        if self._heartbeat_stop:
            self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
    
    def create_savepoint(self):
        """Create rich savepoint with epistemic metadata"""
        savepoint_id = generate_id()
        
        # Extract epistemic metadata from state
        # (User can add via state["_savepoint_metadata"])
        metadata = self._state.variables.get("_savepoint_metadata", {})
        
        self.engine.journal.append(SavepointCreatedEvent(
            event_id=generate_id(),
            workflow_id=self.workflow_id,
            timestamp=utcnow(),
            savepoint_id=savepoint_id,
            step_number=self._state.step_number,
            goal_summary=metadata.get("goal_summary", ""),
            current_hypotheses=metadata.get("hypotheses", []),
            open_questions=metadata.get("questions", []),
            decision_log=metadata.get("decisions", []),
            next_step=metadata.get("next_step", ""),
            snapshot_ref=""  # Filled by snapshot store logic if we integrate it, or left empty
        ))
