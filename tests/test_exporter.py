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
    """Test metrics HTTP exporter"""
    
    def test_exporter_initialization(self):
        """Test exporter can be initialized"""
        exporter = MetricsExporter(port=9999, host='127.0.0.1')
        assert exporter.port == 9999
        assert exporter.host == '127.0.0.1'
        assert exporter.server is None
    
    def test_exporter_start(self):
        """Test exporter starts successfully"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            assert exporter.server is not None
            assert exporter.thread is not None
            assert exporter.thread.is_alive()
        finally:
            exporter.stop()
    
    def test_exporter_stop(self):
        """Test exporter stops cleanly"""
        exporter = MetricsExporter(port=9999)
        exporter.start()
        time.sleep(0.1)
        exporter.stop()
        assert exporter.server is None
    
    def test_exporter_idempotent_start(self):
        """Test starting already running exporter is safe"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            server1 = exporter.server
            exporter.start()  # Should be no-op
            assert exporter.server is server1
        finally:
            exporter.stop()
    
    def test_metrics_endpoint_accessible(self):
        """Test /metrics endpoint is accessible"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            time.sleep(0.2)  # Give server time to start
            
            response = requests.get('http://localhost:9999/metrics', timeout=1)
            assert response.status_code == 200
            assert 'text/plain' in response.headers['Content-Type']
        finally:
            exporter.stop()
    
    def test_health_endpoint_accessible(self):
        """Test /health endpoint is accessible"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9999/health', timeout=1)
            assert response.status_code == 200
            assert response.text == 'OK'
        finally:
            exporter.stop()
    
    def test_invalid_endpoint_returns_404(self):
        """Test invalid endpoint returns 404"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9999/invalid', timeout=1)
            assert response.status_code == 404
        finally:
            exporter.stop()
    
    def test_metrics_format(self):
        """Test metrics are in Prometheus format"""
        exporter = MetricsExporter(port=9999)
        try:
            exporter.start()
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9999/metrics', timeout=1)
            content = response.text
            
            # Should contain Prometheus format metrics
            assert '# HELP' in content or '# TYPE' in content or 'contd_' in content
        finally:
            exporter.stop()


class TestMetricsServerGlobal:
    """Test global metrics server functions"""
    
    def test_start_metrics_server(self):
        """Test global start function"""
        try:
            exporter = start_metrics_server(port=9998)
            assert exporter is not None
            time.sleep(0.2)
            
            response = requests.get('http://localhost:9998/metrics', timeout=1)
            assert response.status_code == 200
        finally:
            stop_metrics_server()
    
    def test_stop_metrics_server(self):
        """Test global stop function"""
        start_metrics_server(port=9997)
        time.sleep(0.2)
        stop_metrics_server()
        
        # Server should be stopped
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get('http://localhost:9997/metrics', timeout=1)
    
    def test_multiple_start_calls(self):
        """Test multiple start calls reuse same server"""
        try:
            exp1 = start_metrics_server(port=9996)
            exp2 = start_metrics_server(port=9996)
            assert exp1 is exp2
        finally:
            stop_metrics_server()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
