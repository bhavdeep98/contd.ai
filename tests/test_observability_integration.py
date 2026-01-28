"""
Integration tests for complete observability setup
"""

import pytest
import time
import requests
from contd.observability import (
    setup_observability,
    teardown_observability,
    collector
)


class TestObservabilitySetup:
    """Test complete observability setup"""
    
    def test_setup_observability(self):
        """Test setup_observability starts all components"""
        try:
            setup_observability(
                metrics_port=9995,
                enable_background=True,
                background_interval=1
            )
            
            time.sleep(0.5)
            
            # Verify metrics server is running
            response = requests.get('http://localhost:9995/metrics', timeout=1)
            assert response.status_code == 200
            
        finally:
            teardown_observability()
    
    def test_setup_without_background(self):
        """Test setup without background collection"""
        try:
            setup_observability(
                metrics_port=9994,
                enable_background=False
            )
            
            time.sleep(0.5)
            
            # Metrics server should work
            response = requests.get('http://localhost:9994/metrics', timeout=1)
            assert response.status_code == 200
            
        finally:
            teardown_observability()
    
    def test_teardown_observability(self):
        """Test teardown cleans up resources"""
        setup_observability(metrics_port=9993)
        time.sleep(0.5)
        teardown_observability()
        
        # Server should be stopped
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get('http://localhost:9993/metrics', timeout=1)
    
    def test_metrics_available_after_setup(self):
        """Test metrics are available after setup"""
        try:
            setup_observability(metrics_port=9992)
            time.sleep(0.5)
            
            # Record some metrics
            collector.record_workflow_start("test_workflow", trigger="api")
            collector.record_step_execution(
                workflow_name="test_workflow",
                step_name="test_step",
                duration_ms=100,
                status="completed"
            )
            
            # Fetch metrics with retry
            content = ""
            for _ in range(5):
                response = requests.get('http://localhost:9992/metrics', timeout=2)
                content = response.text
                if 'contd_workflows_started_total' in content:
                    break
                time.sleep(0.3)
            
            # Should contain our metrics
            assert 'contd_workflows_started_total' in content
            assert 'contd_steps_executed_total' in content
            
        finally:
            teardown_observability()


class TestEndToEndWorkflow:
    """End-to-end workflow with metrics"""
    
    def test_complete_workflow_with_metrics(self):
        """Test complete workflow lifecycle with metrics"""
        try:
            setup_observability(metrics_port=9991)
            time.sleep(0.5)
            
            workflow_name = "e2e_test"
            
            # Simulate workflow
            collector.record_workflow_start(workflow_name, trigger="api")
            
            # Execute steps
            for i in range(3):
                collector.record_step_execution(
                    workflow_name=workflow_name,
                    step_name=f"step_{i}",
                    duration_ms=100 + i * 50,
                    status="completed",
                    user_id="test_user",
                    plan_type="pro"
                )
            
            # Create snapshot
            collector.record_snapshot(
                workflow_name=workflow_name,
                workflow_id="wf_e2e",
                size_bytes=50000,
                duration_ms=25,
                storage_type="s3"
            )
            
            # Complete
            collector.record_workflow_complete(
                workflow_name=workflow_name,
                duration_seconds=2.5,
                status="completed"
            )
            
            # Verify metrics endpoint with retry
            content = ""
            for _ in range(5):
                response = requests.get('http://localhost:9991/metrics', timeout=2)
                assert response.status_code == 200
                content = response.text
                if workflow_name in content:
                    break
                time.sleep(0.3)
            
            assert workflow_name in content
            
        finally:
            teardown_observability()
    
    def test_workflow_with_restore(self):
        """Test workflow with restore metrics"""
        try:
            setup_observability(metrics_port=9990)
            time.sleep(0.5)
            
            workflow_name = "restore_test"
            
            collector.record_workflow_start(workflow_name, trigger="api")
            
            # Restore from checkpoint
            collector.record_restore(
                workflow_name=workflow_name,
                duration_ms=450,
                events_replayed=45,
                had_snapshot=True
            )
            
            # Continue execution
            collector.record_step_execution(
                workflow_name=workflow_name,
                step_name="resumed_step",
                duration_ms=200,
                status="completed"
            )
            
            collector.record_workflow_complete(
                workflow_name=workflow_name,
                duration_seconds=1.5,
                status="completed"
            )
            
            # Verify restore metrics with retry
            content = ""
            for _ in range(5):
                response = requests.get('http://localhost:9990/metrics', timeout=2)
                content = response.text
                if 'contd_restore_duration_milliseconds' in content:
                    break
                time.sleep(0.3)
            
            assert 'contd_restore_duration_milliseconds' in content
            assert 'contd_events_replayed_per_restore' in content
            
        finally:
            teardown_observability()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
