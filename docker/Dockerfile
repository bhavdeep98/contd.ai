FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml ./
COPY requirements-test.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir \
    fastapi \
    uvicorn \
    grpcio \
    grpcio-tools \
    asyncpg \
    redis \
    boto3 \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi \
    prometheus-client \
    structlog \
    pydantic \
    pydantic-settings \
    httpx \
    tenacity

# Copy application code
COPY contd/ ./contd/

# Create non-root user
RUN useradd -m -u 1000 contd && chown -R contd:contd /app
USER contd

# Expose ports
EXPOSE 8080 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the API server
CMD ["python", "-m", "contd.api.server"]
