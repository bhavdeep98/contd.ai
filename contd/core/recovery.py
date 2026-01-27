from typing import Any, List
from ..models.state import WorkflowState
from ..models.events import StepCompletedEvent
from ..models.serialization import apply_delta
from ..persistence.journal import EventJournal
from ..persistence.snapshots import SnapshotStore
from datetime import datetime

class HybridRecovery:
    def __init__(self, journal: EventJournal, snapshots: SnapshotStore):
        self.journal = journal
        self.snapshots = snapshots

    def restore(self, workflow_id: str) -> WorkflowState:
        """
        Deterministic restore from (snapshot + event replay)
        """
        # 1. Load latest snapshot
        state, last_event_seq = self.snapshots.get_latest(workflow_id)
        
        if state is None:
            # No snapshot: full replay from genesis
            # Assuming genesis creates initial state or we return None/Initial
            # Spec called _restore_from_genesis(workflow_id)
            return self._restore_from_genesis(workflow_id)
        
        # 2. Get events after snapshot (ordered by event_seq)
        events = self.journal.get_events(
            workflow_id,
            after_seq=last_event_seq,
            order_by="event_seq ASC"
        )
        
        # 3. Replay events deterministically
        for event in events:
            if isinstance(event, StepCompletedEvent):
                # Validate checksum before apply
                # Note: Validation requires the checksum which might not be on the object 
                # if not retrieved. Assuming EventJournal might ensure integrity or we skip deep check here
                if not self._validate_event(event):
                    raise Exception(f"Event {event.event_id} corrupted")
                
                # Apply delta (JSON Patch)
                state = self._apply_delta(state, event.state_delta)
        
        # 4. Validate final checksum
        if not self._validate_state(state):
            raise Exception(f"Restored state corrupted for {workflow_id}")
        
        return state
    
    def _restore_from_genesis(self, workflow_id: str) -> WorkflowState:
        # Create initial empty state
        # Usually workflow_started event holds initial params.
        # We need to fetch ALL events.
        events = self.journal.get_events(workflow_id, after_seq=-1)
        if not events:
            # Raise or return default? 
            # If no events, workflow doesn't exist.
            raise Exception(f"Workflow {workflow_id} not found")
        
        # Initialize state from first event or default
        state = WorkflowState(
            workflow_id=workflow_id,
            step_number=0,
            variables={},
            metadata={},
            version="1.0",
            checksum=""
        )
        
        for event in events:
            if isinstance(event, StepCompletedEvent):
                 # Apply delta
                 state = self._apply_delta(state, event.state_delta)
        
        return state

    def _apply_delta(self, state: WorkflowState, delta: List[dict]) -> WorkflowState:
        """
        Apply JSON Patch (RFC 6902) operations
        """
        return apply_delta(state, delta)
        
    def _validate_event(self, event: Any) -> bool:
        # Placeholder: Real validation would require checking stored checksum against computed checksum of payload.
        # Since Event object here doesn't have checksum field (it's in DB), we assume true
        # unless we fetch checksum with event.
        return True

    def _validate_state(self, state: WorkflowState) -> bool:
        # Recompute checksum
        # For now return True or implement checksum logic
        return True
