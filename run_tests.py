#!/usr/bin/env python3
"""
Run tests and generate coverage report
"""

import sys
import subprocess


def run_tests():
    """Run pytest with coverage"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--cov=contd",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-report=json"
    ]
    
    result = subprocess.run(cmd)
    return result.returncode


def print_coverage_summary():
    """Print coverage summary"""
    try:
        import json
        with open('coverage.json', 'r') as f:
            data = json.load(f)
            total = data['totals']['percent_covered']
            print(f"\n{'='*60}")
            print(f"Total Coverage: {total:.1f}%")
            print(f"{'='*60}")
            print("\nModule Coverage:")
            for file, stats in data['files'].items():
                if 'contd/' in file:
                    module = file.replace('contd/', '').replace('.py', '')
                    coverage = stats['summary']['percent_covered']
                    print(f"  {module:40s} {coverage:5.1f}%")
    except Exception as e:
        print(f"Could not read coverage data: {e}")


if __name__ == "__main__":
    print("Running tests with coverage...\n")
    exit_code = run_tests()
    
    if exit_code == 0:
        print_coverage_summary()
        print("\nDetailed HTML report: htmlcov/index.html")
    
    sys.exit(exit_code)
