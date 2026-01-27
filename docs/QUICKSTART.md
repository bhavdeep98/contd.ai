# Contd.ai Quickstart Guide

Get up and running with durable workflows in 5 minutes.

## Installation

```bash
pip install contd
```

Or from source:
```bash
git clone https://github.com/contd/contd.ai.git
cd contd.ai
pip install -e .
```

## Your First Workflow

Create `my_workflow.py`:

```python
from contd.sdk import workflow, step

@step()
def fetch_data(url: str) -> dict:
    """Fetch data from external API."""
    import requests
    response = requests.get(url)
    return {"data": response.json()}

@step()
def process_data(data: dict) -> dict:
    """Process the fetched data."""
    items = data.get("data", [])
    return {"processed_count": len(items)}

@step()
def save_results(results: dict) -> dict:
    """Save results to database."""
    print(f"Saved {results['processed_count']} items")
    return {"status": "complete"}

@workflow()
def data_pipeline(url: str):
    """A simple data processing pipeline."""
    data = fetch_data(url)
    results = process_data(data)
    save_results(results)
    return results
```

## Run Locally

### Option 1: Direct Execution

```python
# run.py
from my_workflow import data_pipeline

result = data_pipeline("https://api.example.com/items")
print(result)
```

### Option 2: CLI

```bash
# Initialize local database
contd init

# Run workflow
contd run data_pipeline --input '{"url": "https://api.example.com/items"}'
```

## Add Durability Features

### Retry Policy

```python
from contd.sdk import step, StepConfig, RetryPolicy

@step(StepConfig(
    retry=RetryPolicy(
        max_attempts=3,
        backoff_base=2.0,      # Exponential backoff
        backoff_max=60.0,      # Max 60s between retries
        backoff_jitter=0.5     # Add randomness
    )
))
def fetch_data(url: str) -> dict:
    # Will retry up to 3 times on failure
    ...
```

### Timeouts

```python
from datetime import timedelta

@step(StepConfig(timeout=timedelta(seconds=30)))
def slow_operation():
    # Raises StepTimeout if exceeds 30 seconds
    ...
```

### Savepoints (AI Agent Memory)

```python
from contd.sdk import step, StepConfig, ExecutionContext

@step(StepConfig(savepoint=True))
def analyze_data(data: dict) -> dict:
    ctx = ExecutionContext.current()
    
    # Store epistemic metadata for AI agents
    ctx.create_savepoint({
        "goal_summary": "Analyzing customer data",
        "hypotheses": ["Data quality is good", "No anomalies expected"],
        "questions": ["Are there seasonal patterns?"],
        "decisions": ["Using standard analysis pipeline"],
        "next_step": "generate_report"
    })
    
    return {"analysis": "complete"}
```

## Connect to Server

### Start the Server

```bash
# With PostgreSQL
export DATABASE_URL=postgresql://user:pass@localhost/contd
python -m contd.api.server
```

### Use the Client

```python
from contd.sdk import ContdClient

client = ContdClient(
    api_key="sk_live_your_key",
    base_url="http://localhost:8000"
)

# Start workflow
workflow_id = client.start_workflow(
    workflow_name="data_pipeline",
    input={"url": "https://api.example.com/items"}
)

# Check status
status = client.get_status(workflow_id)
print(f"Status: {status.status}, Step: {status.step_number}")

# Resume if interrupted
client.resume(workflow_id)
```

## Multi-Language Support

### TypeScript

```typescript
import { ContdClient } from '@contd/sdk';

const client = new ContdClient({ apiKey: 'sk_live_...' });
const workflowId = await client.startWorkflow({
  workflowName: 'data_pipeline',
  input: { url: 'https://api.example.com/items' }
});
```

### Go

```go
client := contd.NewClient(contd.ClientConfig{APIKey: "sk_live_..."})
workflowID, _ := client.StartWorkflow(ctx, contd.StartWorkflowInput{
    WorkflowName: "data_pipeline",
    Input: map[string]interface{}{"url": "https://api.example.com/items"},
})
```

### Java

```java
ContdClient client = ContdClient.builder()
    .apiKey("sk_live_...")
    .build();
String workflowId = client.startWorkflow("data_pipeline", 
    Map.of("url", "https://api.example.com/items"), null);
```

## What's Next?

- [Architecture Overview](ARCHITECTURE.md) - Understand how Contd works
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Examples](../examples/) - Real-world workflow examples
- [Migration Guides](MIGRATION_LANGCHAIN.md) - Coming from another framework?
