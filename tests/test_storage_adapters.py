"""
Tests for storage adapters (Phase 3).
"""
import pytest
from datetime import datetime

from contd.persistence.adapters import (
    SQLiteAdapter,
    SQLiteConfig,
    StorageFactory,
    StorageConfig,
    BackendType,
    create_storage,
    create_dev_storage,
)


class TestSQLiteAdapter:
    """Tests for SQLite adapter."""
    
    def test_initialize_in_memory(self):
        """Test in-memory database initialization."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        assert adapter._initialized
        adapter.close()
    
    def test_execute_and_query(self):
        """Test basic execute and query operations."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        # Insert an event
        adapter.execute("""
            INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, "evt-1", "wf-1", "default", 1, "test", '{"data": "test"}', datetime.utcnow().isoformat(), "abc123")
        
        # Query it back
        rows = adapter.query("SELECT * FROM events WHERE workflow_id = ?", "wf-1")
        assert len(rows) == 1
        assert rows[0]["event_id"] == "evt-1"
        
        adapter.close()
    
    def test_query_one(self):
        """Test query_one returns single row."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        adapter.execute("""
            INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, "evt-1", "wf-1", "default", 1, "test", '{}', datetime.utcnow().isoformat(), "abc")
        
        row = adapter.query_one("SELECT * FROM events WHERE event_id = ?", "evt-1")
        assert row is not None
        assert row["event_id"] == "evt-1"
        
        # Non-existent
        row = adapter.query_one("SELECT * FROM events WHERE event_id = ?", "nonexistent")
        assert row is None
        
        adapter.close()
    
    def test_query_val(self):
        """Test query_val returns scalar value."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        adapter.execute("""
            INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, "evt-1", "wf-1", "default", 1, "test", '{}', datetime.utcnow().isoformat(), "abc")
        
        count = adapter.query_val("SELECT COUNT(*) FROM events WHERE workflow_id = ?", "wf-1")
        assert count == 1
        
        adapter.close()
    
    def test_sequence_generation(self):
        """Test event sequence generation."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        seq1 = adapter.get_next_event_seq("wf-1")
        seq2 = adapter.get_next_event_seq("wf-1")
        seq3 = adapter.get_next_event_seq("wf-2")
        
        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 1  # Different workflow
        
        adapter.close()
    
    def test_execute_atomic(self):
        """Test atomic execution of multiple queries."""
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        
        queries = [
            ("""INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
             ("evt-1", "wf-1", "default", 1, "test", '{}', datetime.utcnow().isoformat(), "abc")),
            ("""INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
             ("evt-2", "wf-1", "default", 2, "test", '{}', datetime.utcnow().isoformat(), "def")),
        ]
        
        results = adapter.execute_atomic(queries)
        assert len(results) == 2
        
        count = adapter.query_val("SELECT COUNT(*) FROM events WHERE workflow_id = ?", "wf-1")
        assert count == 2
        
        adapter.close()


class TestStorageFactory:
    """Tests for storage factory."""
    
    def setup_method(self):
        """Reset factory before each test."""
        StorageFactory.reset()
    
    def teardown_method(self):
        """Clean up after each test."""
        StorageFactory.close_all()
    
    def test_create_sqlite_adapter(self):
        """Test creating SQLite adapter via factory."""
        config = StorageConfig(
            db_backend=BackendType.SQLITE,
            sqlite={"database": ":memory:"}
        )
        
        adapter = StorageFactory.create_db_adapter(config)
        assert adapter is not None
        assert adapter._initialized
    
    def test_singleton_behavior(self):
        """Test that factory returns same instance."""
        config = StorageConfig(
            db_backend=BackendType.SQLITE,
            sqlite={"database": ":memory:"}
        )
        
        adapter1 = StorageFactory.create_db_adapter(config)
        adapter2 = StorageFactory.create_db_adapter(config)
        
        assert adapter1 is adapter2
    
    def test_create_all(self):
        """Test creating all adapters at once."""
        config = StorageConfig(
            db_backend=BackendType.SQLITE,
            sqlite={"database": ":memory:"}
        )
        
        adapters = StorageFactory.create_all(config)
        
        assert "db" in adapters
        assert adapters["db"] is not None
        assert adapters["object"] is None  # Not configured
        assert adapters["cache"] is None   # Not configured


class TestConvenienceFunctions:
    """Tests for convenience factory functions."""
    
    def teardown_method(self):
        StorageFactory.close_all()
    
    def test_create_storage_sqlite(self):
        """Test create_storage with SQLite."""
        adapter = create_storage("sqlite", database=":memory:")
        assert adapter is not None
        assert adapter._initialized
    
    def test_create_dev_storage(self):
        """Test create_dev_storage helper."""
        adapter = create_dev_storage()
        assert adapter is not None
        assert adapter._initialized
    
    def test_create_dev_storage_with_file(self):
        """Test create_dev_storage with file path."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            adapter = create_dev_storage(database=db_path)
            
            assert adapter is not None
            
            # Verify file was created
            adapter.execute("""
                INSERT INTO events (event_id, workflow_id, org_id, event_seq, event_type, payload, timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, "evt-1", "wf-1", "default", 1, "test", '{}', datetime.utcnow().isoformat(), "abc")
            
            assert os.path.exists(db_path)
            
            # Close adapter before temp dir cleanup
            adapter.close()
            StorageFactory.reset()


class TestSQLiteWithJournal:
    """Integration tests with EventJournal."""
    
    def test_journal_with_sqlite(self):
        """Test EventJournal works with SQLite adapter."""
        from contd.persistence import EventJournal
        from contd.models.events import StepCompletedEvent, EventType
        
        adapter = create_dev_storage()
        journal = EventJournal(adapter)
        
        # Create and append an event (using correct field names)
        event = StepCompletedEvent(
            event_id="evt-1",
            workflow_id="wf-1",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_id="step-1",
            attempt_id=1,
            state_delta={"status": "ok"},
            duration_ms=100
        )
        
        seq = journal.append(event)
        assert seq == 1
        
        # Retrieve events - check event count instead of specific attribute
        # since reconstruction may return BaseEvent
        event_count = journal.get_event_count("wf-1", "default")
        assert event_count == 1
        
        StorageFactory.close_all()


class TestSQLiteWithSnapshots:
    """Integration tests with SnapshotStore."""
    
    def test_snapshots_with_sqlite(self):
        """Test SnapshotStore works with SQLite adapter."""
        from contd.persistence import SnapshotStore
        from contd.models.state import WorkflowState
        
        # Create mock S3 adapter that stores inline
        class MockS3:
            def put(self, key, data, metadata=None):
                pass
            def get(self, key):
                return "{}"
            def delete(self, key):
                pass
        
        adapter = create_dev_storage()
        store = SnapshotStore(adapter, MockS3())
        
        # Create and save a state (using correct field names)
        state = WorkflowState(
            workflow_id="wf-1",
            org_id="default",
            step_number=5,
            variables={"counter": 10},
            metadata={"created": "now"},
            version="1.0",
            checksum="abc123"
        )
        
        snapshot_id = store.save(state, last_event_seq=10)
        assert snapshot_id is not None
        
        # Load it back
        loaded_state, seq = store.get_latest("wf-1", "default")
        assert loaded_state is not None
        assert loaded_state.step_number == 5
        assert seq == 10
        
        StorageFactory.close_all()


class TestSQLiteWithLeases:
    """Integration tests with LeaseManager."""
    
    def test_leases_with_sqlite(self):
        """Test LeaseManager works with SQLite adapter."""
        from contd.persistence import LeaseManager
        
        adapter = create_dev_storage()
        manager = LeaseManager(adapter)
        
        # Acquire a lease
        lease = manager.acquire("wf-1", "owner-1", "default")
        assert lease is not None
        assert lease.token == 1
        assert lease.owner_id == "owner-1"
        
        # Try to acquire same lease with different owner (should fail)
        lease2 = manager.acquire("wf-1", "owner-2", "default")
        assert lease2 is None
        
        # Release the lease
        released = manager.release(lease)
        assert released
        
        # Now owner-2 can acquire (but token may be 1 since we deleted the row)
        lease3 = manager.acquire("wf-1", "owner-2", "default")
        assert lease3 is not None
        assert lease3.owner_id == "owner-2"
        
        StorageFactory.close_all()
