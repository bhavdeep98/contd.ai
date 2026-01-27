"""
Unit tests for MetricsCollector
"""

import pytest
from unittest.mock import Mock, patch
from contd.observability.metrics import (
    MetricsCollector,
    collector,
    restore_duration_milliseconds,
    workflow_success_rate,
    managed_steps_total,
    checksum_validation_failures_total,
    workflows_started_total,
    workflows_completed_total,
    step_duration_milliseconds,
    idempotency_cache_hits_total,
)


class TestMetricsCollector:
    
    def test_singleton_instance(self):
        """Test collector is singleton"""
        c1 = MetricsCollector.get_instance()
        c2 = MetricsCollector.get_instance()
        assert c1 is c2
        assert c1 is collector
    
    def test_record_workflow_start(self):
        """Test workflow start metric"""
        collector.record_workflow_start(
            workflow_name="test_workflow",
            trigger="api"
        )
        # Metric should increment
        metric = workflows_started_total.labels(
            workflow_name="test_workflow",
            trigger="api"
        )
        assert metric._value._value > 0
    
    def test_record_workflow_complete_success(self):
        """Test workflow completion with success"""
        collector.record_workflow_complete(
            workflow_name="test_workflow",
            duration_seconds=2.5,
            status="completed"
        )
        
        metric = workflows_completed_total.labels(
            workflow_name="test_workflow",
            status="completed"
        )
        assert metric._value._value > 0
    
    def test_record_workflow_complete_failure(self):
        """Test workflow completion with failure"""
        collector.record_workflow_complete(
            workflow_name="test_workflow",
            duration_seconds=1.5,
            status="failed"
        )
        
        metric = workflows_completed_total.labels(
            workflow_name="test_workflow",
            status="failed"
        )
        assert metric._value._value > 0
    
    def test_record_step_execution(self):
        """Test step execution metric"""
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="test_step",
            duration_ms=150.5,
            status="completed",
            was_cached=False,
            user_id="user_123",
            plan_type="pro"
        )
        
        # Check step duration recorded
        metric = step_duration_milliseconds.labels(
            workflow_name="test_workflow",
            step_name="test_step",
            status="completed"
        )
        assert metric._sum._value > 0
    
    def test_record_step_execution_with_cache_hit(self):
        """Test step execution with idempotency cache hit"""
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="cached_step",
            duration_ms=0,
            status="completed",
            was_cached=True
        )
        
        # Check idempotency hit recorded
        metric = idempotency_cache_hits_total.labels(
            workflow_name="test_workflow",
            step_name="cached_step"
        )
        assert metric._value._value > 0
    
    def test_record_step_execution_billing(self):
        """Test billing metric recorded"""
        collector.record_step_execution(
            workflow_name="test_workflow",
            step_name="billable_step",
            duration_ms=100,
            status="completed",
            was_cached=False,
            user_id="user_456",
            plan_type="enterprise"
        )
        
        # Check billing metric
        metric = managed_steps_total.labels(
            user_id="user_456",
            workflow_name="test_workflow",
            plan_type="enterprise"
        )
        assert metric._value._value > 0
    
    def test_record_restore(self):
        """Test restore operation metric (CRITICAL)"""
        collector.record_restore(
            workflow_name="test_workflow",
            duration_ms=450.2,
            events_replayed=45,
            had_snapshot=True
        )
        
        # Check restore duration
        metric = restore_duration_milliseconds.labels(
            workflow_name="test_workflow",
            has_snapshot="True"
        )
        assert metric._sum._value > 0
    
    def test_record_restore_without_snapshot(self):
        """Test restore without snapshot (slower)"""
        collector.record_restore(
            workflow_name="test_workflow",
            duration_ms=2500.0,
            events_replayed=500,
            had_snapshot=False
        )
        
        metric = restore_duration_milliseconds.labels(
            workflow_name="test_workflow",
            has_snapshot="False"
        )
        assert metric._sum._value > 0
    
    def test_record_snapshot(self):
        """Test snapshot creation metric"""
        collector.record_snapshot(
            workflow_name="test_workflow",
            workflow_id="wf_123",
            size_bytes=51200,  # 50KB
            duration_ms=25.5,
            storage_type="s3"
        )
        # Metrics should be recorded (no assertion on internal state)
    
    def test_record_journal_append(self):
        """Test journal append metric"""
        collector.record_journal_append(
            event_type="step_completed",
            duration_ms=5.2
        )
        # Metric should be recorded
    
    def test_record_lease_acquisition_success(self):
        """Test successful lease acquisition"""
        collector.record_lease_acquisition(
            workflow_name="test_workflow",
            duration_ms=15.3,
            result="acquired",
            owner_id="executor_1"
        )
        # Metric should be recorded
    
    def test_record_lease_acquisition_failure(self):
        """Test failed lease acquisition"""
        collector.record_lease_acquisition(
            workflow_name="test_workflow",
            duration_ms=10.0,
            result="locked"
        )
        # Failure metric should be recorded
    
    def test_record_cost_savings(self):
        """Test cost savings metric"""
        collector.record_cost_savings(
            workflow_name="test_workflow",
            steps_avoided=5
        )
        # Metric should be recorded
    
    def test_record_data_corruption(self):
        """Test data corruption metric (CRITICAL)"""
        collector.record_data_corruption(
            data_type="snapshot",
            workflow_id="wf_corrupt"
        )
        
        # Check corruption detected
        metric = checksum_validation_failures_total.labels(
            data_type="snapshot"
        )
        assert metric._value._value > 0
    
    def test_record_critical_error(self):
        """Test critical error metric"""
        collector.record_critical_error(
            component="journal",
            error_type="write_failure"
        )
        # Metric should be recorded


class TestMetricsIntegration:
    """Integration tests for metrics flow"""
    
    def test_complete_workflow_metrics_flow(self):
        """Test complete workflow execution metrics"""
        workflow_name = "integration_test"
        
        # Start workflow
        collector.record_workflow_start(workflow_name, trigger="test")
        
        # Execute steps
        for i in range(3):
            collector.record_step_execution(
                workflow_name=workflow_name,
                step_name=f"step_{i}",
                duration_ms=100.0,
                status="completed",
                user_id="test_user",
                plan_type="free"
            )
        
        # Complete workflow
        collector.record_workflow_complete(
            workflow_name=workflow_name,
            duration_seconds=1.5,
            status="completed"
        )
        
        # Verify metrics recorded
        start_metric = workflows_started_total.labels(
            workflow_name=workflow_name,
            trigger="test"
        )
        assert start_metric._value._value > 0
        
        complete_metric = workflows_completed_total.labels(
            workflow_name=workflow_name,
            status="completed"
        )
        assert complete_metric._value._value > 0
    
    def test_restore_with_snapshot_metrics(self):
        """Test restore operation with snapshot"""
        collector.record_restore(
            workflow_name="restore_test",
            duration_ms=250.0,
            events_replayed=20,
            had_snapshot=True
        )
        
        # Should be fast with snapshot
        metric = restore_duration_milliseconds.labels(
            workflow_name="restore_test",
            has_snapshot="True"
        )
        # Just verify metric was recorded
        assert metric._sum._value > 0
