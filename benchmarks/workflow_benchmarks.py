"""Workflow execution benchmarks."""
import asyncio
import uuid
from typing import Any

import httpx

from .config import BenchmarkConfig
from .runner import BenchmarkRunner


class WorkflowBenchmarks:
    """Benchmarks for workflow operations."""
    
    def __init__(self, config: BenchmarkConfig, runner: BenchmarkRunner):
        self.config = config
        self.runner = runner
        self.client: httpx.AsyncClient | None = None
    
    async def setup(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(base_url=self.config.api_url, timeout=30.0)
    
    async def teardown(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
    
    async def run_all(self):
        """Run all workflow benchmarks."""
        await self.setup()
        try:
            await self.benchmark_workflow_creation()
            await self.benchmark_step_execution()
            await self.benchmark_concurrent_workflows()
            await self.benchmark_workflow_status()
            await self.benchmark_workflow_completion()
        finally:
            await self.teardown()
    
    async def benchmark_workflow_creation(self):
        """Benchmark workflow creation."""
        async def create_workflow():
            workflow_id = str(uuid.uuid4())
            response = await self.client.post(
                "/api/v1/workflows",
                json={
                    "workflow_id": workflow_id,
                    "name": "benchmark_workflow",
                    "input": {"data": "test"}
                }
            )
            response.raise_for_status()
            return workflow_id
        
        await self.runner.run_async_benchmark(
            "workflow_creation",
            create_workflow,
            self.config.workflow_count
        )
    
    async def benchmark_step_execution(self):
        """Benchmark step execution with various payload sizes."""
        for payload_size in self.config.step_payload_sizes:
            payload = {"data": "x" * payload_size}
            
            async def execute_step():
                workflow_id = str(uuid.uuid4())
                # Create workflow
                await self.client.post(
                    "/api/v1/workflows",
                    json={"workflow_id": workflow_id, "name": "step_bench", "input": {}}
                )
                # Execute step
                response = await self.client.post(
                    f"/api/v1/workflows/{workflow_id}/steps",
                    json={
                        "step_id": str(uuid.uuid4()),
                        "name": "benchmark_step",
                        "result": payload
                    }
                )
                response.raise_for_status()
            
            await self.runner.run_async_benchmark(
                f"step_execution_{payload_size}b",
                execute_step,
                self.config.step_iterations // len(self.config.step_payload_sizes),
                metadata={"payload_size": payload_size}
            )
    
    async def benchmark_concurrent_workflows(self):
        """Benchmark concurrent workflow execution."""
        async def run_workflow():
            workflow_id = str(uuid.uuid4())
            await self.client.post(
                "/api/v1/workflows",
                json={"workflow_id": workflow_id, "name": "concurrent_bench", "input": {}}
            )
            for i in range(self.config.steps_per_workflow):
                await self.client.post(
                    f"/api/v1/workflows/{workflow_id}/steps",
                    json={
                        "step_id": str(uuid.uuid4()),
                        "name": f"step_{i}",
                        "result": {"step": i}
                    }
                )
            await self.client.post(f"/api/v1/workflows/{workflow_id}/complete")
        
        await self.runner.run_concurrent_benchmark(
            "concurrent_workflows",
            run_workflow,
            self.config.workflow_count,
            self.config.concurrent_workflows
        )
    
    async def benchmark_workflow_status(self):
        """Benchmark workflow status queries."""
        # Create a workflow first
        workflow_id = str(uuid.uuid4())
        await self.client.post(
            "/api/v1/workflows",
            json={"workflow_id": workflow_id, "name": "status_bench", "input": {}}
        )
        
        async def get_status():
            response = await self.client.get(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
        
        await self.runner.run_async_benchmark(
            "workflow_status_query",
            get_status,
            self.config.step_iterations
        )
    
    async def benchmark_workflow_completion(self):
        """Benchmark full workflow lifecycle."""
        async def complete_workflow():
            workflow_id = str(uuid.uuid4())
            
            # Create
            await self.client.post(
                "/api/v1/workflows",
                json={"workflow_id": workflow_id, "name": "lifecycle_bench", "input": {"test": True}}
            )
            
            # Execute steps
            for i in range(5):
                await self.client.post(
                    f"/api/v1/workflows/{workflow_id}/steps",
                    json={
                        "step_id": str(uuid.uuid4()),
                        "name": f"step_{i}",
                        "result": {"iteration": i}
                    }
                )
            
            # Complete
            await self.client.post(
                f"/api/v1/workflows/{workflow_id}/complete",
                json={"output": {"success": True}}
            )
        
        await self.runner.run_async_benchmark(
            "workflow_full_lifecycle",
            complete_workflow,
            self.config.workflow_count
        )
