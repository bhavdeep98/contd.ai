"""
Persistence adapters for pluggable storage backends.
"""

from .postgres import PostgresAdapter, PostgresConfig
from .s3 import S3Adapter, S3Config, IntegrityError, KeyNotFoundError
from .sqlite import SQLiteAdapter, SQLiteConfig
from .redis import RedisAdapter, RedisConfig, CachedSnapshotStore
from .factory import (
    StorageFactory,
    StorageConfig,
    BackendType,
    create_storage,
    create_production_storage,
    create_dev_storage,
)

__all__ = [
    # Postgres
    "PostgresAdapter",
    "PostgresConfig",
    # S3
    "S3Adapter",
    "S3Config",
    "IntegrityError",
    "KeyNotFoundError",
    # SQLite
    "SQLiteAdapter",
    "SQLiteConfig",
    # Redis
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
