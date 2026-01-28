"""
SQLite adapter for local development and testing.
"""

import logging
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SQLiteConfig:
    """SQLite connection configuration."""

    database: str = ":memory:"  # Use file path for persistence
    timeout: float = 30.0
    check_same_thread: bool = False
    isolation_level: str = "DEFERRED"


class SQLiteAdapter:
    """
    SQLite adapter for local development with:
    - Thread-safe connection management
    - Compatible interface with PostgresAdapter
    - In-memory or file-based storage
    """

    def __init__(self, config: SQLiteConfig = None):
        self.config = config or SQLiteConfig()
        self._local = threading.local()
        self._initialized = False
        self._schema_created = False
        self._sequences: Dict[str, int] = {}
        self._seq_lock = threading.Lock()

    def initialize(self):
        """Initialize the database and create schema."""
        if self._initialized:
            return

        # Mark as initialized first to prevent recursion
        self._initialized = True

        if not self._schema_created:
            self._ensure_schema()
            self._schema_created = True

        logger.info(f"SQLite initialized: {self.config.database}")

    def close(self):
        """Close all connections."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
        self._initialized = False
        self._schema_created = False

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.config.database,
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
                isolation_level=self.config.isolation_level,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def connection(self, isolation_level=None):
        """Get a connection context."""
        if not self._initialized:
            self.initialize()

        conn = self._conn
        old_level = conn.isolation_level
        try:
            if isolation_level:
                conn.isolation_level = isolation_level
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.isolation_level = old_level

    @contextmanager
    def cursor(self, isolation_level=None):
        """Get a cursor with automatic connection management."""
        with self.connection(isolation_level) as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def execute(self, query: str, *args) -> Any:
        """Execute a query with parameters."""
        query = self._convert_query(query)

        with self.cursor() as cur:
            cur.execute(query, args)

            # Handle RETURNING clause (SQLite 3.35+)
            if "RETURNING" in query.upper():
                row = cur.fetchone()
                if row:
                    return row[0] if len(row) == 1 else list(row)

            return cur.rowcount

    def execute_with_wal_sync(self, query: str, *args) -> Any:
        """Execute with WAL sync (same as execute for SQLite)."""
        return self.execute(query, *args)

    def query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return all rows as dicts."""
        query = self._convert_query(query)

        with self.cursor() as cur:
            cur.execute(query, args)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def query_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return first row."""
        query = self._convert_query(query)

        with self.cursor() as cur:
            cur.execute(query, args)
            row = cur.fetchone()
            return dict(row) if row else None

    def query_val(self, query: str, *args) -> Any:
        """Execute a query and return single scalar value."""
        query = self._convert_query(query)

        with self.cursor() as cur:
            cur.execute(query, args)
            row = cur.fetchone()
            return row[0] if row else None

    def execute_atomic(self, queries: List[Tuple[str, tuple]]) -> List[Any]:
        """Execute multiple queries atomically."""
        results = []

        with self.connection("EXCLUSIVE") as conn:
            cur = conn.cursor()
            try:
                for query, args in queries:
                    query = self._convert_query(query)
                    cur.execute(query, args)

                    if "RETURNING" in query.upper():
                        row = cur.fetchone()
                        results.append(
                            row[0]
                            if row and len(row) == 1
                            else (list(row) if row else None)
                        )
                    else:
                        results.append(cur.rowcount)
            finally:
                cur.close()

        return results

    def _convert_query(self, query: str) -> str:
        """Convert Postgres-style queries to SQLite."""
        # Convert %s to ? placeholders
        query = query.replace("%s", "?")

        return query

    def create_workflow_sequence(self, workflow_id: str):
        """Create a sequence for workflow event ordering (simulated)."""
        with self._seq_lock:
            if workflow_id not in self._sequences:
                self._sequences[workflow_id] = 0

    def get_next_event_seq(self, workflow_id: str) -> int:
        """Get next event sequence number for a workflow."""
        with self._seq_lock:
            if workflow_id not in self._sequences:
                # Check if there are existing events
                max_seq = self.query_val(
                    "SELECT MAX(event_seq) FROM events WHERE workflow_id = ?",
                    workflow_id,
                )
                self._sequences[workflow_id] = max_seq or 0

            self._sequences[workflow_id] += 1
            return self._sequences[workflow_id]

    def _ensure_schema(self):
        """Create required tables."""
        schema = """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'default',
            event_seq INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            schema_version TEXT DEFAULT '1.0',
            producer_version TEXT,
            checksum TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_events_workflow 
        ON events(workflow_id, org_id, event_seq);
        
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'default',
            step_number INTEGER NOT NULL,
            last_event_seq INTEGER NOT NULL,
            state_inline TEXT,
            state_s3_key TEXT,
            state_checksum TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_snapshots_workflow 
        ON snapshots(workflow_id, org_id, last_event_seq DESC);
        
        CREATE TABLE IF NOT EXISTS workflow_leases (
            workflow_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL DEFAULT 'default',
            owner_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            lease_expires_at TEXT NOT NULL,
            fencing_token INTEGER NOT NULL DEFAULT 1,
            heartbeat_at TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_leases_expires 
        ON workflow_leases(lease_expires_at);
        """

        with self.cursor() as cur:
            cur.executescript(schema)

        logger.info("SQLite schema initialized")

    def ensure_schema(self):
        """Public method to ensure schema exists."""
        self._ensure_schema()
