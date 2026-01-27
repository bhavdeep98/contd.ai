# AI Continuity Layer (ACL)

## 1. Executive Summary

Modern AI systems fail at a fundamental capability: **continuing unfinished work across time**. While memory systems allow recall of facts, preferences, and prior decisions, they do not track *ongoing work*. As a result, AI agents struggle with interruptions, task handoff, and long-running workflows.

The AI Continuity Layer (ACL) addresses this gap by introducing a **minimal, deterministic, and auditable workflow kernel** that enables an AI system to reliably resume work where it left off. ACL is deliberately scoped, engineered to sit cleanly beside existing memory systems without contaminating them.

---

## 2. Problem Statement

### 2.1 Core Problem

AI systems today lack:
- A persistent notion of **ongoing state**
- Awareness of **progress**
- Explicit representation of **unfinished work**

As a result:
- Interruptions reset progress
- Intent must be re-derived repeatedly
- Long-running workflows become fragile

### 2.2 What Existing Memory Solves (and Does Not)

Memory systems solve:
- Recall of semantic information
- Preferences and stable decisions
- Knowledge accumulation

They do *not* solve:
- Task lifecycle
- Progress tracking
- Resume semantics
- Deterministic next-step selection

ACL exists to solve precisely these gaps.

---

## 3. Design Principles

1. **Explicit State Over Inference**  
   No task status or progress is inferred from conversation logs.

2. **Deterministic Resumption**  
   Given the same state, the system always selects the same next step.

3. **Append-Only Truth**  
   All state changes are recorded as immutable events.

4. **Strict Boundaries**  
   - Continuity tracks *work*
   - Memory tracks *knowledge*

5. **Minimalism**  
   Only the primitives required for continuity are implemented.

---

## 4. System Scope

### In Scope
- Goals, tasks, and progress
- Interruptions and resumption
- Checkpoints
- Deterministic next-step logic

### Out of Scope
- Knowledge storage
- Autonomous goal creation
- Optimization or planning algorithms
- Correctness of outputs
- Project management features

---

## 5. High-Level Architecture

```
┌───────────────────────────────┐
│         Client / UI           │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│     Continuity API Layer      │
│  (Authoritative Work State)   │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│   Continuity Core Engine      │
│  - State Machine              │
│  - Resume Policy              │
│  - Event Ledger               │
└───────────────┬───────────────┘
        ┌───────┴────────┐
        ↓                ↓
┌───────────────┐   ┌────────────────┐
│  Memory Store │   │  LLM Executor  │
│  (Read-Only)  │   │  (Tool)        │
└───────────────┘   └────────────────┘
```

---

## 6. Core Data Model

### 6.1 Goal

Represents *why* work is being done.

- `goal_id`
- `text`
- `priority`
- `status`: active | paused | done
- `created_at`

### 6.2 Task

Represents a unit of work.

- `task_id`
- `goal_id`
- `title`
- `status`: todo | doing | blocked | done
- `acceptance_criteria[]` (optional)
- `depends_on[]` (optional)
- `updated_at`

### 6.3 Checkpoint

A precise resume handle.

- `task_id`
- `where_we_left_off` (1–3 sentences)
- `next_step` (single atomic action)
- `needed_context_refs[]`
- `blockers[]`
- `timestamp`

### 6.4 Event (Append-Only Ledger)

- `event_id`
- `timestamp`
- `type`
- `payload`

Events are the source of truth for reconstructing state.

---

## 7. State Machine

### Task State Transitions

Allowed transitions only:
- todo → doing
- doing → blocked | done | todo
- blocked → doing | todo
- done → doing (reopen)

Every transition emits an event.
Invalid transitions are rejected.

---

## 8. Core Algorithms

### 8.1 State Rehydration

**Input:** project_id  
**Output:** ActiveWorkState

Steps:
1. Load events
2. Rebuild current goals and tasks
3. Identify active task
4. Load latest checkpoint
5. Collect unresolved blockers

### 8.2 Next-Step Selection Policy

Deterministic priority order:
1. Task with status = doing
2. Most recently blocked task
3. Highest priority todo task
4. If none, request task proposals (non-committal)

Returns:
- `task_id`
- `next_step`
- `required_context_refs`

---

## 9. Interaction with External Memory Systems

### Read-Only Usage

ACL may query external memory systems for:
- Stable preferences
- Past decisions
- Domain facts

### Write Restrictions

ACL may only write *stable learnings* to external memory systems.

ACL must never store:
- Task status
- Checkpoints
- Progress

**Rule:** If it changes daily, it does not belong in external memory.

---

## 10. APIs (Minimal Set)

1. `create_goal(text, priority)`
2. `add_task(goal_id, title, acceptance_criteria?)`
3. `start_task(task_id)`
4. `pause_task(task_id, reason?)` / `block_task(task_id, blocker)`
5. `complete_task(task_id, evidence?)`
6. `update_checkpoint(task_id, where_left_off, next_step, context_refs[])`
7. `get_next_step(project_id)`

---

## 11. Persistence Contracts & Restore Invariants

### 11.1 Event Ordering and Sequencing

All events are assigned a **monotonic per-workflow sequence number (`event_seq`)** at write time. Restore logic MUST replay events strictly by `event_seq`, never by timestamp, to avoid clock skew and reordering bugs.

Snapshots persist the `last_event_seq` they cover. On restore:
- Load latest snapshot
- Replay events where `event_seq > last_event_seq`

### 11.2 Exactly-Once Execution Semantics

The system guarantees:
- **Exactly-once commit** of step results
- **At-most-once execution** under a valid workflow lease

This is enforced via:
- Workflow leases (single active executor per workflow)
- Idempotency guards keyed by `(workflow_id, step_id)`
- Append-only event journal with unique constraints

### 11.3 Workflow Leases

A workflow lease is required before executing any step.

- Leases have an expiration timestamp
- Executors must renew leases periodically
- Expired leases may be stolen by another executor

This prevents concurrent execution and duplicate side effects.

### 11.4 Snapshot Atomicity

Snapshots are created atomically with:
- A materialized state blob (inline or S3)
- The `last_event_seq` included

Restore MUST treat snapshots as authoritative up to `last_event_seq`.

### 11.5 State Delta Semantics

State changes are represented using a **standardized delta format** (e.g., JSON Patch RFC 6902).

Invariants:
- Deltas must be deterministic
- Applying deltas in sequence MUST reconstruct identical state
- Checksums are validated after restore and delta application

### 11.6 Integrity Checks

Every `WorkflowState` includes a checksum computed over a canonical serialization.

Restore MUST:
- Validate checksum on snapshot load
- Validate checksum after delta replay
- Fail closed on mismatch

---

## 11.7 Persistence Layer Specification

This section operationalizes the persistence contracts into concrete storage schemas and protocols. The continuity core relies on these guarantees for deterministic restore, safe execution, and auditability.

### 11.7.1 Event Journal Schema (Postgres)

```sql
CREATE TABLE events (
  event_id UUID NOT NULL,
  workflow_id UUID NOT NULL,
  event_seq BIGINT NOT NULL,        -- Monotonic per workflow
  event_type VARCHAR(50) NOT NULL,
  payload JSONB NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  schema_version VARCHAR(10) NOT NULL,
  producer_version VARCHAR(20) NOT NULL,
  checksum VARCHAR(64) NOT NULL,    -- SHA256 of canonical payload
  PRIMARY KEY (workflow_id, event_seq),
  UNIQUE (event_id)
);

CREATE INDEX idx_events_workflow_seq ON events(workflow_id, event_seq);
CREATE INDEX idx_events_type ON events(event_type);
```

**Append protocol (contract):**
- Assign `event_seq` atomically per workflow (transactional allocation + insert)
- Persist checksum for payload integrity validation
- Events are immutable once written

### 11.7.2 Workflow Lease Schema (Single Executor + Fencing)

```sql
CREATE TABLE workflow_leases (
  workflow_id UUID PRIMARY KEY,
  owner_id TEXT NOT NULL,
  acquired_at TIMESTAMPTZ NOT NULL,
  lease_expires_at TIMESTAMPTZ NOT NULL,
  fencing_token BIGINT NOT NULL,    -- Monotonic, fences stale owners
  heartbeat_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_leases_expiry ON workflow_leases(lease_expires_at);
```

**Lease protocol (contract):**
- A valid lease is required before executing any step
- Heartbeat extends the lease only if `(workflow_id, owner_id, fencing_token)` match
- Fencing token increments on lease takeover; stale executors are rejected

### 11.7.3 Idempotency Tables (Attempts + Completed)

```sql
CREATE TABLE step_attempts (
  workflow_id UUID NOT NULL,
  step_id VARCHAR(100) NOT NULL,
  attempt_id INT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  fencing_token BIGINT,
  PRIMARY KEY (workflow_id, step_id, attempt_id)
);

CREATE TABLE completed_steps (
  workflow_id UUID NOT NULL,
  step_id VARCHAR(100) NOT NULL,
  attempt_id INT NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL,
  result_snapshot_ref TEXT,         -- Reference, not inline state
  result_checksum VARCHAR(64),
  PRIMARY KEY (workflow_id, step_id),
  FOREIGN KEY (workflow_id, step_id, attempt_id)
    REFERENCES step_attempts(workflow_id, step_id, attempt_id)
);
```

**Idempotency contract:**
- Each `(workflow_id, step_id)` may complete at most once
- Retries allocate unique `attempt_id` via atomic insert
- Completed results are checksummed and loaded via snapshot refs

### 11.7.4 Snapshot Schema (Inline + S3)

```sql
CREATE TABLE snapshots (
  snapshot_id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL,
  step_number INT NOT NULL,
  last_event_seq BIGINT NOT NULL,   -- Critical for deterministic restore
  state_inline JSONB,               -- For small state
  state_s3_key TEXT,                -- For large state
  state_checksum VARCHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_snapshots_workflow_seq ON snapshots(workflow_id, last_event_seq DESC);
```

**Snapshot contract:**
- Each snapshot MUST include `last_event_seq`
- Restore MUST replay events where `event_seq > last_event_seq` in ascending order
- Checksum validation MUST fail closed

### 11.7.5 Delta Format and Deterministic Replay

State deltas MUST be represented in a standardized format such as **JSON Patch (RFC 6902)**.

Invariants:
- `compute_delta(old, new)` is deterministic
- Applying deltas in `event_seq` order reconstructs identical state
- Integrity checks validate both event payloads and restored state

### 11.7.6 Exactly-Once Semantics by Step Type

| Step Type | System Guarantee | Requirement |
|---|---|---|
| Pure computation | Exactly-once execution (under lease) | None |
| Idempotent side effects | At-least-once safe | External idempotency OK |
| Non-idempotent side effects | Requires external idempotency key | Mandatory |

### 11.7.7 Observability Contracts (Minimum)

Core metrics:
- `restore_time_ms`
- `events_replayed_per_restore`
- `time_since_last_snapshot_sec`
- `journal_size_since_snapshot_bytes`
- `lease_acquisition_failures`
- `idempotency_cache_hits`

Guideline: if `events_replayed_per_restore` routinely exceeds ~100, snapshot policy needs tuning.

---

## 12. Testing Strategy

Test **system invariants**, not AI intelligence.

### What We Test
- Valid state transitions
- Event emission correctness
- Checkpoint persistence
- Resume logic determinism
- Interruption/resumption scenarios
- Conflict handling

### What We Mock
- LLM outputs
- Task decomposition
- Summaries

---

## 13. Build Plan

### Phase 0 – Foundations (Week 1)
- Define schemas
- Implement Event Ledger
- Implement Task state machine
- Unit tests for transitions

### Phase 1 – Core Continuity (Week 2)
- Goal and Task APIs
- Checkpoint creation/update
- State rehydration logic
- Deterministic resume policy

### Phase 2 – Integration (Week 3)
- External memory system integration
- LLM executor interface
- Context loading controls

### Phase 3 – Robustness (Week 4)
- Interruption/resumption tests
- Conflict and rollback handling
- Multi-project isolation

### Phase 4 – Hardening (Week 5)
- Metrics and logging
- Failure injection tests
- Documentation and examples

---

## 14. Success Criteria

The system is successful if:
- Work can be paused and resumed days later without loss
- The same state always yields the same next step
- No task state is inferred implicitly
- External memory systems remain independent and reusable

---

## 15. One-Sentence Summary

**The AI Continuity Layer gives AI systems a reliable sense of unfinished work by representing progress as explicit state with deterministic resumption, cleanly separated from memory and intelligence.**
