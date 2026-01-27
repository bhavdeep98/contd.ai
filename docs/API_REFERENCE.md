# Contd.ai API Reference

## REST API

Base URL: `https://api.contd.ai` (or your self-hosted instance)

### Authentication

All API requests require authentication via one of:
- `Authorization: Bearer <jwt_token>` - User sessions
- `X-API-Key: <api_key>` - Service integrations

Organization context required for most endpoints:
- `X-Organization-Id: <org_id>`

---

## Workflows

### Start Workflow

```http
POST /v1/workflows
```

Start a new workflow execution.

**Request Body:**
```json
{
  "workflow_name": "string",
  "input": { },
  "config": {
    "tags": { "key": "value" }
  }
}
```

**Response:** `201 Created`
```json
{
  "workflow_id": "wf-550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors:**
- `404` - Workflow not registered
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

### Get Workflow Status

```http
GET /v1/workflows/{workflow_id}
```

**Response:** `200 OK`
```json
{
  "workflow_id": "wf-550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "step_number": 3,
  "current_step": "process_payment",
  "started_at": "2025-01-27T10:00:00Z",
  "updated_at": "2025-01-27T10:05:00Z"
}
```

**Status Values:**
- `pending` - Queued, not started
- `running` - Currently executing
- `suspended` - Paused, awaiting resume
- `completed` - Successfully finished
- `failed` - Terminated with error

---

### Resume Workflow

```http
POST /v1/workflows/{workflow_id}/resume
```

Resume a suspended or failed workflow.

**Response:** `202 Accepted`
```json
{
  "status": "Resuming"
}
```

---

### List Savepoints

```http
GET /v1/workflows/{workflow_id}/savepoints
```

**Response:** `200 OK`
```json
{
  "savepoints": [
    {
      "savepoint_id": "sp-123",
      "step_number": 5,
      "created_at": "2025-01-27T10:03:00Z",
      "metadata": {
        "goal_summary": "Processing order #12345",
        "hypotheses": ["Payment will succeed"],
        "next_step": "ship_order"
      }
    }
  ]
}
```

---

### Time Travel

```http
POST /v1/workflows/{workflow_id}/time-travel
```

Create a new workflow branched from a savepoint.

**Request Body:**
```json
{
  "savepoint_id": "sp-123"
}
```

**Response:** `201 Created`
```json
{
  "new_workflow_id": "wf-new-branch-id"
}
```

---

## Authentication

### User Signup

```http
POST /v1/auth/signup
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe"
}
```

**Response:** `201 Created`
```json
{
  "user_id": "usr-123",
  "email": "user@example.com"
}
```

---

### Login (Get Token)

```http
POST /v1/auth/token
Content-Type: application/x-www-form-urlencoded
```

**Request Body:**
```
username=user@example.com&password=secure_password
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Create Organization

```http
POST /v1/auth/organizations
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "name": "My AI Team"
}
```

**Response:** `201 Created`
```json
{
  "org_id": "org-456",
  "name": "My AI Team"
}
```

---

### Create API Key

```http
POST /v1/auth/apikeys
Authorization: Bearer <token>
X-Organization-Id: <org_id>
```

**Request Body:**
```json
{
  "name": "Production Agent",
  "scopes": ["workflow:read", "workflow:write"]
}
```

**Response:** `201 Created`
```json
{
  "key_id": "key-789",
  "api_key": "sk_live_...",
  "name": "Production Agent",
  "scopes": ["workflow:read", "workflow:write"]
}
```

**Note:** The `api_key` is only shown once. Store it securely.

---

## Webhooks

### Register Webhook

```http
POST /v1/webhooks
```

**Request Body:**
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["workflow.completed", "workflow.failed"],
  "secret": "your_webhook_secret"
}
```

**Response:** `201 Created`
```json
{
  "webhook_id": "wh-123",
  "url": "https://your-server.com/webhook",
  "events": ["workflow.completed", "workflow.failed"]
}
```

---

### Webhook Events

Events are delivered as POST requests with signature header:

```http
POST https://your-server.com/webhook
X-Contd-Signature: sha256=...
Content-Type: application/json
```

**Event Payload:**
```json
{
  "event": "workflow.completed",
  "workflow_id": "wf-123",
  "timestamp": "2025-01-27T10:10:00Z",
  "data": {
    "status": "completed",
    "duration_seconds": 45.2
  }
}
```

**Event Types:**
- `workflow.started`
- `workflow.completed`
- `workflow.failed`
- `workflow.suspended`
- `step.completed`
- `savepoint.created`

---

## Python SDK Reference

### Decorators

#### `@workflow(config: WorkflowConfig = None)`

```python
from contd.sdk import workflow, WorkflowConfig

@workflow(WorkflowConfig(
    workflow_id=None,        # Auto-generated if None
    max_duration=None,       # timedelta, optional
    retry_policy=None,       # Default retry for steps
    tags={"team": "ai"},     # Metadata tags
    org_id=None              # Organization ID
))
def my_workflow(input_data):
    pass
```

#### `@step(config: StepConfig = None)`

```python
from contd.sdk import step, StepConfig, RetryPolicy
from datetime import timedelta

@step(StepConfig(
    checkpoint=True,         # Create checkpoint after step
    idempotency_key=None,    # Custom key function
    retry=RetryPolicy(
        max_attempts=3,
        backoff_base=2.0,
        backoff_max=60.0,
        backoff_jitter=0.5,
        retryable_exceptions=[ConnectionError]
    ),
    timeout=timedelta(seconds=30),
    savepoint=False          # Create rich savepoint
))
def my_step(data):
    return {"result": "done"}
```

### ExecutionContext

```python
from contd.sdk import ExecutionContext

# Get current context (inside workflow/step)
ctx = ExecutionContext.current()

# Access properties
ctx.workflow_id      # Current workflow ID
ctx.org_id           # Organization ID
ctx.workflow_name    # Workflow function name
ctx.tags             # Metadata tags

# Create savepoint with epistemic metadata
ctx.create_savepoint({
    "goal_summary": "Processing customer order",
    "hypotheses": ["Payment will succeed"],
    "questions": ["Is inventory available?"],
    "decisions": ["Using express shipping"],
    "next_step": "validate_inventory"
})

# Update tags at runtime
ctx.update_tags({"priority": "high"})
```

### Client

```python
from contd.sdk import ContdClient

client = ContdClient(
    api_key="sk_live_...",
    base_url="https://api.contd.ai"
)

# Start workflow
workflow_id = client.start_workflow(
    workflow_name="process_order",
    input={"order_id": "12345"},
    config={"tags": {"priority": "high"}}
)

# Get status
status = client.get_status(workflow_id)

# Resume
client.resume(workflow_id)

# Time travel
new_id = client.time_travel(workflow_id, "savepoint-id")

# List savepoints
savepoints = client.list_savepoints(workflow_id)
```

### Errors

```python
from contd.sdk.errors import (
    ContdError,           # Base exception
    WorkflowLocked,       # Workflow already running
    WorkflowNotFound,     # Workflow doesn't exist
    StepTimeout,          # Step exceeded timeout
    StepExecutionFailed,  # Step raised exception
    TooManyAttempts,      # Retry limit exceeded
    NoActiveWorkflow      # No context available
)

try:
    result = my_step()
except WorkflowLocked as e:
    print(f"Locked by: {e.owner_id}")
except StepTimeout as e:
    print(f"Step {e.step_name} timed out after {e.timeout_seconds}s")
except TooManyAttempts as e:
    print(f"Failed after {e.max_attempts} attempts: {e.last_error}")
```

---

## gRPC API

### Service Definition

```protobuf
service WorkflowService {
  rpc StartWorkflow(StartWorkflowRequest) returns (StartWorkflowResponse);
  rpc GetStatus(GetStatusRequest) returns (WorkflowStatusResponse);
  rpc Resume(ResumeRequest) returns (ResumeResponse);
  rpc StreamUpdates(StreamRequest) returns (stream WorkflowUpdate);
}
```

### Python gRPC Client

```python
import grpc
from contd.api.proto import workflow_pb2, workflow_pb2_grpc

channel = grpc.insecure_channel('localhost:50051')
stub = workflow_pb2_grpc.WorkflowServiceStub(channel)

# Start workflow
response = stub.StartWorkflow(workflow_pb2.StartWorkflowRequest(
    workflow_name="process_order",
    input_json='{"order_id": "12345"}'
))

# Stream updates
for update in stub.StreamUpdates(workflow_pb2.StreamRequest(
    workflow_id=response.workflow_id
)):
    print(f"Step {update.step_number}: {update.status}")
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| POST /v1/workflows | 100/min |
| GET /v1/workflows/* | 1000/min |
| POST /v1/auth/* | 10/min |
| Webhooks | 1000/min |

Rate limit headers:
- `X-RateLimit-Limit`: Maximum requests
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp
