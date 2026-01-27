"""
Example: Push metrics to Pushgateway (for batch jobs)
"""

import time
from contd.observability import collector, MetricsPusher


def main():
    # Setup pusher (requires Pushgateway running)
    pusher = MetricsPusher(
        gateway_url='localhost:9091',
        job_name='contd_batch',
        instance='batch_worker_1'
    )
    
    # Execute batch workflow
    print("Running batch workflow...")
    
    collector.record_workflow_start(
        workflow_name="batch_etl",
        trigger="schedule"
    )
    
    # Simulate work
    for i in range(3):
        start = time.time()
        time.sleep(0.2)
        duration_ms = (time.time() - start) * 1000
        
        collector.record_step_execution(
            workflow_name="batch_etl",
            step_name=f"extract_step_{i}",
            duration_ms=duration_ms,
            status="completed",
            user_id="batch_user",
            plan_type="enterprise"
        )
    
    collector.record_workflow_complete(
        workflow_name="batch_etl",
        duration_seconds=1.5,
        status="completed"
    )
    
    # Push metrics to gateway
    print("Pushing metrics to Pushgateway...")
    pusher.push()
    
    print("✓ Metrics pushed successfully")
    print("View at http://localhost:9091/metrics")


if __name__ == "__main__":
    main()
