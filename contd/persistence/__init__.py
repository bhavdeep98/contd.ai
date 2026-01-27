"""
Persistence layer for event sourcing and state management.
"""
from .journal import EventJournal, EventCorruptionError
from .snapshots import SnapshotStore, SnapshotNotFoundError, SnapshotCorruptionError
from .leases import LeaseManager, Lease, LeaseError, LeaseNotHeldError, StaleLeaseError
from .adapters import (
    # Postgres
    PostgresAdapter,
    PostgresConfig,
    # S3
    S3Adapter,
    S3Config,
    IntegrityError,
    KeyNotFoundError,
    # SQLite
    SQLiteAdapter,
    SQLiteConfig,
    # Redis
    RedisAdapter,
    RedisConfig,
    CachedSnapshotStore,
    # Factory
    StorageFactory,
    StorageConfig,
    BackendType,
    create_storage,
    create_production_storage,
    create_dev_storage,
)

__all__ = [
    # Journal
    "EventJournal",
    "EventCorruptionError",
    # Snapshots
    "SnapshotStore",
    "SnapshotNotFoundError",
    "SnapshotCorruptionError",
    # Leases
    "LeaseManager",
    "Lease",
    "LeaseError",
    "LeaseNotHeldError",
    "StaleLeaseError",
    # Adapters - Postgres
    "PostgresAdapter",
    "PostgresConfig",
    # Adapters - S3
    "S3Adapter",
    "S3Config",
    "IntegrityError",
    "KeyNotFoundError",
    # Adapters - SQLite
    "SQLiteAdapter",
    "SQLiteConfig",
    # Adapters - Redis
    "RedisAdapter",
    "RedisConfig",
    "CachedSnapshotStore",
    # Factory
    "StorageFactory",
    "StorageConfig",
    "BackendType",
    "create_storage",
    "create_production_storage",
    "create_dev_storage",
]
