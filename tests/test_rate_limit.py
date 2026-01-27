"""Tests for rate limiting middleware."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import Response

from contd.api.rate_limit import (
    RateLimitConfig,
    TokenBucket,
    SlidingWindowCounter,
    InMemoryRateLimiter,
    RateLimitMiddleware,
    create_rate_limiter
)


class TestTokenBucket:
    """Tests for TokenBucket algorithm."""
    
    @pytest.mark.asyncio
    async def test_initial_tokens(self):
        """Bucket starts with full capacity."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        assert bucket.tokens == 10
    
    @pytest.mark.asyncio
    async def test_consume_success(self):
        """Can consume tokens when available."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        result = await bucket.consume(5)
        assert result is True
        assert bucket.tokens == 5
    
    @pytest.mark.asyncio
    async def test_consume_failure(self):
        """Cannot consume more tokens than available."""
        bucket = TokenBucket(rate=1.0, capacity=5)
        await bucket.consume(5)
        result = await bucket.consume(1)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Tokens refill over time."""
        bucket = TokenBucket(rate=10.0, capacity=10)  # 10 tokens/sec
        await bucket.consume(10)
        assert bucket.tokens == 0
        
        await asyncio.sleep(0.2)  # Wait 200ms
        result = await bucket.consume(1)
        assert result is True  # Should have ~2 tokens now
    
    def test_retry_after(self):
        """Retry-after calculation."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        bucket.tokens = 0.5
        assert bucket.retry_after == 0.5


class TestSlidingWindowCounter:
    """Tests for SlidingWindowCounter algorithm."""
    
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        """Allows requests within limit."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=10)
        
        for _ in range(10):
            allowed, remaining = await counter.is_allowed()
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        """Blocks requests over limit."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=5)
        
        for _ in range(5):
            await counter.is_allowed()
        
        allowed, remaining = await counter.is_allowed()
        assert allowed is False
        assert remaining == 0
    
    @pytest.mark.asyncio
    async def test_remaining_count(self):
        """Tracks remaining requests correctly."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=10)
        
        allowed, remaining = await counter.is_allowed()
        assert remaining == 9
        
        allowed, remaining = await counter.is_allowed()
        assert remaining == 8


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""
    
    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5,
            enabled=True
        )
        return InMemoryRateLimiter(config)
    
    @pytest.fixture
    def mock_request(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        request.state.user_id = None  # Explicitly set to None
        return request
    
    @pytest.mark.asyncio
    async def test_allows_initial_requests(self, limiter, mock_request):
        """Allows initial requests."""
        allowed, headers = await limiter.is_allowed(mock_request)
        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
    
    @pytest.mark.asyncio
    async def test_key_extraction_api_key(self, limiter, mock_request):
        """Extracts key from API key header."""
        mock_request.headers = {"X-API-Key": "sk_live_test123456"}
        key = limiter._get_key(mock_request)
        assert key.startswith("apikey:")
    
    @pytest.mark.asyncio
    async def test_key_extraction_ip(self, limiter, mock_request):
        """Falls back to IP address."""
        key = limiter._get_key(mock_request)
        assert key == "ip:127.0.0.1"
    
    @pytest.mark.asyncio
    async def test_key_extraction_forwarded(self, limiter, mock_request):
        """Uses X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        key = limiter._get_key(mock_request)
        assert key == "ip:10.0.0.1"
    
    @pytest.mark.asyncio
    async def test_disabled_limiter(self, mock_request):
        """Disabled limiter allows all requests."""
        config = RateLimitConfig(enabled=False)
        limiter = InMemoryRateLimiter(config)
        
        allowed, headers = await limiter.is_allowed(mock_request)
        assert allowed is True
        assert headers == {}


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""
    
    @pytest.fixture
    def app(self):
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=100,
            burst_size=3,
            enabled=True
        )
        app.add_middleware(RateLimitMiddleware, config=config)
        
        return app
    
    def test_middleware_config(self, app):
        """Middleware is configured correctly."""
        # Check that middleware was added by verifying user_middleware
        assert len(app.user_middleware) > 0
    
    def test_excluded_paths_defined(self):
        """Excluded paths are defined."""
        assert "/health" in RateLimitMiddleware.EXCLUDED_PATHS
        assert "/metrics" in RateLimitMiddleware.EXCLUDED_PATHS
        assert "/docs" in RateLimitMiddleware.EXCLUDED_PATHS


class TestCreateRateLimiter:
    """Tests for create_rate_limiter factory."""
    
    def test_creates_middleware(self):
        """Creates middleware with config."""
        middleware_factory = create_rate_limiter(
            requests_per_minute=100,
            requests_per_hour=1000,
            burst_size=20
        )
        
        app = FastAPI()
        middleware = middleware_factory(app)
        
        assert isinstance(middleware, RateLimitMiddleware)
        assert middleware.config.requests_per_minute == 100
        assert middleware.config.requests_per_hour == 1000
    
    def test_disabled_limiter(self):
        """Can create disabled limiter."""
        middleware_factory = create_rate_limiter(enabled=False)
        
        app = FastAPI()
        middleware = middleware_factory(app)
        
        assert middleware.config.enabled is False
