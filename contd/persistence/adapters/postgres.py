"""
Postgres adapter with connection pooling and WAL support.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

try:
    import psycopg2
    from psycopg2 import pool, extras  # noqa: F401
    from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger(__name__)


@dataclass
class PostgresConfig:
    """Postgres connection configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "contd"
    user: str = "contd"
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10
    # WAL settings
    synchronous_commit: str = "on"  # 'on', 'off', 'local', 'remote_write'


class PostgresAdapter:
    """
    Postgres adapter with:
    - Connection pooling
    - WAL-based durability
    - Atomic operations with proper isolation
    - Fencing token support
    """

    def __init__(self, config: PostgresConfig = None):
        if not HAS_PSYCOPG2:
            raise ImportError(
                "psycopg2 is required. Install with: pip install psycopg2-binary"
            )

        self.config = config or PostgresConfig()
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._initialized = False

    def initialize(self):
        """Initialize connection pool."""
        if self._initialized:
            return

        self._pool = pool.ThreadedConnectionPool(
            minconn=self.config.min_connections,
            maxconn=self.config.max_connections,
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
        )
        self._initialized = True
        logger.info(
            f"Postgres pool initialized: {self.config.host}:{self.config.port}/{self.config.database}"
        )

    def close(self):
        """Close all connections."""
        if self._pool:
            self._pool.closeall()
            self._initialized = False

    @contextmanager
    def connection(self, isolation_level=None):
        """Get a connection from the pool."""
        if not self._initialized:
            self.initialize()

        conn = self._pool.getconn()
        try:
            if isolation_level:
                conn.set_isolation_level(isolation_level)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def cursor(self, isolation_level=None):
        """Get a cursor with automatic connection management."""
        with self.connection(isolation_level) as conn:
            cur = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                yield cur
            finally:
                cur.close()

    def execute(self, query: str, *args) -> Any:
        """
        Execute a query with parameters.
        Converts ? placeholders to %s for psycopg2.
        Returns the result for RETURNING clauses.
        """
        # Convert ? to %s placeholder style
        query = query.replace("?", "%s")

        with self.cursor() as cur:
            cur.execute(query, args)

            # Check if this is a RETURNING query
            if "RETURNING" in query.upper():
                row = cur.fetchone()
                if row:
                    # Return first value if single column
                    values = list(row.values())
                    return values[0] if len(values) == 1 else values

            return cur.rowcount

    def execute_with_wal_sync(self, query: str, *args) -> Any:
        """
        Execute with synchronous WAL commit for durability.
        Critical for event journal appends.
        """
        query = query.replace("?", "%s")

        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                # Ensure synchronous commit for this transaction
                cur.execute(
                    f"SET synchronous_commit = '{self.config.synchronous_commit}'"
                )
                cur.execute(query, args)

                result = None
                if "RETURNING" in query.upper():
                    row = cur.fetchone()
                    if row:
                        values = list(row.values())
                        result = values[0] if len(values) == 1 else values
                else:
                    result = cur.rowcount

                return result
            finally:
                cur.close()

    def query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return all rows as dicts."""
        query = query.replace("?", "%s")

        with self.cursor() as cur:
            cur.execute(query, args)
            return cur.fetchall()

    def query_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return first row."""
        query = query.replace("?", "%s")

        with self.cursor() as cur:
            cur.execute(query, args)
            return cur.fetchone()

    def query_val(self, query: str, *args) -> Any:
        """Execute a query and return single scalar value."""
        query = query.replace("?", "%s")

        with self.cursor() as cur:
            cur.execute(query, args)
            row = cur.fetchone()
            if row:
                return list(row.values())[0]
            return None

    def execute_atomic(self, queries: List[Tuple[str, tuple]]) -> List[Any]:
        """
        Execute multiple queries atomically in a single transaction.
        Used for operations that must succeed or fail together.
        """
        results = []

        with self.connection(ISOLATION_LEVEL_SERIALIZABLE) as conn:
            cur = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                for query, args in queries:
                    query = query.replace("?", "%s")
                    cur.execute(query, args)

                    if "RETURNING" in query.upper():
                        row = cur.fetchone()
                        if row:
                            values = list(row.values())
                            results.append(values[0] if len(values) == 1 else values)
                        else:
                            results.append(None)
                    else:
                        results.append(cur.rowcount)
            finally:
                cur.close()

        return results

    def create_workflow_sequence(self, workflow_id: str):
        """Create a sequence for workflow event ordering."""
        import re
        # Validate workflow_id to prevent SQL injection
        if not re.match(r'^[a-zA-Z0-9_-]+$', workflow_id):
            raise ValueError(f"Invalid workflow_id format: {workflow_id}")
        
        seq_name = f"event_seq_{workflow_id.replace('-', '_')}"

        with self.cursor() as cur:
            # Use IF NOT EXISTS for idempotency
            cur.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")

    def get_next_event_seq(self, workflow_id: str) -> int:
        """Get next event sequence number for a workflow."""
        import re
        # Validate workflow_id to prevent SQL injection
        if not re.match(r'^[a-zA-Z0-9_-]+$', workflow_id):
            raise ValueError(f"Invalid workflow_id format: {workflow_id}")
        
        seq_name = f"event_seq_{workflow_id.replace('-', '_')}"

        # Ensure sequence exists
        self.create_workflow_sequence(workflow_id)

        return self.query_val(f"SELECT nextval('{seq_name}')")

    def ensure_schema(self):
        """Ensure all required tables exist."""
        import os

        schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")

        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema_sql = f.read()

            with self.connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(schema_sql)
                    logger.info("Schema initialized successfully")
                except psycopg2.errors.DuplicateTable:
                    # Tables already exist
                    pass
                finally:
                    cur.close()
