"""
Tests for health check endpoints.
"""

import pytest
from fastapi import FastAPI
from contd.observability.health import (
    router,
    HealthStatus,
    ComponentHealth,
    HealthResponse,
    check_database_health,
    check_lease_manager_health,
    check_snapshot_store_health,
    check_metrics_health,
)


@pytest.fixture
def app():
    """Create test FastAPI app with health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    from starlette.testclient import TestClient
    return TestClient(app=app)


class TestLivenessEndpoint:
    """Test /health/live endpoint."""
    
    @pytest.mark.asyncio
    async def test_liveness_returns_200(self, app):
        """Liveness probe should always return 200."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/live")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_liveness_returns_ok_status(self, app):
        """Liveness probe should return ok status."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/live")
            data = response.json()
            assert data["status"] == "ok"


class TestReadinessEndpoint:
    """Test /health/ready endpoint."""
    
    @pytest.mark.asyncio
    async def test_readiness_returns_response(self, app):
        """Readiness probe should return a response."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            # May be 200 or 503 depending on engine state
            assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_readiness_has_ready_field(self, app):
        """Readiness response should have ready field."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            data = response.json()
            assert "ready" in data
            assert isinstance(data["ready"], bool)


class TestHealthEndpoint:
    """Test /health endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_returns_response(self, app):
        """Health endpoint should return a response."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            # May be 200 or 503 depending on component health
            assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_health_has_required_fields(self, app):
        """Health response should have required fields."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            
            assert "status" in data
            assert "version" in data
            assert "uptime_seconds" in data
            assert "components" in data
    
    @pytest.mark.asyncio
    async def test_health_status_is_valid(self, app):
        """Health status should be valid enum value."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            
            valid_statuses = ["healthy", "degraded", "unhealthy"]
            assert data["status"] in valid_statuses
    
    @pytest.mark.asyncio
    async def test_health_components_is_list(self, app):
        """Components should be a list."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            
            assert isinstance(data["components"], list)
    
    @pytest.mark.asyncio
    async def test_health_uptime_is_positive(self, app):
        """Uptime should be positive."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            data = response.json()
            
            assert data["uptime_seconds"] >= 0


class TestComponentHealthEndpoint:
    """Test /health/components/{name} endpoint."""
    
    @pytest.mark.asyncio
    async def test_unknown_component_returns_404(self, app):
        """Unknown component should return 404."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/components/unknown_component")
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_database_component_returns_response(self, app):
        """Database component check should return response."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/components/database")
            # May be 200 or 503
            assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_metrics_component_returns_response(self, app):
        """Metrics component check should return response."""
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/components/metrics")
            assert response.status_code in [200, 503]


class TestHealthCheckFunctions:
    """Test individual health check functions."""
    
    @pytest.mark.asyncio
    async def test_check_database_health_returns_component(self):
        """check_database_health should return ComponentHealth."""
        result = await check_database_health()
        assert isinstance(result, ComponentHealth)
        assert result.name == "database"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY]
    
    @pytest.mark.asyncio
    async def test_check_lease_manager_health_returns_component(self):
        """check_lease_manager_health should return ComponentHealth."""
        result = await check_lease_manager_health()
        assert isinstance(result, ComponentHealth)
        assert result.name == "lease_manager"
    
    @pytest.mark.asyncio
    async def test_check_snapshot_store_health_returns_component(self):
        """check_snapshot_store_health should return ComponentHealth."""
        result = await check_snapshot_store_health()
        assert isinstance(result, ComponentHealth)
        assert result.name == "snapshot_store"
    
    @pytest.mark.asyncio
    async def test_check_metrics_health_returns_component(self):
        """check_metrics_health should return ComponentHealth."""
        result = await check_metrics_health()
        assert isinstance(result, ComponentHealth)
        assert result.name == "metrics"


class TestHealthModels:
    """Test health check models."""
    
    def test_health_status_enum(self):
        """HealthStatus should have expected values."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
    
    def test_component_health_model(self):
        """ComponentHealth should be constructable."""
        component = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=10.5,
            message="All good"
        )
        assert component.name == "test"
        assert component.status == HealthStatus.HEALTHY
        assert component.latency_ms == 10.5
    
    def test_health_response_model(self):
        """HealthResponse should be constructable."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            uptime_seconds=3600.0,
            components=[]
        )
        assert response.status == HealthStatus.HEALTHY
        assert response.version == "1.0.0"
