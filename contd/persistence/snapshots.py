from typing import Any, Optional, Tuple
from datetime import datetime
import json
import hashlib
import uuid
from ..models.state import WorkflowState
from ..models.serialization import serialize, deserialize

def utcnow():
    return datetime.utcnow()

def generate_id():
    return str(uuid.uuid4())

class SnapshotStore:
    INLINE_THRESHOLD = 100_000  # 100KB
    
    def __init__(self, db: Any, s3: Any):
        self.db = db
        self.s3 = s3
    
    def save(self, state: WorkflowState, last_event_seq: int) -> str:
        """
        Save snapshot atomically.
        Returns: snapshot_id
        """
        snapshot_id = generate_id()
        serialized = serialize(state)
        # Checksum logic
        checksum = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        
        if len(serialized) < self.INLINE_THRESHOLD:
            # Store inline
            self.db.execute("""
                INSERT INTO snapshots
                (snapshot_id, workflow_id, org_id, step_number, last_event_seq, 
                 state_inline, state_checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, snapshot_id, state.workflow_id, state.org_id, state.step_number, 
                 last_event_seq, serialized, checksum, utcnow())
        else:
            # Store in S3
            s3_key = f"snapshots/{state.workflow_id}/{snapshot_id}.bin"
            self.s3.put(s3_key, serialized)
            
            self.db.execute("""
                INSERT INTO snapshots
                (snapshot_id, workflow_id, org_id, step_number, last_event_seq,
                 state_s3_key, state_checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, snapshot_id, state.workflow_id, state.org_id, state.step_number,
                 last_event_seq, s3_key, checksum, utcnow())
        
        return snapshot_id
    
    def load(self, snapshot_id: str) -> WorkflowState:
        """Load and validate snapshot"""
        row = self.db.query("""
            SELECT state_inline, state_s3_key, state_checksum
            FROM snapshots WHERE snapshot_id = ?
        """, snapshot_id)
        
        # Determine how query returns results (list of dicts, or scalar if row access? 
        # Usually tuple or dict. Assuming dict-like row or object)
        if hasattr(row, 'state_inline'): # Object like
            r = row
        elif isinstance(row, list) and row: # List of rows
            r = row[0]
        else: # row itself might be the dict/tuple
            r = row

        if r['state_inline']:
            serialized = r['state_inline']
        else:
            serialized = self.s3.get(r['state_s3_key'])
        
        # Validate checksum
        if hashlib.sha256(serialized.encode('utf-8')).hexdigest() != r['state_checksum']:
            raise Exception(f"Snapshot {snapshot_id} corrupted")
        
        return deserialize(serialized, cls=WorkflowState)
    
    def get_latest(self, workflow_id: str, org_id: str = "default") -> Tuple[Optional[WorkflowState], int]:
        """
        Returns: (state, last_event_seq)
        """
        row = self.db.query("""
            SELECT snapshot_id, last_event_seq
            FROM snapshots
            WHERE workflow_id = ? AND org_id = ?
            ORDER BY last_event_seq DESC
            LIMIT 1
        """, workflow_id, org_id)
        
        if not row:
            return None, -1
        
        # Normalize row access
        r = row[0] if isinstance(row, list) else row
        
        state = self.load(r['snapshot_id'])
        return state, r['last_event_seq']
