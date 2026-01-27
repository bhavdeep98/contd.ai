# Contd.ai Architecture

## Overview

Contd.ai is a durable execution engine designed for long-running AI agent workflows. It provides exactly-once execution semantics, automatic recovery, and multi-tenant isolation.

## Core Principles

1. **Durability First**: Every state change is persisted before acknowledgment
2. **Exactly-Once Semantics**: Steps execute exactly once, even across failures
3. **Multi-Tenancy**: Complete isolation between organizations
4. **Hybrid Recovery**: Fast restoration via snapshots + event replay

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│  Python SDK │ TypeScript  │   Go SDK    │  Java SDK   │   CLI   │
│  @workflow  │   @contd    │   contd.    │  @Workflow  │  contd  │
│  @step      │   Client    │   Client    │  @Step      │   run   │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
       │             │             │             │           │
       └─────────────┴──────┬──────┴─────────────┴───────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
├─────────────────────────────┬───────────────────────────────────┤
│      FastAPI (REST)         │           gRPC                    │
│   /v1/workflows             │      WorkflowService              │
│   /v1/auth                  │      StreamingUpdates             │
│   /v1/webhooks              │                                   │
└──────────────┬──────────────┴───────────────┬───────────────────┘
               │                              │
               └──────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Core Engine                                │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│   Lease     │ Idempotency │  Recovery   │   State     │ Event   │
│  Manager    │   Cache     │   Engine    │  Machine    │  Loop   │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
       │             │             │             │           │
       └─────────────┴──────┬──────┴─────────────┴───────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Persistence Layer                             │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│   Journal   │  Snapshots  │   Leases    │     Auth Store        │
│  (Events)   │  (State)    │  (Locks)    │   (Users/Keys)        │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬────────────┘
       │             │             │                 │
       ▼             ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Adapters                              │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│  PostgreSQL │   SQLite    │    Redis    │         S3            │
│  (Primary)  │   (Dev)     │  (Cache)    │    (Snapshots)        │
└─────────────┴─────────────┴─────────────┴───────────────────────┘
```

## Component Details

### SDK Layer (`contd/sdk/`)

The SDK provides the developer-facing API through decorators:

- **`@workflow`**: Marks a function as a resumable workflow
  - Acquires exclusive lease before execution
  - Starts background heartbeat for lease renewal
  - Handles state restoration on resume
  - Emits observability metrics

- **`@step`**: Marks a function as an idempotent step
  - Checks idempotency cache before execution
  - Records intention before execution (write-ahead)
  - Computes state delta on completion
  - Supports retry policies and timeouts

- **`ExecutionContext`**: Thread-local context for workflow execution
  - Manages state and step counters
  - Provides savepoint creation
  - Handles heartbeat lifecycle

### Core Engine (`contd/core/`)

The execution engine orchestrates workflow lifecycle:

- **`ExecutionEngine`**: Central coordinator
  - Singleton pattern for resource sharing
  - Manages journal, snapshots, and leases
  - Provides restore and recovery operations

- **`LeaseManager`**: Distributed locking
  - Prevents concurrent execution of same workflow
  - Heartbeat-based lease renewal
  - Automatic expiration on failure

- **`IdempotencyCache`**: Exactly-once semantics
  - Tracks completed steps by workflow + step ID
  - Returns cached results on replay
  - Allocates unique attempt IDs

- **`RecoveryEngine`**: State restoration
  - Hybrid recovery: snapshot + event replay
  - Checksum validation for integrity
  - Handles partial failures

### Persistence Layer (`contd/persistence/`)

Pluggable storage with multiple adapters:

- **Journal**: Append-only event log
  - `StepIntentionEvent`: Before step execution
  - `StepCompletedEvent`: After successful step
  - `StepFailedEvent`: On step failure
  - `SavepointCreatedEvent`: Rich savepoint metadata

- **Snapshots**: Periodic state captures
  - Reduces replay time on recovery
  - Configurable snapshot interval
  - S3-compatible storage

- **Leases**: Distributed locks
  - PostgreSQL advisory locks (production)
  - SQLite file locks (development)
  - Redis SETNX (high-performance)

### API Layer (`contd/api/`)

REST and gRPC interfaces:

- **REST Endpoints**:
  - `POST /v1/workflows` - Start workflow
  - `GET /v1/workflows/{id}` - Get status
  - `POST /v1/workflows/{id}/resume` - Resume workflow
  - `GET /v1/workflows/{id}/savepoints` - List savepoints
  - `POST /v1/workflows/{id}/time-travel` - Branch from savepoint

- **gRPC Service**:
  - Streaming workflow updates
  - Efficient binary protocol
  - Language-agnostic clients

## Data Flow

### Workflow Execution

```
1. Client calls POST /v1/workflows
2. API validates request and generates workflow_id
3. Workflow function invoked in background thread
4. @workflow decorator:
   a. Creates ExecutionContext
   b. Acquires lease (or raises WorkflowLocked)
   c. Starts heartbeat thread
   d. Checks if resuming (restores state if so)
   e. Executes workflow function
5. Each @step:
   a. Checks idempotency cache
   b. If cached: return cached result
   c. If not: write intention → execute → write completion
   d. Update state and checkpoint
6. On completion: release lease, emit metrics
```

### Recovery Flow

```
1. Resume request received
2. Engine.restore(workflow_id):
   a. Load latest snapshot (if exists)
   b. Replay events since snapshot
   c. Validate checksum
   d. Return reconstructed state
3. @workflow decorator detects resume
4. Steps replay with idempotency:
   - Completed steps return cached results
   - Execution continues from last incomplete step
```

## Multi-Tenancy

Organization isolation is enforced at multiple levels:

1. **API Layer**: `X-Organization-Id` header required
2. **Auth Context**: Validated against JWT/API key
3. **Persistence**: `org_id` column in all tables
4. **Queries**: Always filtered by org_id

## Observability

Built-in metrics and tracing:

- **Metrics** (Prometheus format):
  - `contd_workflows_started_total`
  - `contd_workflows_completed_total`
  - `contd_restore_duration_milliseconds`
  - `contd_step_duration_milliseconds`
  - `contd_lease_acquisition_duration_milliseconds`

- **Tracing** (OpenTelemetry):
  - Workflow spans with step children
  - Distributed context propagation
  - Integration with Jaeger/Zipkin

## Security Model

- **Authentication**: JWT tokens for users, API keys for services
- **Authorization**: Scoped permissions (workflow:read, workflow:write)
- **Encryption**: TLS in transit, optional at-rest encryption
- **Audit**: All operations logged with actor context
