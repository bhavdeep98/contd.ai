"""
Contd SDK Testing Utilities

Provides test harnesses and mocks for testing workflows
without requiring real infrastructure.
"""

from typing import Callable, Optional, Any, List, Type
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

from contd.sdk.errors import WorkflowInterrupted
from contd.core.engine import ExecutionEngine, EngineConfig
from contd.models.state import WorkflowState
from contd.models.events import BaseEvent


@dataclass
class StepExecution:
    """Record of a step execution during testing."""

    step_name: str
    step_id: str
    attempt: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    result: Any = None
    error: Optional[str] = None
    was_cached: bool = False


@dataclass
class WorkflowExecution:
    """Record of a workflow execution during testing."""

    workflow_id: str
    workflow_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    steps: List[StepExecution] = field(default_factory=list)
    final_state: Optional[WorkflowState] = None
    error: Optional[str] = None
    interrupted_at_step: Optional[int] = None


class MockExecutionEngine(ExecutionEngine):
    """
    Mock execution engine for testing.

    Provides:
    - In-memory storage (no real DB/S3)
    - Step interception for testing resume
    - Event recording for assertions
    - Configurable failure injection
    """

    def __init__(self):
        # Use mock config
        config = EngineConfig(use_mocks=True)
        super().__init__(config)

        self._interrupt_at_step: Optional[int] = None
        self._fail_at_step: Optional[int] = None
        self._fail_with: Optional[Type[Exception]] = None
        self._recorded_events: List[BaseEvent] = []
        self._step_counter = 0
        self._workflow_id: Optional[str] = None

    def set_interrupt_at(self, step_number: int):
        """Configure interruption at specific step (for testing resume)."""
        self._interrupt_at_step = step_number

    def set_fail_at(
        self, step_number: int, exception_type: Type[Exception] = Exception
    ):
        """Configure failure injection at specific step."""
        self._fail_at_step = step_number
        self._fail_with = exception_type

    def check_interrupt(self, step_number: int, workflow_id: str):
        """Check if workflow should be interrupted (called by step decorator)."""
        if (
            self._interrupt_at_step is not None
            and step_number >= self._interrupt_at_step
        ):
            raise WorkflowInterrupted(workflow_id, step_number)

    def check_failure(self, step_number: int):
        """Check if failure should be injected."""
        if self._fail_at_step is not None and step_number == self._fail_at_step:
            raise (self._fail_with or Exception)(
                f"Injected failure at step {step_number}"
            )

    def record_event(self, event: BaseEvent):
        """Record event for later assertions."""
        self._recorded_events.append(event)

    def get_recorded_events(self) -> List[BaseEvent]:
        """Get all recorded events."""
        return self._recorded_events.copy()

    def clear_recorded_events(self):
        """Clear recorded events."""
        self._recorded_events.clear()

    def reset(self):
        """Reset all mock state."""
        self._interrupt_at_step = None
        self._fail_at_step = None
        self._fail_with = None
        self._recorded_events.clear()
        self._step_counter = 0
        self._workflow_id = None


class ContdTestCase:
    """
    Test harness for workflow testing.

    Provides utilities for:
    - Running workflows with mock infrastructure
    - Simulating interruptions and failures
    - Testing resume behavior
    - Asserting on workflow state and events

    Example:
        >>> class TestMyWorkflow(ContdTestCase):
        ...     def test_basic_execution(self):
        ...         result = self.run_workflow(my_workflow, input_data={"x": 1})
        ...         self.assert_completed()
        ...         self.assert_step_count(3)
        ...
        ...     def test_resume_after_interrupt(self):
        ...         # First run - interrupt at step 2
        ...         self.run_workflow(my_workflow, interrupt_at_step=2)
        ...         self.assert_interrupted()
        ...
        ...         # Resume - should complete
        ...         self.resume_workflow()
        ...         self.assert_completed()
    """

    def __init__(self):
        self.engine = MockExecutionEngine()
        self._original_instance = ExecutionEngine._instance
        ExecutionEngine._instance = self.engine

        self.executions: List[WorkflowExecution] = []
        self.current_execution: Optional[WorkflowExecution] = None

    def setUp(self):
        """Set up test fixtures. Call in test setUp method."""
        self.engine.reset()
        self.executions.clear()
        self.current_execution = None
        ExecutionEngine._instance = self.engine

    def tearDown(self):
        """Tear down test fixtures. Call in test tearDown method."""
        ExecutionEngine._instance = self._original_instance

    def run_workflow(
        self,
        workflow_fn: Callable,
        *args,
        interrupt_at_step: Optional[int] = None,
        fail_at_step: Optional[int] = None,
        fail_with: Optional[Type[Exception]] = None,
        **kwargs,
    ) -> Optional[Any]:
        """
        Run a workflow with optional interruption or failure injection.

        Args:
            workflow_fn: The @workflow decorated function
            *args: Positional arguments for the workflow
            interrupt_at_step: Step number to interrupt at (for testing resume)
            fail_at_step: Step number to inject failure at
            fail_with: Exception type to raise at fail_at_step
            **kwargs: Keyword arguments for the workflow

        Returns:
            Workflow result if completed, None if interrupted
        """
        # Configure mock engine
        if interrupt_at_step is not None:
            self.engine.set_interrupt_at(interrupt_at_step)
        if fail_at_step is not None:
            self.engine.set_fail_at(fail_at_step, fail_with or Exception)

        # Create execution record
        execution = WorkflowExecution(
            workflow_id="",  # Will be set by workflow
            workflow_name=workflow_fn.__name__,
            started_at=datetime.utcnow(),
        )
        self.current_execution = execution
        self.executions.append(execution)

        try:
            result = workflow_fn(*args, **kwargs)
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            return result

        except WorkflowInterrupted as e:
            execution.status = "interrupted"
            execution.interrupted_at_step = e.details.get("interrupted_at_step")
            return None

        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            raise

    def resume_workflow(
        self,
        workflow_fn: Optional[Callable] = None,
        workflow_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """
        Resume an interrupted workflow.

        Args:
            workflow_fn: The workflow function (uses last if not provided)
            workflow_id: Specific workflow ID to resume
            *args, **kwargs: Arguments for the workflow

        Returns:
            Workflow result if completed
        """
        # Clear interrupt setting for resume
        self.engine._interrupt_at_step = None

        if workflow_fn is None and self.current_execution:
            # Try to get workflow from registry
            from contd.sdk.registry import WorkflowRegistry

            workflow_fn = WorkflowRegistry.get(self.current_execution.workflow_name)

        if workflow_fn is None:
            raise ValueError("No workflow function provided and none found in registry")

        return self.run_workflow(workflow_fn, *args, **kwargs)

    # ========================================================================
    # Assertions
    # ========================================================================

    def assert_completed(self, message: str = ""):
        """Assert that the last workflow completed successfully."""
        if not self.current_execution:
            raise AssertionError("No workflow execution to check")
        if self.current_execution.status != "completed":
            raise AssertionError(
                f"Workflow not completed: status={self.current_execution.status}. {message}"
            )

    def assert_interrupted(self, at_step: Optional[int] = None, message: str = ""):
        """Assert that the last workflow was interrupted."""
        if not self.current_execution:
            raise AssertionError("No workflow execution to check")
        if self.current_execution.status != "interrupted":
            raise AssertionError(
                f"Workflow not interrupted: status={self.current_execution.status}. {message}"
            )
        if (
            at_step is not None
            and self.current_execution.interrupted_at_step != at_step
        ):
            raise AssertionError(
                f"Interrupted at wrong step: expected={at_step}, "
                f"actual={self.current_execution.interrupted_at_step}. {message}"
            )

    def assert_failed(self, error_contains: Optional[str] = None, message: str = ""):
        """Assert that the last workflow failed."""
        if not self.current_execution:
            raise AssertionError("No workflow execution to check")
        if self.current_execution.status != "failed":
            raise AssertionError(
                f"Workflow not failed: status={self.current_execution.status}. {message}"
            )
        if error_contains and error_contains not in (
            self.current_execution.error or ""
        ):
            raise AssertionError(
                f"Error message doesn't contain '{error_contains}': "
                f"actual='{self.current_execution.error}'. {message}"
            )

    def assert_step_count(self, expected: int, message: str = ""):
        """Assert the number of steps executed."""
        if not self.current_execution:
            raise AssertionError("No workflow execution to check")
        actual = len(self.current_execution.steps)
        if actual != expected:
            raise AssertionError(
                f"Step count mismatch: expected={expected}, actual={actual}. {message}"
            )

    def assert_event_count(
        self, expected: int, event_type: Optional[str] = None, message: str = ""
    ):
        """Assert the number of events recorded."""
        events = self.engine.get_recorded_events()
        if event_type:
            events = [e for e in events if getattr(e, "event_type", None) == event_type]
        actual = len(events)
        if actual != expected:
            raise AssertionError(
                f"Event count mismatch: expected={expected}, actual={actual}. {message}"
            )

    def assert_state_contains(self, key: str, value: Any = None, message: str = ""):
        """Assert that final state contains a key (and optionally value)."""
        if not self.current_execution or not self.current_execution.final_state:
            raise AssertionError("No final state to check")

        state_vars = self.current_execution.final_state.variables
        if key not in state_vars:
            raise AssertionError(f"State missing key '{key}'. {message}")
        if value is not None and state_vars[key] != value:
            raise AssertionError(
                f"State value mismatch for '{key}': expected={value}, "
                f"actual={state_vars[key]}. {message}"
            )

    # ========================================================================
    # Utilities
    # ========================================================================

    def get_events(self, event_type: Optional[str] = None) -> List[BaseEvent]:
        """Get recorded events, optionally filtered by type."""
        events = self.engine.get_recorded_events()
        if event_type:
            events = [e for e in events if getattr(e, "event_type", None) == event_type]
        return events

    def get_final_state(self) -> Optional[WorkflowState]:
        """Get the final state of the last execution."""
        return self.current_execution.final_state if self.current_execution else None

    def print_execution_summary(self):
        """Print a summary of the last execution (for debugging)."""
        if not self.current_execution:
            print("No execution to summarize")
            return

        ex = self.current_execution
        print(f"\n{'='*50}")
        print(f"Workflow: {ex.workflow_name}")
        print(f"Status: {ex.status}")
        print(f"Steps: {len(ex.steps)}")
        if ex.interrupted_at_step:
            print(f"Interrupted at: step {ex.interrupted_at_step}")
        if ex.error:
            print(f"Error: {ex.error}")
        print(f"Events recorded: {len(self.engine.get_recorded_events())}")
        print(f"{'='*50}\n")


@contextmanager
def mock_workflow_context():
    """
    Context manager for running workflows with mock infrastructure.

    Example:
        >>> with mock_workflow_context() as ctx:
        ...     result = my_workflow(input_data)
        ...     assert ctx.engine.get_recorded_events()
    """
    test_case = ContdTestCase()
    test_case.setUp()
    try:
        yield test_case
    finally:
        test_case.tearDown()


class WorkflowTestBuilder:
    """
    Fluent builder for workflow tests.

    Example:
        >>> (WorkflowTestBuilder(my_workflow)
        ...     .with_input(x=1, y=2)
        ...     .interrupt_at(step=3)
        ...     .run()
        ...     .assert_interrupted()
        ...     .resume()
        ...     .assert_completed())
    """

    def __init__(self, workflow_fn: Callable):
        self.workflow_fn = workflow_fn
        self.test_case = ContdTestCase()
        self.test_case.setUp()
        self._args = ()
        self._kwargs = {}
        self._interrupt_at: Optional[int] = None
        self._fail_at: Optional[int] = None
        self._fail_with: Optional[Type[Exception]] = None

    def with_input(self, *args, **kwargs) -> "WorkflowTestBuilder":
        """Set workflow input arguments."""
        self._args = args
        self._kwargs = kwargs
        return self

    def interrupt_at(self, step: int) -> "WorkflowTestBuilder":
        """Configure interruption at step."""
        self._interrupt_at = step
        return self

    def fail_at(
        self, step: int, exception: Type[Exception] = Exception
    ) -> "WorkflowTestBuilder":
        """Configure failure injection at step."""
        self._fail_at = step
        self._fail_with = exception
        return self

    def run(self) -> "WorkflowTestBuilder":
        """Execute the workflow."""
        self.test_case.run_workflow(
            self.workflow_fn,
            *self._args,
            interrupt_at_step=self._interrupt_at,
            fail_at_step=self._fail_at,
            fail_with=self._fail_with,
            **self._kwargs,
        )
        # Reset for potential resume
        self._interrupt_at = None
        self._fail_at = None
        return self

    def resume(self) -> "WorkflowTestBuilder":
        """Resume the workflow."""
        self.test_case.resume_workflow(self.workflow_fn, *self._args, **self._kwargs)
        return self

    def assert_completed(self) -> "WorkflowTestBuilder":
        """Assert workflow completed."""
        self.test_case.assert_completed()
        return self

    def assert_interrupted(
        self, at_step: Optional[int] = None
    ) -> "WorkflowTestBuilder":
        """Assert workflow was interrupted."""
        self.test_case.assert_interrupted(at_step)
        return self

    def assert_failed(
        self, error_contains: Optional[str] = None
    ) -> "WorkflowTestBuilder":
        """Assert workflow failed."""
        self.test_case.assert_failed(error_contains)
        return self

    def cleanup(self):
        """Clean up test resources."""
        self.test_case.tearDown()
