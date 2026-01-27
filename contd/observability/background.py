"""
Background metrics collection - system resources, health checks, etc.
"""

import psutil
import threading
import time
from typing import Optional
from .metrics import (
    process_memory_bytes,
    process_cpu_usage_percent,
    component_health_status,
    database_connection_errors_total
)


class BackgroundCollector:
    """Collects system metrics in background thread"""
    
    def __init__(self, interval_seconds: int = 15):
        self.interval = interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.process = psutil.Process()
    
    def start(self):
        """Start background collection"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop background collection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _collect_loop(self):
        """Main collection loop"""
        while self.running:
            try:
                self._collect_system_metrics()
            except Exception as e:
                print(f"Error collecting metrics: {e}")
            
            time.sleep(self.interval)
    
    def _collect_system_metrics(self):
        """Collect system resource metrics"""
        # Memory
        mem_info = self.process.memory_info()
        process_memory_bytes.labels(memory_type='rss').set(mem_info.rss)
        process_memory_bytes.labels(memory_type='heap').set(mem_info.vms)
        
        # CPU
        cpu_percent = self.process.cpu_percent(interval=1)
        process_cpu_usage_percent.set(cpu_percent)


# Global collector instance
_collector: Optional[BackgroundCollector] = None


def start_background_collection(interval_seconds: int = 15):
    """Start background metrics collection"""
    global _collector
    if _collector is None:
        _collector = BackgroundCollector(interval_seconds)
    _collector.start()
    return _collector


def stop_background_collection():
    """Stop background metrics collection"""
    global _collector
    if _collector:
        _collector.stop()
        _collector = None


__all__ = ['BackgroundCollector', 'start_background_collection', 'stop_background_collection']
