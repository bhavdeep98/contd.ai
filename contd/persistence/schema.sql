-- 1.1 Event Append Protocol
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

-- 1.2 Lease Protocol
CREATE TABLE workflow_leases (
    workflow_id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    fencing_token BIGINT NOT NULL,    -- Monotonic, for fencing stale owners
    heartbeat_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_leases_expiry ON workflow_leases(lease_expires_at);

-- 1.3 Idempotency Table
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

-- 1.4 Snapshot Protocol
CREATE TABLE snapshots (
    snapshot_id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL,
    step_number INT NOT NULL,
    last_event_seq BIGINT NOT NULL,   -- Critical for restore
    state_inline JSONB,               -- For small state (<100KB)
    state_s3_key TEXT,                -- For large state
    state_checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_snapshots_workflow ON snapshots(workflow_id, last_event_seq DESC);
