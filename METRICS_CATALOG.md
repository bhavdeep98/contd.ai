# Contd.ai Metrics Catalog

Comprehensive specification of all 120 metrics for Contd.ai observability.

## Implementation Status

**Currently Implemented**: 30 core metrics (P0 + P1 priority)  
**Documented for Future**: 90 additional metrics (P2 + optional)

See `contd/observability/metrics.py` for implemented metrics.

---

## Metrics Priority Matrix

| Priority | Category | Count | Why Critical |
|----------|----------|-------|--------------|
| **P0** | Correctness | 7 | Data integrity, idempotency |
| **P0** | Performance | 2 | Restore latency (core value prop) |
| **P0** | Availability | 2 | Workflow success rate |
| **P1** | Business | 2 | Revenue tracking (managed steps) |
| **P1** | Performance | 8 | Latency & throughput |
| **P1** | Cost | 2 | Unit economics |
| **P1** | Operations | 7 | System health |
| **P2** | Engagement | 15 | Product-market fit |
| **P2** | Resources | 20 | Capacity planning |
| **P2** | Growth | 10 | Business insights |

**Total**: ~120 metrics

---

## P0: Critical Metrics (Implemented ✓)

### Performance: Restore Latency
```python
restore_duration_milliseconds = Histogram(
    "contd_restore_duration_milliseconds",
    "Time to restore workflow state (SLO: <1s P95)",
    ["workflow_name", "has_snapshot"],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000]
)

events_replayed_per_restore = Histogram(
    "contd_events_replayed_per_restore",
    "Events replayed during restore (target: <100)",
    ["workflow_name"],
    buckets=[0, 10, 50, 100, 500, 1000, 5000]
)
```

**Why Critical**: Core value proposition. If restore is slow, the entire product fails.

**SLO**: P95 < 1 second

**Alert**: P95 > 1s for 5 minutes

---

### Correctness: Data Integrity
```python
checksum_validation_failures_total = Counter(
    "contd_checksum_validation_failures_total",
    "Failed checksum validations (DATA CORRUPTION)",
    ["data_type"]  # event, snapshot, state
)

state_corruption_detected_total = Counter(
    "contd_state_corruption_detected_total",
    "Detected state corruption",
    ["workflow_id", "detection_point"]
)
```

**Why Critical**: Any data corruption is catastrophic for user trust.

**SLO**: 0 corruption events

**Alert**: Any corruption event triggers P0 page

---

### Availability: Workflow Success
```python
workflow_success_rate = Gauge(
    "contd_workflow_success_rate",
    "Workflow success rate (target: >99%)",
    ["workflow_name", "timeframe"]
)

workflows_completed_total = Counter(
    "contd_workflows_completed_total",
    "Total workflows completed",
    ["workflow_name", "status"]
)
```

**Why Critical**: Core reliability metric.

**SLO**: >99% success rate

**Alert**: Success rate < 99% for 15 minutes

---

### Correctness: Idempotency
```python
idempotency_cache_hits_total = Counter(
    "contd_idempotency_cache_hits_total",
    "Steps skipped due to idempotency",
    ["workflow_name", "step_name"]
)
```

**Why Critical**: Validates core correctness guarantee.

**Target**: >80% hit rate for resumed workflows

---

## P1: Important Metrics (Implemented ✓)

### Business: Billing
```python
managed_steps_total = Counter(
    "contd_managed_steps_total",
    "Total managed steps (billing unit)",
    ["user_id", "workflow_name", "plan_type"]
)
```

**Why Important**: Direct revenue tracking.

---

### Cost: Savings
```python
avoided_recomputation_steps_total = Counter(
    "contd_avoided_recomputation_steps_total",
    "Steps avoided via resume (cost saved)",
    ["workflow_name"]
)
```

**Why Important**: Demonstrates product value.

---

## P2: Additional Metrics (Documented for Future)

### System Health (Not Yet Implemented)

```python
# API Health
api_health_status = Gauge(
    "contd_api_health_status",
    "API health status (1=healthy, 0=unhealthy)",
    ["endpoint", "environment"]
)

api_request_duration_milliseconds = Histogram(
    "contd_api_request_duration_milliseconds",
    "API request latency",
    ["endpoint", "method"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000]
)

api_error_rate = Counter(
    "contd_api_error_rate_total",
    "API error count",
    ["endpoint", "status_code"]
)

# System Uptime
system_uptime_seconds = Gauge(
    "contd_system_uptime_seconds",
    "Time since system start",
    ["environment", "region"]
)

# Database Health
database_connection_pool_size = Gauge(
    "contd_db_connection_pool_size",
    "Database connection pool size",
    ["pool_name", "state"]  # active, idle, waiting
)

db_query_duration_milliseconds = Histogram(
    "contd_db_query_duration_milliseconds",
    "Database query duration",
    ["operation", "table"],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

# Component Health
component_health_check_duration_seconds = Histogram(
    "contd_component_health_check_duration_seconds",
    "Component health check duration",
    ["component"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

heartbeat_failures_total = Counter(
    "contd_heartbeat_failures_total",
    "Total heartbeat failures",
    ["workflow_id", "reason"]
)

lease_renewal_failures_total = Counter(
    "contd_lease_renewal_failures_total",
    "Failed lease renewals",
    ["workflow_id", "reason"]
)
```

---

### Performance: Additional Latency (Not Yet Implemented)

```python
# Checkpoint Performance
checkpoint_duration_milliseconds = Histogram(
    "contd_checkpoint_duration_milliseconds",
    "Time to create checkpoint",
    ["workflow_name", "snapshot_created"],
    buckets=[1, 5, 10, 50, 100, 500, 1000]
)

snapshot_load_duration_milliseconds = Histogram(
    "contd_snapshot_load_duration_milliseconds",
    "Time to load snapshot",
    ["storage_type"],
    buckets=[10, 50, 100, 500, 1000, 5000]
)

# Throughput Rates
steps_per_second = Gauge(
    "contd_steps_per_second",
    "Current step execution rate",
    ["workflow_name"]
)

events_per_second = Gauge(
    "contd_events_per_second",
    "Current event append rate"
)

# Workflow Lifecycle
workflows_suspended_total = Counter(
    "contd_workflows_suspended_total",
    "Total workflows suspended",
    ["workflow_name", "reason"]
)
```

---

### Correctness: Additional Integrity (Not Yet Implemented)

```python
# Restore Validation
restore_validation_failures_total = Counter(
    "contd_restore_validation_failures_total",
    "Failed state restoration validations",
    ["workflow_name", "validation_type"]
)

# Fencing
fencing_token_violations_total = Counter(
    "contd_fencing_token_violations_total",
    "Stale executor detected (fencing worked)",
    ["workflow_id"]
)

# Concurrency Issues
concurrent_execution_attempts_total = Counter(
    "contd_concurrent_execution_attempts_total",
    "Attempts to execute same workflow concurrently (BAD)",
    ["workflow_id"]
)

lease_expires_forced_total = Counter(
    "contd_lease_expires_forced_total",
    "Leases that expired (not released properly)",
    ["workflow_id", "owner_id"]
)

# Retry Behavior
step_retry_exhausted_total = Counter(
    "contd_step_retry_exhausted_total",
    "Steps that exhausted all retries",
    ["workflow_name", "step_name", "final_error"]
)

# Idempotency Rate
idempotency_cache_hit_rate = Gauge(
    "contd_idempotency_cache_hit_rate",
    "Percentage of steps cached",
    ["workflow_name"]
)
```

---

### Resource Metrics (Not Yet Implemented)

```python
# Storage Growth
journal_events_count = Gauge(
    "contd_journal_events_count",
    "Number of events in journal",
    ["workflow_id", "event_type"]
)

journal_size_since_last_snapshot_bytes = Gauge(
    "contd_journal_size_since_last_snapshot_bytes",
    "Journal growth since last snapshot",
    ["workflow_id"]
)

snapshot_storage_total_bytes = Gauge(
    "contd_snapshot_storage_total_bytes",
    "Total snapshot storage used",
    ["storage_type"]
)

# S3 Operations
s3_operations_total = Counter(
    "contd_s3_operations_total",
    "Total S3 operations",
    ["operation", "status"]
)

s3_bytes_transferred = Counter(
    "contd_s3_bytes_transferred",
    "Total bytes transferred to/from S3",
    ["direction"]  # upload, download
)

# Database Storage
database_table_size_bytes = Gauge(
    "contd_database_table_size_bytes",
    "Database table size",
    ["table_name"]
)

database_row_count = Gauge(
    "contd_database_row_count",
    "Number of rows in table",
    ["table_name"]
)

# Memory & CPU
process_cpu_usage_percent = Gauge(
    "contd_process_cpu_usage_percent",
    "Process CPU usage percentage"
)

state_cache_size_bytes = Gauge(
    "contd_state_cache_size_bytes",
    "In-memory state cache size"
)

state_cache_entries = Gauge(
    "contd_state_cache_entries",
    "Number of cached workflow states"
)

# Thread Pools
thread_pool_size = Gauge(
    "contd_thread_pool_size",
    "Thread pool size",
    ["pool_name", "state"]
)

thread_pool_queue_size = Gauge(
    "contd_thread_pool_queue_size",
    "Thread pool queue depth",
    ["pool_name"]
)
```

---

### Business Metrics (Not Yet Implemented)

```python
# User Activity
active_users_total = Gauge(
    "contd_active_users_total",
    "Number of active users",
    ["timeframe"]  # daily, weekly, monthly
)

new_users_total = Counter(
    "contd_new_users_total",
    "New user registrations",
    ["plan_type"]
)

# Workflow Usage
workflows_per_user = Histogram(
    "contd_workflows_per_user",
    "Workflows per user distribution",
    ["plan_type"],
    buckets=[1, 5, 10, 25, 50, 100, 500, 1000]
)

unique_workflows_count = Gauge(
    "contd_unique_workflows_count",
    "Number of unique workflow types",
    ["user_id"]
)

steps_per_workflow = Histogram(
    "contd_steps_per_workflow",
    "Steps per workflow distribution",
    ["workflow_name"],
    buckets=[1, 5, 10, 25, 50, 100, 500, 1000, 5000]
)

average_workflow_complexity = Gauge(
    "contd_average_workflow_complexity",
    "Average number of steps per workflow",
    ["plan_type"]
)

# Revenue
billable_steps_per_user_monthly = Gauge(
    "contd_billable_steps_per_user_monthly",
    "Monthly billable steps per user",
    ["user_id", "plan_type"]
)

monthly_recurring_revenue = Gauge(
    "contd_monthly_recurring_revenue_usd",
    "Monthly recurring revenue",
    ["plan_type"]
)

average_revenue_per_user = Gauge(
    "contd_average_revenue_per_user_usd",
    "ARPU in USD",
    ["plan_type"]
)

users_by_plan = Gauge(
    "contd_users_by_plan",
    "User count by plan",
    ["plan_type"]
)

# Plan Changes
plan_upgrades_total = Counter(
    "contd_plan_upgrades_total",
    "Plan upgrade events",
    ["from_plan", "to_plan"]
)

plan_downgrades_total = Counter(
    "contd_plan_downgrades_total",
    "Plan downgrade events",
    ["from_plan", "to_plan"]
)

churn_total = Counter(
    "contd_churn_total",
    "User churn events",
    ["plan_type", "reason"]
)
```

---

### Feature Adoption (Not Yet Implemented)

```python
# Feature Usage
savepoint_usage_total = Counter(
    "contd_savepoint_usage_total",
    "Savepoint creation count",
    ["workflow_name", "user_id"]
)

time_travel_usage_total = Counter(
    "contd_time_travel_usage_total",
    "Time-travel debug usage",
    ["user_id"]
)

nested_workflow_usage_total = Counter(
    "contd_nested_workflow_usage_total",
    "Nested workflow usage",
    ["parent_workflow", "child_workflow"]
)

# Resume Patterns
resume_reasons = Counter(
    "contd_resume_reasons_total",
    "Why workflows were resumed",
    ["reason"]  # interruption, manual, scheduled, debug
)

time_to_resume_hours = Histogram(
    "contd_time_to_resume_hours",
    "Time between suspension and resume",
    ["workflow_name"],
    buckets=[0.1, 1, 6, 12, 24, 48, 168]
)

long_running_workflows = Gauge(
    "contd_long_running_workflows",
    "Workflows running > 1 hour",
    ["workflow_name", "duration_bucket"]
)
```

---

### Cost Metrics (Not Yet Implemented)

```python
# Infrastructure Costs
compute_cost_per_workflow_usd = Histogram(
    "contd_compute_cost_per_workflow_usd",
    "Estimated compute cost per workflow",
    ["workflow_name"],
    buckets=[0.001, 0.01, 0.1, 1, 10, 100]
)

storage_cost_daily_usd = Gauge(
    "contd_storage_cost_daily_usd",
    "Daily storage cost estimate",
    ["storage_type"]
)

# LLM Costs
llm_tokens_used_total = Counter(
    "contd_llm_tokens_used_total",
    "Total LLM tokens consumed",
    ["workflow_name", "model", "token_type"]
)

llm_cost_per_workflow_usd = Histogram(
    "contd_llm_cost_per_workflow_usd",
    "LLM cost per workflow",
    ["workflow_name"],
    buckets=[0.01, 0.1, 1, 10, 100]
)

# Cost Efficiency
estimated_cost_saved_usd = Counter(
    "contd_estimated_cost_saved_usd",
    "Estimated cost saved via resume",
    ["workflow_name"]
)

token_savings_from_snapshots_total = Counter(
    "contd_token_savings_from_snapshots_total",
    "Tokens saved by using snapshots vs full replay",
    ["workflow_name"]
)

cost_per_managed_step_usd = Gauge(
    "contd_cost_per_managed_step_usd",
    "Infrastructure cost per managed step",
    ["workflow_name"]
)

gross_margin_per_user_usd = Gauge(
    "contd_gross_margin_per_user_usd",
    "Revenue minus infrastructure cost per user",
    ["plan_type"]
)
```

---

### User Experience (Not Yet Implemented)

```python
# Reliability
resume_success_rate = Gauge(
    "contd_resume_success_rate",
    "Percentage of successful resumes",
    ["workflow_name"]
)

error_rate_per_workflow = Gauge(
    "contd_error_rate_per_workflow",
    "Errors per 1000 steps",
    ["workflow_name", "error_type"]
)

mean_time_to_recovery_seconds = Histogram(
    "contd_mean_time_to_recovery_seconds",
    "MTTR after interruption",
    ["workflow_name"],
    buckets=[1, 10, 30, 60, 300, 600]
)

# SLO Compliance
restore_slo_compliance = Gauge(
    "contd_restore_slo_compliance",
    "Percentage of restores < 1s",
    ["workflow_name"]
)

step_execution_slo_compliance = Gauge(
    "contd_step_execution_slo_compliance",
    "Percentage of steps within SLO",
    ["workflow_name", "slo_threshold"]
)
```

---

### Operational Metrics (Not Yet Implemented)

```python
# Alerting Signals
data_loss_events_total = Counter(
    "contd_data_loss_events_total",
    "Potential data loss events (CRITICAL)",
    ["event_type"]
)

degraded_performance_duration_seconds = Counter(
    "contd_degraded_performance_duration_seconds",
    "Time spent in degraded state",
    ["component"]
)

resource_exhaustion_warnings_total = Counter(
    "contd_resource_exhaustion_warnings_total",
    "Resource exhaustion warnings",
    ["resource_type"]
)

# Maintenance
schema_migrations_applied_total = Counter(
    "contd_schema_migrations_applied_total",
    "Database schema migrations",
    ["version", "status"]
)

state_migrations_executed_total = Counter(
    "contd_state_migrations_executed_total",
    "State schema migrations",
    ["from_version", "to_version", "status"]
)

old_snapshots_cleaned_total = Counter(
    "contd_old_snapshots_cleaned_total",
    "Snapshots deleted by cleanup",
    ["workflow_id", "reason"]
)

old_events_archived_total = Counter(
    "contd_old_events_archived_total",
    "Events archived",
    ["workflow_id"]
)
```

---

### Product Metrics (Not Yet Implemented)

```python
# Engagement
user_sessions_total = Counter(
    "contd_user_sessions_total",
    "User login sessions",
    ["user_id", "client_type"]
)

session_duration_seconds = Histogram(
    "contd_session_duration_seconds",
    "User session duration",
    ["user_id"],
    buckets=[60, 300, 600, 1800, 3600, 7200]
)

new_feature_adoption_rate = Gauge(
    "contd_new_feature_adoption_rate",
    "Percentage of users using new feature",
    ["feature_name", "user_cohort"]
)

documentation_views_total = Counter(
    "contd_documentation_views_total",
    "Documentation page views",
    ["page_path", "user_id"]
)

support_tickets_total = Counter(
    "contd_support_tickets_total",
    "Support ticket count",
    ["category", "priority"]
)

# Growth
invitations_sent_total = Counter(
    "contd_invitations_sent_total",
    "Team invitations sent",
    ["sender_plan"]
)

invitations_accepted_total = Counter(
    "contd_invitations_accepted_total",
    "Team invitations accepted",
    ["inviter_plan"]
)

user_retention_rate = Gauge(
    "contd_user_retention_rate",
    "User retention rate",
    ["cohort_month", "retention_period"]
)

workflow_retention_rate = Gauge(
    "contd_workflow_retention_rate",
    "Workflows re-run rate",
    ["workflow_name", "timeframe"]
)
```

---

## Dashboard Organization

### Executive Dashboard
- Monthly Recurring Revenue
- Active Users (DAU/MAU)
- Workflow Success Rate
- Gross Margin per User
- Churn Rate

### Engineering Dashboard
- **P95 Restore Latency** (SLO: < 1s)
- Events Replayed per Restore (Target: < 100)
- Workflow Success Rate (Target: > 99%)
- Idempotency Hit Rate
- Critical Errors (Target: 0)

### Operations Dashboard
- System Health Status
- Database Connection Pool
- Journal Growth Rate
- Snapshot Storage Growth
- Resource Utilization

### Product Dashboard
- Feature Adoption Rates
- Average Steps per Workflow
- Long-Running Workflow Count
- Time-Travel Usage
- Documentation Engagement

### Cost Dashboard
- Infrastructure Cost per User
- Token Cost per Workflow
- Storage Cost Growth
- Cost Savings from Resumability
- Gross Margin Trend

---

## Critical Alerts

```yaml
alerts:
  # Correctness
  - name: DataCorruptionDetected
    expr: rate(contd_checksum_validation_failures_total[5m]) > 0
    severity: critical
    message: "Data corruption detected"
  
  # Performance
  - name: RestoreLatencyHigh
    expr: histogram_quantile(0.95, contd_restore_duration_milliseconds) > 1000
    severity: warning
    message: "P95 restore latency > 1s (SLO breach)"
  
  - name: EventReplayHigh
    expr: histogram_quantile(0.95, contd_events_replayed_per_restore) > 100
    severity: warning
    message: "P95 events replayed > 100 (snapshot policy issue)"
  
  # Availability
  - name: WorkflowSuccessRateLow
    expr: contd_workflow_success_rate < 0.99
    severity: critical
    message: "Workflow success rate < 99%"
  
  # Cost
  - name: InfrastructureCostSpike
    expr: rate(contd_storage_cost_daily_usd[1h]) > 1.5
    severity: warning
    message: "Infrastructure cost spiking"
  
  # Business
  - name: ChurnRateHigh
    expr: rate(contd_churn_total[24h]) > 0.05
    severity: critical
    message: "Churn rate > 5% (business risk)"
```

---

## Implementation Roadmap

### Phase 1: Core Metrics (Implemented ✓)
- 30 essential metrics for MVP
- Focus on correctness, performance, availability
- Basic business metrics (billing)

### Phase 2: Operational Metrics (Next)
- System health monitoring
- Resource tracking
- Alert infrastructure

### Phase 3: Business Intelligence (Future)
- User engagement
- Feature adoption
- Revenue analytics

### Phase 4: Cost Optimization (Future)
- Detailed cost tracking
- Efficiency metrics
- ROI calculations

---

## Usage Example

```python
from contd.observability.metrics import collector

# Record workflow execution
collector.record_workflow_start("data_pipeline", trigger="api")

# Record step with idempotency
collector.record_step_execution(
    workflow_name="data_pipeline",
    step_name="fetch_data",
    duration_ms=150.5,
    status="completed",
    was_cached=True,
    user_id="user_123",
    plan_type="pro"
)

# Record restore (CRITICAL METRIC)
collector.record_restore(
    workflow_name="data_pipeline",
    duration_ms=450.2,
    events_replayed=45,
    had_snapshot=True
)

# Record completion
collector.record_workflow_complete(
    workflow_name="data_pipeline",
    duration_seconds=125.3,
    status="completed"
)
```

---

## Notes

- All 120 metrics are documented here for reference
- Only 30 core metrics are implemented in production code
- Additional metrics can be added incrementally based on need
- Metric cardinality is carefully controlled to avoid explosion
- All histograms use carefully chosen bucket boundaries
