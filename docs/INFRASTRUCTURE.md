# Infrastructure Guide

## Overview

Contd provides complete infrastructure-as-code for deploying to any major cloud provider or local development.

## Local Development

### Docker Compose

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# With hot reload for development
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f contd-api

# Stop
docker-compose -f docker/docker-compose.yml down
```

Services included:
- Contd API (HTTP :8080, gRPC :50051)
- PostgreSQL (:5432)
- Redis (:6379)
- MinIO S3 (:9000, console :9001)
- Jaeger tracing (:16686)
- Prometheus (:9090)
- Grafana (:3000)

## Kubernetes Deployment

### Helm Chart

```bash
# Install with built-in databases (dev/staging)
helm install contd helm/contd -f helm/contd/values-dev.yaml

# Install with external databases (production)
helm install contd helm/contd \
  -f helm/contd/values-production.yaml \
  --set contd.database.host=mydb.example.com \
  --set contd.database.existingSecret=db-credentials \
  --set contd.redis.host=myredis.example.com
```

## Cloud Infrastructure

### AWS

```bash
cd terraform/aws
terraform init
terraform apply -var="environment=production"
```

Provisions: VPC, EKS, RDS PostgreSQL, ElastiCache Redis, S3

### GCP

```bash
cd terraform/gcp
terraform init
terraform apply -var="project_id=my-project" -var="environment=production"
```

Provisions: VPC, GKE, Cloud SQL, Memorystore, Cloud Storage

### Azure

```bash
cd terraform/azure
terraform init
terraform apply -var="environment=production"
```

Provisions: VNet, AKS, PostgreSQL Flexible Server, Azure Cache, Storage Account

## CI/CD

GitHub Actions workflows:
- `ci.yml` - Lint, test, security scan, build
- `release.yml` - Build multi-arch images, publish to PyPI, create GitHub release
- `deploy.yml` - Deploy to any environment via Helm

## Benchmarking

```bash
python -m benchmarks.run_benchmarks --api-url http://localhost:8080
```

Measures: workflow creation, step execution, persistence operations, recovery performance.
