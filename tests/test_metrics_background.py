"""
Unit tests for background metrics collection
"""

import pytest
import time
from unittest.mock import Mock, patch
from contd.observability.background import (
    BackgroundCollector,
    start_background_collection,
    stop_background_collection
)
from contd.observability.metrics import (
    process_memory_bytes,
    process_cpu_usage_percent
)


class TestBackgroundCollector:
    
    def test_collector_initialization(self):
        """Test collector can be initialized"""
        collector = BackgroundCollector(interval_seconds=5)
        assert collector.interval == 5
        assert collector.running is False
        assert collector.thread is None
    
    def test_collector_start(self):
        """Test collector starts background thread"""
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
        time.sleep(0.1)
        
        collector.stop()
        assert collector.running is False
    
    def test_collector_collects_metrics(self):
        """Test collector actually collects metrics"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            time.sleep(1.5)  # Wait for at least one collection
            
            # Check memory metric was set
            rss_metric = process_memory_bytes.labels(memory_type='rss')
            assert rss_metric._value._value > 0
            
            # Check CPU metric was set
            cpu_metric = process_cpu_usage_percent
            assert cpu_metric._value._value >= 0
            
        finally:
            collector.stop()
    
    def test_collector_handles_errors_gracefully(self):
        """Test collector doesn't crash on errors"""
        collector = BackgroundCollector(interval_seconds=1)
        
        with patch('psutil.Process.memory_info', side_effect=Exception("Test error")):
            try:
                collector.start()
                time.sleep(1.5)
                # Should still be running despite error
                assert collector.running is True
            finally:
                collector.stop()
    
    def test_double_start_is_safe(self):
        """Test starting collector twice doesn't crash"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            collector.start()  # Should be no-op
            assert collector.running is True
        finally:
            collector.stop()
    
    def test_global_start_function(self):
        """Test global start_background_collection"""
        try:
            collector = start_background_collection(interval_seconds=1)
            assert collector is not None
            assert collector.running is True
        finally:
            stop_background_collection()
    
    def test_global_stop_function(self):
        """Test global stop_background_collection"""
        start_background_collection(interval_seconds=1)
        time.sleep(0.1)
        
        stop_background_collection()
        # Should stop cleanly without error
    
    def test_memory_metrics_collected(self):
        """Test memory metrics are collected"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            time.sleep(1.5)
            
            # RSS memory
            rss = process_memory_bytes.labels(memory_type='rss')._value._value
            assert rss > 0
            
            # Heap memory
            heap = process_memory_bytes.labels(memory_type='heap')._value._value
            assert heap > 0
            
        finally:
            collector.stop()
    
    def test_cpu_metrics_collected(self):
        """Test CPU metrics are collected"""
        collector = BackgroundCollector(interval_seconds=1)
        try:
            collector.start()
            time.sleep(1.5)
            
            cpu = process_cpu_usage_percent._value._value
            assert cpu >= 0
            assert cpu <= 100  # Should be percentage
            
        finally:
            collector.stop()
    
    def test_collection_interval_respected(self):
        """Test collection happens at specified interval"""
        collector = BackgroundCollector(interval_seconds=2)
        
        collection_count = 0
        original_collect = collector._collect_system_metrics
        
        def counting_collect():
            nonlocal collection_count
            collection_count += 1
            original_collect()
        
        collector._collect_system_metrics = counting_collect
        
        try:
            collector.start()
            time.sleep(4.5)  # Should collect ~2 times
            
            # Allow some tolerance
            assert collection_count >= 1
            assert collection_count <= 3
            
        finally:
            collector.stop()
