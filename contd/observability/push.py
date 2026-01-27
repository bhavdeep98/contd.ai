"""
Push-based metrics emission to Prometheus Pushgateway
Useful for batch jobs and short-lived processes
"""

from prometheus_client import push_to_gateway, CollectorRegistry, REGISTRY
from typing import Optional
import time


class MetricsPusher:
    """Push metrics to Prometheus Pushgateway"""
    
    def __init__(
        self,
        gateway_url: str,
        job_name: str = 'contd',
        instance: Optional[str] = None,
        registry: CollectorRegistry = REGISTRY
    ):
        self.gateway_url = gateway_url
        self.job_name = job_name
        self.instance = instance or f"contd-{int(time.time())}"
        self.registry = registry
    
    def push(self, grouping_key: Optional[dict] = None):
        """Push current metrics to gateway"""
        grouping = grouping_key or {}
        grouping['instance'] = self.instance
        
        push_to_gateway(
            self.gateway_url,
            job=self.job_name,
            registry=self.registry,
            grouping_key=grouping
        )
    
    def push_on_exit(self):
        """Register push on process exit"""
        import atexit
        atexit.register(self.push)


__all__ = ['MetricsPusher']
