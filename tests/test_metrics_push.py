"""
Unit tests for metrics push gateway
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from contd.observability.push import MetricsPusher


class TestMetricsPusher:
    
    def test_pusher_initialization(self):
        """Test pusher can be initialized"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job',
            instance='test_instance'
        )
        assert pusher.gateway_url == 'localhost:9091'
        assert pusher.job_name == 'test_job'
        assert pusher.instance == 'test_instance'
    
    def test_pusher_default_instance(self):
        """Test pusher generates default instance name"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job'
        )
        assert pusher.instance.startswith('contd-')
    
    @patch('contd.observability.push.push_to_gateway')
    def test_push_metrics(self, mock_push):
        """Test pushing metrics to gateway"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job',
            instance='test_instance'
        )
        
        pusher.push()
        
        mock_push.assert_called_once()
        call_args = mock_push.call_args
        assert call_args[0][0] == 'localhost:9091'
        assert call_args[1]['job'] == 'test_job'
    
    @patch('contd.observability.push.push_to_gateway')
    def test_push_with_grouping_key(self, mock_push):
        """Test pushing with custom grouping key"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job',
            instance='test_instance'
        )
        
        pusher.push(grouping_key={'env': 'prod', 'region': 'us-east'})
        
        mock_push.assert_called_once()
        grouping = mock_push.call_args[1]['grouping_key']
        assert grouping['env'] == 'prod'
        assert grouping['region'] == 'us-east'
        assert grouping['instance'] == 'test_instance'
    
    @patch('contd.observability.push.push_to_gateway')
    def test_push_on_exit_registration(self, mock_push):
        """Test push_on_exit registers atexit handler"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job'
        )
        
        with patch('atexit.register') as mock_atexit:
            pusher.push_on_exit()
            mock_atexit.assert_called_once_with(pusher.push)
    
    @patch('contd.observability.push.push_to_gateway')
    def test_push_handles_errors(self, mock_push):
        """Test push handles gateway errors"""
        mock_push.side_effect = Exception("Gateway unavailable")
        
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job'
        )
        
        with pytest.raises(Exception, match="Gateway unavailable"):
            pusher.push()
    
    @patch('contd.observability.push.push_to_gateway')
    def test_multiple_pushes(self, mock_push):
        """Test multiple pushes work correctly"""
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job'
        )
        
        pusher.push()
        pusher.push()
        pusher.push()
        
        assert mock_push.call_count == 3
    
    @patch('contd.observability.push.push_to_gateway')
    def test_custom_registry(self, mock_push):
        """Test pusher with custom registry"""
        from prometheus_client import CollectorRegistry
        
        custom_registry = CollectorRegistry()
        pusher = MetricsPusher(
            gateway_url='localhost:9091',
            job_name='test_job',
            registry=custom_registry
        )
        
        pusher.push()
        
        call_args = mock_push.call_args
        assert call_args[1]['registry'] == custom_registry
