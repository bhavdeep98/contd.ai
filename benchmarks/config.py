"""Benchmark configuration."""
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    
    # Target configuration
    api_url: str = field(default_factory=lambda: os.getenv("CONTD_API_URL", "http://localhost:8080"))
    
    # Workflow benchmarks
    workflow_count: int = 100
    steps_per_workflow: int = 10
    concurrent_workflows: int = 10
    
    # Step benchmarks
    step_iterations: int = 1000
    step_payload_sizes: list[int] = field(default_factory=lambda: [100, 1000, 10000, 100000])
    
    # Persistence benchmarks
    snapshot_sizes: list[int] = field(default_factory=lambda: [1024, 10240, 102400, 1048576])
    journal_entry_count: int = 1000
    
    # Load test configuration
    load_test_duration_seconds: int = 60
    load_test_rps: list[int] = field(default_factory=lambda: [10, 50, 100, 500])
    
    # Recovery benchmarks
    recovery_workflow_count: int = 50
    recovery_step_count: int = 20
    
    # Output
    output_dir: str = "benchmark_results"
    output_format: str = "json"  # json, csv, markdown


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""
    
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float
    errors: int = 0
    metadata: dict = field(default_factory=dict)
