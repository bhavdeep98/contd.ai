"""
Tests for context preservation features.

Tests the annotate(), ingest(), distill cycle, health tracking,
and context restoration.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from contd.context import (
    ContextHealth,
    HealthSignals,
    ReasoningLedger,
    ContextEntry,
    ContextDigest,
)
from contd.context.ledger import StepSignal
from contd.models.events import (
    ContextAnnotatedEvent,
    ContextIngestedEvent,
    ContextDigestedEvent,
    EventType,
)


class TestReasoningLedger:
    """Tests for the reasoning ledger."""

    def test_empty_ledger(self):
        ledger = ReasoningLedger()
        assert len(ledger.raw_buffer) == 0
        assert ledger.raw_buffer_bytes == 0
        assert len(ledger.annotations) == 0
        assert len(ledger.digests) == 0

    def test_ingest_chunks(self):
        ledger = ReasoningLedger()
        ledger.ingest("First chunk of reasoning")
        ledger.ingest("Second chunk")
        
        assert len(ledger.raw_buffer) == 2
        assert ledger.raw_buffer_bytes > 0

    def test_annotate(self):
        ledger = ReasoningLedger()
        ledger.annotate(1, "step_1", "Chose regression because data is tabular")
        
        assert len(ledger.annotations) == 1
        assert ledger.annotations[0].text == "Chose regression because data is tabular"
        assert ledger.annotations[0].step_number == 1

    def test_accept_digest_clears_buffer(self):
        ledger = ReasoningLedger()
        ledger.ingest("chunk1")
        ledger.ingest("chunk2")
        
        digest = ContextDigest(
            digest_id="test-id",
            step_number=5,
            timestamp=datetime.utcnow(),
            payload={"summary": "test"},
            raw_chunk_count=2,
            raw_byte_count=12,
        )
        ledger.accept_digest(digest)
        
        assert len(ledger.raw_buffer) == 0
        assert ledger.raw_buffer_bytes == 0
        assert len(ledger.digests) == 1

    def test_should_distill_by_steps(self):
        ledger = ReasoningLedger()
        ledger.distill_every = 3
        ledger.ingest("chunk")
        
        # Not enough steps yet
        ledger._steps_since_distill = 2
        assert not ledger.should_distill()
        
        # Now enough steps
        ledger._steps_since_distill = 3
        assert ledger.should_distill()

    def test_should_distill_by_threshold(self):
        ledger = ReasoningLedger()
        ledger.distill_threshold = 100
        
        # Not enough bytes
        ledger.ingest("small")
        assert not ledger.should_distill()
        
        # Now enough bytes
        ledger.ingest("x" * 100)
        assert ledger.should_distill()

    def test_get_restore_context(self):
        ledger = ReasoningLedger()
        ledger.annotate(1, "step_1", "note 1")
        ledger.ingest("reasoning chunk")
        
        ctx = ledger.get_restore_context()
        
        assert ctx["digest"] is None
        assert len(ctx["annotations"]) == 1
        assert len(ctx["undigested"]) == 1


class TestContextHealth:
    """Tests for health signal computation."""

    def test_insufficient_signals(self):
        """Health returns unknown when not enough data."""
        signals = [
            StepSignal(1, "step_1", 100, 50, False, datetime.utcnow()),
        ]
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=0,
            total_context_bytes=100,
            context_budget=1000,
            steps_since_distill=1,
        )
        
        assert health.output_trend == "unknown"
        assert health.recommendation == "ok"

    def test_declining_output_trend(self):
        """Detect declining output sizes."""
        signals = []
        # Older signals with higher output
        for i in range(5):
            signals.append(
                StepSignal(i, f"step_{i}", 1000, 50, False, datetime.utcnow())
            )
        # Recent signals with lower output
        for i in range(5, 10):
            signals.append(
                StepSignal(i, f"step_{i}", 500, 50, False, datetime.utcnow())
            )
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=0,
            total_context_bytes=7500,
            context_budget=10000,
            steps_since_distill=10,
        )
        
        assert health.output_trend == "declining"

    def test_retry_rate_calculation(self):
        """Calculate retry rate from recent signals."""
        signals = []
        for i in range(10):
            was_retry = i >= 8  # Last 2 are retries
            signals.append(
                StepSignal(i, f"step_{i}", 100, 50, was_retry, datetime.utcnow())
            )
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=0,
            total_context_bytes=1000,
            context_budget=0,
            steps_since_distill=10,
        )
        
        # Window is 5, so 2 retries in last 5 = 40%
        assert health.retry_rate == pytest.approx(0.4)

    def test_budget_usage(self):
        """Calculate budget usage percentage."""
        signals = [
            StepSignal(i, f"step_{i}", 100, 50, False, datetime.utcnow())
            for i in range(5)
        ]
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=0,
            total_context_bytes=800,
            context_budget=1000,
            steps_since_distill=5,
        )
        
        assert health.budget_used == pytest.approx(0.8)

    def test_recommendation_warning_on_high_budget(self):
        """Recommend warning when budget > 90%."""
        signals = [
            StepSignal(i, f"step_{i}", 100, 50, False, datetime.utcnow())
            for i in range(5)
        ]
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=0,
            total_context_bytes=950,
            context_budget=1000,
            steps_since_distill=5,
        )
        
        assert health.recommendation == "warning"

    def test_recommendation_distill_on_buffer(self):
        """Recommend distill when buffer has data and steps since distill > 3."""
        signals = [
            StepSignal(i, f"step_{i}", 100, 50, False, datetime.utcnow())
            for i in range(5)
        ]
        
        health = ContextHealth.compute(
            signals=signals,
            buffer_bytes=1000,
            total_context_bytes=500,
            context_budget=10000,
            steps_since_distill=5,
        )
        
        assert health.recommendation == "distill"


class TestHealthSignals:
    """Tests for HealthSignals dataclass."""

    def test_to_dict(self):
        health = HealthSignals(
            output_trend="declining",
            output_decline_pct=-0.25,
            retry_rate=0.15,
            duration_trend="normal",
            duration_spike_factor=1.2,
            budget_used=0.7,
            steps_since_distill=5,
            buffer_bytes=1000,
            recommendation="distill",
        )
        
        d = health.to_dict()
        
        assert d["output_trend"] == "declining"
        assert d["output_decline_pct"] == -0.25
        assert d["retry_rate"] == 0.15
        assert d["recommendation"] == "distill"


class TestContextEvents:
    """Tests for context preservation events."""

    def test_annotation_event(self):
        event = ContextAnnotatedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=5,
            step_name="analyze_data",
            text="Chose regression because data is tabular",
        )
        
        assert event.event_type == EventType.CONTEXT_ANNOTATED
        assert event.step_number == 5
        assert "regression" in event.text

    def test_context_ingested_event(self):
        event = ContextIngestedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            step_number=3,
            step_name="think",
            chunk_bytes=1024,
            storage_ref="",
        )
        
        assert event.event_type == EventType.CONTEXT_INGESTED
        assert event.chunk_bytes == 1024

    def test_context_digested_event(self):
        event = ContextDigestedEvent(
            event_id="test-id",
            workflow_id="wf-123",
            org_id="default",
            timestamp=datetime.utcnow(),
            digest_id="digest-123",
            step_number=10,
            payload={"goal": "Find optimal architecture"},
            raw_chunk_count=5,
            raw_byte_count=2048,
        )
        
        assert event.event_type == EventType.CONTEXT_DIGESTED
        assert event.payload["goal"] == "Find optimal architecture"
        assert event.raw_chunk_count == 5


class TestRecipes:
    """Tests for the recipe functions."""

    def test_distill_on_decline(self):
        from contd.sdk.recipes import distill_on_decline
        
        ctx = MagicMock()
        health = HealthSignals(
            output_trend="declining",
            output_decline_pct=-0.3,
            retry_rate=0.0,
            duration_trend="normal",
            duration_spike_factor=1.0,
            budget_used=0.5,
            steps_since_distill=5,
            buffer_bytes=1000,
            recommendation="distill",
        )
        
        distill_on_decline(ctx, health)
        
        ctx.request_distill.assert_called_once()

    def test_distill_on_decline_no_action_when_stable(self):
        from contd.sdk.recipes import distill_on_decline
        
        ctx = MagicMock()
        health = HealthSignals(
            output_trend="stable",
            output_decline_pct=0.0,
            retry_rate=0.0,
            duration_trend="normal",
            duration_spike_factor=1.0,
            budget_used=0.5,
            steps_since_distill=5,
            buffer_bytes=1000,
            recommendation="ok",
        )
        
        distill_on_decline(ctx, health)
        
        ctx.request_distill.assert_not_called()

    def test_warn_on_budget(self):
        from contd.sdk.recipes import warn_on_budget
        
        ctx = MagicMock()
        health = HealthSignals(
            output_trend="stable",
            output_decline_pct=0.0,
            retry_rate=0.0,
            duration_trend="normal",
            duration_spike_factor=1.0,
            budget_used=0.85,
            steps_since_distill=5,
            buffer_bytes=0,
            recommendation="distill",
        )
        
        with patch("contd.sdk.recipes.logger") as mock_logger:
            warn_on_budget(ctx, health)
            mock_logger.warning.assert_called_once()
            ctx.set_variable.assert_called()

    def test_savepoint_on_drift(self):
        from contd.sdk.recipes import savepoint_on_drift
        
        ctx = MagicMock()
        health = HealthSignals(
            output_trend="declining",
            output_decline_pct=-0.3,
            retry_rate=0.25,
            duration_trend="spiking",
            duration_spike_factor=2.5,
            budget_used=0.5,
            steps_since_distill=5,
            buffer_bytes=1000,
            recommendation="savepoint",
        )
        
        savepoint_on_drift(ctx, health)
        
        ctx.create_savepoint.assert_called_once()
        ctx.request_distill.assert_called_once()

    def test_simple_distill(self):
        from contd.sdk.recipes import simple_distill
        
        result = simple_distill(
            ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
            {"total_chunks_seen": 10}
        )
        
        assert result["raw_recent"] == ["chunk3", "chunk4", "chunk5"]
        assert result["total_chunks_seen"] == 15

    def test_combined_health_handler(self):
        from contd.sdk.recipes import combined_health_handler
        
        ctx = MagicMock()
        health = HealthSignals(
            output_trend="declining",
            output_decline_pct=-0.3,
            retry_rate=0.25,
            duration_trend="normal",
            duration_spike_factor=1.0,
            budget_used=0.85,
            steps_since_distill=5,
            buffer_bytes=1000,
            recommendation="warning",
        )
        
        with patch("contd.sdk.recipes.logger"):
            combined_health_handler(ctx, health)
        
        # Should trigger distill (declining), savepoint (retry rate), and warn (budget)
        ctx.request_distill.assert_called_once()
        ctx.create_savepoint.assert_called_once()
