"""Recovery and replay benchmarks."""
import asyncio
import os
import tempfile
import uuid
from typing import Any

from .config import BenchmarkConfig
from .runner import BenchmarkRunner


class RecoveryBenchmarks:
    """Benchmarks for recovery operations."""
    
    def __init__(self, config: BenchmarkConfig, runner: BenchmarkRunner):
        self.config = config
        self.runner = runner
    
    async def run_all(self):
        """Run all recovery benchmarks."""
        await self.benchmark_state_recovery()
        await self.benchmark_journal_replay()
        await self.benchmark_savepoint_restore()
    
    async def benchmark_state_recovery(self):
        """Benchmark state recovery from persistence."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            print("SQLite adapter not available, skipping benchmark")
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "recovery_bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            # Create workflows with varying step counts
            workflow_ids = []
            for i in range(self.config.recovery_workflow_count):
                workflow_id = str(uuid.uuid4())
                workflow_ids.append(workflow_id)
                
                state = {
                    "workflow_id": workflow_id,
                    "status": "running",
                    "current_step": self.config.recovery_step_count - 1,
                    "steps": [
                        {
                            "step_id": str(uuid.uuid4()),
                            "name": f"step_{j}",
                            "status": "completed",
                            "result": {"data": f"result_{j}"}
                        }
                        for j in range(self.config.recovery_step_count)
                    ]
                }
                await adapter.save_state(workflow_id, state)
            
            # Benchmark recovery
            async def recover_workflow():
                workflow_id = workflow_ids[0]
                state = await adapter.load_state(workflow_id)
                # Simulate recovery processing
                if state:
                    _ = state.get("steps", [])
                    _ = state.get("current_step", 0)
            
            await self.runner.run_async_benchmark(
                "state_recovery",
                recover_workflow,
                self.config.step_iterations,
                metadata={"step_count": self.config.recovery_step_count}
            )
            
            await adapter.close()
    
    async def benchmark_journal_replay(self):
        """Benchmark journal replay performance."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "replay_bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            # Create workflow with journal entries
            workflow_id = str(uuid.uuid4())
            journal_entries = [
                {
                    "sequence": i,
                    "event_type": "step_completed",
                    "step_id": str(uuid.uuid4()),
                    "timestamp": f"2024-01-01T00:00:{i:02d}Z",
                    "data": {"result": f"result_{i}"}
                }
                for i in range(self.config.journal_entry_count)
            ]
            
            await adapter.save_state(workflow_id, {
                "workflow_id": workflow_id,
                "status": "running",
                "journal": journal_entries
            })
            
            # Benchmark replay
            async def replay_journal():
                state = await adapter.load_state(workflow_id)
                if state:
                    journal = state.get("journal", [])
                    # Simulate replay
                    reconstructed_state = {}
                    for entry in journal:
                        if entry["event_type"] == "step_completed":
                            reconstructed_state[entry["step_id"]] = entry["data"]
            
            await self.runner.run_async_benchmark(
                f"journal_replay_{self.config.journal_entry_count}_entries",
                replay_journal,
                100,
                metadata={"journal_entries": self.config.journal_entry_count}
            )
            
            await adapter.close()
    
    async def benchmark_savepoint_restore(self):
        """Benchmark savepoint restoration."""
        try:
            from contd.persistence.adapters.sqlite import SQLiteAdapter
        except ImportError:
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "savepoint_bench.db")
            adapter = SQLiteAdapter(db_path)
            await adapter.initialize()
            
            # Create workflow with savepoints
            workflow_id = str(uuid.uuid4())
            savepoints = {}
            
            for i in range(10):
                savepoint_id = f"savepoint_{i}"
                savepoints[savepoint_id] = {
                    "savepoint_id": savepoint_id,
                    "step_index": i * 5,
                    "state_snapshot": {
                        "completed_steps": list(range(i * 5)),
                        "data": {"checkpoint": i}
                    }
                }
            
            await adapter.save_state(workflow_id, {
                "workflow_id": workflow_id,
                "status": "running",
                "savepoints": savepoints
            })
            
            # Benchmark restore
            async def restore_savepoint():
                state = await adapter.load_state(workflow_id)
                if state:
                    savepoints = state.get("savepoints", {})
                    # Restore from middle savepoint
                    savepoint = savepoints.get("savepoint_5")
                    if savepoint:
                        _ = savepoint["state_snapshot"]
            
            await self.runner.run_async_benchmark(
                "savepoint_restore",
                restore_savepoint,
                self.config.step_iterations
            )
            
            await adapter.close()
