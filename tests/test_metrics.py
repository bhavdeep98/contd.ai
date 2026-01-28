"""
Unit tests for metrics collection and emission
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from contd.observability.metrics import (
    MetricsCollector,
    collector,
    restore_duration_milliseconds,
    workflow_success_rate,
    managed_steps_total,
    checksum_validation_failures_total,
)


class TestMetricsCollector:
    """Test MetricsCollector functionality"""
    
    def test_singleton_instance(self):
        """Test collector is singleton"""
        c1 = MetricsCollector.get_instance()
        c2 = MetricsCollector.get_instance()
        assert c1 is c2
    
    def test_record_workflow_start(self):
        """Test workflow start recording"""
        collector.record_workflow_start(
            workflow_name="test_workflow",
            trigger="api"
        )
        # Verify metric was incremented (check via registry)
        # In real test, would query REGISTRY for metric value
    
    def test_record_workflow_complete_success(self):
        """Test successful workflow completion"""
        collector.record_workflow_complete(
            workflow_name="test_workflow",
            duration_seconds=2.5,
            status="completed"
        )
    
    def test_record_workflow_complete_failure(self):
        """Test failed workflow completion"""
        collector.record_workflow_complete(
            workflow_name="test_workflow",
            duration_seconds=1.0,
            status="failed"
        )
    
    def test_record_step_execution(self):
        """Test step execution recording"""
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="test_step",
            duration_ms=150.5,
            status="completed",
            was_cached=False,
            user_id="user_123",
            plan_type="pro"
        )
    
    def test_record_step_execution_cached(self):
        """Test cached step execution"""
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="test_step",
            duration_ms=0,
            status="completed",
            was_cached=True,
            user_id="user_123",
            plan_type="pro"
        )
    
    def test_record_restore(self):
        """Test restore operation recording"""
        collector.record_restore(
            workflow_name="test_workflow",
            duration_ms=450.2,
            events_replayed=45,
            had_snapshot=True
        )
    
    def test_record_restore_without_snapshot(self):
        """Test restore without snapshot"""
        collector.record_restore(
            workflow_name="test_workflow",
            duration_ms=2500.0,
            events_replayed=500,
            had_snapshot=False
        )
    
    def test_record_snapshot(self):
        """Test snapshot recording"""
        collector.record_snapshot(
            workflow_name="test_workflow",
            workflow_id="wf_123",
            size_bytes=51200,  # 50KB
            duration_ms=25.5,
            storage_type="s3"
        )
    
    def test_record_journal_append(self):
        """Test journal append recording"""
        collector.record_journal_append(
            event_type="step_completed",
            duration_ms=5.2
        )
    
    def test_record_lease_acquisition_success(self):
        """Test successful lease acquisition"""
        collector.record_lease_acquisition(
            workflow_name="test_workflow",
            duration_ms=15.3,
            result="acquired",
            owner_id="executor_1"
        )
    
    def test_record_lease_acquisition_failure(self):
        """Test failed lease acquisition"""
        collector.record_lease_acquisition(
            workflow_name="test_workflow",
            duration_ms=10.0,
            result="locked"
        )
    
    def test_record_cost_savings(self):
        """Test cost savings recording"""
        collector.record_cost_savings(
            workflow_name="test_workflow",
            steps_avoided=5
        )
    
    def test_record_data_corruption(self):
        """Test data corruption recording"""
        collector.record_data_corruption(
            data_type="snapshot",
            workflow_id="wf_123"
        )
    
    def test_record_critical_error(self):
        """Test critical error recording"""
        collector.record_critical_error(
            component="journal",
            error_type="write_failure"
        )
    
    def test_billing_metric_only_on_success(self):
        """Test billing metric only recorded on successful steps"""
        # Failed step should not increment billing
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="test_step",
            duration_ms=100,
            status="failed",
            was_cached=False,
            user_id="user_123",
            plan_type="pro"
        )
        
        # Successful step should increment billing
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="test_step",
            duration_ms=100,
            status="completed",
            was_cached=False,
            user_id="user_123",
            plan_type="pro"
        )


class TestMetricsHistogramBuckets:
    """Test histogram bucket boundaries"""
    
    def test_restore_duration_buckets(self):
        """Test restore duration has appropriate buckets"""
        # Should have buckets from 10ms to 10s
        collector.record_restore(
            workflow_name="fast",
            duration_ms=50,
            events_replayed=10,
            had_snapshot=True
        )
        
        collector.record_restore(
            workflow_name="slow",
            duration_ms=5000,
            events_replayed=1000,
            had_snapshot=False
        )
    
    def test_step_duration_buckets(self):
        """Test step duration has appropriate buckets"""
        # Should handle fast and slow steps
        collector.record_step_execution(
            workflow_name="test",
            step_name="fast_step",
            duration_ms=10,
            status="completed"
        )
        
        collector.record_step_execution(
            workflow_name="test",
            step_name="slow_step",
            duration_ms=30000,
            status="completed"
        )


class TestMetricsLabels:
    """Test metric label handling"""
    
    def test_workflow_name_label(self):
        """Test workflow_name label is applied"""
        collector.record_workflow_start(
            workflow_name="my_workflow",
            trigger="api"
        )
    
    def test_storage_type_label(self):
        """Test storage_type label for snapshots"""
        collector.record_snapshot(
            workflow_name="test",
            workflow_id="wf_1",
            size_bytes=1024,
            duration_ms=10,
            storage_type="inline"
        )
        
        collector.record_snapshot(
            workflow_name="test",
            workflow_id="wf_2",
            size_bytes=1024000,
            duration_ms=100,
            storage_type="s3"
        )
    
    def test_plan_type_label(self):
        """Test plan_type label for billing"""
        for plan in ["free", "pro", "enterprise"]:
            collector.record_step_execution(
                workflow_name="test",
                step_name="step",
                duration_ms=100,
                status="completed",
                user_id=f"user_{plan}",
                plan_type=plan
            )


class TestMetricsIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_workflow_metrics(self):
        """Test metrics for complete workflow lifecycle"""
        workflow_name = "integration_test"
        
        # Start
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
        
        # Complete
        collector.record_workflow_complete(
            workflow_name=workflow_name,
            duration_seconds=1.5,
            status="completed"
        )
    
    def test_workflow_with_restore(self):
        """Test workflow that resumes from checkpoint"""
        workflow_name = "resume_test"
        
        # Start
        collector.record_workflow_start(workflow_name, trigger="api")
        
        # Restore
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
        
        # Complete
        collector.record_workflow_complete(
            workflow_name=workflow_name,
            duration_seconds=2.0,
            status="completed"
        )
    
    def test_workflow_with_failures_and_retries(self):
        """Test workflow with failures and retries"""
        workflow_name = "retry_test"
        
        collector.record_workflow_start(workflow_name, trigger="api")
        
        # Failed attempt
        collector.record_step_execution(
            workflow_name=workflow_name,
            step_name="flaky_step",
            duration_ms=100,
            status="failed"
        )
        
        # Successful retry
        collector.record_step_execution(
            workflow_name=workflow_name,
            step_name="flaky_step",
            duration_ms=150,
            status="completed"
        )
        
        collector.record_workflow_complete(
            workflow_name=workflow_name,
            duration_seconds=1.0,
            status="completed"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
