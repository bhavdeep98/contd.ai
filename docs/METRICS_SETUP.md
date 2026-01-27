# Metrics Setup Guide

## Quick Start

### 1. Basic Setup (Pull-based)

```python
from contd.observability import setup_observability

# Start metrics server
setup_observability(
    metrics_port=9090,
    enable_background=True
)

# Metrics available at http://localhost:9090/metrics
```

### 2. Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'contd'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
```

### 3. Run Prometheus

```bash
prometheus --config.file=prometheus.yml
```

Access Prometheus UI at http://localhost:9090

---

## Push-based (for batch jobs)

### 1. Start Pushgateway

```bash
docker run -d -p 9091:9091 prom/pushgateway
```

### 2. Push Metrics

```python
from contd.observability import MetricsPusher, collector

pusher = MetricsPusher(
    gateway_url='localhost:9091',
    job_name='contd_batch'
)

# Execute workflow...
collector.record_workflow_start("batch_job", trigger="schedule")

# Push metrics
pusher.push()
```

---

## Automatic Metrics (via decorators)

Metrics are automatically emitted when using `@workflow` and `@step` decorators:

```python
from contd.sdk import workflow, step

@workflow()
def my_workflow():
    # Automatically emits:
    # - contd_workflows_started_total
    # - contd_workflows_completed_total
    # - contd_workflow_duration_seconds
    # - contd_lease_acquisition_duration_milliseconds
    
    result = process_data()
    return result

@step()
def process_data():
    # Automatically emits:
    # - contd_steps_executed_total
    # - contd_step_duration_milliseconds
    # - contd_managed_steps_total (billing)
    # - contd_idempotency_cache_hits_total (if cached)
    
    return {"status": "done"}
```

---

## Key Metrics

### P0 Critical

- `contd_restore_duration_milliseconds` - Restore latency (SLO: <1s P95)
- `contd_events_replayed_per_restore` - Events replayed (target: <100)
- `contd_checksum_validation_failures_total` - Data corruption
- `contd_workflow_success_rate` - Success rate (target: >99%)

### P1 Important

- `contd_managed_steps_total` - Billing metric
- `contd_step_duration_milliseconds` - Step latency
- `contd_lease_acquisition_failures_total` - Concurrency issues
- `contd_snapshot_save_duration_milliseconds` - Snapshot performance

---

## Grafana Dashboards

### Import Dashboard

1. Open Grafana (http://localhost:3000)
2. Add Prometheus data source
3. Import dashboard JSON (see `docs/grafana/`)

### Key Panels

- **Restore Latency P95** - Critical SLO
- **Workflow Success Rate** - Availability
- **Managed Steps** - Revenue tracking
- **Idempotency Hit Rate** - Efficiency

---

## Alerts

### Critical Alerts

```yaml
# Data corruption
- alert: DataCorruption
  expr: rate(contd_checksum_validation_failures_total[5m]) > 0
  severity: critical

# Restore latency breach
- alert: RestoreLatencySLO
  expr: histogram_quantile(0.95, contd_restore_duration_milliseconds) > 1000
  severity: warning

# Low success rate
- alert: WorkflowSuccessRate
  expr: contd_workflow_success_rate < 0.99
  severity: critical
```

---

## Production Deployment

### Docker Compose

```yaml
version: '3'
services:
  contd:
    image: contd:latest
    ports:
      - "9090:9090"
    environment:
      - METRICS_PORT=9090
  
  prometheus:
    image: prom/prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

### Kubernetes

```yaml
apiVersion: v1
kind: Service
metadata:
  name: contd-metrics
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
spec:
  selector:
    app: contd
  ports:
    - port: 9090
```

---

## Troubleshooting

### Metrics not appearing

1. Check server is running: `curl http://localhost:9090/metrics`
2. Verify Prometheus scraping: Check Prometheus targets page
3. Check for errors in logs

### High cardinality

Avoid high-cardinality labels:
- ❌ `workflow_id` (unique per execution)
- ✅ `workflow_name` (bounded set)

### Memory usage

Background collector runs every 15s by default. Adjust if needed:

```python
setup_observability(background_interval=60)  # 1 minute
```
