"""
Metrics exporter - exposes Prometheus metrics via HTTP endpoint
"""

from prometheus_client import generate_latest, REGISTRY, CONTENT_TYPE_LATEST, Info
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from typing import Optional

# Create an info metric that's always present
_exporter_info = Info('contd_exporter', 'Contd metrics exporter information')
_exporter_info.info({'version': '1.0.0', 'status': 'running'})


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""

    def do_GET(self):
        if self.path == "/metrics":
            # Generate Prometheus format metrics
            try:
                metrics = generate_latest(REGISTRY)
            except Exception:
                metrics = b"# No metrics available\n"
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(metrics)))
            self.end_headers()
            self.wfile.write(metrics)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress request logging
        pass


class MetricsExporter:
    """Runs HTTP server to expose metrics"""

    def __init__(self, port: int = 9090, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Start metrics server in background thread"""
        if self.server:
            return

        self.server = HTTPServer((self.host, self.port), MetricsHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Metrics server started on http://{self.host}:{self.port}/metrics")

    def stop(self):
        """Stop metrics server"""
        if self.server:
            self.server.shutdown()
            self.server = None
            self.thread = None


# Global exporter instance
_exporter: Optional[MetricsExporter] = None


def start_metrics_server(port: int = 9090, host: str = "127.0.0.1"):
    """Start metrics exporter server"""
    global _exporter
    if _exporter is None:
        _exporter = MetricsExporter(port, host)
    _exporter.start()
    return _exporter


def stop_metrics_server():
    """Stop metrics exporter server"""
    global _exporter
    if _exporter:
        _exporter.stop()
        _exporter = None


__all__ = ["MetricsExporter", "start_metrics_server", "stop_metrics_server"]
