"""
Complete example: Workflow with automatic metrics emission
"""

import time
from contd.sdk import workflow, step, WorkflowConfig, StepConfig
from contd.observability import setup_observability, teardown_observability


# Setup metrics server
setup_observability(metrics_port=9090)
print("Metrics: http://localhost:9090/metrics")


@workflow(WorkflowConfig(
    tags={'trigger': 'api', 'user_id': 'user_123', 'plan_type': 'pro'}
))
def data_pipeline():
    """
    Workflow with automatic metrics:
    - Workflow start/complete
    - Lease acquisition
    - Restore (if resuming)
    """
    print("Starting data pipeline...")
    
    data = fetch_data()
    processed = process_data(data)
    result = save_results(processed)
    
    return result


@step(StepConfig(checkpoint=True))
def fetch_data():
    """
    Emits:
    - step_duration_milliseconds
    - steps_executed_total
    - managed_steps_total (billing)
    """
    print("  Fetching data...")
    time.sleep(0.1)
    return {"data": [1, 2, 3, 4, 5]}


@step(StepConfig(checkpoint=True))
def process_data(state):
    """
    Emits:
    - step_duration_milliseconds
    - idempotency_cache_hits_total (if cached)
    """
    print("  Processing data...")
    time.sleep(0.2)
    state['processed'] = sum(state['data'])
    return state


@step(StepConfig(checkpoint=True))
def save_results(state):
    """
    Emits:
    - step_duration_milliseconds
    - snapshot_save_duration_milliseconds (if snapshot created)
    """
    print("  Saving results...")
    time.sleep(0.1)
    state['saved'] = True
    return state


if __name__ == "__main__":
    try:
        # Run workflow
        result = data_pipeline()
        print(f"\n✓ Workflow completed: {result}")
        
        # View metrics
        print("\nMetrics emitted:")
        print("- contd_workflows_started_total{workflow_name='data_pipeline'}")
        print("- contd_workflows_completed_total{workflow_name='data_pipeline',status='completed'}")
        print("- contd_workflow_duration_seconds{workflow_name='data_pipeline'}")
        print("- contd_steps_executed_total{workflow_name='data_pipeline',step_name='fetch_data'}")
        print("- contd_managed_steps_total{user_id='user_123',plan_type='pro'}")
        print("- contd_lease_acquisition_duration_milliseconds{result='acquired'}")
        
        print("\nView all metrics: http://localhost:9090/metrics")
        print("Press Ctrl+C to stop...")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        teardown_observability()
