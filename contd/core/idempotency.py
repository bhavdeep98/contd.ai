from typing import Any, Optional
from datetime import datetime
from psycopg2 import IntegrityError
from ..persistence.leases import Lease
from ..persistence.snapshots import SnapshotStore
from ..models.state import WorkflowState
import hashlib

def utcnow():
    return datetime.utcnow()

class TooManyAttempts(Exception):
    pass

class IdempotencyGuard:
    def __init__(self, db: Any, snapshots: SnapshotStore):
        self.db = db
        self.snapshots = snapshots

    def allocate_attempt(self, workflow_id: str, step_id: str, lease: Lease) -> int:
        """Atomic attempt allocation"""
        # Insert attempts until one succeeds (handles races)
        for attempt_id in range(1, 100):  # Sanity limit
            try:
                self.db.execute("""
                    INSERT INTO step_attempts 
                    (workflow_id, step_id, attempt_id, started_at, fencing_token)
                    VALUES (?, ?, ?, ?, ?)
                """, workflow_id, step_id, attempt_id, utcnow(), lease.token)
                return attempt_id
            except IntegrityError:
                continue
        
        raise TooManyAttempts(f"{workflow_id}/{step_id}")
    
    def check_completed(self, workflow_id: str, step_id: str) -> Optional[WorkflowState]:
        """Return cached result if already completed"""
        result = self.db.query("""
            SELECT result_snapshot_ref, result_checksum
            FROM completed_steps
            WHERE workflow_id = ? AND step_id = ?
        """, workflow_id, step_id)
        
        if not result:
            return None
            
        r = result[0] if isinstance(result, list) else result
        
        # Load snapshot and validate checksum
        state = self.snapshots.load(r['result_snapshot_ref'])
        if self._compute_checksum(state) != r['result_checksum']:
            raise Exception(f"Corrupted result for {step_id}")
        
        return state
    
    def mark_completed(
        self, 
        workflow_id: str, 
        step_id: str, 
        attempt_id: int,
        state: WorkflowState
    ):
        """Mark step completed (idempotent)"""
        # We need a last_event_seq for saving snapshot. 
        # The spec `SnapshotStore.save` takes `last_event_seq`.
        # However, `IdempotencyGuard` logic in spec snippet calls `self.snapshots.save(state)`.
        # The Spec's SnapshotStore definition actually required `save(state, last_event_seq)`.
        # But in IdempotencyGuard snippet, it just calls `self.snapshots.save(state)`.
        # This implies `last_event_seq` might be inferred or I should grab it from somewhere.
        # But `WorkflowState` doesn't strictly hold `last_event_seq` unless I added it? 
        # It holds `step_number`. 
        # I'll modify `IdempotencyGuard.mark_completed` to accept `last_event_seq` or fetch it?
        # Actually, let's assume `last_event_seq` is needed. I'll add it as argument.
        # Or I'll use `state.step_number` as proxy, but spec differentiated them.
        # I will assume `last_event_seq` is passed or available. 
        # I'll stick to spec snippet signature but add `last_event_seq` to be safe, 
        # or better: `state` needs to track its causal dependency `last_event_seq`.
        # Since I can't change `WorkflowState` too much without deviating, I'll pass it in implementation.
        # Wait, the spec: 
        # `snapshot_ref = self.snapshots.save(state)`
        # `SnapshotStore.save(state, last_event_seq)`
        # Mismatch in spec snippets. I will align them: `mark_completed` should take `last_event_seq` or default 0.
        
        pass # To be filled below with correct signature
        
    def _compute_checksum(self, state: WorkflowState) -> str:
        from ..models.serialization import serialize
        return hashlib.sha256(serialize(state).encode('utf-8')).hexdigest()

    # Re-defining mark_completed to include last_event_seq
    def mark_completed(
        self, 
        workflow_id: str, 
        step_id: str, 
        attempt_id: int,
        state: WorkflowState,
        last_event_seq: int = 0
    ):
        """Mark step completed (idempotent)"""
        snapshot_ref = self.snapshots.save(state, last_event_seq)
        checksum = self._compute_checksum(state)
        
        self.db.execute("""
            INSERT INTO completed_steps 
            (workflow_id, step_id, attempt_id, completed_at, result_snapshot_ref, result_checksum)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (workflow_id, step_id) DO NOTHING
        """, workflow_id, step_id, attempt_id, utcnow(), snapshot_ref, checksum)
