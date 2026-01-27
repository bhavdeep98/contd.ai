# Performance Benchmarks

## Running Benchmarks

```bash
# Run all benchmarks
python -m benchmarks.run_benchmarks

# With options
python -m benchmarks.run_benchmarks \
  --api-url http://localhost:8080 \
  --workflows 100 \
  --iterations 1000 \
  --output-dir results \
  --format markdown
```

## Benchmark Suites

### Persistence Benchmarks
- SQLite read/write operations
- Snapshot save with various sizes
- Journal append performance

### Recovery Benchmarks
- State recovery from persistence
- Journal replay performance
- Savepoint restoration

### Workflow Benchmarks (requires running server)
- Workflow creation
- Step execution with payload sizes
- Concurrent workflow execution
- Status queries
- Full lifecycle completion

## Output

Results are saved to `benchmark_results/` in JSON or Markdown format.
