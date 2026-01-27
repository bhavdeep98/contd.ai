#!/usr/bin/env python3
"""Main benchmark runner script."""
import argparse
import asyncio
import sys

from .config import BenchmarkConfig
from .runner import BenchmarkRunner
from .workflow_benchmarks import WorkflowBenchmarks
from .persistence_benchmarks import PersistenceBenchmarks
from .recovery_benchmarks import RecoveryBenchmarks


async def run_all_benchmarks(config: BenchmarkConfig):
    """Run all benchmark suites."""
    runner = BenchmarkRunner(config)
    
    print("Starting Contd Performance Benchmarks")
    print("=" * 50)
    
    # Persistence benchmarks (local, no server needed)
    print("\n[1/3] Running Persistence Benchmarks...")
    persistence = PersistenceBenchmarks(config, runner)
    await persistence.run_all()
    
    # Recovery benchmarks (local)
    print("\n[2/3] Running Recovery Benchmarks...")
    recovery = RecoveryBenchmarks(config, runner)
    await recovery.run_all()
    
    # Workflow benchmarks (requires running server)
    print("\n[3/3] Running Workflow Benchmarks...")
    try:
        workflow = WorkflowBenchmarks(config, runner)
        await workflow.run_all()
    except Exception as e:
        print(f"  Skipped (server not available): {e}")
    
    runner.print_summary()
    runner.save_results()
    print(f"\nResults saved to {config.output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Run Contd benchmarks")
    parser.add_argument("--api-url", default="http://localhost:8080")
    parser.add_argument("--workflows", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--output-dir", default="benchmark_results")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()
    
    config = BenchmarkConfig(
        api_url=args.api_url,
        workflow_count=args.workflows,
        step_iterations=args.iterations,
        output_dir=args.output_dir,
        output_format=args.format
    )
    
    asyncio.run(run_all_benchmarks(config))


if __name__ == "__main__":
    main()
