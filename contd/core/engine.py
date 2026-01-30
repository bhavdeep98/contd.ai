"""
Core execution engine with lease management and persistence.
"""

import threading
import logging
from typing import Any, Optional, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass

from contd.persistence.journal import EventJournal
from contd.persistence.leases import LeaseManager, Lease
from contd.persistence.snapshots import SnapshotStore
from contd.persistence.adapters.postgres import PostgresAdapter, PostgresConfig
from contd.persistence.adapters.s3 import S3Adapter, S3Config
from contd.core.idempotency import IdempotencyGuard
from contd.core.recovery import HybridRecovery
from contd.models.state import WorkflowState

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.utcnow()


@dataclass
class EngineConfig:
    """Configuration for the execution engine."""

    postgres: PostgresConfig = None
    s3: S3Config = None
    # Snapshot policy
    snapshot_interval: int = 10  # Snapshot every N steps
    snapshot_on_complete: bool = True
    # Use mock adapters for testing
    use_mocks: bool = False


class ExecutionEngine:
    """
    Core execution engine providing:
    - Lease-based workflow ownership
    - Event sourcing with WAL durability
    - Hybrid snapshot + replay recovery
    - Idempotent step execution
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()

        # Initialize adapters
        if self.config.use_mocks:
            self.db = MockDB(self.config.postgres)
            self.s3 = MockS3(self.config.s3)
        else:
            self.db = PostgresAdapter(self.config.postgres or PostgresConfig())
            self.s3 = S3Adapter(self.config.s3 or S3Config())

        # Initialize core components
        self.journal = EventJournal(self.db)
        self.snapshots = SnapshotStore(self.db, self.s3)
        self.lease_manager = LeaseManager(self.db)
        self.idempotency = IdempotencyGuard(self.db, self.snapshots)
        self.recovery = HybridRecovery(self.journal, self.snapshots)

        self._initialized = False

    def initialize(self):
        """Initialize database connections and schema."""
        if self._initialized:
            return

        if not self.config.use_mocks:
            self.db.initialize()
            self.s3.initialize()
            # Optionally ensure schema exists
            # self.db.ensure_schema()

        self._initialized = True
        logger.info("ExecutionEngine initialized")

    @classmethod
    def get_instance(cls, config: EngineConfig = None) -> "ExecutionEngine":
        """Get singleton instance of the engine."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = ExecutionEngine(config)
            return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance.close()
            cls._instance = None

    def close(self):
        """Close all connections."""
        if hasattr(self.db, "close"):
            self.db.close()
        self._initialized = False

    def restore(self, workflow_id: str, org_id: str) -> Tuple[WorkflowState, int]:
        """
        Restore workflow state from persistence.

        Returns:
            Tuple of (state, last_event_seq)
        """
        return self.recovery.restore(workflow_id, org_id)

    def restore_with_context(
        self, workflow_id: str, org_id: str
    ) -> Tuple[WorkflowState, int, dict]:
        """
        Restore workflow state AND reasoning context from persistence.

        Returns:
            Tuple of (state, last_event_seq, context_dict)

        The context_dict contains annotations, digests, and undigested
        reasoning — raw materials for the developer to reconstruct
        agent context after a crash.
        """
        return self.recovery.restore_with_context(workflow_id, org_id)

    def acquire_lease(
        self, workflow_id: str, owner_id: str, org_id: str = "default"
    ) -> Optional[Lease]:
        """
        Acquire exclusive lease on a workflow.

        Returns:
            Lease if acquired, None if held by another
        """
        return self.lease_manager.acquire(workflow_id, owner_id, org_id)

    def release_lease(self, lease: Lease):
        """Release a workflow lease."""
        self.lease_manager.release(lease)

    def maybe_snapshot(self, state: WorkflowState, last_event_seq: int):
        """
        Create snapshot if policy conditions are met.

        Default policy: snapshot every N steps.
        """
        if state.step_number % self.config.snapshot_interval == 0:
            self.snapshots.save(state, last_event_seq)
            logger.debug(f"Created snapshot at step {state.step_number}")

    def complete_workflow(
        self, workflow_id: str, state: WorkflowState, last_event_seq: int
    ):
        """
        Mark workflow as completed.
        Creates final snapshot if configured.
        """
        if self.config.snapshot_on_complete:
            self.snapshots.save(state, last_event_seq)

        # Could also append WorkflowCompletedEvent here
        logger.info(f"Workflow completed: {workflow_id}")

    def get_workflow_status(self, workflow_id: str, org_id: str = "default") -> dict:
        """Get current status of a workflow."""
        lease = self.lease_manager.get_current_lease(workflow_id, org_id)
        event_count = self.journal.get_event_count(workflow_id, org_id)
        snapshots = self.snapshots.list_snapshots(workflow_id, org_id)

        return {
            "workflow_id": workflow_id,
            "org_id": org_id,
            "has_lease": lease is not None,
            "lease_owner": lease.owner_id if lease else None,
            "lease_expires": lease.expires_at if lease else None,
            "event_count": event_count,
            "snapshot_count": len(snapshots),
            "latest_snapshot_step": snapshots[0]["step_number"] if snapshots else None,
        }


class MockDB:
    """
    In-memory mock database for testing.
    Implements the same interface as PostgresAdapter.
    """

    def __init__(self, config=None):
        self.config = config
        self.lock = threading.Lock()
        self.tables: Dict[str, list] = {
            "events": [],
            "workflow_leases": [],
            "step_attempts": [],
            "completed_steps": [],
            "snapshots": [],
        }
        self.sequences: Dict[str, int] = {}

    def initialize(self):
        pass

    def close(self):
        pass

    def execute(self, sql: str, *args) -> Any:
        """Execute SQL (mock implementation)."""
        sql_lower = sql.lower()

        with self.lock:
            # Handle RETURNING clause
            if "returning" in sql_lower:
                if "fencing_token" in sql_lower:
                    return 1
                if "attempt_id" in sql_lower:
                    return args[3] if len(args) > 3 else 1

            # Handle INSERT
            if "insert into" in sql_lower:
                table = self._extract_table(sql)
                if table:
                    self.tables.setdefault(table, []).append(args)
                return 1

            # Handle UPDATE
            if "update" in sql_lower:
                return 1

            # Handle DELETE
            if "delete" in sql_lower:
                return 1

        return None

    def execute_with_wal_sync(self, sql: str, *args) -> Any:
        """WAL sync is a no-op for mock."""
        return self.execute(sql, *args)

    def query(self, sql: str, *args) -> list:
        """Query (mock returns empty or minimal data)."""
        return []

    def query_one(self, sql: str, *args) -> Optional[dict]:
        """Query single row."""
        return None

    def query_val(self, sql: str, *args) -> Any:
        """Query single value."""
        if "nextval" in sql.lower():
            # Extract sequence name and increment
            seq_name = args[0] if args else "default"
            with self.lock:
                self.sequences.setdefault(seq_name, 0)
                self.sequences[seq_name] += 1
                return self.sequences[seq_name]
        if "max" in sql.lower():
            return 0
        if "count" in sql.lower():
            return 0
        return None

    def get_next_event_seq(self, workflow_id: str) -> int:
        """Get next event sequence."""
        with self.lock:
            self.sequences.setdefault(workflow_id, 0)
            self.sequences[workflow_id] += 1
            return self.sequences[workflow_id]

    def _extract_table(self, sql: str) -> Optional[str]:
        """Extract table name from SQL."""
        sql_lower = sql.lower()
        if "insert into" in sql_lower:
            parts = sql_lower.split("insert into")[1].strip().split()
            if parts:
                return parts[0].strip("(")
        return None


class MockS3:
    """
    In-memory mock S3 for testing.
    Implements the same interface as S3Adapter.
    """

    def __init__(self, config=None):
        self.config = config
        self.storage: Dict[str, str] = {}
        self.metadata: Dict[str, dict] = {}

    def initialize(self):
        pass

    def put(self, key: str, data: str, metadata: dict = None) -> str:
        """Store data."""
        import hashlib

        self.storage[key] = data
        self.metadata[key] = metadata or {}
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, key: str, expected_checksum: str = None) -> str:
        """Retrieve data."""
        if key not in self.storage:
            raise KeyError(f"Key not found: {key}")
        return self.storage[key]

    def delete(self, key: str):
        """Delete data."""
        self.storage.pop(key, None)
        self.metadata.pop(key, None)

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self.storage

    def list_keys(self, prefix: str) -> list:
        """List keys with prefix."""
        return [k for k in self.storage.keys() if k.startswith(prefix)]
