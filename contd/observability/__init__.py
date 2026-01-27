"""
Contd.ai Observability Module
"""

from .metrics import collector, MetricsCollector
from .exporter import start_metrics_server, stop_metrics_server
from .background import start_background_collection, stop_background_collection
from .push import MetricsPusher


def setup_observability(
    metrics_port: int = 9090,
    enable_background: bool = True,
    background_interval: int = 15
):
    """Setup complete observability stack"""
    start_metrics_server(port=metrics_port)
    if enable_background:
        start_background_collection(interval_seconds=background_interval)


def teardown_observability():
    """Cleanup observability resources"""
    stop_metrics_server()
    stop_background_collection()


__all__ = [
    'collector',
    'MetricsCollector',
    'start_metrics_server',
    'stop_metrics_server',
    'start_background_collection',
    'stop_background_collection',
    'MetricsPusher',
    'setup_observability',
    'teardown_observability',
]
