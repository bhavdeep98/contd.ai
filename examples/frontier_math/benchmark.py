"""
Benchmark runner for FrontierMath problems.

Runs multiple problems and tracks solve rates, costs, and performance.
"""

import sys
import os
import json
import time
import glob
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import ModelConfig, SolverConfig, BenchmarkConfig
from solver import FrontierMathSolver

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FrontierMathBenchmark:
    """Benchmark runner for FrontierMath problems."""
    
    def __init__(
        self,
        model_config: ModelConfig,
        solver_config: SolverConfig,
        benchmark_config: BenchmarkConfig
    ):
        self.model_config = model_config
        self.solver_config = solver_config
        self.benchmark_config = benchmark_config
        self.solver = FrontierMathSolver(model_config, solver_config)
        
        # Ensure results directory exists
        os.makedirs(benchmark_config.results_dir, exist_ok=True)
    
    def run(self) -> Dict[str, Any]:
        """Run benchmark on all problems."""
        logger.info("=" * 60)
        logger.info("FrontierMath Benchmark")
        logger.info("=" * 60)
        logger.info(f"Problems dir: {self.benchmark_config.problems_dir}")
        logger.info(f"Model: {self.model_config.provider} / {self.model_config.model_name}")
        logger.info(f"Max problems: {self.benchmark_config.max_problems or 'all'}")
        logger.info("=" * 60)
        
        # Load problems
        problems = self._load_problems()
        logger.info(f"Loaded {len(problems)} problems")
        
        if not problems:
            logger.error("No problems found!")
            return {"error": "No problems found"}
        
        # Run benchmark
        results = []
        start_time = time.time()
        
        for i, problem_data in enumerate(problems):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Problem {i+1}/{len(problems)}: {problem_data['id']}")
            logger.info(f"{'=' * 60}")
            
            problem_start = time.time()
            
            try:
                result = self.solver.solve(problem_data['problem'])
                result['problem_id'] = problem_data['id']
                result['problem_file'] = problem_data['file']
                result['time_seconds'] = time.time() - problem_start
                
                results.append(result)
                
                logger.info(f"Result: {result['status']}")
                if result['status'] == 'solved':
                    logger.info(f"✅ SOLVED in {result['steps']} steps")
                else:
                    logger.info(f"❌ NOT SOLVED ({result['status']})")
                
            except Exception as e:
                logger.error(f"Error solving problem: {e}")
                results.append({
                    'problem_id': problem_data['id'],
                    'problem_file': problem_data['file'],
                    'status': 'error',
                    'error': str(e),
                    'time_seconds': time.time() - problem_start
                })
        
        total_time = time.time() - start_time
        
        # Compute statistics
        stats = self._compute_stats(results, total_time)
        
        # Save results
        self._save_results(stats)
        
        # Print summary
        self._print_summary(stats)
        
        return stats
    
    def _load_problems(self) -> List[Dict[str, Any]]:
        """Load problems from directory."""
        problems_dir = Path(self.benchmark_config.problems_dir)
        
        if not problems_dir.exists():
            logger.warning(f"Problems directory not found: {problems_dir}")
            return []
        
        # Find all .txt files
        problem_files = list(problems_dir.glob("*.txt"))
        
        # Apply filter if specified
        if self.benchmark_config.problem_filter:
            import re
            pattern = re.compile(self.benchmark_config.problem_filter)
            problem_files = [f for f in problem_files if pattern.search(f.name)]
        
        # Limit number of problems
        if self.benchmark_config.max_problems:
            problem_files = problem_files[:self.benchmark_config.max_problems]
        
        # Load problem content
        problems = []
        for file_path in problem_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                problems.append({
                    'id': file_path.stem,
                    'file': str(file_path),
                    'problem': content
                })
        
        return problems
    
    def _compute_stats(self, results: List[Dict], total_time: float) -> Dict[str, Any]:
        """Compute benchmark statistics."""
        total = len(results)
        solved = sum(1 for r in results if r['status'] == 'solved')
        timeout = sum(1 for r in results if r['status'] == 'timeout')
        max_steps = sum(1 for r in results if r['status'] == 'max_steps')
        errors = sum(1 for r in results if r['status'] == 'error')
        
        # Compute averages for solved problems
        solved_results = [r for r in results if r['status'] == 'solved']
        
        if solved_results:
            avg_steps = sum(r.get('steps', 0) for r in solved_results) / len(solved_results)
            avg_cost = sum(r.get('cost', 0) for r in solved_results) / len(solved_results)
            avg_time = sum(r.get('time_seconds', 0) for r in solved_results) / len(solved_results)
        else:
            avg_steps = 0
            avg_cost = 0
            avg_time = 0
        
        return {
            'benchmark_id': f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'model': {
                'provider': self.model_config.provider,
                'model_name': self.model_config.model_name,
            },
            'config': {
                'max_steps': self.solver_config.max_steps,
                'cost_budget': self.solver_config.cost_budget,
                'distill_every': self.solver_config.distill_every,
            },
            'summary': {
                'total_problems': total,
                'solved': solved,
                'timeout': timeout,
                'max_steps': max_steps,
                'errors': errors,
                'solve_rate': solved / total if total > 0 else 0,
                'avg_steps': avg_steps,
                'avg_cost': avg_cost,
                'avg_time_seconds': avg_time,
                'total_time_seconds': total_time,
            },
            'results': results
        }
    
    def _save_results(self, stats: Dict[str, Any]):
        """Save benchmark results to file."""
        filename = f"{stats['benchmark_id']}.json"
        filepath = os.path.join(self.benchmark_config.results_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"\n📊 Results saved to: {filepath}")
    
    def _print_summary(self, stats: Dict[str, Any]):
        """Print benchmark summary."""
        summary = stats['summary']
        
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Total Problems:  {summary['total_problems']}")
        print(f"Solved:          {summary['solved']} ({summary['solve_rate']:.1%})")
        print(f"Timeout:         {summary['timeout']}")
        print(f"Max Steps:       {summary['max_steps']}")
        print(f"Errors:          {summary['errors']}")
        print()
        print(f"Avg Steps:       {summary['avg_steps']:.1f}")
        print(f"Avg Cost:        ${summary['avg_cost']:.2f}")
        print(f"Avg Time:        {summary['avg_time_seconds']:.1f}s")
        print(f"Total Time:      {summary['total_time_seconds']:.1f}s")
        print("=" * 60)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FrontierMath Benchmark Runner")
    parser.add_argument("--problems-dir", type=str, help="Directory containing problems")
    parser.add_argument("--max-problems", type=int, help="Maximum number of problems to run")
    parser.add_argument("--model", type=str, help="Model provider")
    parser.add_argument("--results-dir", type=str, help="Directory for results")
    
    args = parser.parse_args()
    
    # Load configs
    model_config = ModelConfig.from_env()
    if args.model:
        model_config.provider = args.model
    
    solver_config = SolverConfig.from_env()
    
    benchmark_config = BenchmarkConfig.from_env()
    if args.problems_dir:
        benchmark_config.problems_dir = args.problems_dir
    if args.max_problems:
        benchmark_config.max_problems = args.max_problems
    if args.results_dir:
        benchmark_config.results_dir = args.results_dir
    
    # Run benchmark
    benchmark = FrontierMathBenchmark(model_config, solver_config, benchmark_config)
    benchmark.run()


if __name__ == "__main__":
    main()
