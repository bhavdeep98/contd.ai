"""
Unit tests for observability setup
"""

import pytest
import time
from unittest.mock import Mock, patch
from contd.observability import (
    setup_observability,
    teardown_observability,
    collector
)


class TestObservabilitySetup:
    
    @patch('contd.observability.start_metrics_server')
    @patch('contd.observability.start_background_collection')
    def test_setup_observability_default(self, mock_bg, mock_server):
        """Test setup with default parameters"""
        setup_observability()
        
        mock_server.assert_called_once_with(port=9090)
        mock_bg.assert_called_once_with(interval_seconds=15)
    
    @patch('contd.observability.start_metrics_server')
    @patch('contd.observability.start_background_collection')
    def test_setup_observability_custom_port(self, mock_bg, mock_server):
        """Test setup with custom port"""
        setup_observability(metrics_port=8080)
        
        mock_server.assert_called_once_with(port=8080)
    
    @patch('contd.observability.start_metrics_server')
    @patch('contd.observability.start_background_collection')
    def test_setup_observability_no_background(self, mock_bg, mock_server):
        """Test setup without background collection"""
        setup_observability(enable_background=False)
        
        mock_server.assert_called_once()
        mock_bg.assert_not_called()
    
    @patch('contd.observability.start_metrics_server')
    @patch('contd.observability.start_background_collection')
    def test_setup_observability_custom_interval(self, mock_bg, mock_server):
        """Test setup with custom background interval"""
        setup_observability(background_interval=30)
        
        mock_bg.assert_called_once_with(interval_seconds=30)
    
    @patch('contd.observability.stop_metrics_server')
    @patch('contd.observability.stop_background_collection')
    def test_teardown_observability(self, mock_bg_stop, mock_server_stop):
        """Test teardown cleans up resources"""
        teardown_observability()
        
        mock_server_stop.assert_called_once()
        mock_bg_stop.assert_called_once()
    
    def test_collector_is_available(self):
        """Test collector is accessible after import"""
        assert collector is not None
        assert hasattr(collector, 'record_workflow_start')
        assert hasattr(collector, 'record_step_execution')
        assert hasattr(collector, 'record_restore')


class TestObservabilityIntegration:
    """Integration tests for full observability stack"""
    
    def test_full_setup_and_teardown(self):
        """Test complete setup and teardown cycle"""
        try:
            setup_observability(
                metrics_port=9988,
                enable_background=True,
                background_interval=1
            )
            
            time.sleep(0.5)
            
            # Record some metrics
            collector.record_workflow_start("test_workflow", trigger="test")
            collector.record_step_execution(
                workflow_name="test_workflow",
                step_name="test_step",
                duration_ms=100,
                status="completed"
            )
            
            # Should work without errors
            
        finally:
            teardown_observability()
    
    def test_metrics_accessible_after_setup(self):
        """Test metrics endpoint is accessible after setup"""
        import requests
        
        try:
            setup_observability(metrics_port=9987, enable_background=False)
            time.sleep(0.5)
            
            response = requests.get('http://localhost:9987/metrics', timeout=2)
            assert response.status_code == 200
            
        finally:
            teardown_observability()
    
    def test_background_collection_after_setup(self):
        """Test background collection works after setup"""
        from contd.observability.metrics import process_memory_bytes
        
        try:
            setup_observability(
                metrics_port=9986,
                enable_background=True,
                background_interval=1
            )
            
            time.sleep(1.5)
            
            # Check background metrics collected
            metric = process_memory_bytes.labels(memory_type='rss')
            assert metric._value._value > 0
            
        finally:
            teardown_observability()
