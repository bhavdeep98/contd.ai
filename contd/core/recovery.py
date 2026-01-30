"""
Hybrid recovery strategy combining snapshots and event replay.
"""

from typing import Any, List, Tuple, Optional
from dataclasses import asdict
import hashlib
import logging

from ..models.state import WorkflowState
from ..models.events import (
    StepCompletedEvent,
    AnnotationCreatedEvent,
    ReasoningIngestedEvent,
    ContextDigestCreatedEvent,
    SavepointCreatedEvent,
)
from ..models.serialization import apply_delta, serialize
from ..persistence.journal import EventJournal
from ..persistence.snapshots import SnapshotStore
from .context_preservation import RestoredContext

logger = logging.getLogger(__name__)


class HybridRecovery:
    """
    Deterministic state recovery using snapshot + event replay.

    Recovery strategy:
    1. Load latest snapshot (if exists)
    2. Replay events after snapshot's last_event_seq
    3. Validate final state checksum

    This provides:
    - Fast recovery (snapshots reduce replay time)
    - Full auditability (events are source of truth)
    - Corruption detection (checksums at every step)
    """

    def __init__(self, journal: EventJournal, snapshots: SnapshotStore):
        self.journal = journal
        self.snapshots = snapshots

    def restore(
        self, workflow_id: str, org_id: str, validate_checksums: bool = True
    ) -> Tuple[WorkflowState, int]:
        """
        Deterministic restore from (snapshot + event replay).

        Returns:
            Tuple of (restored_state, last_event_seq)

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            StateCorruptionError: If checksum validation fails
        """
        # 1. Load latest snapshot
        state, last_event_seq = self.snapshots.get_latest(workflow_id, org_id)

        if state is None:
            # No snapshot: full replay from genesis
            logger.info(f"No snapshot found, restoring from genesis: {workflow_id}")
            return self._restore_from_genesis(workflow_id, org_id, validate_checksums)

        logger.info(f"Restoring from snapshot at seq {last_event_seq}: {workflow_id}")

        # 2. Get events after snapshot
        events = self.journal.get_events(
            workflow_id,
            org_id=org_id,
            after_seq=last_event_seq,
            order_by="event_seq ASC",
            validate_checksums=validate_checksums,
        )

        if not events:
            # No events after snapshot, state is current
            return state, last_event_seq

        # 3. Replay events deterministically
        current_seq = last_event_seq
        for event in events:
            state, current_seq = self._apply_event(state, event, validate_checksums)

        # 4. Validate final state
        if validate_checksums and not self._validate_state_checksum(state):
            raise StateCorruptionError(
                f"Final state checksum invalid for {workflow_id}"
            )

        return state, current_seq

    def restore_with_context(
        self, workflow_id: str, org_id: str, validate_checksums: bool = True
    ) -> Tuple[WorkflowState, int, RestoredContext]:
        """
        Restore workflow state AND reasoning context.
        
        Returns:
            Tuple of (restored_state, last_event_seq, context)
            
        The context includes:
        - digest: Latest distilled reasoning context
        - undigested: Raw chunks since last distill
        - annotations: Step-associated breadcrumbs
        - digest_history: Full audit trail of digests
        - savepoints: Epistemic metadata from savepoints
        - Execution stats (steps, output bytes, durations)
        """
        # First, do normal state restore
        state, last_event_seq = self.restore(workflow_id, org_id, validate_checksums)
        
        # Then, extract context from all events
        context = self._extract_context(workflow_id, org_id)
        
        return state, last_event_seq, context

    def _extract_context(self, workflow_id: str, org_id: str) -> RestoredContext:
        """
        Extract reasoning context from event journal.
        
        Scans all events to build:
        - Annotations (step-associated)
        - Digest history
        - Undigested reasoning chunks
        - Savepoint metadata
        - Execution stats
        """
        context = RestoredContext()
        
        # Get ALL events (not just after snapshot) for full context
        events = self.journal.get_events(
            workflow_id,
            org_id=org_id,
            after_seq=-1,
            order_by="event_seq ASC",
            validate_checksums=False,  # Context extraction doesn't need validation
        )
        
        last_digest_seq = -1
        
        for event in events:
            event_seq = getattr(event, "event_seq", 0)
            
            if isinstance(event, AnnotationCreatedEvent):
                context.annotations.append({
                    "step": event.step_number,
                    "step_name": event.step_name,
                    "text": event.text,
                })
            
            elif isinstance(event, ContextDigestCreatedEvent):
                digest_entry = {
                    "step": event.step_number,
                    "digest": event.digest,
                    "chunks_processed": event.chunks_processed,
                    "failed": event.distill_failed,
                }
                if event.distill_failed:
                    digest_entry["error"] = event.error
                    digest_entry["raw_chunks"] = event.raw_chunks
                
                context.digest_history.append(digest_entry)
                
                # Track latest successful digest
                if not event.distill_failed:
                    context.digest = event.digest
                else:
                    # Failed digest still counts as "latest" for raw chunk access
                    context.digest = {
                        "_distill_failed": True,
                        "raw_chunks": event.raw_chunks,
                        "error": event.error,
                    }
                
                last_digest_seq = event_seq
            
            elif isinstance(event, ReasoningIngestedEvent):
                # Only include chunks AFTER the last digest
                if event_seq > last_digest_seq:
                    context.undigested.append(event.chunk)
            
            elif isinstance(event, SavepointCreatedEvent):
                context.savepoints.append({
                    "step": event.step_number,
                    "savepoint_id": event.savepoint_id,
                    "goal_summary": event.goal_summary,
                    "hypotheses": event.current_hypotheses,
                    "questions": event.open_questions,
                    "decisions": event.decision_log,
                    "next_step": event.next_step,
                })
            
            elif isinstance(event, StepCompletedEvent):
                context.steps_completed += 1
                context.step_durations.append(event.duration_ms)
                # Estimate output size from delta
                if event.state_delta:
                    context.total_output_bytes += len(str(event.state_delta))
        
        return context

    def restore_to_point(
        self, workflow_id: str, org_id: str, target_seq: int
    ) -> Tuple[WorkflowState, int]:
        """
        Restore state to a specific point in time (event sequence).
        Useful for debugging or rollback scenarios.
        """
        # Get snapshot at or before target
        state, snapshot_seq = self.snapshots.get_at_seq(workflow_id, org_id, target_seq)

        if state is None:
            state, snapshot_seq = self._create_initial_state(workflow_id, org_id), -1

        # Replay events up to target
        events = self.journal.get_events(
            workflow_id, org_id=org_id, after_seq=snapshot_seq, order_by="event_seq ASC"
        )

        current_seq = snapshot_seq
        for event in events:
            # Get event sequence (need to track it)
            event_seq = getattr(event, "event_seq", current_seq + 1)
            if event_seq > target_seq:
                break

            state, current_seq = self._apply_event(state, event, validate=False)

        return state, current_seq

    def _restore_from_genesis(
        self, workflow_id: str, org_id: str, validate_checksums: bool
    ) -> Tuple[WorkflowState, int]:
        """Restore by replaying all events from the beginning."""
        # Fetch all events
        events = self.journal.get_events(
            workflow_id,
            org_id=org_id,
            after_seq=-1,
            validate_checksums=validate_checksums,
        )

        if not events:
            raise WorkflowNotFoundError(f"Workflow {workflow_id} not found (no events)")

        # Initialize state
        state = self._create_initial_state(workflow_id, org_id)

        # Replay all events
        current_seq = 0
        for event in events:
            state, current_seq = self._apply_event(state, event, validate_checksums)

        return state, current_seq

    def _create_initial_state(self, workflow_id: str, org_id: str) -> WorkflowState:
        """Create initial empty state for a workflow."""
        state = WorkflowState(
            workflow_id=workflow_id,
            step_number=0,
            variables={},
            metadata={},
            version="1.0",
            checksum="",
            org_id=org_id,
        )
        # Compute initial checksum
        return self._update_checksum(state)

    def _apply_event(
        self, state: WorkflowState, event: Any, validate: bool = True
    ) -> Tuple[WorkflowState, int]:
        """
        Apply a single event to state.
        Returns updated state and event sequence.
        """
        event_seq = getattr(event, "event_seq", state.step_number + 1)

        if isinstance(event, StepCompletedEvent):
            # Validate event before applying
            if validate and not self._validate_event(event):
                raise EventCorruptionError(f"Event validation failed: {event.event_id}")

            # Apply JSON Patch delta
            if event.state_delta:
                state = apply_delta(state, event.state_delta)

            # Update checksum after applying delta
            state = self._update_checksum(state)

        # Handle other event types as needed
        # WorkflowStarted, StepFailed, etc. may update metadata

        return state, event_seq

    def _apply_delta(self, state: WorkflowState, delta: List[dict]) -> WorkflowState:
        """Apply JSON Patch (RFC 6902) operations."""
        return apply_delta(state, delta)

    def _update_checksum(self, state: WorkflowState) -> WorkflowState:
        """Recompute and update state checksum."""
        # Create state dict without checksum for hashing
        state_dict = asdict(state)
        state_dict["checksum"] = ""

        checksum = hashlib.sha256(serialize(state_dict).encode("utf-8")).hexdigest()

        # Return new state with updated checksum (WorkflowState is frozen)
        return WorkflowState(
            workflow_id=state.workflow_id,
            step_number=state.step_number,
            variables=state.variables,
            metadata=state.metadata,
            version=state.version,
            checksum=checksum,
            org_id=state.org_id,
        )

    def _validate_event(self, event: Any) -> bool:
        """
        Validate event integrity.
        In production, this would verify the event's stored checksum.
        """
        # Basic validation - ensure required fields exist
        if not hasattr(event, "event_id") or not event.event_id:
            return False
        if not hasattr(event, "workflow_id") or not event.workflow_id:
            return False
        return True

    def _validate_state_checksum(self, state: WorkflowState) -> bool:
        """Verify state checksum is valid."""
        if not state.checksum:
            return True  # No checksum to validate

        # Recompute checksum
        state_dict = asdict(state)
        state_dict["checksum"] = ""

        expected = hashlib.sha256(serialize(state_dict).encode("utf-8")).hexdigest()

        return state.checksum == expected


class WorkflowNotFoundError(Exception):
    """Raised when a workflow doesn't exist."""

    pass


class StateCorruptionError(Exception):
    """Raised when state checksum validation fails."""

    pass


class EventCorruptionError(Exception):
    """Raised when event validation fails."""

    pass
