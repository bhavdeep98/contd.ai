# Docker Setup

## Quick Start

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Development mode with hot reload
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| contd-api | 8080, 50051 | Contd API (HTTP + gRPC) |
| postgres | 5432 | PostgreSQL database |
| redis | 6379 | Redis cache |
| minio | 9000, 9001 | S3-compatible storage |
| jaeger | 16686 | Distributed tracing UI |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Dashboards (admin/admin) |

## Environment Variables

- `CONTD_DATABASE_URL` - PostgreSQL connection string
- `CONTD_REDIS_URL` - Redis connection string
- `CONTD_S3_ENDPOINT` - S3/MinIO endpoint
- `CONTD_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
