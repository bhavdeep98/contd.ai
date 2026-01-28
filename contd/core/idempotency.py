"""
Idempotency guard for exactly-once step execution.
"""

from typing import Any, Optional
from datetime import datetime
import hashlib
import logging

from ..persistence.leases import Lease
from ..persistence.snapshots import SnapshotStore
from ..models.state import WorkflowState

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.utcnow()


class TooManyAttempts(Exception):
    """Raised when step has exceeded maximum retry attempts."""

    pass


class AttemptConflict(Exception):
    """Raised when attempt allocation conflicts with existing attempt."""

    pass


class IdempotencyGuard:
    """
    Ensures exactly-once execution semantics for workflow steps.

    Provides:
    - Atomic attempt allocation with fencing token validation
    - Cached result lookup for completed steps
    - Checksum validation for result integrity
    """

    MAX_ATTEMPTS = 100  # Sanity limit

    def __init__(self, db: Any, snapshots: SnapshotStore):
        self.db = db
        self.snapshots = snapshots

    def allocate_attempt(
        self, workflow_id: str, step_id: str, lease: Lease, org_id: str = "default"
    ) -> int:
        """
        Atomically allocate the next attempt ID for a step.

        Uses fencing token to ensure only the current lease holder
        can allocate attempts.

        Returns:
            The allocated attempt_id (1-indexed)

        Raises:
            TooManyAttempts: If max attempts exceeded
            AttemptConflict: If allocation fails due to race
        """
        # Validate fencing token first
        if not self._validate_fencing_token(workflow_id, org_id, lease.token):
            raise AttemptConflict(
                f"Stale fencing token for {workflow_id}: token={lease.token}"
            )

        # Try to allocate attempts atomically
        for attempt_id in range(1, self.MAX_ATTEMPTS + 1):
            try:
                result = self.db.execute(
                    """
                    INSERT INTO step_attempts 
                    (workflow_id, org_id, step_id, attempt_id, started_at, fencing_token)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (workflow_id, step_id, attempt_id) DO NOTHING
                    RETURNING attempt_id
                """,
                    workflow_id,
                    org_id,
                    step_id,
                    attempt_id,
                    utcnow(),
                    lease.token,
                )

                if result:
                    logger.debug(
                        f"Allocated attempt: {workflow_id}/{step_id}#{attempt_id}"
                    )
                    return attempt_id

            except Exception as e:
                logger.debug(f"Attempt allocation conflict: {e}")
                continue

        raise TooManyAttempts(
            f"Step {workflow_id}/{step_id} exceeded {self.MAX_ATTEMPTS} attempts"
        )

    def _validate_fencing_token(
        self, workflow_id: str, org_id: str, token: int
    ) -> bool:
        """Validate that the fencing token is current."""
        current_token = self.db.query_val(
            """
            SELECT fencing_token
            FROM workflow_leases
            WHERE workflow_id = ? AND org_id = ?
        """,
            workflow_id,
            org_id,
        )

        return current_token == token

    def check_completed(
        self, workflow_id: str, step_id: str, org_id: str = "default"
    ) -> Optional[WorkflowState]:
        """
        Check if step is already completed and return cached result.

        Returns:
            WorkflowState if step completed, None otherwise

        Raises:
            Exception if stored result is corrupted
        """
        result = self.db.query(
            """
            SELECT result_snapshot_ref, result_checksum
            FROM completed_steps
            WHERE workflow_id = ? AND org_id = ? AND step_id = ?
        """,
            workflow_id,
            org_id,
            step_id,
        )

        if not result:
            return None

        row = result[0] if isinstance(result, list) else result

        if not row.get("result_snapshot_ref"):
            return None

        # Load snapshot and validate checksum
        state = self.snapshots.load(row["result_snapshot_ref"])
        actual_checksum = self._compute_checksum(state)

        if actual_checksum != row["result_checksum"]:
            raise ResultCorruptionError(
                f"Corrupted result for {workflow_id}/{step_id}: "
                f"expected={row['result_checksum']}, actual={actual_checksum}"
            )

        logger.debug(f"Found cached result: {workflow_id}/{step_id}")
        return state

    def mark_completed(
        self,
        workflow_id: str,
        step_id: str,
        attempt_id: int,
        state: WorkflowState,
        last_event_seq: int,
        org_id: str = "default",
    ):
        """
        Mark step as completed with result snapshot.

        This operation is idempotent - if the step is already marked
        complete, this is a no-op.
        """
        # Save snapshot
        snapshot_ref = self.snapshots.save(state, last_event_seq)
        checksum = self._compute_checksum(state)

        # Insert completion record (idempotent via ON CONFLICT)
        self.db.execute(
            """
            INSERT INTO completed_steps 
            (workflow_id, org_id, step_id, attempt_id, completed_at, result_snapshot_ref, result_checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (workflow_id, step_id) DO NOTHING
        """,
            workflow_id,
            org_id,
            step_id,
            attempt_id,
            utcnow(),
            snapshot_ref,
            checksum,
        )

        logger.debug(f"Marked completed: {workflow_id}/{step_id}#{attempt_id}")

    def get_attempt_info(
        self, workflow_id: str, step_id: str, org_id: str = "default"
    ) -> dict:
        """Get information about attempts for a step."""
        attempts = self.db.query(
            """
            SELECT attempt_id, started_at, fencing_token
            FROM step_attempts
            WHERE workflow_id = ? AND org_id = ? AND step_id = ?
            ORDER BY attempt_id
        """,
            workflow_id,
            org_id,
            step_id,
        )

        completed = self.db.query(
            """
            SELECT attempt_id, completed_at
            FROM completed_steps
            WHERE workflow_id = ? AND org_id = ? AND step_id = ?
        """,
            workflow_id,
            org_id,
            step_id,
        )

        return {
            "attempts": attempts or [],
            "completed": completed[0] if completed else None,
            "total_attempts": len(attempts) if attempts else 0,
        }

    def _compute_checksum(self, state: WorkflowState) -> str:
        """Compute SHA256 checksum of state."""
        from ..models.serialization import serialize

        return hashlib.sha256(serialize(state).encode("utf-8")).hexdigest()


class ResultCorruptionError(Exception):
    """Raised when a cached step result fails checksum validation."""

    pass
