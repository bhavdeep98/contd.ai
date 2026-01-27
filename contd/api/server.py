from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from concurrent import futures
import grpc
import threading
import uvicorn
import logging
import time
import os

from contd.api.routes import router as workflow_router
from contd.api.proto import workflow_pb2_grpc
from contd.api.grpc_service import WorkflowService
from contd.core.engine import ExecutionEngine
from contd.observability.health import router as health_router
from contd.observability import setup_observability, teardown_observability
from contd.api.rate_limit import RateLimitMiddleware, RateLimitConfig

# Setup structured JSON logging if enabled
if os.getenv("CONTD_JSON_LOGGING", "false").lower() == "true":
    from contd.observability.logging import setup_json_logging
    setup_json_logging()
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger("contd.server")

# OpenAPI customization
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Contd Workflow API",
        version="1.0.0",
        description="""
## Contd Workflow Engine API

Durable workflow execution engine with time-travel debugging capabilities.

### Features
- **Workflow Management**: Start, monitor, and resume workflows
- **Time-Travel Debugging**: Create savepoints and branch workflows
- **Webhooks**: Subscribe to workflow events
- **Multi-tenancy**: Organization-based isolation

### Authentication
All API endpoints require authentication via:
- **Bearer Token**: JWT token from `/v1/auth/token`
- **API Key**: Pass in `X-API-Key` header

### Rate Limiting
API requests are rate limited per API key or IP address:
- 60 requests per minute
- 1000 requests per hour
        """,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "apiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    # Apply security globally
    openapi_schema["security"] = [
        {"bearerAuth": []},
        {"apiKeyAuth": []}
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app = FastAPI(
    title="Contd Workflow API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.openapi = custom_openapi

# Rate limiting middleware
rate_limit_config = RateLimitConfig(
    requests_per_minute=int(os.getenv("CONTD_RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.getenv("CONTD_RATE_LIMIT_PER_HOUR", "1000")),
    burst_size=int(os.getenv("CONTD_RATE_LIMIT_BURST", "10")),
    enabled=os.getenv("CONTD_RATE_LIMIT_ENABLED", "true").lower() == "true"
)

redis_url = os.getenv("CONTD_REDIS_URL")  # For distributed rate limiting
app.add_middleware(RateLimitMiddleware, config=rate_limit_config, redis_url=redis_url)

# Include routes
app.include_router(workflow_router)
from contd.api.auth_routes import router as auth_router
app.include_router(auth_router)
from contd.api.webhook_routes import router as webhook_router
app.include_router(webhook_router)
app.include_router(health_router)

# gRPC Server
grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
workflow_pb2_grpc.add_WorkflowServiceServicer_to_server(WorkflowService(), grpc_server)
grpc_server.add_insecure_port('[::]:50051')

@app.on_event("startup")
async def startup_event():
    logger.info("Starting gRPC server on port 50051")
    grpc_server.start()
    
    # Initialize engine
    ExecutionEngine.get_instance()
    logger.info("Engine initialized")
    
    # Initialize webhook dispatcher
    from contd.api.webhooks import WebhookDispatcher, WebhookStore, set_webhook_dispatcher
    try:
        engine = ExecutionEngine.get_instance()
        webhook_store = WebhookStore(engine.db)
        dispatcher = WebhookDispatcher(webhook_store)
        set_webhook_dispatcher(dispatcher)
        logger.info("Webhook dispatcher initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize webhook dispatcher: {e}")
    
    # Setup observability if enabled
    if os.getenv("CONTD_OBSERVABILITY", "true").lower() == "true":
        metrics_port = int(os.getenv("CONTD_METRICS_PORT", "9090"))
        tracing_endpoint = os.getenv("CONTD_TRACING_ENDPOINT")
        setup_observability(
            metrics_port=metrics_port,
            enable_tracing=bool(tracing_endpoint),
            tracing_endpoint=tracing_endpoint,
            enable_json_logging=os.getenv("CONTD_JSON_LOGGING", "false").lower() == "true",
        )
        logger.info(f"Observability enabled (metrics port: {metrics_port})")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping gRPC server")
    grpc_server.stop(0)
    
    # Cleanup webhook dispatcher
    from contd.api.webhooks import get_webhook_dispatcher
    dispatcher = get_webhook_dispatcher()
    if dispatcher:
        await dispatcher.close()
        logger.info("Webhook dispatcher closed")
    
    teardown_observability()
    logger.info("Observability shutdown complete")

def main():
    """Entry point to run the server"""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
