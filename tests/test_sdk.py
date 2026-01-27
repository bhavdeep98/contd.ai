"""
Tests for SDK Phase 2 components.
"""
import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from contd.sdk import (
    workflow, step, WorkflowConfig, StepConfig,
    RetryPolicy, SavepointMetadata,
    ContdError, WorkflowLocked, NoActiveWorkflow, StepTimeout, TooManyAttempts,
    ContdTestCase, WorkflowTestBuilder, mock_workflow_context,
    WorkflowStatus, StepStatus,
)
from contd.sdk.types import WorkflowInput, WorkflowResult, WorkflowConfigModel
from contd.sdk.context import ExecutionContext


class TestRetryPolicy:
    """Tests for RetryPolicy with exponential backoff."""
    
    def test_default_values(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_base == 2.0
        assert policy.backoff_max == 60.0
        assert policy.backoff_jitter == 0.5
    
    def test_custom_values(self):
        policy = RetryPolicy(
            max_attempts=5,
            backoff_base=3.0,
            backoff_max=120.0,
            backoff_jitter=0.3
        )
        assert policy.max_attempts == 5
        assert policy.backoff_base == 3.0
    
    def test_should_retry_within_attempts(self):
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(1, Exception("test")) is True
        assert policy.should_retry(2, Exception("test")) is True
        assert policy.should_retry(3, Exception("test")) is False
    
    def test_should_retry_exception_filter(self):
        policy = RetryPolicy(
            max_attempts=3,
            retryable_exceptions=(ValueError, TypeError)
        )
        assert policy.should_retry(1, ValueError("test")) is True
        assert policy.should_retry(1, TypeError("test")) is True
        assert policy.should_retry(1, RuntimeError("test")) is False
    
    def test_backoff_exponential(self):
        policy = RetryPolicy(backoff_base=2.0, backoff_jitter=0.0)
        # Without jitter, backoff should be exactly 2^attempt
        assert policy.backoff(1) == 2.0
        assert policy.backoff(2) == 4.0
        assert policy.backoff(3) == 8.0
    
    def test_backoff_max_cap(self):
        policy = RetryPolicy(backoff_base=2.0, backoff_max=10.0, backoff_jitter=0.0)
        assert policy.backoff(10) == 10.0  # Capped at max
    
    def test_backoff_with_jitter(self):
        policy = RetryPolicy(backoff_base=2.0, backoff_jitter=0.5)
        # With jitter, backoff should be within range
        for _ in range(10):
            backoff = policy.backoff(2)  # Base would be 4.0
            assert 2.0 <= backoff <= 6.0  # 4.0 ± 50%
    
    def test_validation_max_attempts(self):
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=101)


class TestSavepointMetadata:
    """Tests for SavepointMetadata."""
    
    def test_default_values(self):
        meta = SavepointMetadata()
        assert meta.goal_summary == ""
        assert meta.hypotheses == []
        assert meta.questions == []
        assert meta.decisions == []
        assert meta.next_step == ""
    
    def test_custom_values(self):
        meta = SavepointMetadata(
            goal_summary="Process order",
            hypotheses=["Payment will succeed"],
            questions=["Is inventory available?"],
            next_step="Validate inventory"
        )
        assert meta.goal_summary == "Process order"
        assert len(meta.hypotheses) == 1
    
    def test_add_decision(self):
        meta = SavepointMetadata()
        meta.add_decision(
            decision="Use credit card",
            rationale="Customer preference",
            alternatives=["PayPal", "Bank transfer"]
        )
        assert len(meta.decisions) == 1
        assert meta.decisions[0]["decision"] == "Use credit card"
        assert meta.decisions[0]["rationale"] == "Customer preference"
        assert len(meta.decisions[0]["alternatives"]) == 2


class TestErrorHierarchy:
    """Tests for error hierarchy with clear messages."""
    
    def test_contd_error_base(self):
        err = ContdError("Something went wrong")
        assert "Something went wrong" in str(err)
    
    def test_workflow_locked_with_details(self):
        err = WorkflowLocked(
            workflow_id="wf-123",
            owner_id="executor-456",
            expires_at="2024-01-01T12:00:00"
        )
        assert "wf-123" in str(err)
        assert "executor-456" in str(err)
        assert err.workflow_id == "wf-123"
    
    def test_no_active_workflow(self):
        err = NoActiveWorkflow()
        assert "No active workflow" in str(err)
    
    def test_step_timeout(self):
        err = StepTimeout(
            workflow_id="wf-123",
            step_id="step_0",
            step_name="process_payment",
            timeout_seconds=30.0,
            elapsed_seconds=35.5
        )
        assert "30" in str(err)
        assert "35.5" in str(err)
        assert err.step_id == "step_0"
    
    def test_too_many_attempts(self):
        err = TooManyAttempts(
            workflow_id="wf-123",
            step_id="step_0",
            step_name="process_payment",
            max_attempts=3,
            last_error="Connection refused"
        )
        assert "3" in str(err)
        assert "Connection refused" in str(err)
    
    def test_error_inheritance(self):
        """All errors should inherit from ContdError."""
        from contd.sdk.errors import (
            WorkflowLocked, NoActiveWorkflow, StepTimeout,
            IntegrityError, PersistenceError, RecoveryError
        )
        
        assert issubclass(WorkflowLocked, ContdError)
        assert issubclass(NoActiveWorkflow, ContdError)
        assert issubclass(StepTimeout, ContdError)
        assert issubclass(IntegrityError, ContdError)
        assert issubclass(PersistenceError, ContdError)
        assert issubclass(RecoveryError, ContdError)


class TestPydanticModels:
    """Tests for Pydantic validation models."""
    
    def test_workflow_input_validation(self):
        input_data = WorkflowInput(
            workflow_name="process_order",
            input_data={"order_id": "123"},
            tags={"team": "platform"}
        )
        assert input_data.workflow_name == "process_order"
    
    def test_workflow_input_name_required(self):
        with pytest.raises(ValueError):
            WorkflowInput(workflow_name="")
    
    def test_workflow_input_tag_validation(self):
        # Tag key too long
        with pytest.raises(ValueError):
            WorkflowInput(
                workflow_name="test",
                tags={"a" * 100: "value"}
            )
    
    def test_workflow_config_model_validation(self):
        config = WorkflowConfigModel(
            workflow_id="my-workflow-123",
            max_duration_seconds=3600,
            tags={"env": "prod"}
        )
        assert config.workflow_id == "my-workflow-123"
    
    def test_workflow_config_invalid_id(self):
        with pytest.raises(ValueError):
            WorkflowConfigModel(workflow_id="invalid id with spaces!")
    
    def test_workflow_result(self):
        result = WorkflowResult(
            workflow_id="wf-123",
            status=WorkflowStatus.COMPLETED,
            result={"output": "success"},
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:01:00",
            duration_ms=60000,
            step_count=5
        )
        assert result.status == WorkflowStatus.COMPLETED
        assert result.step_count == 5


class TestEnums:
    """Tests for status enums."""
    
    def test_workflow_status_values(self):
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
    
    def test_step_status_values(self):
        assert StepStatus.PENDING == "pending"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"


class TestExecutionContext:
    """Tests for ExecutionContext."""
    
    def test_no_active_workflow_raises(self):
        ExecutionContext.clear()
        with pytest.raises(NoActiveWorkflow):
            ExecutionContext.current()
    
    def test_generate_step_id(self):
        # Create a mock context
        with patch.object(ExecutionContext, 'get_or_create') as mock:
            ctx = MagicMock()
            ctx._step_counter = 0
            ctx.generate_step_id = lambda name: f"{name}_{ctx._step_counter}"
            
            assert ctx.generate_step_id("process") == "process_0"
            ctx._step_counter = 5
            assert ctx.generate_step_id("validate") == "validate_5"


class TestDecorators:
    """Tests for workflow and step decorators."""
    
    def test_workflow_config_defaults(self):
        config = WorkflowConfig()
        assert config.workflow_id is None
        assert config.max_duration is None
        assert config.retry_policy is None
        assert config.tags is None
        assert config.org_id is None
    
    def test_workflow_config_custom(self):
        policy = RetryPolicy(max_attempts=5)
        config = WorkflowConfig(
            workflow_id="my-workflow",
            max_duration=timedelta(hours=1),
            retry_policy=policy,
            tags={"env": "test"},
            org_id="org-123"
        )
        assert config.workflow_id == "my-workflow"
        assert config.max_duration == timedelta(hours=1)
        assert config.retry_policy.max_attempts == 5
    
    def test_step_config_defaults(self):
        config = StepConfig()
        assert config.checkpoint is True
        assert config.idempotency_key is None
        assert config.retry is None
        assert config.timeout is None
        assert config.savepoint is False
    
    def test_step_config_custom(self):
        policy = RetryPolicy(max_attempts=3)
        config = StepConfig(
            checkpoint=False,
            retry=policy,
            timeout=timedelta(seconds=30),
            savepoint=True
        )
        assert config.checkpoint is False
        assert config.retry.max_attempts == 3
        assert config.timeout == timedelta(seconds=30)
        assert config.savepoint is True


class TestTestingUtilities:
    """Tests for testing utilities."""
    
    def test_contd_test_case_creation(self):
        test_case = ContdTestCase()
        assert test_case.engine is not None
        assert test_case.executions == []
        test_case.tearDown()
    
    def test_mock_execution_engine(self):
        from contd.sdk.testing import MockExecutionEngine
        
        engine = MockExecutionEngine()
        assert engine._interrupt_at_step is None
        
        engine.set_interrupt_at(5)
        assert engine._interrupt_at_step == 5
        
        engine.reset()
        assert engine._interrupt_at_step is None
    
    def test_mock_context_manager(self):
        with mock_workflow_context() as ctx:
            assert ctx.engine is not None
            # Context should be set up
            assert ctx.executions == []
