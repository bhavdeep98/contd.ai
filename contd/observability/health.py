"""
Health Check Endpoints for Contd.ai

Provides liveness, readiness, and detailed health checks for
Kubernetes deployments and load balancer health probes.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
import time
import asyncio


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    name: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    uptime_seconds: float
    components: List[ComponentHealth]


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    ready: bool


# Track startup time
_start_time = time.time()
_version = "0.1.0"

# Health check router
router = APIRouter(tags=["health"])


async def check_database_health() -> ComponentHealth:
    """Check database connectivity."""
    start = time.time()
    try:
        from contd.core.engine import ExecutionEngine

        engine = ExecutionEngine.get_instance()
        # Simple connectivity check
        if engine.journal:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="database", status=HealthStatus.HEALTHY, latency_ms=latency
            )
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message="Journal not initialized",
        )
    except Exception as e:
        return ComponentHealth(
            name="database", status=HealthStatus.UNHEALTHY, message=str(e)
        )


async def check_lease_manager_health() -> ComponentHealth:
    """Check lease manager health."""
    start = time.time()
    try:
        from contd.core.engine import ExecutionEngine

        engine = ExecutionEngine.get_instance()
        if engine.lease_manager:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="lease_manager", status=HealthStatus.HEALTHY, latency_ms=latency
            )
        return ComponentHealth(
            name="lease_manager",
            status=HealthStatus.UNHEALTHY,
            message="Lease manager not initialized",
        )
    except Exception as e:
        return ComponentHealth(
            name="lease_manager", status=HealthStatus.UNHEALTHY, message=str(e)
        )


async def check_snapshot_store_health() -> ComponentHealth:
    """Check snapshot store health."""
    start = time.time()
    try:
        from contd.core.engine import ExecutionEngine

        engine = ExecutionEngine.get_instance()
        if engine.snapshot_store:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="snapshot_store", status=HealthStatus.HEALTHY, latency_ms=latency
            )
        return ComponentHealth(
            name="snapshot_store",
            status=HealthStatus.UNHEALTHY,
            message="Snapshot store not initialized",
        )
    except Exception as e:
        return ComponentHealth(
            name="snapshot_store", status=HealthStatus.UNHEALTHY, message=str(e)
        )


async def check_metrics_health() -> ComponentHealth:
    """Check metrics exporter health."""
    try:
        from contd.observability.exporter import _exporter

        if _exporter and _exporter.server:
            return ComponentHealth(name="metrics", status=HealthStatus.HEALTHY)
        return ComponentHealth(
            name="metrics",
            status=HealthStatus.DEGRADED,
            message="Metrics server not running",
        )
    except Exception as e:
        return ComponentHealth(
            name="metrics", status=HealthStatus.DEGRADED, message=str(e)
        )


@router.get("/health/live", response_model=LivenessResponse)
async def liveness():
    """
    Kubernetes liveness probe.

    Returns 200 if the process is alive.
    Used to detect deadlocks or hung processes.
    """
    return LivenessResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response):
    """
    Kubernetes readiness probe.

    Returns 200 if the service is ready to accept traffic.
    Checks critical dependencies.
    """
    try:
        from contd.core.engine import ExecutionEngine

        engine = ExecutionEngine.get_instance()

        # Check critical components
        ready = engine.journal is not None and engine.lease_manager is not None

        if not ready:
            response.status_code = 503
            return ReadinessResponse(status="not_ready", ready=False)

        return ReadinessResponse(status="ready", ready=True)
    except Exception:
        response.status_code = 503
        return ReadinessResponse(status="not_ready", ready=False)


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response):
    """
    Detailed health check endpoint.

    Returns comprehensive health status of all components.
    """
    # Run all health checks concurrently
    checks = await asyncio.gather(
        check_database_health(),
        check_lease_manager_health(),
        check_snapshot_store_health(),
        check_metrics_health(),
        return_exceptions=True,
    )

    components = []
    for check in checks:
        if isinstance(check, Exception):
            components.append(
                ComponentHealth(
                    name="unknown", status=HealthStatus.UNHEALTHY, message=str(check)
                )
            )
        else:
            components.append(check)

    # Determine overall status
    unhealthy_count = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)
    degraded_count = sum(1 for c in components if c.status == HealthStatus.DEGRADED)

    if unhealthy_count > 0:
        overall_status = HealthStatus.UNHEALTHY
        response.status_code = 503
    elif degraded_count > 0:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    # Update component health metrics
    try:
        from contd.observability.metrics import component_health_status

        for comp in components:
            health_value = 1 if comp.status == HealthStatus.HEALTHY else 0
            component_health_status.labels(component=comp.name).set(health_value)
    except Exception:
        pass

    return HealthResponse(
        status=overall_status,
        version=_version,
        uptime_seconds=time.time() - _start_time,
        components=components,
    )


@router.get("/health/components/{component_name}")
async def component_health(component_name: str, response: Response):
    """
    Check health of a specific component.
    """
    check_funcs = {
        "database": check_database_health,
        "lease_manager": check_lease_manager_health,
        "snapshot_store": check_snapshot_store_health,
        "metrics": check_metrics_health,
    }

    if component_name not in check_funcs:
        response.status_code = 404
        return {"error": f"Unknown component: {component_name}"}

    result = await check_funcs[component_name]()

    if result.status == HealthStatus.UNHEALTHY:
        response.status_code = 503

    return result


__all__ = [
    "router",
    "HealthStatus",
    "ComponentHealth",
    "HealthResponse",
]
