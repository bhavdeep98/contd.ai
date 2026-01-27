"""
Factory pattern for pluggable storage backends.
"""
import logging
from typing import Any, Dict, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Supported backend types."""
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    S3 = "s3"
    REDIS = "redis"


@dataclass
class StorageConfig:
    """
    Unified storage configuration.
    Allows configuring all backends from a single config object.
    """
    # Primary database backend
    db_backend: BackendType = BackendType.SQLITE
    
    # Object storage backend (for large snapshots)
    object_backend: Optional[BackendType] = None
    
    # Cache backend (optional)
    cache_backend: Optional[BackendType] = None
    
    # Backend-specific configs
    postgres: Optional[Dict[str, Any]] = None
    sqlite: Optional[Dict[str, Any]] = None
    s3: Optional[Dict[str, Any]] = None
    redis: Optional[Dict[str, Any]] = None
    
    # Feature flags
    enable_caching: bool = False
    enable_large_snapshot_offload: bool = True


class StorageFactory:
    """
    Factory for creating storage adapters.
    
    Supports:
    - Pluggable backends (Postgres, SQLite, S3, Redis)
    - Lazy initialization
    - Singleton instances per configuration
    - Graceful fallbacks
    """
    
    _instances: Dict[str, Any] = {}
    _adapters: Dict[BackendType, Type] = {}
    
    @classmethod
    def register_adapter(cls, backend_type: BackendType, adapter_class: Type):
        """Register an adapter class for a backend type."""
        cls._adapters[backend_type] = adapter_class
        logger.debug(f"Registered adapter: {backend_type.value} -> {adapter_class.__name__}")
    
    @classmethod
    def _load_default_adapters(cls):
        """Load default adapters if not already registered."""
        if cls._adapters:
            return
        
        # Postgres
        try:
            from .postgres import PostgresAdapter
            cls._adapters[BackendType.POSTGRES] = PostgresAdapter
        except ImportError:
            pass
        
        # SQLite
        try:
            from .sqlite import SQLiteAdapter
            cls._adapters[BackendType.SQLITE] = SQLiteAdapter
        except ImportError:
            pass
        
        # S3
        try:
            from .s3 import S3Adapter
            cls._adapters[BackendType.S3] = S3Adapter
        except ImportError:
            pass
        
        # Redis
        try:
            from .redis import RedisAdapter
            cls._adapters[BackendType.REDIS] = RedisAdapter
        except ImportError:
            pass
    
    @classmethod
    def create_db_adapter(cls, config: StorageConfig) -> Any:
        """
        Create the primary database adapter.
        Returns Postgres or SQLite adapter based on config.
        """
        cls._load_default_adapters()
        
        backend = config.db_backend
        instance_key = f"db:{backend.value}"
        
        if instance_key in cls._instances:
            return cls._instances[instance_key]
        
        adapter_class = cls._adapters.get(backend)
        if not adapter_class:
            raise ValueError(f"No adapter registered for backend: {backend.value}")
        
        # Get backend-specific config
        backend_config = None
        if backend == BackendType.POSTGRES and config.postgres:
            from .postgres import PostgresConfig
            backend_config = PostgresConfig(**config.postgres)
        elif backend == BackendType.SQLITE and config.sqlite:
            from .sqlite import SQLiteConfig
            backend_config = SQLiteConfig(**config.sqlite)
        
        adapter = adapter_class(backend_config)
        adapter.initialize()
        
        cls._instances[instance_key] = adapter
        logger.info(f"Created DB adapter: {backend.value}")
        return adapter
    
    @classmethod
    def create_object_adapter(cls, config: StorageConfig) -> Optional[Any]:
        """
        Create the object storage adapter (S3).
        Returns None if not configured.
        """
        if not config.object_backend:
            return None
        
        cls._load_default_adapters()
        
        backend = config.object_backend
        instance_key = f"object:{backend.value}"
        
        if instance_key in cls._instances:
            return cls._instances[instance_key]
        
        adapter_class = cls._adapters.get(backend)
        if not adapter_class:
            logger.warning(f"No adapter for object backend: {backend.value}")
            return None
        
        backend_config = None
        if backend == BackendType.S3 and config.s3:
            from .s3 import S3Config
            backend_config = S3Config(**config.s3)
        
        adapter = adapter_class(backend_config)
        adapter.initialize()
        
        cls._instances[instance_key] = adapter
        logger.info(f"Created object adapter: {backend.value}")
        return adapter
    
    @classmethod
    def create_cache_adapter(cls, config: StorageConfig) -> Optional[Any]:
        """
        Create the cache adapter (Redis).
        Returns None if not configured or caching disabled.
        """
        if not config.enable_caching or not config.cache_backend:
            return None
        
        cls._load_default_adapters()
        
        backend = config.cache_backend
        instance_key = f"cache:{backend.value}"
        
        if instance_key in cls._instances:
            return cls._instances[instance_key]
        
        adapter_class = cls._adapters.get(backend)
        if not adapter_class:
            logger.warning(f"No adapter for cache backend: {backend.value}")
            return None
        
        try:
            backend_config = None
            if backend == BackendType.REDIS and config.redis:
                from .redis import RedisConfig
                backend_config = RedisConfig(**config.redis)
            
            adapter = adapter_class(backend_config)
            adapter.initialize()
            
            cls._instances[instance_key] = adapter
            logger.info(f"Created cache adapter: {backend.value}")
            return adapter
        except Exception as e:
            logger.warning(f"Failed to create cache adapter: {e}")
            return None
    
    @classmethod
    def create_all(cls, config: StorageConfig) -> Dict[str, Any]:
        """
        Create all configured adapters.
        Returns dict with 'db', 'object', and 'cache' keys.
        """
        return {
            'db': cls.create_db_adapter(config),
            'object': cls.create_object_adapter(config),
            'cache': cls.create_cache_adapter(config)
        }
    
    @classmethod
    def close_all(cls):
        """Close all adapter instances."""
        for key, adapter in cls._instances.items():
            try:
                if hasattr(adapter, 'close'):
                    adapter.close()
                logger.debug(f"Closed adapter: {key}")
            except Exception as e:
                logger.warning(f"Error closing adapter {key}: {e}")
        cls._instances.clear()
    
    @classmethod
    def reset(cls):
        """Reset factory state (for testing)."""
        cls.close_all()
        cls._adapters.clear()


def create_storage(
    backend: str = "sqlite",
    **kwargs
) -> Any:
    """
    Convenience function to create a storage adapter.
    
    Args:
        backend: One of 'postgres', 'sqlite', 's3', 'redis'
        **kwargs: Backend-specific configuration
    
    Returns:
        Configured adapter instance
    
    Example:
        # SQLite for local dev
        db = create_storage("sqlite", database="./data/contd.db")
        
        # Postgres for production
        db = create_storage("postgres", host="db.example.com", database="contd")
    """
    backend_type = BackendType(backend.lower())
    
    config = StorageConfig(
        db_backend=backend_type,
        **{backend.lower(): kwargs} if kwargs else {}
    )
    
    return StorageFactory.create_db_adapter(config)


def create_production_storage(
    postgres_config: Dict[str, Any],
    s3_config: Dict[str, Any] = None,
    redis_config: Dict[str, Any] = None,
    enable_caching: bool = True
) -> Dict[str, Any]:
    """
    Create production storage stack.
    
    Args:
        postgres_config: Postgres connection settings
        s3_config: S3 settings for large snapshots (optional)
        redis_config: Redis settings for caching (optional)
        enable_caching: Whether to enable Redis caching
    
    Returns:
        Dict with 'db', 'object', 'cache' adapters
    """
    config = StorageConfig(
        db_backend=BackendType.POSTGRES,
        object_backend=BackendType.S3 if s3_config else None,
        cache_backend=BackendType.REDIS if redis_config else None,
        postgres=postgres_config,
        s3=s3_config,
        redis=redis_config,
        enable_caching=enable_caching and redis_config is not None
    )
    
    return StorageFactory.create_all(config)


def create_dev_storage(database: str = ":memory:") -> Any:
    """
    Create development storage (SQLite).
    
    Args:
        database: SQLite database path or ":memory:" for in-memory
    
    Returns:
        SQLite adapter instance
    """
    return create_storage("sqlite", database=database)


def create_adapter(backend: str, config: Dict[str, Any]) -> Any:
    """
    Create a storage adapter from CLI config dict.
    
    Args:
        backend: One of 'sqlite', 'postgres', 'redis', 'memory'
        config: Configuration dictionary with backend-specific settings
    
    Returns:
        Configured adapter instance
    """
    StorageFactory._load_default_adapters()
    
    if backend == "memory":
        # Use in-memory SQLite
        from .sqlite import SQLiteAdapter, SQLiteConfig
        adapter = SQLiteAdapter(SQLiteConfig(database=":memory:"))
        adapter.initialize()
        return adapter
    
    if backend == "sqlite":
        from .sqlite import SQLiteAdapter, SQLiteConfig
        sqlite_path = config.get("sqlite_path", ".contd/contd.db")
        adapter = SQLiteAdapter(SQLiteConfig(database=sqlite_path))
        adapter.initialize()
        return adapter
    
    if backend == "postgres":
        from .postgres import PostgresAdapter, PostgresConfig
        pg_config = PostgresConfig(
            host=config.get("postgres_host", "localhost"),
            port=config.get("postgres_port", 5432),
            database=config.get("postgres_database", "contd"),
            user=config.get("postgres_user", "postgres"),
            password=config.get("postgres_password", "")
        )
        adapter = PostgresAdapter(pg_config)
        adapter.initialize()
        return adapter
    
    if backend == "redis":
        from .redis import RedisAdapter, RedisConfig
        redis_url = config.get("redis_url", "redis://localhost:6379")
        adapter = RedisAdapter(RedisConfig(url=redis_url))
        adapter.initialize()
        return adapter
    
    raise ValueError(f"Unknown backend: {backend}")
