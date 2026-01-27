from typing import Callable
from contd.sdk.errors import WorkflowInterrupted
from contd.core.engine import ExecutionEngine

class MockExecutionEngine(ExecutionEngine):
    def __init__(self):
        super().__init__()
        self._interrupt_at_step: int | None = None
    
    def set_interrupt_at(self, step_number: int):
        self._interrupt_at_step = step_number
    
    def check_interrupt(self, step_number: int):
        if self._interrupt_at_step is not None and step_number >= self._interrupt_at_step:
            raise WorkflowInterrupted(f"Interrupted at step {step_number} for testing")

class ContdTestCase:
    """Test harness for workflows"""
    
    def __init__(self):
        self.engine = MockExecutionEngine()
        # How to inject this engine into the Context?
        # Context uses ExecutionEngine.get_instance().
        # We need to override the singleton or dependency injection.
        # Simple hack: replace singleton
        ExecutionEngine._instance = self.engine
    
    def run_workflow(
        self,
        workflow_fn: Callable,
        *args,
        interrupt_at_step: int | None = None,
        **kwargs
    ):
        """
        Run workflow with optional interruption for testing resume.
        """
        
        if interrupt_at_step:
            self.engine.set_interrupt_at(interrupt_at_step)
        
        try:
            return workflow_fn(*args, **kwargs)
        except WorkflowInterrupted:
            return None
        except Exception as e:
            raise e
