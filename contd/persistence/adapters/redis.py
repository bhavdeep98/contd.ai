"""
Redis adapter for snapshot caching.
"""
from __future__ import annotations
import json
import logging
import hashlib
from typing import Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    import redis as redis_module

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    # Cache settings
    default_ttl: int = 3600  # 1 hour
    key_prefix: str = "contd:cache:"
    # Connection pool
    max_connections: int = 10


class RedisAdapter:
    """
    Redis adapter for snapshot caching with:
    - Automatic TTL management
    - Checksum validation
    - Connection pooling
    - Graceful degradation on failures
    """
    
    def __init__(self, config: RedisConfig = None):
        if not HAS_REDIS:
            raise ImportError("redis is required. Install with: pip install redis")
        
        self.config = config or RedisConfig()
        self._client: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Redis connection pool."""
        if self._initialized:
            return
        
        self._pool = redis.ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            db=self.config.db,
            password=self.config.password,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            max_connections=self.config.max_connections,
            decode_responses=True
        )
        self._client = redis.Redis(connection_pool=self._pool)
        self._initialized = True
        logger.info(f"Redis initialized: {self.config.host}:{self.config.port}")
    
    def close(self):
        """Close all connections."""
        if self._pool:
            self._pool.disconnect()
            self._initialized = False
    
    @property
    def client(self) -> Any:
        if not self._initialized:
            self.initialize()
        return self._client
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key."""
        return f"{self.config.key_prefix}{key}"
    
    def get(self, key: str, expected_checksum: str = None) -> Optional[str]:
        """
        Get cached value with optional checksum validation.
        Returns None on cache miss or validation failure.
        """
        try:
            full_key = self._make_key(key)
            
            # Get value and checksum atomically
            pipe = self.client.pipeline()
            pipe.get(full_key)
            pipe.get(f"{full_key}:checksum")
            value, stored_checksum = pipe.execute()
            
            if value is None:
                return None
            
            # Validate checksum if provided
            if expected_checksum and stored_checksum != expected_checksum:
                logger.warning(f"Cache checksum mismatch for {key}")
                self.delete(key)
                return None
            
            # Verify data integrity
            actual_checksum = self._compute_checksum(value)
            if stored_checksum and actual_checksum != stored_checksum:
                logger.warning(f"Cache corruption detected for {key}")
                self.delete(key)
                return None
            
            logger.debug(f"Cache hit: {key}")
            return value
            
        except redis.RedisError as e:
            logger.warning(f"Redis get failed for {key}: {e}")
            return None
    
    def set(self, key: str, value: str, ttl: int = None) -> bool:
        """
        Set cached value with checksum and TTL.
        Returns True on success, False on failure.
        """
        try:
            full_key = self._make_key(key)
            ttl = ttl or self.config.default_ttl
            checksum = self._compute_checksum(value)
            
            # Set value and checksum atomically
            pipe = self.client.pipeline()
            pipe.setex(full_key, ttl, value)
            pipe.setex(f"{full_key}:checksum", ttl, checksum)
            pipe.execute()
            
            logger.debug(f"Cache set: {key} (ttl={ttl}s)")
            return True
            
        except redis.RedisError as e:
            logger.warning(f"Redis set failed for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cached value."""
        try:
            full_key = self._make_key(key)
            
            pipe = self.client.pipeline()
            pipe.delete(full_key)
            pipe.delete(f"{full_key}:checksum")
            pipe.execute()
            
            logger.debug(f"Cache delete: {key}")
            return True
            
        except redis.RedisError as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.client.exists(self._make_key(key)))
        except redis.RedisError:
            return False
    
    def get_snapshot(self, workflow_id: str, org_id: str = "default") -> Optional[str]:
        """Get cached snapshot for a workflow."""
        key = f"snapshot:{org_id}:{workflow_id}"
        return self.get(key)
    
    def set_snapshot(self, workflow_id: str, data: str, org_id: str = "default", ttl: int = None) -> bool:
        """Cache a snapshot."""
        key = f"snapshot:{org_id}:{workflow_id}"
        return self.set(key, data, ttl)
    
    def invalidate_snapshot(self, workflow_id: str, org_id: str = "default") -> bool:
        """Invalidate cached snapshot."""
        key = f"snapshot:{org_id}:{workflow_id}"
        return self.delete(key)
    
    def get_multi(self, keys: list) -> dict:
        """Get multiple cached values."""
        try:
            full_keys = [self._make_key(k) for k in keys]
            values = self.client.mget(full_keys)
            return {k: v for k, v in zip(keys, values) if v is not None}
        except redis.RedisError as e:
            logger.warning(f"Redis mget failed: {e}")
            return {}
    
    def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with a given prefix."""
        try:
            pattern = self._make_key(f"{prefix}*")
            keys = list(self.client.scan_iter(match=pattern))
            if keys:
                return self.client.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.warning(f"Redis clear_prefix failed: {e}")
            return 0
    
    def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False
    
    def _compute_checksum(self, data: str) -> str:
        """Compute SHA256 checksum."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


class CachedSnapshotStore:
    """
    Wrapper that adds Redis caching to any SnapshotStore.
    Falls back to underlying store on cache miss.
    """
    
    def __init__(self, store: Any, cache: RedisAdapter):
        self.store = store
        self.cache = cache
    
    def save(self, state: Any, last_event_seq: int) -> str:
        """Save snapshot and invalidate cache."""
        snapshot_id = self.store.save(state, last_event_seq)
        self.cache.invalidate_snapshot(state.workflow_id, state.org_id)
        return snapshot_id
    
    def load(self, snapshot_id: str) -> Any:
        """Load snapshot (cache not used for ID-based loads)."""
        return self.store.load(snapshot_id)
    
    def get_latest(self, workflow_id: str, org_id: str = "default"):
        """Get latest snapshot with caching."""
        from ..serialization import serialize, deserialize
        from ...models.state import WorkflowState
        
        # Try cache first
        cached = self.cache.get_snapshot(workflow_id, org_id)
        if cached:
            try:
                data = json.loads(cached)
                state = deserialize(data['state'], cls=WorkflowState)
                return state, data['last_event_seq']
            except Exception:
                self.cache.invalidate_snapshot(workflow_id, org_id)
        
        # Fall back to store
        state, seq = self.store.get_latest(workflow_id, org_id)
        
        # Cache the result
        if state:
            cache_data = json.dumps({
                'state': serialize(state),
                'last_event_seq': seq
            })
            self.cache.set_snapshot(workflow_id, cache_data, org_id)
        
        return state, seq
    
    def delete(self, snapshot_id: str):
        """Delete snapshot and invalidate cache."""
        # Get workflow info before delete
        row = self.store._query_snapshot(snapshot_id)
        if row:
            self.cache.invalidate_snapshot(
                row.get('workflow_id', ''),
                row.get('org_id', 'default')
            )
        self.store.delete(snapshot_id)
