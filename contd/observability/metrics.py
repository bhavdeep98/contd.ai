"""
Contd.ai Core Metrics System

Essential metrics for production monitoring.
See METRICS_CATALOG.md for full 120-metric specification.

Priority Levels:
- P0: Critical for correctness, performance, availability
- P1: Important for business and operations
- P2: Nice-to-have for insights
"""

from prometheus_client import Counter, Histogram, Gauge
from dataclasses import dataclass
from typing import Optional

# =============================================================================
# P0: CRITICAL METRICS
# =============================================================================

# Performance: Restore latency (CORE VALUE PROP)
restore_duration_milliseconds = Histogram(
    "contd_restore_duration_milliseconds",
    "Time to restore workflow state (SLO: <1s P95)",
    ["workflow_name", "has_snapshot"],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000],
)

events_replayed_per_restore = Histogram(
    "contd_events_replayed_per_restore",
    "Events replayed during restore (target: <100)",
    ["workflow_name"],
    buckets=[0, 10, 50, 100, 500, 1000, 5000],
)

# Correctness: Data integrity
checksum_validation_failures_total = Counter(
    "contd_checksum_validation_failures_total",
    "Failed checksum validations (DATA CORRUPTION)",
    ["data_type"],  # event, snapshot, state
)

state_corruption_detected_total = Counter(
    "contd_state_corruption_detected_total",
    "Detected state corruption",
    ["detection_point"],  # Removed workflow_id to prevent cardinality explosion
)

# Availability: Workflow success
workflow_success_rate = Gauge(
    "contd_workflow_success_rate",
    "Workflow success rate (target: >99%)",
    ["workflow_name", "timeframe"],  # 1h, 24h, 7d
)

workflows_completed_total = Counter(
    "contd_workflows_completed_total",
    "Total workflows completed",
    ["workflow_name", "status"],  # completed, failed
)

# Correctness: Idempotency
idempotency_cache_hits_total = Counter(
    "contd_idempotency_cache_hits_total",
    "Steps skipped due to idempotency",
    ["workflow_name", "step_name"],
)


# =============================================================================
# P1: IMPORTANT METRICS
# =============================================================================

# Performance: Workflow & step execution
workflow_duration_seconds = Histogram(
    "contd_workflow_duration_seconds",
    "Total workflow execution time",
    ["workflow_name", "status"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200, 14400],
)

step_duration_milliseconds = Histogram(
    "contd_step_duration_milliseconds",
    "Step execution duration",
    ["workflow_name", "step_name", "status"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
)

# Throughput
workflows_started_total = Counter(
    "contd_workflows_started_total",
    "Total workflows started",
    ["workflow_name", "trigger"],  # api, schedule, manual
)

workflows_resumed_total = Counter(
    "contd_workflows_resumed_total", "Total workflows resumed", ["workflow_name"]
)

steps_executed_total = Counter(
    "contd_steps_executed_total",
    "Total steps executed",
    ["workflow_name", "step_name", "status"],
)

# Business: Billing metric (use plan_type for aggregation, not user_id)
managed_steps_total = Counter(
    "contd_managed_steps_total",
    "Total managed steps (billing unit)",
    ["workflow_name", "plan_type"],  # Removed user_id to prevent cardinality explosion
)

# Cost: Savings from resumability
avoided_recomputation_steps_total = Counter(
    "contd_avoided_recomputation_steps_total",
    "Steps avoided via resume (cost saved)",
    ["workflow_name"],
)

# Persistence: Snapshot operations
snapshot_save_duration_milliseconds = Histogram(
    "contd_snapshot_save_duration_milliseconds",
    "Time to save snapshot",
    ["storage_type"],  # inline, s3
    buckets=[10, 50, 100, 500, 1000, 5000],
)

snapshot_size_bytes = Histogram(
    "contd_snapshot_size_bytes",
    "Snapshot size distribution",
    ["workflow_name", "storage_type"],
    buckets=[1024, 10240, 102400, 1024000, 10240000, 102400000],
)

# Persistence: Journal operations
journal_append_duration_milliseconds = Histogram(
    "contd_journal_append_duration_milliseconds",
    "Time to append event to journal",
    ["event_type"],
    buckets=[1, 5, 10, 25, 50, 100],
)

events_appended_total = Counter(
    "contd_events_appended_total", "Total events appended to journal", ["event_type"]
)

# Concurrency: Lease management
lease_acquisition_duration_milliseconds = Histogram(
    "contd_lease_acquisition_duration_milliseconds",
    "Time to acquire workflow lease",
    ["result"],  # acquired, locked, failed
    buckets=[1, 10, 50, 100, 500, 1000],
)

lease_acquisition_failures_total = Counter(
    "contd_lease_acquisition_failures_total",
    "Failed lease acquisitions",
    ["workflow_name", "reason"],
)

active_leases = Gauge("contd_active_leases", "Currently held leases", ["owner_id"])

# System health
component_health_status = Gauge(
    "contd_component_health_status",
    "Component health (1=healthy, 0=unhealthy)",
    ["component"],  # journal, snapshot_store, lease_manager, s3
)

database_connection_errors_total = Counter(
    "contd_database_connection_errors_total",
    "Database connection errors",
    ["error_type"],
)


# =============================================================================
# P2: OPERATIONAL INSIGHTS
# =============================================================================

# Retries
step_retries_total = Counter(
    "contd_step_retries_total",
    "Step retry attempts",
    ["workflow_name", "step_name", "attempt_number"],
)

# Storage growth (use workflow_name for aggregation, not workflow_id)
journal_size_bytes = Gauge(
    "contd_journal_size_bytes", "Journal size per workflow type", ["workflow_name"]
)

snapshot_count = Gauge(
    "contd_snapshot_count", "Number of snapshots per workflow type", ["workflow_name"]
)

# Resource usage
process_memory_bytes = Gauge(
    "contd_process_memory_bytes", "Process memory usage", ["memory_type"]  # rss, heap
)

process_cpu_usage_percent = Gauge(
    "contd_process_cpu_usage_percent", "Process CPU usage percentage"
)

# Critical errors
critical_errors_total = Counter(
    "contd_critical_errors_total", "Critical system errors", ["component", "error_type"]
)


# =============================================================================
# METRICS COLLECTOR
# =============================================================================


@dataclass
class MetricsCollector:
    """
    Simplified metrics collection interface.

    Focuses on the most critical metrics for production monitoring.
    """

    _instance: Optional["MetricsCollector"] = None

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_workflow_start(self, workflow_name: str, trigger: str = "api"):
        """Record workflow start"""
        workflows_started_total.labels(
            workflow_name=workflow_name, trigger=trigger
        ).inc()

    def record_workflow_complete(
        self,
        workflow_name: str,
        duration_seconds: float,
        status: str,  # "completed" or "failed"
    ):
        """Record workflow completion"""
        workflow_duration_seconds.labels(
            workflow_name=workflow_name, status=status
        ).observe(duration_seconds)

        workflows_completed_total.labels(
            workflow_name=workflow_name, status=status
        ).inc()

    def record_step_execution(
        self,
        workflow_name: str,
        step_name: str,
        duration_ms: float,
        status: str,
        was_cached: bool = False,
        user_id: Optional[str] = None,
        plan_type: str = "free",
    ):
        """Record step execution"""
        step_duration_milliseconds.labels(
            workflow_name=workflow_name, step_name=step_name, status=status
        ).observe(duration_ms)

        steps_executed_total.labels(
            workflow_name=workflow_name, step_name=step_name, status=status
        ).inc()

        if was_cached:
            idempotency_cache_hits_total.labels(
                workflow_name=workflow_name, step_name=step_name
            ).inc()

        # Billing metric (aggregate by plan_type, not user_id)
        if status == "completed":
            managed_steps_total.labels(
                workflow_name=workflow_name, plan_type=plan_type
            ).inc()

    def record_restore(
        self,
        workflow_name: str,
        duration_ms: float,
        events_replayed: int,
        had_snapshot: bool,
    ):
        """Record restore operation (CRITICAL METRIC)"""
        restore_duration_milliseconds.labels(
            workflow_name=workflow_name, has_snapshot=str(had_snapshot)
        ).observe(duration_ms)

        events_replayed_per_restore.labels(workflow_name=workflow_name).observe(
            events_replayed
        )

        workflows_resumed_total.labels(workflow_name=workflow_name).inc()

    def record_snapshot(
        self,
        workflow_name: str,
        workflow_id: str,
        size_bytes: int,
        duration_ms: float,
        storage_type: str,
    ):
        """Record snapshot creation"""
        snapshot_save_duration_milliseconds.labels(storage_type=storage_type).observe(
            duration_ms
        )

        snapshot_size_bytes.labels(
            workflow_name=workflow_name, storage_type=storage_type
        ).observe(size_bytes)

        # Use workflow_name instead of workflow_id to prevent cardinality explosion
        snapshot_count.labels(workflow_name=workflow_name).inc()

    def record_journal_append(self, event_type: str, duration_ms: float):
        """Record journal append"""
        journal_append_duration_milliseconds.labels(event_type=event_type).observe(
            duration_ms
        )

        events_appended_total.labels(event_type=event_type).inc()

    def record_lease_acquisition(
        self,
        workflow_name: str,
        duration_ms: float,
        result: str,  # "acquired", "locked", "failed"
        owner_id: Optional[str] = None,
    ):
        """Record lease acquisition attempt"""
        lease_acquisition_duration_milliseconds.labels(result=result).observe(
            duration_ms
        )

        if result != "acquired":
            lease_acquisition_failures_total.labels(
                workflow_name=workflow_name, reason=result
            ).inc()
        elif owner_id:
            active_leases.labels(owner_id=owner_id).inc()

    def record_cost_savings(self, workflow_name: str, steps_avoided: int):
        """Record cost savings from resume"""
        avoided_recomputation_steps_total.labels(workflow_name=workflow_name).inc(
            steps_avoided
        )

    def record_data_corruption(self, data_type: str, workflow_id: Optional[str] = None):
        """Record data corruption (CRITICAL)"""
        checksum_validation_failures_total.labels(data_type=data_type).inc()

        if workflow_id:
            # Log the workflow_id for debugging but don't use it as a label
            import logging

            logging.getLogger(__name__).error(
                f"Data corruption detected in workflow {workflow_id}"
            )
            state_corruption_detected_total.labels(detection_point="checksum").inc()

    def record_critical_error(self, component: str, error_type: str):
        """Record critical error"""
        critical_errors_total.labels(component=component, error_type=error_type).inc()


# Global collector instance
collector = MetricsCollector.get_instance()


__all__ = [
    "MetricsCollector",
    "collector",
    # Export critical metrics
    "restore_duration_milliseconds",
    "events_replayed_per_restore",
    "workflow_success_rate",
    "checksum_validation_failures_total",
    "managed_steps_total",
    # Export system metrics for background collector
    "process_memory_bytes",
    "process_cpu_usage_percent",
]
