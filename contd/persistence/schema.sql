-- 1.0 Identity & Access Management (Must check this first for tenancy)

CREATE TABLE organizations (
    org_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE organization_members (
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    role VARCHAR(50) NOT NULL, -- 'owner', 'admin', 'member', 'viewer'
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id)
);

CREATE TABLE api_keys (
    key_id UUID PRIMARY KEY,
    key_prefix VARCHAR(10) NOT NULL,
    key_hash VARCHAR(255) NOT NULL, -- store hash of the full key
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    user_id UUID REFERENCES users(user_id), -- optional, if service account
    name VARCHAR(255),
    scopes TEXT[], -- 'workflow:read', 'workflow:write', etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- 1.1 Event Append Protocol
CREATE TABLE events (
    event_id UUID NOT NULL,
    org_id UUID NOT NULL,             -- Multi-tenancy
    workflow_id UUID NOT NULL,
    event_seq BIGINT NOT NULL,        -- Monotonic per workflow
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    schema_version VARCHAR(10) NOT NULL,
    producer_version VARCHAR(20) NOT NULL,
    checksum VARCHAR(64) NOT NULL,    -- SHA256 of canonical payload
    
    PRIMARY KEY (workflow_id, event_seq),
    UNIQUE (event_id),
    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
);

CREATE INDEX idx_events_workflow_seq ON events(workflow_id, event_seq);
CREATE INDEX idx_events_org ON events(org_id);
CREATE INDEX idx_events_type ON events(event_type);

-- 1.2 Lease Protocol
CREATE TABLE workflow_leases (
    workflow_id UUID PRIMARY KEY,
    org_id UUID NOT NULL,             -- Multi-tenancy
    owner_id TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    fencing_token BIGINT NOT NULL,    -- Monotonic, for fencing stale owners
    heartbeat_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
);

CREATE INDEX idx_leases_expiry ON workflow_leases(lease_expires_at);
CREATE INDEX idx_leases_org ON workflow_leases(org_id);

-- 1.3 Idempotency Table
CREATE TABLE step_attempts (
    workflow_id UUID NOT NULL,
    org_id UUID NOT NULL,             -- Multi-tenancy
    step_id VARCHAR(100) NOT NULL,
    attempt_id INT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    fencing_token BIGINT,
    
    PRIMARY KEY (workflow_id, step_id, attempt_id),
    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
);

CREATE TABLE completed_steps (
    workflow_id UUID NOT NULL,
    org_id UUID NOT NULL,             -- Multi-tenancy
    step_id VARCHAR(100) NOT NULL,
    attempt_id INT NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    result_snapshot_ref TEXT,         -- Reference, not inline state
    result_checksum VARCHAR(64),
    
    PRIMARY KEY (workflow_id, step_id),
    FOREIGN KEY (workflow_id, step_id, attempt_id) 
        REFERENCES step_attempts(workflow_id, step_id, attempt_id),
    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
);

-- 1.4 Snapshot Protocol
CREATE TABLE snapshots (
    snapshot_id UUID PRIMARY KEY,
    org_id UUID NOT NULL,             -- Multi-tenancy
    workflow_id UUID NOT NULL,
    step_number INT NOT NULL,
    last_event_seq BIGINT NOT NULL,   -- Critical for restore
    state_inline JSONB,               -- For small state (<100KB)
    state_s3_key TEXT,                -- For large state
    state_checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
);

CREATE INDEX idx_snapshots_workflow ON snapshots(workflow_id, last_event_seq DESC);
CREATE INDEX idx_snapshots_org ON snapshots(org_id);

-- 1.5 Webhooks
CREATE TABLE webhooks (
    webhook_id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    url TEXT NOT NULL,
    events TEXT NOT NULL,              -- JSON array of event types
    secret_hash VARCHAR(64) NOT NULL,
    description TEXT,
    headers TEXT,                      -- JSON object of custom headers
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhooks_org ON webhooks(org_id);
CREATE INDEX idx_webhooks_enabled ON webhooks(org_id, enabled);

CREATE TABLE webhook_deliveries (
    delivery_id UUID PRIMARY KEY,
    webhook_id UUID NOT NULL REFERENCES webhooks(webhook_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    response_status INT,
    response_body TEXT,
    duration_ms INT,
    success BOOLEAN DEFAULT FALSE,
    attempt INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id, created_at DESC);
CREATE INDEX idx_webhook_deliveries_success ON webhook_deliveries(webhook_id, success);
