from datetime import datetime
from typing import Any, List, Optional
import json
import hashlib
from ..models.events import BaseEvent, EventType
from ..core.version import __version__ # Assuming this exists or define it

def utcnow():
    return datetime.utcnow()

class EventJournal:
    def __init__(self, db: Any):
        self.db = db

    def append(self, event: BaseEvent) -> int:
        """
        Append event with atomic sequence assignment.
        Returns: event_seq
        """
        event_seq = self._allocate_seq(event.workflow_id)
        
        # Create Canonical Payload
        # We need to serialize the event excluding fields that aren't part of the payload 
        # or are computed (like seq, if it was in event). 
        # The spec says "checksum = SHA256 of canonical payload".
        # payload is JSONB `event`. 
        # Assuming `event` object is what we store in payload.
        # Use simple json dump of the event dataclass.
        
        from dataclasses import asdict
        payload = asdict(event)
        canonical_str = json.dumps(payload, sort_keys=True)
        checksum = self._compute_checksum(canonical_str)
        
        schema_version = getattr(event, 'schema_version', '1.0')
        producer_version = "0.0.1" # Using fixed for now or import __version__
        
        self.db.execute("""
            INSERT INTO events (
                event_id, workflow_id, event_seq, event_type,
                payload, timestamp, schema_version, producer_version, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, 
            event.event_id,
            event.workflow_id,
            event_seq,
            payload.get('event_type') or 'unknown', # Assuming event_type field or fallback
            canonical_str,
            event.timestamp,
            schema_version,
            producer_version,
            checksum
        )
        
        return event_seq
    
    def _allocate_seq(self, workflow_id: str) -> int:
        """Atomic sequence allocation"""
        # Option 1: Postgres sequence per workflow (scalable)
        # Assuming adapter handles the dynamic sequence name or we fallback to simpler counter
        # Using atomic UPDATE on a counters table might be safer if dynamic seqs are tricky in this prompt 
        # BUT spec code explicitly showed: "SELECT nextval('event_seq_' || ?)"
        # I will execute strictly as spec, but catch if it fails (spec is directive).
        return self.db.query_val(
            "SELECT nextval('event_seq_' || ?)", 
            workflow_id
        )
        
    def _compute_checksum(self, payload_str: str) -> str:
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        
    def get_events(self, workflow_id: str, after_seq: int = -1, order_by: str = "event_seq ASC") -> List[Any]:
        """
        Retrieve events for replay.
        """
        # Note: Parsing order_by to avoid injection if this were public, but here internal.
        sql = f"""
            SELECT payload, event_type 
            FROM events 
            WHERE workflow_id = ? AND event_seq > ?
            ORDER BY {order_by}
        """
        rows = self.db.query(sql, workflow_id, after_seq)
        
        # Deserialize rows back to Event objects
        # We need a strict deserializer or just return dicts. Spec `HybridRecovery` expects objects (event.state_delta etc.)
        events = []
        for row in rows:
            # Simplification: deserialize based on type.
            # Ideally use a factory.
            event_dict = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
            # Reconstruct object logic here or return dict wrapped
            events.append(self._reconstruct_event(event_dict))
            
        return events

    def _reconstruct_event(self, data: dict):
        # Determine class from event_type and instantiate
        from ..models.events import StepCompletedEvent, StepIntentionEvent, StepFailedEvent, SavepointCreatedEvent
        
        etype = data.get('event_type')
        if etype == EventType.STEP_COMPLETED.value:
            return StepCompletedEvent(**data)
        elif etype == EventType.STEP_INTENTION.value:
            return StepIntentionEvent(**data)
        elif etype == EventType.STEP_FAILED.value:
            return StepFailedEvent(**data)
        elif etype == EventType.SAVEPOINT_CREATED.value:
            return SavepointCreatedEvent(**data)
        elif etype == EventType.WORKFLOW_STARTED.value:
            # Need WorkflowStartedEvent class if it exists? 
            # If not in models/events.py yet, handle gracefully or return BaseEvent
            pass
        return BaseEvent(**data) # Fallback
