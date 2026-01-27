"""Benchmark runner and reporting."""
import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

from .config import BenchmarkConfig, BenchmarkResult


class BenchmarkRunner:
    """Runs benchmarks and collects results."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: list[BenchmarkResult] = []
    
    async def run_async_benchmark(
        self,
        name: str,
        func: Callable[..., Any],
        iterations: int,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Run an async benchmark function multiple times."""
        times: list[float] = []
        errors = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await func(*args, **kwargs)
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms
        
        return self._calculate_result(name, times, errors, kwargs.get("metadata", {}))
    
    def run_sync_benchmark(
        self,
        name: str,
        func: Callable[..., Any],
        iterations: int,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Run a sync benchmark function multiple times."""
        times: list[float] = []
        errors = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func(*args, **kwargs)
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)
        
        return self._calculate_result(name, times, errors, kwargs.get("metadata", {}))
    
    async def run_concurrent_benchmark(
        self,
        name: str,
        func: Callable[..., Any],
        total_iterations: int,
        concurrency: int,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Run concurrent async benchmark."""
        times: list[float] = []
        errors = 0
        semaphore = asyncio.Semaphore(concurrency)
        
        async def run_one():
            nonlocal errors
            async with semaphore:
                start = time.perf_counter()
                try:
                    await func(*args, **kwargs)
                except Exception:
                    errors += 1
                end = time.perf_counter()
                times.append((end - start) * 1000)
        
        tasks = [run_one() for _ in range(total_iterations)]
        await asyncio.gather(*tasks)
        
        metadata = kwargs.get("metadata", {})
        metadata["concurrency"] = concurrency
        return self._calculate_result(name, times, errors, metadata)
    
    def _calculate_result(
        self,
        name: str,
        times: list[float],
        errors: int,
        metadata: dict
    ) -> BenchmarkResult:
        """Calculate statistics from timing data."""
        if not times:
            return BenchmarkResult(
                name=name,
                iterations=0,
                total_time_ms=0,
                avg_time_ms=0,
                min_time_ms=0,
                max_time_ms=0,
                p50_ms=0,
                p95_ms=0,
                p99_ms=0,
                throughput_per_sec=0,
                errors=errors,
                metadata=metadata
            )
        
        sorted_times = sorted(times)
        total_time = sum(times)
        
        result = BenchmarkResult(
            name=name,
            iterations=len(times),
            total_time_ms=total_time,
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=self._percentile(sorted_times, 50),
            p95_ms=self._percentile(sorted_times, 95),
            p99_ms=self._percentile(sorted_times, 99),
            throughput_per_sec=(len(times) / total_time) * 1000 if total_time > 0 else 0,
            errors=errors,
            metadata=metadata
        )
        
        self.results.append(result)
        return result
    
    def _percentile(self, sorted_data: list[float], percentile: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
    
    def save_results(self, filename: str | None = None):
        """Save results to file."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{timestamp}"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "api_url": self.config.api_url,
                "workflow_count": self.config.workflow_count,
                "steps_per_workflow": self.config.steps_per_workflow,
            },
            "results": [
                {
                    "name": r.name,
                    "iterations": r.iterations,
                    "total_time_ms": r.total_time_ms,
                    "avg_time_ms": r.avg_time_ms,
                    "min_time_ms": r.min_time_ms,
                    "max_time_ms": r.max_time_ms,
                    "p50_ms": r.p50_ms,
                    "p95_ms": r.p95_ms,
                    "p99_ms": r.p99_ms,
                    "throughput_per_sec": r.throughput_per_sec,
                    "errors": r.errors,
                    "metadata": r.metadata
                }
                for r in self.results
            ]
        }
        
        if self.config.output_format == "json":
            with open(output_dir / f"{filename}.json", "w") as f:
                json.dump(data, f, indent=2)
        elif self.config.output_format == "markdown":
            self._save_markdown(output_dir / f"{filename}.md", data)
    
    def _save_markdown(self, path: Path, data: dict):
        """Save results as markdown table."""
        lines = [
            "# Benchmark Results",
            f"\nTimestamp: {data['timestamp']}\n",
            "## Results\n",
            "| Benchmark | Iterations | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput/s | Errors |",
            "|-----------|------------|----------|----------|----------|----------|--------------|--------|"
        ]
        
        for r in data["results"]:
            lines.append(
                f"| {r['name']} | {r['iterations']} | {r['avg_time_ms']:.2f} | "
                f"{r['p50_ms']:.2f} | {r['p95_ms']:.2f} | {r['p99_ms']:.2f} | "
                f"{r['throughput_per_sec']:.1f} | {r['errors']} |"
            )
        
        with open(path, "w") as f:
            f.write("\n".join(lines))
    
    def print_summary(self):
        """Print results summary to console."""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        
        for result in self.results:
            print(f"\n{result.name}")
            print("-" * 40)
            print(f"  Iterations:    {result.iterations}")
            print(f"  Avg time:      {result.avg_time_ms:.2f} ms")
            print(f"  P50:           {result.p50_ms:.2f} ms")
            print(f"  P95:           {result.p95_ms:.2f} ms")
            print(f"  P99:           {result.p99_ms:.2f} ms")
            print(f"  Throughput:    {result.throughput_per_sec:.1f} ops/sec")
            if result.errors > 0:
                print(f"  Errors:        {result.errors}")
