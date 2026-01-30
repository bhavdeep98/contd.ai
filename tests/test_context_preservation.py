"""
Tests for context preservation features.

Tests the annotate(), ingest(), distill cycle, health tracking,
and context restoration.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from contd.core.context_preservation import (
    ContextHealth,
    ReasoningBuffer,
    RestoredContext,
    HealthTracker,
    execute_distill,
)
from contd.models.events import (
    AnnotationCreatedEvent,
    ReasoningIngestedEvent,
    ContextDigestCreatedEvent,
    EventType,
)


class TestReasoningBuffer:
    """Tests for the reasoning buffer."""

    def test_empty_buffer(self):
        buffer = ReasoningBuffer()
        assert len(buffer) == 0
        assert buffer.total_chars == 0

    def test_add_chunks(self):
        buffer = ReasoningBuffer()
        buffer.add("First chunk of reasoning")
        buffer.add("Second chunk")
        
        assert len(buffer) == 2
        assert buffer.total_chars == len("First chunk of reasoning") + len("Second chunk")

    def test_clear_returns_chunks(self):
        buffer = ReasoningBuffer()
        buffer.add("chunk1")
        buffer.add("chunk2")
        
        chunks = buffer.clear()
        
        assert chunks == ["chunk1", "chunk2"]
        assert len(buffer) == 0
        assert buffer.total_chars == 0

    def test_empty_chunk_ignored(self):
        buffer = ReasoningBuffer()
        buffer.add("")
        # Empty string still gets added (developer's choice to filter)
        assert len(buffer) == 1


class TestHealthTracker:
    """Tests for health signal tracking."""

    def test_initial_state(self):
        tracker = HealthTracker()
        buffer = ReasoningBuffer()
        
        health = tracker.compute_health(buffer, 0, None, 0)
        
        assert health.output_trend == "stable"
        assert health.duration_trend == "stable"
        assert health.retry_rate == 0.0
        assert health.budget_used == 0.0

    def test_record_step(self):
        tracker = HealthTracker()
        tracker.record_step(output_size=100, duration_ms=50)
        tracker.record_step(output_size=150, duration_ms=60)
        
        assert tracker.total_steps == 2
        assert tracker.total_output_bytes == 250
        assert len(tracker.output_sizes) == 2

    def test_retry_tracking(self):
        tracker = HealthTracker()
        tracker.record_step(100, 50, was_retry=False)
        tracker.record_step(100, 50, was_retry=True)
        tracker.record_step(100, 50, was_retry=False)
        
        buffer = ReasoningBuffer()
        health = tracker.compute_health(buffer, 0, None, 3)
        
        assert health.retry_count == 1
        assert health.retry_rate == pytest.approx(1/3)

    def test_budget_tracking(self):
        tracker = HealthTracker(context_budget=1000)
        tracker.record_step(output_size=800, duration_ms=50)
        
        buffer = ReasoningBuffer()
        health = tracker.compute_health(buffer, 0, None, 1)
        
        assert health.budget_used == 0.8
        assert health.budget_limit == 1000

    def test_declining_trend(self):
        tracker = HealthTracker()
        # Simulate declining output sizes
        for size in [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]:
            tracker.record_step(output_size=size, duration_ms=50)
        
        buffer = ReasoningBuffer()
        health = tracker.compute_health(buffer, 0, None, 10)
        
        assert health.output_trend == "declining"

    def test_increasing_trend(self):
        tracker = HealthTracker()
        # Simulate increasing output sizes
        for size in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            tracker.record_step(output_size=size, duration_ms=50)
        
        buffer = ReasoningBuffer()
        health = tracker.compute_health(buffer, 0, None, 10)
        
        assert health.output_trend == "increasing"

    def test_recommendation_distill_on_large_buffer(self):
        tracker = HealthTracker()
        buffer = ReasoningBuffer()
        # Add enough to exceed 5000 char threshold
        buffer.add("x" * 6000)
        
        health = tracker.compute_health(buffer, 0, None, 1)
        
        assert health.recommendation == "distill"

    def test_recommendation_savepoint_on_drift(self):
        tracker = HealthTracker()
        # High retry rate
        for _ in range(10):
            tracker.record_step(100, 50, was_retry=True)
        # Also need declining output for savepoint recommendation
        tracker.output_sizes = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
        
        buffer = ReasoningBuffer()
        health = tracker.compute_health(buffer, 0, None, 10)
        
        assert health.recommendation == "savepoint"


class TestExecuteDistill:
    """Tests for distill function execution."""

    def test_successful_distill(self):
        def my_distill(chunks, prev):
            return {"summary": "test", "chunks_count": len(chunks)}
        
        result = execute_distill(my_distill, ["chunk1", "chunk2"], None)
        
        assert result == {"summary": "test", "chunks_count": 2}

    def test_distill_with_previous(self):
        def my_distill(chunks, prev):
            return {"prev_summary": prev.get("summary") if prev else None}
        
        result = execute_distill(
            my_distill, 
            ["chunk"], 
            {"summary": "previous"}
        )
        
        assert result == {"prev_summary": "previous"}

    def test_distill_failure_returns_fallback(self):
        def failing_distill(chunks, prev):
            raise ValueError("Distill failed!")
        
        result = execute_distill(failing_distill, ["chunk1", "chunk2"], None)
        
        assert result["_distill_failed"] is True
        assert result["raw_chunks"] == ["chunk1", "chunk2"]
        assert "Distill failed!" in result["error"]
        assert "traceback" in result


class TestRestoredContext:
    """Tests for restored context structure."""

    def test_empty_context(self):
        ctx = RestoredContext()
        
        assert ctx.digest is None
        assert ctx.undigested == []
        assert ctx.annotations == []
        assert ctx.digest_history == []
        assert ctx.savepoints == []
        assert ctx.steps_completed == 0

    def test_to_dict(self):
        ctx = RestoredContext(
            digest={"goal": "test"},
            annotations=[{"step": 1, "text": "note"}],
            steps_completed=5,
        )
        
        d = ctx.to_dict()
        
        assert d["digest"] == {"goal": "test"}
        assert d["annotations"] == [{"step": 1, "text": "note"}]
        assert d["steps_completed"] == 5


class TestContextEvents:
    """Tests for context preservation events."""

    def test_annotation_event(self):
        event = AnnotationCreatedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=5,
            step_name="analyze_data",
            text="Chose regression because data is tabular",
        )
        
        assert event.event_type == EventType.ANNOTATION_CREATED
        assert event.step_number == 5
        assert "regression" in event.text

    def test_reasoning_ingested_event(self):
        event = ReasoningIngestedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=3,
            chunk="Thinking about approach X...",
            chunk_size=28,
        )
        
        assert event.event_type == EventType.REASONING_INGESTED
        assert event.chunk_size == 28

    def test_context_digest_event(self):
        event = ContextDigestCreatedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=10,
            digest={"goal": "Find optimal architecture"},
            chunks_processed=5,
            distill_failed=False,
        )
        
        assert event.event_type == EventType.CONTEXT_DIGEST_CREATED
        assert event.digest["goal"] == "Find optimal architecture"
        assert event.chunks_processed == 5

    def test_failed_digest_event(self):
        event = ContextDigestCreatedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=10,
            digest={},
            chunks_processed=5,
            distill_failed=True,
            error="TimeoutError",
            raw_chunks=["chunk1", "chunk2"],
        )
        
        assert event.distill_failed is True
        assert event.error == "TimeoutError"
        assert event.raw_chunks == ["chunk1", "chunk2"]


class TestContextHealth:
    """Tests for ContextHealth dataclass."""

    def test_to_dict(self):
        health = ContextHealth(
            output_trend="declining",
            retry_rate=0.15,
            budget_used=0.7,
            recommendation="distill",
        )
        
        d = health.to_dict()
        
        assert d["output_trend"] == "declining"
        assert d["retry_rate"] == 0.15
        assert d["budget_used"] == 0.7
        assert d["recommendation"] == "distill"


class TestRecipes:
    """Tests for the recipe functions."""

    def test_distill_on_decline(self):
        from contd.sdk.recipes import distill_on_decline
        
        ctx = MagicMock()
        health = ContextHealth(
            output_trend="declining",
            reasoning_buffer_size=5,
        )
        
        distill_on_decline(ctx, health)
        
        ctx.request_distill.assert_called_once()

    def test_distill_on_decline_no_action_when_stable(self):
        from contd.sdk.recipes import distill_on_decline
        
        ctx = MagicMock()
        health = ContextHealth(
            output_trend="stable",
            reasoning_buffer_size=5,
        )
        
        distill_on_decline(ctx, health)
        
        ctx.request_distill.assert_not_called()

    def test_warn_on_budget(self):
        from contd.sdk.recipes import warn_on_budget
        
        ctx = MagicMock()
        health = ContextHealth(
            budget_used=0.85,
            total_output_bytes=42500,
            budget_limit=50000,
        )
        
        with patch("contd.sdk.recipes.logger") as mock_logger:
            warn_on_budget(ctx, health)
            mock_logger.warning.assert_called_once()

    def test_simple_distill(self):
        from contd.sdk.recipes import simple_distill
        
        result = simple_distill(
            ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
            {"total_chunks_seen": 10}
        )
        
        assert result["raw_recent"] == ["chunk3", "chunk4", "chunk5"]
        assert result["total_chunks_seen"] == 15
