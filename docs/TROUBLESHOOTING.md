# Troubleshooting Guide

## Common Issues

### WorkflowLocked Error

**Symptom:**
```python
contd.sdk.errors.WorkflowLocked: Workflow wf-123 is locked by another executor
```

**Causes:**
1. Previous execution crashed without releasing lease
2. Another process is running the same workflow
3. Lease heartbeat failed

**Solutions:**
```python
# Option 1: Wait for lease to expire (default: 30s)
import time
time.sleep(35)
client.resume(workflow_id)

# Option 2: Force release (admin only)
from contd.core.engine import ExecutionEngine
engine = ExecutionEngine.get_instance()
engine.lease_manager.force_release(workflow_id)

# Option 3: Check who holds the lease
lease = engine.lease_manager.get_current_lease(workflow_id)
print(f"Held by: {lease.owner_id}, expires: {lease.expires_at}")
```

---

### StepTimeout Error

**Symptom:**
```python
contd.sdk.errors.StepTimeout: Step 'fetch_data' timed out after 30.0s
```

**Causes:**
1. External API is slow
2. Timeout too aggressive
3. Network issues

**Solutions:**
```python
# Increase timeout
@step(StepConfig(timeout=timedelta(minutes=5)))
def fetch_data():
    ...

# Add retry for transient failures
@step(StepConfig(
    timeout=timedelta(seconds=30),
    retry=RetryPolicy(max_attempts=3)
))
def fetch_data():
    ...

# Use async with proper timeout handling
import asyncio
async def fetch_with_timeout():
    try:
        return await asyncio.wait_for(fetch(), timeout=30)
    except asyncio.TimeoutError:
        return {"status": "timeout", "fallback": True}
```

---

### TooManyAttempts Error

**Symptom:**
```python
contd.sdk.errors.TooManyAttempts: Step 'process' failed after 3 attempts
```

**Causes:**
1. Persistent failure (not transient)
2. Bug in step logic
3. External dependency down

**Solutions:**
```python
# Check the last error
try:
    process_data()
except TooManyAttempts as e:
    print(f"Last error: {e.last_error}")
    # Decide: fix bug, increase attempts, or fail gracefully

# Increase max attempts for flaky operations
@step(StepConfig(retry=RetryPolicy(max_attempts=10)))
def flaky_operation():
    ...

# Add specific retryable exceptions
@step(StepConfig(retry=RetryPolicy(
    max_attempts=5,
    retryable_exceptions=[ConnectionError, TimeoutError]
)))
def network_call():
    ...
```

---

### NoActiveWorkflow Error

**Symptom:**
```python
contd.sdk.errors.NoActiveWorkflow: No workflow context found
```

**Causes:**
1. Calling `ExecutionContext.current()` outside workflow
2. Missing `@workflow` decorator
3. Running step directly without workflow

**Solutions:**
```python
# Wrong: calling step directly
result = my_step()  # NoActiveWorkflow!

# Correct: call within workflow
@workflow()
def my_workflow():
    result = my_step()  # Works!

# For testing, use mock context
from contd.sdk.testing import ContdTestCase
tc = ContdTestCase()
tc.setUp()
result = tc.run_workflow("test", my_workflow, {})
```

---

### Database Connection Errors

**Symptom:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify connection string
export DATABASE_URL=postgresql://user:pass@localhost:5432/contd

# Test connection
python -c "from contd.persistence.adapters import PostgresAdapter; PostgresAdapter().health_check()"

# For development, use SQLite
contd init --backend sqlite
```

---

### Metrics Not Appearing

**Symptom:** Prometheus shows no Contd metrics

**Solutions:**
```python
# 1. Ensure metrics server is started
from contd.observability import setup_observability
setup_observability(metrics_port=9090)

# 2. Check server is running
curl http://localhost:9090/metrics

# 3. Verify Prometheus config
# prometheus.yml
scrape_configs:
  - job_name: 'contd'
    static_configs:
      - targets: ['localhost:9090']

# 4. Check Prometheus targets page
# http://localhost:9090/targets
```

---

### Workflow Not Resuming Correctly

**Symptom:** Workflow restarts from beginning instead of resuming

**Causes:**
1. Different workflow_id used
2. State not persisted
3. Idempotency cache cleared

**Solutions:**
```python
# Ensure same workflow_id is used
original_id = "wf-123"
client.resume(original_id)  # Not a new ID!

# Check state exists
engine = ExecutionEngine.get_instance()
state = engine.restore(original_id)
print(f"State at step: {state.step_number}")

# Verify journal has events
events = engine.journal.get_events(original_id)
print(f"Events: {len(events)}")
```

---

### High Memory Usage

**Symptom:** Process memory grows over time

**Causes:**
1. Large state objects
2. Too many concurrent workflows
3. Memory leaks in steps

**Solutions:**
```python
# 1. Keep state small
@step()
def process_large_file(path: str):
    # Don't return large data
    result = process(path)
    save_to_storage(result)
    return {"status": "done", "path": path}  # Small state

# 2. Use streaming for large data
@step()
def stream_process():
    for chunk in read_chunks():
        process_chunk(chunk)
    return {"processed": True}

# 3. Configure snapshot interval
engine = ExecutionEngine.get_instance()
engine.snapshot_interval = 10  # Snapshot every 10 steps
```

---

### Slow Recovery Times

**Symptom:** Workflow resume takes too long

**Causes:**
1. Too many events to replay
2. No snapshots
3. Slow storage

**Solutions:**
```python
# 1. Enable more frequent snapshots
@workflow(WorkflowConfig(snapshot_interval=5))
def my_workflow():
    ...

# 2. Check restore metrics
# contd_restore_duration_milliseconds
# contd_events_replayed_per_restore

# 3. Use faster storage
# Redis for leases, S3 for snapshots
```

---

## Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or specific modules
logging.getLogger('contd.core').setLevel(logging.DEBUG)
logging.getLogger('contd.sdk').setLevel(logging.DEBUG)
```

CLI debug mode:
```bash
contd --debug run my_workflow
```

## Health Checks

```python
from contd.observability.health import HealthChecker

checker = HealthChecker()
status = checker.check_all()

print(f"Database: {status['database']}")
print(f"Storage: {status['storage']}")
print(f"Leases: {status['leases']}")
```

## Getting Help

1. Check [GitHub Issues](https://github.com/contd/contd.ai/issues)
2. Search [Discussions](https://github.com/contd/contd.ai/discussions)
3. Join [Discord](https://discord.gg/contd)
4. Email: support@contd.ai
