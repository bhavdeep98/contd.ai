from typing import Any
from contd.models.state import WorkflowState
from contd.models.events import StepCompletedEvent
from contd.models.serialization import apply_delta


# Placeholder helper since apply_event was not strictly defined but used
def apply_event(state: WorkflowState, event: Any) -> WorkflowState:
    if isinstance(event, StepCompletedEvent):
        return apply_delta(state, event.state_delta)
    # Handle other events if necessary
    return state


class HybridRecoveryStrategy:
    """Snapshot + replay recent events"""

    def __init__(self, journal_store: Any, snapshot_store: Any):
        self.journal = journal_store
        self.snapshots = snapshot_store

    def restore(self, workflow_id: str) -> WorkflowState:
        # 1. Load latest snapshot
        snapshot = self.snapshots.get_latest(workflow_id)
        if not snapshot:
            return self._restore_from_genesis(workflow_id)

        # 2. Get events since snapshot
        events = self.journal.get_since(workflow_id, snapshot.timestamp)

        # 3. Replay events
        state = snapshot.state
        for event in events:
            if isinstance(event, StepCompletedEvent):
                state = apply_delta(state, event.state_delta)

        return state

    def _restore_from_genesis(self, workflow_id: str):
        """Full replay (no snapshot)"""
        events = self.journal.get_all(workflow_id)
        # Assuming initial state creation logic exists
        state = WorkflowState(
            workflow_id=workflow_id,
            step_number=0,
            variables={},
            metadata={},
            version="1.0",
            checksum="",
        )
        for event in events:
            state = apply_event(state, event)
        return state
