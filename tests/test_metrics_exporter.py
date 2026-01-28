"""
Unit tests for metrics exporter
"""

import pytest
import time
import requests
from unittest.mock import Mock, patch
from contd.observability.exporter import (
    MetricsExporter,
    start_metrics_server,
    stop_metrics_server
)


class TestMetricsExporter:
    
    def test_exporter_initialization(self):
        """Test exporter can be initialized"""
        exporter = MetricsExporter(port=9999, host='127.0.0.1')
        assert exporter.port == 9999
        assert exporter.host == '127.0.0.1'
        assert exporter.server is None
    
    def test_exporter_start(self):
        """Test exporter starts HTTP server"""
        exporter = MetricsExporter(port=9998)
        try:
            exporter.start()
            assert exporter.server is not None
            assert exporter.thread is not None
            assert exporter.thread.is_alive()
        finally:
            exporter.stop()
    
    def test_exporter_stop(self):
        """Test exporter stops cleanly"""
        exporter = MetricsExporter(port=9997)
        exporter.start()
        time.sleep(0.1)
        
        exporter.stop()
        assert exporter.server is None
        assert exporter.thread is None
    
    def test_metrics_endpoint_accessible(self):
        """Test /metrics endpoint is accessible"""
        exporter = MetricsExporter(port=9996)
        try:
            exporter.start()
            time.sleep(0.2)  # Wait for server to start
            
            response = requests.get('http://localhost:9996/metrics', timeout=2)
            assert response.status_code == 200
            assert 'text/plain' in response.headers['Content-Type']
            
        finally:
            exporter.stop()
    
    def test_health_endpoint_accessible(self):
        """Test /health endpoint is accessible"""
        exporter = MetricsExporter(port=9995)
        try:
            exporter.start()
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9995/health', timeout=2)
            assert response.status_code == 200
            assert response.text == 'OK'
            
        finally:
            exporter.stop()
    
    def test_invalid_endpoint_returns_404(self):
        """Test invalid endpoint returns 404"""
        exporter = MetricsExporter(port=9994)
        try:
            exporter.start()
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9994/invalid', timeout=2)
            assert response.status_code == 404
            
        finally:
            exporter.stop()
    
    def test_start_metrics_server_global(self):
        """Test global start_metrics_server function"""
        try:
            exporter = start_metrics_server(port=9993)
            assert exporter is not None
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9993/metrics', timeout=2)
            assert response.status_code == 200
            
        finally:
            stop_metrics_server()
    
    def test_stop_metrics_server_global(self):
        """Test global stop_metrics_server function"""
        start_metrics_server(port=9992)
        time.sleep(0.2)
        
        stop_metrics_server()
        
        # Server should be stopped
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get('http://localhost:9992/metrics', timeout=1)
    
    def test_double_start_is_safe(self):
        """Test starting server twice doesn't crash"""
        exporter = MetricsExporter(port=9991)
        try:
            exporter.start()
            exporter.start()  # Should be no-op
            assert exporter.server is not None
        finally:
            exporter.stop()
    
    def test_metrics_content_format(self):
        """Test metrics are in Prometheus format"""
        # Import metrics to ensure they're registered
        from contd.observability.metrics import collector
        
        exporter = MetricsExporter(port=9990)
        try:
            exporter.start()
            time.sleep(0.5)
            
            # Record a metric to ensure something is in the registry
            collector.record_workflow_start("test_format_workflow", trigger="test")
            
            # Retry a few times in case of timing issues
            content = ""
            for _ in range(5):
                response = requests.get('http://localhost:9990/metrics', timeout=2)
                content = response.text
                if 'contd_workflows_started_total' in content:
                    break
                time.sleep(0.3)
            
            # Should contain our recorded metric
            assert 'contd_workflows_started_total' in content
            
        finally:
            exporter.stop()


class TestMetricsHandler:
    """Test HTTP handler behavior"""
    
    def test_handler_suppresses_logs(self):
        """Test handler doesn't spam logs"""
        exporter = MetricsExporter(port=9989)
        try:
            exporter.start()
            time.sleep(0.2)
            
            # Multiple requests shouldn't spam logs
            for _ in range(5):
                requests.get('http://localhost:9989/metrics', timeout=1)
            
            # No assertion - just verify no crash
            
        finally:
            exporter.stop()
