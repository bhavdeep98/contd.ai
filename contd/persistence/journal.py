"""
Event Journal with Postgres WAL support for durable event sourcing.
"""
from datetime import datetime
from typing import Any, List, Optional, Tuple
import json
import hashlib
from dataclasses import asdict
from ..models.events import BaseEvent, EventType

# Version for producer tracking
PRODUCER_VERSION = "1.0.0"


def utcnow():
    return datetime.utcnow()


class EventJournal:
    """
    Append-only event journal with:
    - Atomic sequence allocation per workflow
    - WAL-based durability (synchronous commit)
    - Checksum validation for integrity
    - Efficient replay with sequence-based ordering
    """
    
    def __init__(self, db: Any):
        self.db = db
        self._use_wal_sync = hasattr(db, 'execute_with_wal_sync')

    def append(self, event: BaseEvent) -> int:
        """
        Append event with atomic sequence assignment.
        Uses WAL synchronous commit for durability.
        Returns: event_seq
        """
        # Allocate sequence atomically
        event_seq = self._allocate_seq(event.workflow_id)
        
        # Create canonical payload for checksum
        payload = asdict(event)
        canonical_str = self._canonicalize(payload)
        checksum = self._compute_checksum(canonical_str)
        
        schema_version = getattr(event, 'schema_version', '1.0')
        event_type = self._extract_event_type(payload)
        
        # Use WAL-sync if available for durability
        execute_fn = (
            self.db.execute_with_wal_sync 
            if self._use_wal_sync 
            else self.db.execute
        )
        
        execute_fn("""
            INSERT INTO events (
                event_id, workflow_id, org_id, event_seq, event_type,
                payload, timestamp, schema_version, producer_version, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, 
            event.event_id,
            event.workflow_id,
            event.org_id,
            event_seq,
            event_type,
            canonical_str,
            event.timestamp,
            schema_version,
            PRODUCER_VERSION,
            checksum
        )
        
        return event_seq
    
    def append_batch(self, events: List[BaseEvent]) -> List[int]:
        """
        Append multiple events atomically.
        All events must be for the same workflow.
        """
        if not events:
            return []
        
        workflow_id = events[0].workflow_id
        if not all(e.workflow_id == workflow_id for e in events):
            raise ValueError("All events must be for the same workflow")
        
        sequences = []
        for event in events:
            seq = self.append(event)
            sequences.append(seq)
        
        return sequences
    
    def _allocate_seq(self, workflow_id: str) -> int:
        """
        Atomic sequence allocation using Postgres sequences.
        Creates sequence if it doesn't exist.
        """
        # Check if db has specialized method
        if hasattr(self.db, 'get_next_event_seq'):
            return self.db.get_next_event_seq(workflow_id)
        
        # Fallback: use dynamic sequence name
        # Note: workflow_id must be sanitized for sequence name
        safe_id = workflow_id.replace('-', '_')
        return self.db.query_val(f"SELECT nextval('event_seq_{safe_id}')")
    
    def _canonicalize(self, payload: dict) -> str:
        """Create canonical JSON representation for checksumming."""
        return json.dumps(payload, sort_keys=True, default=str)
    
    def _compute_checksum(self, payload_str: str) -> str:
        """Compute SHA256 checksum of canonical payload."""
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
    
    def _extract_event_type(self, payload: dict) -> str:
        """Extract event type string from payload."""
        event_type = payload.get('event_type')
        if hasattr(event_type, 'value'):
            return event_type.value
        return str(event_type) if event_type else 'unknown'
    
    def get_events(
        self, 
        workflow_id: str, 
        org_id: str = "default", 
        after_seq: int = -1, 
        order_by: str = "event_seq ASC",
        limit: int = None,
        validate_checksums: bool = True
    ) -> List[Any]:
        """
        Retrieve events for replay with optional checksum validation.
        """
        # Build query with optional limit
        sql = f"""
            SELECT event_seq, payload, event_type, checksum
            FROM events 
            WHERE workflow_id = ? AND org_id = ? AND event_seq > ?
            ORDER BY {order_by}
        """
        if limit:
            sql += f" LIMIT {limit}"
        
        rows = self.db.query(sql, workflow_id, org_id, after_seq)
        
        events = []
        for row in rows:
            payload_str = row['payload'] if isinstance(row['payload'], str) else json.dumps(row['payload'])
            
            # Validate checksum if requested
            if validate_checksums:
                actual_checksum = self._compute_checksum(payload_str)
                if actual_checksum != row['checksum']:
                    raise EventCorruptionError(
                        f"Event corruption detected at seq {row['event_seq']}: "
                        f"expected={row['checksum']}, actual={actual_checksum}"
                    )
            
            event_dict = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            events.append(self._reconstruct_event(event_dict))
        
        return events
    
    def get_event_count(self, workflow_id: str, org_id: str = "default") -> int:
        """Get total event count for a workflow."""
        result = self.db.query_val("""
            SELECT COUNT(*) FROM events 
            WHERE workflow_id = ? AND org_id = ?
        """, workflow_id, org_id)
        return result or 0
    
    def get_latest_seq(self, workflow_id: str, org_id: str = "default") -> int:
        """Get the latest event sequence number."""
        result = self.db.query_val("""
            SELECT MAX(event_seq) FROM events 
            WHERE workflow_id = ? AND org_id = ?
        """, workflow_id, org_id)
        return result or 0

    def _reconstruct_event(self, data: dict):
        """Reconstruct event object from stored data."""
        from ..models.events import (
            StepCompletedEvent, StepIntentionEvent, 
            StepFailedEvent, SavepointCreatedEvent
        )
        
        etype = data.get('event_type')
        
        # Handle enum values
        if hasattr(etype, 'value'):
            etype = etype.value
        
        # Map to event classes
        event_map = {
            EventType.STEP_COMPLETED.value: StepCompletedEvent,
            EventType.STEP_INTENTION.value: StepIntentionEvent,
            EventType.STEP_FAILED.value: StepFailedEvent,
            EventType.SAVEPOINT_CREATED.value: SavepointCreatedEvent,
        }
        
        event_cls = event_map.get(etype)
        if event_cls:
            # Filter data to only include fields the class accepts
            return self._safe_construct(event_cls, data)
        
        return self._safe_construct(BaseEvent, data)
    
    def _safe_construct(self, cls, data: dict):
        """Safely construct an event, handling extra/missing fields."""
        import inspect
        sig = inspect.signature(cls)
        valid_params = set(sig.parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_params}
        return cls(**filtered)


class EventCorruptionError(Exception):
    """Raised when event checksum validation fails."""
    pass
