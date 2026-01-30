# Contd.ai

[![PyPI version](https://img.shields.io/pypi/v/contd.svg)](https://pypi.org/project/contd/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/contd?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pepy.tech/projects/contd)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-yellow.svg)](LICENSE)

**The Durable Execution Engine for Agentic Workflows.**

Contd.ai is a lightweight, multi-tenant framework designed to build, run, and recover long-running AI agent workflows. It provides durable execution guarantees, meaning your agents can pause, resume, crash, and recover exactly where they left off—without losing state or context.

## Key Features

*   **Durable Execution**: Workflows are resumable by default. State is persisted after every step.
*   **Multi-Tenancy**: Built-in organization isolation. Data and execution contexts are strictly scoped to organizations.
*   **Epistemic Savepoints**: Specialized markers for AI agents to save their logic state (hypotheses, goals, decisions) alongside execution state.
*   **Hybrid Recovery**: Fast restoration using snapshots + event replay.
*   **Idempotency**: Automatic retries and de-duplication of steps.
*   **Context Preservation**: Prevents "context rot" in long-running agents with reasoning ledgers and distillation.
*   **LLM Cost Tracking**: Built-in token counting and cost management for LLM-powered workflows.

## Architecture

Contd.ai follows a layered architecture:

*   **SDK (`contd.sdk`)**: Python decorators (`@workflow`, `@step`) to define workflows. Handles context propagation and serialization.
*   **Engine (`contd.core`)**: The brain. Manages the event loop, recovery logic, and lease management.
*   **API (`contd.api`)**: FastAPI interactions for submitting workflows, querying status, and time-travel.
*   **Persistence (`contd.persistence`)**: Pluggable storage adapters. Currently supports Postgres (Journal/Leases) and S3 (Snapshots).

## Client Libraries

Contd provides SDKs for multiple languages:

| Language | Package | Install |
|----------|---------|---------|
| Python | `contd` | `pip install contd` |
| TypeScript/Node.js | `@contd.ai/sdk` | `npm install @contd.ai/sdk` |
| Go | `github.com/bhavdeep98/contd.ai/sdks/go` | `go get github.com/bhavdeep98/contd.ai/sdks/go` |
| Java | `ai.contd:contd-sdk` | Coming soon |

See the `sdks/` directory for full documentation on each SDK.


## Getting Started

### Prerequisites

*   Python 3.10+
*   PostgreSQL (Local or Remote)

### Installation

**From PyPI (Recommended):**

```bash
pip install contd
```

[View on PyPI](https://pypi.org/project/contd/)

**With optional dependencies:**

```bash
pip install contd[postgres]      # PostgreSQL support
pip install contd[redis]         # Redis support
pip install contd[s3]            # S3 storage support
pip install contd[observability] # Metrics & tracing
pip install contd[all]           # Everything
```

**From Source:**

```bash
git clone https://github.com/bhavdeep98/contd.ai.git
cd contd.ai
pip install -e .
```

### Database Setup

1. Create a PostgreSQL database.
2. Run the schema script to initialize tables:

```bash
psql -d contd_db -f contd/persistence/schema.sql
```

### Running the Server

Start the API and gRPC server:

```bash
python -m contd.api.server
```

The server listens on:
*   **HTTP API**: `http://localhost:8000`
*   **gRPC**: `localhost:50051`

## Usage Example

### Defining a Workflow

```python
from contd.sdk.decorators import workflow, step
from contd.sdk.llm import llm_step, LLMStepConfig
from contd.sdk.context import ExecutionContext

@step
def research_topic(topic: str):
    # Simulate work
    return {"summary": f"Research on {topic} complete."}

@llm_step(LLMStepConfig(model="gpt-4o", cost_budget=0.50))
def generate_content(context: dict):
    # LLM call with automatic token tracking
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Write about: {context['summary']}"}]
    )
    return {"response": response, "content": response.choices[0].message.content}

@workflow
def blog_agent(topic: str):
    # Add reasoning breadcrumb
    ctx = ExecutionContext.current()
    ctx.annotate(f"Starting research on topic: {topic}")
    
    data = research_topic(topic)
    final = generate_content(data)
    return final
```

### Triggering a Workflow

Use your API Key to trigger the workflow via HTTP:

```http
POST /v1/workflows
X-API-Key: sk_live_...

{
  "workflow_name": "blog_agent",
  "input": { "topic": "AI Agents" }
}
```

## CLI Usage

Contd includes a powerful CLI for local development and workflow management.

### Installation

```bash
pip install -e .
```

### Initialize a Project

```bash
contd init                    # Initialize with SQLite (default)
contd init --backend postgres # Initialize with Postgres
```

### Run a Workflow

```bash
contd run my_workflow --input '{"key": "value"}'
contd run my_workflow -f input.json
```

### Check Workflow Status

```bash
contd status <workflow_id>
```

### Resume a Suspended Workflow

```bash
contd resume <workflow_id>
```

### Inspect Workflow State

```bash
contd inspect <workflow_id>           # Basic info
contd inspect <workflow_id> --verbose # Full state and events
```

### Time-Travel Debugging

```bash
contd time-travel <workflow_id> <savepoint_id>      # Create new workflow from savepoint
contd time-travel <workflow_id> <savepoint_id> --dry-run # Preview without creating
```

### View Execution Logs

```bash
contd logs <workflow_id>
contd logs <workflow_id> -n 100 -l DEBUG # More lines, debug level
```

### List Workflows

```bash
contd list                    # All workflows
contd list --status running   # Filter by status
```


## Testing

Run the test suite:

```bash
pytest tests/
```

## Documentation

| Document | Description |
|----------|-------------|
| [Quickstart Guide](docs/QUICKSTART.md) | Get started in 5 minutes |
| [Architecture](docs/ARCHITECTURE.md) | System design and components |
| [API Reference](docs/API_REFERENCE.md) | Complete REST/gRPC/SDK reference |
| [Metrics Setup](docs/METRICS_SETUP.md) | Observability configuration |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Contributing](docs/CONTRIBUTING.md) | How to contribute |

## Examples

See the [examples/](examples/) directory for 12+ real-world workflow examples:

- Basic pipelines and error handling
- AI agents with tools
- RAG pipelines
- E-commerce order processing (saga pattern)
- ETL workflows
- Human-in-the-loop approvals
- Batch processing
- Webhook integrations
- Research and code review agents
- Customer support automation

## License

Business Source License 1.1 - see [LICENSE](LICENSE) for details.

Free for non-commercial use. Converts to Apache 2.0 on January 27, 2030. Contact licensing@contd.ai for commercial licensing.
