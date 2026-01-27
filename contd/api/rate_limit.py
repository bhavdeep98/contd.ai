"""
Rate limiting middleware for the Contd API.

Supports multiple strategies:
- In-memory (default, for single instance)
- Redis (for distributed deployments)
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    enabled: bool = True


class TokenBucket:
    """Token bucket algorithm for rate limiting."""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    @property
    def retry_after(self) -> float:
        """Seconds until a token is available."""
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) / self.rate


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""
    
    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests: list = []
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> tuple:
        """Check if request is allowed. Returns (allowed, remaining)."""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            
            self.requests = [t for t in self.requests if t > cutoff]
            
            remaining = self.max_requests - len(self.requests)
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True, remaining - 1
            
            return False, 0
    
    @property
    def reset_time(self) -> float:
        """Seconds until the window resets."""
        if not self.requests:
            return 0
        oldest = min(self.requests)
        return max(0, self.window_seconds - (time.monotonic() - oldest))


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._minute_windows: Dict[str, SlidingWindowCounter] = {}
        self._hour_windows: Dict[str, SlidingWindowCounter] = {}
        self._bursts: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    def _get_key(self, request: Request) -> str:
        """Extract rate limit key from request."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"apikey:{api_key[:16]}"
        
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        return f"ip:{client_ip}"
    
    async def _get_or_create_windows(self, key: str):
        """Get or create rate limit windows for a key."""
        async with self._lock:
            if key not in self._minute_windows:
                self._minute_windows[key] = SlidingWindowCounter(60, self.config.requests_per_minute)
            if key not in self._hour_windows:
                self._hour_windows[key] = SlidingWindowCounter(3600, self.config.requests_per_hour)
            if key not in self._bursts:
                self._bursts[key] = TokenBucket(
                    rate=self.config.requests_per_minute / 60,
                    capacity=self.config.burst_size
                )
        
        return (
            self._minute_windows[key],
            self._hour_windows[key],
            self._bursts[key]
        )
    
    async def is_allowed(self, request: Request) -> tuple:
        """Check if request is allowed. Returns (allowed, headers)."""
        if not self.config.enabled:
            return True, {}
        
        key = self._get_key(request)
        minute_window, hour_window, burst = await self._get_or_create_windows(key)
        
        burst_allowed = await burst.consume()
        minute_allowed, minute_remaining = await minute_window.is_allowed()
        hour_allowed, hour_remaining = await hour_window.is_allowed()
        
        headers = {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(minute_remaining),
            "X-RateLimit-Reset": str(int(minute_window.reset_time)),
            "X-RateLimit-Limit-Hour": str(self.config.requests_per_hour),
            "X-RateLimit-Remaining-Hour": str(hour_remaining),
        }
        
        if not minute_allowed or not hour_allowed:
            headers["Retry-After"] = str(int(max(minute_window.reset_time, 1)))
            return False, headers
        
        if not burst_allowed:
            headers["X-RateLimit-Burst-Exceeded"] = "true"
        
        return True, headers


class RedisRateLimiter:
    """Redis-based distributed rate limiter."""
    
    def __init__(self, config: RateLimitConfig, redis_url: str):
        self.config = config
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        """Lazy initialize Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = await aioredis.from_url(self.redis_url)
            except ImportError:
                logger.warning("redis package not installed, falling back to in-memory")
                return None
        return self._redis
    
    def _get_key(self, request: Request) -> str:
        """Extract rate limit key from request."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"ratelimit:apikey:{api_key[:16]}"
        
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"ratelimit:user:{user_id}"
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        return f"ratelimit:ip:{client_ip}"
    
    async def is_allowed(self, request: Request) -> tuple:
        """Check if request is allowed using Redis."""
        if not self.config.enabled:
            return True, {}
        
        redis = await self._get_redis()
        if redis is None:
            return True, {}
        
        key = self._get_key(request)
        minute_key = f"{key}:minute"
        hour_key = f"{key}:hour"
        
        now = int(time.time())
        minute_window_start = now - 60
        hour_window_start = now - 3600
        
        pipe = redis.pipeline()
        
        pipe.zremrangebyscore(minute_key, 0, minute_window_start)
        pipe.zremrangebyscore(hour_key, 0, hour_window_start)
        pipe.zcard(minute_key)
        pipe.zcard(hour_key)
        
        results = await pipe.execute()
        minute_count = results[2]
        hour_count = results[3]
        
        minute_remaining = max(0, self.config.requests_per_minute - minute_count)
        hour_remaining = max(0, self.config.requests_per_hour - hour_count)
        
        headers = {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(minute_remaining),
            "X-RateLimit-Reset": str(60 - (now % 60)),
            "X-RateLimit-Limit-Hour": str(self.config.requests_per_hour),
            "X-RateLimit-Remaining-Hour": str(hour_remaining),
        }
        
        if minute_count >= self.config.requests_per_minute or hour_count >= self.config.requests_per_hour:
            headers["Retry-After"] = str(60 - (now % 60))
            return False, headers
        
        pipe = redis.pipeline()
        pipe.zadd(minute_key, {str(now): now})
        pipe.zadd(hour_key, {str(now): now})
        pipe.expire(minute_key, 120)
        pipe.expire(hour_key, 7200)
        await pipe.execute()
        
        return True, headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    EXCLUDED_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}
    
    def __init__(
        self,
        app,
        config: Optional[RateLimitConfig] = None,
        redis_url: Optional[str] = None,
        key_func: Optional[Callable] = None
    ):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        
        if redis_url:
            self.limiter = RedisRateLimiter(self.config, redis_url)
        else:
            self.limiter = InMemoryRateLimiter(self.config)
        
        self.key_func = key_func
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        if request.method == "OPTIONS":
            return await call_next(request)
        
        allowed, headers = await self.limiter.is_allowed(request)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {request.url.path}")
            response = Response(
                content='{"detail": "Rate limit exceeded. Please retry later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json"
            )
            for key, value in headers.items():
                response.headers[key] = value
            return response
        
        response = await call_next(request)
        
        for key, value in headers.items():
            response.headers[key] = value
        
        return response


def create_rate_limiter(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_size: int = 10,
    redis_url: Optional[str] = None,
    enabled: bool = True
):
    """Factory function to create rate limit middleware."""
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_size=burst_size,
        enabled=enabled
    )
    return lambda app: RateLimitMiddleware(app, config=config, redis_url=redis_url)
