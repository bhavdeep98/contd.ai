"""
Persistence layer for event sourcing and state management.
"""
from .journal import EventJournal, EventCorruptionError
from .snapshots import SnapshotStore, SnapshotNotFoundError, SnapshotCorruptionError
from .leases import LeaseManager, Lease, LeaseError, LeaseNotHeldError, StaleLeaseError
from .adapters import PostgresAdapter, PostgresConfig, S3Adapter, S3Config

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
    # Adapters
    "PostgresAdapter",
    "PostgresConfig",
    "S3Adapter",
    "S3Config",
]
