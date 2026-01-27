"""Persistence layer benchmarks."""
import asyncio
import os
import tempfile
import uuid
from typing import Any

from .config import BenchmarkConfig
from .runner import BenchmarkRunner


class PersistenceBenchmarks:
    """Benchmarks for persistence operations."""
    
    def __init__(self, config: BenchmarkConfig, runner: BenchmarkRunner):
        self.config = config
        self.runner = runner
    
    async def run_all(self):
        """Run all persistence benchmarks."""
        await self.benchmark_sqlite_operations()
        await self.benchmark_snapshot_sizes()
        await self.benchmark_journal_writes()
    
    async def benchmark_sqlite_operations(self):
        """Benchmark SQLite adapter operations."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            print("SQLite adapter not available, skipping benchmark")
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            # Write benchmark
            async def write_state():
                workflow_id = str(uuid.uuid4())
                await adapter.save_state(workflow_id, {
                    "status": "running",
                    "steps": [{"id": str(uuid.uuid4()), "result": "ok"} for _ in range(10)]
                })
            
            await self.runner.run_async_benchmark(
                "sqlite_write",
                write_state,
                self.config.step_iterations
            )
            
            # Read benchmark
            workflow_id = str(uuid.uuid4())
            await adapter.save_state(workflow_id, {"status": "completed", "data": "test"})
            
            async def read_state():
                await adapter.load_state(workflow_id)
            
            await self.runner.run_async_benchmark(
                "sqlite_read",
                read_state,
                self.config.step_iterations
            )
            
            await adapter.close()
    
    async def benchmark_snapshot_sizes(self):
        """Benchmark snapshot operations with various sizes."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "snap_bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            for size in self.config.snapshot_sizes:
                data = {"payload": "x" * size}
                
                async def save_snapshot():
                    workflow_id = str(uuid.uuid4())
                    await adapter.save_state(workflow_id, data)
                
                await self.runner.run_async_benchmark(
                    f"snapshot_save_{size}b",
                    save_snapshot,
                    100,
                    metadata={"snapshot_size": size}
                )
            
            await adapter.close()
    
    async def benchmark_journal_writes(self):
        """Benchmark journal entry writes."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "journal_bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            workflow_id = str(uuid.uuid4())
            await adapter.save_state(workflow_id, {"status": "running"})
            
            async def append_journal():
                entry = {
                    "event_type": "step_completed",
                    "step_id": str(uuid.uuid4()),
                    "timestamp": "2024-01-01T00:00:00Z",
                    "data": {"result": "success"}
                }
                # Simulate journal append by updating state
                state = await adapter.load_state(workflow_id) or {}
                journal = state.get("journal", [])
                journal.append(entry)
                state["journal"] = journal
                await adapter.save_state(workflow_id, state)
            
            await self.runner.run_async_benchmark(
                "journal_append",
                append_journal,
                self.config.journal_entry_count
            )
            
            await adapter.close()
