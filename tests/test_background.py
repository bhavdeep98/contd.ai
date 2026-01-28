"""
Unit tests for background metrics collection
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from contd.observability.background import (
    BackgroundCollector,
    start_background_collection,
    stop_background_collection
)


class TestBackgroundCollector:
    """Test background metrics collector"""
    
    def test_collector_initialization(self):
        """Test collector can be initialized"""
        collector = BackgroundCollector(interval_seconds=5)
        assert collector.interval == 5
        assert collector.running is False
        assert collector.thread is None
    
    def test_collector_start(self):
        """Test collector starts successfully"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            assert collector.running is True
            assert collector.thread is not None
            assert collector.thread.is_alive()
        finally:
            collector.stop()
    
    def test_collector_stop(self):
        """Test collector stops cleanly"""
        collector = BackgroundCollector(interval_seconds=1)
        collector.start()
        time.sleep(0.5)
        collector.stop()
        assert collector.running is False
    
    def test_collector_idempotent_start(self):
        """Test starting already running collector is safe"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            thread1 = collector.thread
            collector.start()  # Should be no-op
            assert collector.thread is thread1
        finally:
            collector.stop()
    
    @patch('contd.observability.metrics.process_memory_bytes')
    @patch('contd.observability.metrics.process_cpu_usage_percent')
    def test_system_metrics_collected(self, mock_cpu, mock_memory):
        """Test system metrics are collected"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            time.sleep(1.5)  # Wait for at least one collection
            
            # Verify metrics were set
            assert mock_memory.labels.called
            assert mock_cpu.set.called
        finally:
            collector.stop()
    
    def test_collection_interval(self):
        """Test collection happens at specified interval"""
        call_count = 0
        
        def mock_collect():
            nonlocal call_count
            call_count += 1
        
        collector = BackgroundCollector(interval_seconds=1)
        collector._collect_system_metrics = mock_collect
        
        try:
            collector.start()
            time.sleep(2.5)
            
            # Should have collected 2-3 times
            assert 2 <= call_count <= 3
        finally:
            collector.stop()
    
    def test_collection_error_handling(self):
        """Test collector handles errors gracefully"""
        def mock_collect_error():
            raise Exception("Test error")
        
        collector = BackgroundCollector(interval_seconds=1)
        collector._collect_system_metrics = mock_collect_error
        
        try:
            collector.start()
            time.sleep(1.5)
            # Should still be running despite errors
            assert collector.running is True
        finally:
            collector.stop()


class TestBackgroundCollectionGlobal:
    """Test global background collection functions"""
    
    def test_start_background_collection(self):
        """Test global start function"""
        try:
            collector = start_background_collection(interval_seconds=1)
            assert collector is not None
            assert collector.running is True
        finally:
            stop_background_collection()
    
    def test_stop_background_collection(self):
        """Test global stop function"""
        start_background_collection(interval_seconds=1)
        time.sleep(0.5)
        stop_background_collection()
        # Should be stopped
    
    def test_multiple_start_calls(self):
        """Test multiple start calls reuse same collector"""
        try:
            col1 = start_background_collection(interval_seconds=1)
            col2 = start_background_collection(interval_seconds=1)
            assert col1 is col2
        finally:
            stop_background_collection()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
