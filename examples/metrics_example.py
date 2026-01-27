"""
Example: Using Contd.ai metrics
"""

import time
from contd.observability import setup_observability, teardown_observability, collector


def main():
    # Setup metrics server on port 9090
    # Prometheus will scrape http://localhost:9090/metrics
    setup_observability(
        metrics_port=9090,
        enable_background=True,
        background_interval=15
    )
    
    print("Metrics available at http://localhost:9090/metrics")
    print("Health check at http://localhost:9090/health")
    
    # Simulate workflow execution
    simulate_workflow()
    
    # Keep running to allow Prometheus scraping
    print("\nPress Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        teardown_observability()


def simulate_workflow():
    """Simulate a workflow with metrics"""
    
    # Start workflow
    collector.record_workflow_start(
        workflow_name="data_pipeline",
        trigger="api"
    )
    
    # Execute steps
    for i in range(5):
        start = time.time()
        time.sleep(0.1)  # Simulate work
        duration_ms = (time.time() - start) * 1000
        
        collector.record_step_execution(
            workflow_name="data_pipeline",
            step_name=f"step_{i}",
            duration_ms=duration_ms,
            status="completed",
            was_cached=(i % 2 == 0),  # Every other step cached
            user_id="user_123",
            plan_type="pro"
        )
    
    # Simulate restore
    collector.record_restore(
        workflow_name="data_pipeline",
        duration_ms=450.2,
        events_replayed=45,
        had_snapshot=True
    )
    
    # Complete workflow
    collector.record_workflow_complete(
        workflow_name="data_pipeline",
        duration_seconds=2.5,
        status="completed"
    )
    
    # Record snapshot
    collector.record_snapshot(
        workflow_name="data_pipeline",
        workflow_id="wf_123",
        size_bytes=1024 * 50,  # 50KB
        duration_ms=25.5,
        storage_type="s3"
    )
    
    # Record journal append
    collector.record_journal_append(
        event_type="step_completed",
        duration_ms=5.2
    )
    
    # Record lease acquisition
    collector.record_lease_acquisition(
        workflow_name="data_pipeline",
        duration_ms=15.3,
        result="acquired",
        owner_id="executor_1"
    )
    
    # Record cost savings
    collector.record_cost_savings(
        workflow_name="data_pipeline",
        steps_avoided=3
    )
    
    print("✓ Workflow metrics recorded")


if __name__ == "__main__":
    main()
