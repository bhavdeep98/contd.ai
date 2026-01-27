# Migration Guide: Temporal to Contd.ai

This guide helps you migrate workflows from Temporal to Contd.ai.

## Comparison

| Feature | Temporal | Contd.ai |
|---------|----------|----------|
| Language | Go, Java, Python, TS | Python (primary), TS, Go, Java |
| Deployment | Self-hosted cluster | Single binary or hosted |
| Complexity | High (requires cluster) | Low (embedded or API) |
| AI-specific | Generic | Epistemic savepoints |
| Learning curve | Steep | Gentle |

## When to Migrate

**Choose Contd.ai when:**
- Building AI agent workflows
- Need simpler deployment
- Want epistemic savepoints for AI reasoning
- Prefer Python-first development

**Stay with Temporal when:**
- Already invested in Temporal infrastructure
- Need advanced features (signals, queries, child workflows)
- Running at massive scale (millions of workflows)

## Basic Workflow Migration

### Temporal (Python)

```python
from temporalio import workflow, activity
from datetime import timedelta

@activity.defn
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

@activity.defn
async def process_data(data: dict) -> dict:
    return {"processed": len(data)}

@workflow.defn
class DataPipelineWorkflow:
    @workflow.run
    async def run(self, url: str) -> dict:
        data = await workflow.execute_activity(
            fetch_data,
            url,
            start_to_close_timeout=timedelta(seconds=30),
        )
        result = await workflow.execute_activity(
            process_data,
            data,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result
```

### Contd.ai

```python
from contd.sdk import workflow, step, StepConfig
from datetime import timedelta

@step(StepConfig(timeout=timedelta(seconds=30)))
def fetch_data(url: str) -> dict:
    import requests
    response = requests.get(url)
    return response.json()

@step(StepConfig(timeout=timedelta(seconds=30)))
def process_data(data: dict) -> dict:
    return {"processed": len(data)}

@workflow()
def data_pipeline(url: str) -> dict:
    data = fetch_data(url)
    result = process_data(data)
    return result
```

## Activity to Step Migration

### Temporal Activity

```python
@activity.defn
async def send_email(to: str, subject: str, body: str) -> bool:
    # Activity with retry
    ...
    return True

# In workflow
result = await workflow.execute_activity(
    send_email,
    args=["user@example.com", "Hello", "Body"],
    start_to_close_timeout=timedelta(seconds=60),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=5,
    ),
)
```

### Contd.ai Step

```python
from contd.sdk import step, StepConfig, RetryPolicy
from datetime import timedelta

@step(StepConfig(
    timeout=timedelta(seconds=60),
    retry=RetryPolicy(
        max_attempts=5,
        backoff_base=1.0,
        backoff_max=60.0,
    )
))
def send_email(to: str, subject: str, body: str) -> bool:
    # Step with retry
    ...
    return True

# In workflow - just call directly
result = send_email("user@example.com", "Hello", "Body")
```

## Workflow Patterns

### Saga Pattern

#### Temporal

```python
@workflow.defn
class OrderSagaWorkflow:
    @workflow.run
    async def run(self, order: dict) -> dict:
        try:
            await workflow.execute_activity(reserve_inventory, order)
            await workflow.execute_activity(charge_payment, order)
            await workflow.execute_activity(ship_order, order)
            return {"status": "completed"}
        except Exception as e:
            # Compensate
            await workflow.execute_activity(cancel_shipment, order)
            await workflow.execute_activity(refund_payment, order)
            await workflow.execute_activity(release_inventory, order)
            raise
```

#### Contd.ai

```python
from contd.sdk import workflow, step

@step()
def reserve_inventory(order: dict) -> dict:
    return {"reservation_id": "res-123"}

@step()
def charge_payment(order: dict) -> dict:
    return {"payment_id": "pay-456"}

@step()
def ship_order(order: dict) -> dict:
    return {"shipment_id": "ship-789"}

# Compensation steps
@step()
def cancel_shipment(order: dict): pass

@step()
def refund_payment(order: dict): pass

@step()
def release_inventory(order: dict): pass

@workflow()
def order_saga(order: dict) -> dict:
    completed_steps = []
    
    try:
        reserve_inventory(order)
        completed_steps.append("inventory")
        
        charge_payment(order)
        completed_steps.append("payment")
        
        ship_order(order)
        completed_steps.append("shipment")
        
        return {"status": "completed"}
        
    except Exception as e:
        # Compensate in reverse order
        if "shipment" in completed_steps:
            cancel_shipment(order)
        if "payment" in completed_steps:
            refund_payment(order)
        if "inventory" in completed_steps:
            release_inventory(order)
        raise
```

### Timer/Sleep

#### Temporal

```python
@workflow.defn
class DelayedWorkflow:
    @workflow.run
    async def run(self) -> dict:
        await workflow.execute_activity(step1)
        await asyncio.sleep(3600)  # 1 hour
        await workflow.execute_activity(step2)
```

#### Contd.ai

```python
import time
from contd.sdk import workflow, step

@step()
def step1(): pass

@step()
def step2(): pass

@step()
def durable_sleep(seconds: int) -> dict:
    """Sleep is checkpointed - survives restarts."""
    time.sleep(seconds)
    return {"slept": seconds}

@workflow()
def delayed_workflow():
    step1()
    durable_sleep(3600)  # 1 hour - checkpointed!
    step2()
```

### Signals (External Events)

#### Temporal

```python
@workflow.defn
class ApprovalWorkflow:
    def __init__(self):
        self.approved = False
    
    @workflow.signal
    async def approve(self):
        self.approved = True
    
    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: self.approved)
        return {"status": "approved"}
```

#### Contd.ai

```python
from contd.sdk import workflow, step, ExecutionContext

@step()
def wait_for_approval(workflow_id: str) -> dict:
    """Poll for external approval signal."""
    import time
    from contd.core.engine import ExecutionEngine
    
    engine = ExecutionEngine.get_instance()
    
    while True:
        state = engine.restore(workflow_id)
        if state.variables.get("approved"):
            return {"approved": True}
        time.sleep(5)  # Poll every 5 seconds

@workflow()
def approval_workflow():
    ctx = ExecutionContext.current()
    result = wait_for_approval(ctx.workflow_id)
    return {"status": "approved"}

# External signal via API
# POST /v1/workflows/{id}/signal
# {"signal": "approve", "data": {"approved": true}}
```

## Client Migration

### Temporal Client

```python
from temporalio.client import Client

client = await Client.connect("localhost:7233")

# Start workflow
handle = await client.start_workflow(
    DataPipelineWorkflow.run,
    "https://api.example.com",
    id="my-workflow-id",
    task_queue="my-queue",
)

# Get result
result = await handle.result()

# Query status
status = await handle.query(DataPipelineWorkflow.get_status)
```

### Contd.ai Client

```python
from contd.sdk import ContdClient

client = ContdClient(api_key="sk_live_...")

# Start workflow
workflow_id = client.start_workflow(
    workflow_name="data_pipeline",
    input={"url": "https://api.example.com"}
)

# Get status
status = client.get_status(workflow_id)

# Get result (poll or webhook)
while status.status != "completed":
    time.sleep(1)
    status = client.get_status(workflow_id)
```

## Worker Migration

### Temporal Worker

```python
from temporalio.worker import Worker

async def main():
    client = await Client.connect("localhost:7233")
    
    worker = Worker(
        client,
        task_queue="my-queue",
        workflows=[DataPipelineWorkflow],
        activities=[fetch_data, process_data],
    )
    
    await worker.run()
```

### Contd.ai

```python
# No separate worker needed!
# Workflows run in the API server or directly

# Option 1: Run via API server
python -m contd.api.server

# Option 2: Run directly
from my_workflows import data_pipeline
result = data_pipeline("https://api.example.com")

# Option 3: CLI
contd run data_pipeline --input '{"url": "..."}'
```

## Key Differences

| Concept | Temporal | Contd.ai |
|---------|----------|----------|
| Activity | `@activity.defn` | `@step()` |
| Workflow | `@workflow.defn` class | `@workflow()` function |
| Execution | `workflow.execute_activity()` | Direct function call |
| Worker | Separate process | Embedded in API |
| Task Queue | Required | Not needed |
| Signals | `@workflow.signal` | API endpoint |
| Queries | `@workflow.query` | `get_status()` |
| Child Workflows | `workflow.execute_child_workflow()` | Call workflow function |

## Gradual Migration

Run both systems during migration:

```python
from contd.sdk import workflow, step
from temporalio.client import Client

@step()
def call_temporal_workflow(workflow_id: str, input: dict) -> dict:
    """Bridge to existing Temporal workflow."""
    import asyncio
    
    async def run():
        client = await Client.connect("localhost:7233")
        handle = await client.start_workflow(
            LegacyWorkflow.run,
            input,
            id=workflow_id,
            task_queue="legacy-queue",
        )
        return await handle.result()
    
    return asyncio.run(run())

@workflow()
def hybrid_workflow(data: dict):
    """Mix Contd and Temporal."""
    # New Contd step
    processed = new_contd_step(data)
    
    # Call legacy Temporal workflow
    legacy_result = call_temporal_workflow("legacy-wf", processed)
    
    # Continue in Contd
    return finalize_step(legacy_result)
```

## Next Steps

- [Quickstart Guide](QUICKSTART.md) - Get started with Contd.ai
- [Architecture](ARCHITECTURE.md) - Understand the system
- [API Reference](API_REFERENCE.md) - Full API documentation
