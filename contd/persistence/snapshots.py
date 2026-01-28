"""
Snapshot store with hybrid Postgres + S3 storage and integrity validation.
"""

from typing import Any, Optional, Tuple, List
from datetime import datetime
import hashlib
import uuid
from ..models.state import WorkflowState
from ..models.serialization import serialize, deserialize


def utcnow():
    return datetime.utcnow()


def generate_id():
    return str(uuid.uuid4())


class SnapshotStore:
    """
    Hybrid snapshot storage:
    - Small states (<100KB) stored inline in Postgres
    - Large states stored in S3 with reference in Postgres
    - Checksum validation on all reads
    - Automatic cleanup of old snapshots
    """

    INLINE_THRESHOLD = 100_000  # 100KB
    MAX_SNAPSHOTS_PER_WORKFLOW = 10  # Keep last N snapshots

    def __init__(self, db: Any, s3: Any):
        self.db = db
        self.s3 = s3

    def save(self, state: WorkflowState, last_event_seq: int) -> str:
        """
        Save snapshot atomically with checksum.
        Returns: snapshot_id
        """
        snapshot_id = generate_id()
        serialized = serialize(state)
        checksum = self._compute_checksum(serialized)

        if len(serialized) < self.INLINE_THRESHOLD:
            self._save_inline(snapshot_id, state, last_event_seq, serialized, checksum)
        else:
            self._save_to_s3(snapshot_id, state, last_event_seq, serialized, checksum)

        # Cleanup old snapshots (async in production)
        self._cleanup_old_snapshots(state.workflow_id, state.org_id)

        return snapshot_id

    def _save_inline(
        self,
        snapshot_id: str,
        state: WorkflowState,
        last_event_seq: int,
        serialized: str,
        checksum: str,
    ):
        """Store small state inline in Postgres."""
        self.db.execute(
            """
            INSERT INTO snapshots
            (snapshot_id, workflow_id, org_id, step_number, last_event_seq, 
             state_inline, state_checksum, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            snapshot_id,
            state.workflow_id,
            state.org_id,
            state.step_number,
            last_event_seq,
            serialized,
            checksum,
            utcnow(),
        )

    def _save_to_s3(
        self,
        snapshot_id: str,
        state: WorkflowState,
        last_event_seq: int,
        serialized: str,
        checksum: str,
    ):
        """Store large state in S3 with reference in Postgres."""
        s3_key = f"snapshots/{state.org_id}/{state.workflow_id}/{snapshot_id}.json"

        # Store in S3 with checksum metadata
        self.s3.put(
            s3_key,
            serialized,
            metadata={
                "workflow_id": state.workflow_id,
                "step_number": str(state.step_number),
                "last_event_seq": str(last_event_seq),
            },
        )

        # Store reference in Postgres
        self.db.execute(
            """
            INSERT INTO snapshots
            (snapshot_id, workflow_id, org_id, step_number, last_event_seq,
             state_s3_key, state_checksum, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            snapshot_id,
            state.workflow_id,
            state.org_id,
            state.step_number,
            last_event_seq,
            s3_key,
            checksum,
            utcnow(),
        )

    def load(self, snapshot_id: str) -> WorkflowState:
        """Load and validate snapshot by ID."""
        row = self._query_snapshot(snapshot_id)

        if not row:
            raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")

        return self._load_and_validate(row)

    def _query_snapshot(self, snapshot_id: str) -> Optional[dict]:
        """Query snapshot metadata from Postgres."""
        result = self.db.query(
            """
            SELECT snapshot_id, state_inline, state_s3_key, state_checksum
            FROM snapshots WHERE snapshot_id = ?
        """,
            snapshot_id,
        )

        if not result:
            return None

        return result[0] if isinstance(result, list) else result

    def _load_and_validate(self, row: dict) -> WorkflowState:
        """Load state data and validate checksum."""
        if row.get("state_inline"):
            serialized = row["state_inline"]
        elif row.get("state_s3_key"):
            serialized = self.s3.get(row["state_s3_key"])
        else:
            raise SnapshotCorruptionError(f"Snapshot {row['snapshot_id']} has no data")

        # Validate checksum
        actual_checksum = self._compute_checksum(serialized)
        if actual_checksum != row["state_checksum"]:
            raise SnapshotCorruptionError(
                f"Snapshot {row['snapshot_id']} corrupted: "
                f"expected={row['state_checksum']}, actual={actual_checksum}"
            )

        return deserialize(serialized, cls=WorkflowState)

    def get_latest(
        self, workflow_id: str, org_id: str = "default"
    ) -> Tuple[Optional[WorkflowState], int]:
        """
        Get the most recent snapshot for a workflow.
        Returns: (state, last_event_seq) or (None, -1) if no snapshot exists
        """
        result = self.db.query(
            """
            SELECT snapshot_id, last_event_seq, state_inline, state_s3_key, state_checksum
            FROM snapshots
            WHERE workflow_id = ? AND org_id = ?
            ORDER BY last_event_seq DESC
            LIMIT 1
        """,
            workflow_id,
            org_id,
        )

        if not result:
            return None, -1

        row = result[0] if isinstance(result, list) else result
        state = self._load_and_validate(row)
        return state, row["last_event_seq"]

    def get_at_seq(
        self, workflow_id: str, org_id: str, target_seq: int
    ) -> Tuple[Optional[WorkflowState], int]:
        """
        Get the snapshot at or before a specific event sequence.
        Useful for point-in-time recovery.
        """
        result = self.db.query(
            """
            SELECT snapshot_id, last_event_seq, state_inline, state_s3_key, state_checksum
            FROM snapshots
            WHERE workflow_id = ? AND org_id = ? AND last_event_seq <= ?
            ORDER BY last_event_seq DESC
            LIMIT 1
        """,
            workflow_id,
            org_id,
            target_seq,
        )

        if not result:
            return None, -1

        row = result[0] if isinstance(result, list) else result
        state = self._load_and_validate(row)
        return state, row["last_event_seq"]

    def list_snapshots(self, workflow_id: str, org_id: str = "default") -> List[dict]:
        """List all snapshots for a workflow."""
        return self.db.query(
            """
            SELECT snapshot_id, step_number, last_event_seq, created_at
            FROM snapshots
            WHERE workflow_id = ? AND org_id = ?
            ORDER BY last_event_seq DESC
        """,
            workflow_id,
            org_id,
        )

    def delete(self, snapshot_id: str):
        """Delete a snapshot and its S3 data if applicable."""
        row = self._query_snapshot(snapshot_id)

        if row and row.get("state_s3_key"):
            try:
                self.s3.delete(row["state_s3_key"])
            except Exception:
                pass  # S3 deletion is best-effort

        self.db.execute("DELETE FROM snapshots WHERE snapshot_id = ?", snapshot_id)

    def _cleanup_old_snapshots(self, workflow_id: str, org_id: str):
        """Remove old snapshots beyond retention limit."""
        # Get snapshots to delete (use LIMIT with OFFSET for SQLite compatibility)
        old_snapshots = self.db.query(
            """
            SELECT snapshot_id, state_s3_key
            FROM snapshots
            WHERE workflow_id = ? AND org_id = ?
            ORDER BY last_event_seq DESC
            LIMIT -1 OFFSET ?
        """,
            workflow_id,
            org_id,
            self.MAX_SNAPSHOTS_PER_WORKFLOW,
        )

        for row in old_snapshots or []:
            r = row if isinstance(row, dict) else dict(row)
            if r.get("state_s3_key"):
                try:
                    self.s3.delete(r["state_s3_key"])
                except Exception:
                    pass

            self.db.execute(
                "DELETE FROM snapshots WHERE snapshot_id = ?", r["snapshot_id"]
            )

    def _compute_checksum(self, data: str) -> str:
        """Compute SHA256 checksum."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


class SnapshotNotFoundError(Exception):
    """Raised when a snapshot is not found."""

    pass


class SnapshotCorruptionError(Exception):
    """Raised when snapshot checksum validation fails."""

    pass
