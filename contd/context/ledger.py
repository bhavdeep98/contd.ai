"""
Reasoning ledger for context rot prevention.

The ledger accumulates two kinds of reasoning data:
- Annotations: developer-supplied breadcrumbs (lightweight, always available)
- Ingested reasoning: raw reasoning tokens from the model (when available)

Periodically, the ingested reasoning is compressed via a developer-provided
distill function into a ContextDigest. The engine handles the plumbing
(buffering, triggering, storing, restoring). The developer brings the
intelligence (what to distill, how to compress).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single reasoning breadcrumb attached to a step."""

    step_number: int
    step_name: str
    timestamp: datetime
    text: str

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "timestamp": self.timestamp.isoformat(),
            "text": self.text,
        }

    @staticmethod
    def from_dict(d: dict) -> "ContextEntry":
        return ContextEntry(
            step_number=d["step_number"],
            step_name=d["step_name"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            text=d["text"],
        )


@dataclass
class ContextDigest:
    """
    Compressed reasoning context produced by the developer's distill function.

    The engine doesn't define what goes in here — the developer's distill
    function returns a dict, and the engine stores it. The structure below
    is just the envelope.
    """

    digest_id: str
    step_number: int  # Step at which distillation occurred
    timestamp: datetime
    payload: Dict[str, Any]  # Whatever the distill function returned
    raw_chunk_count: int  # How many raw chunks were compressed
    raw_byte_count: int  # Total bytes of raw reasoning compressed

    def to_dict(self) -> dict:
        return {
            "digest_id": self.digest_id,
            "step_number": self.step_number,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "raw_chunk_count": self.raw_chunk_count,
            "raw_byte_count": self.raw_byte_count,
        }

    @staticmethod
    def from_dict(d: dict) -> "ContextDigest":
        return ContextDigest(
            digest_id=d["digest_id"],
            step_number=d["step_number"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            payload=d["payload"],
            raw_chunk_count=d["raw_chunk_count"],
            raw_byte_count=d["raw_byte_count"],
        )


@dataclass
class StepSignal:
    """Observable signals from a step execution (no semantic understanding needed)."""

    step_number: int
    step_name: str
    output_bytes: int
    duration_ms: int
    was_retry: bool
    timestamp: datetime


@dataclass
class ReasoningLedger:
    """
    Append-only reasoning state that lives alongside the data state.

    The ledger does not interpret reasoning. It buffers, triggers
    distillation, and preserves context for restore.

    Usage by ExecutionContext:
        ledger.annotate(step, name, "Chose X because Y")
        ledger.ingest("raw reasoning tokens from model...")
        ledger.record_step_signal(step, name, output_bytes, duration_ms, was_retry)

        if ledger.should_distill():
            digest = distill_fn(ledger.raw_buffer, ledger.latest_digest)
            ledger.accept_digest(digest)

        health = ledger.compute_health(context_budget)
    """

    # Annotations: developer-supplied reasoning breadcrumbs
    annotations: List[ContextEntry] = field(default_factory=list)

    # Raw reasoning buffer: accumulated between distillations
    raw_buffer: List[str] = field(default_factory=list)
    raw_buffer_bytes: int = 0

    # Digests: compressed reasoning from distill function
    digests: List[ContextDigest] = field(default_factory=list)

    # Step signals: observable metrics per step
    step_signals: List[StepSignal] = field(default_factory=list)

    # Distillation policy
    distill_every: int = 0  # Every N steps (0 = disabled)
    distill_threshold: int = 0  # When buffer exceeds N bytes (0 = disabled)
    _steps_since_distill: int = 0

    def annotate(self, step_number: int, step_name: str, text: str) -> None:
        """Add a developer-supplied reasoning breadcrumb."""
        self.annotations.append(
            ContextEntry(
                step_number=step_number,
                step_name=step_name,
                timestamp=datetime.utcnow(),
                text=text,
            )
        )

    def ingest(self, reasoning: str) -> None:
        """
        Accept raw reasoning tokens from the model.

        Call this when the model exposes its thinking — extended thinking
        tokens, chain-of-thought, etc. The engine buffers these and
        periodically passes them to the developer's distill function.
        """
        if not reasoning:
            return
        self.raw_buffer.append(reasoning)
        self.raw_buffer_bytes += len(reasoning.encode("utf-8"))
        logger.debug(
            f"Ingested {len(reasoning)} chars of reasoning "
            f"(buffer: {self.raw_buffer_bytes} bytes, {len(self.raw_buffer)} chunks)"
        )

    def record_step_signal(
        self,
        step_number: int,
        step_name: str,
        output_bytes: int,
        duration_ms: int,
        was_retry: bool,
    ) -> None:
        """Record observable signals from a step execution."""
        self.step_signals.append(
            StepSignal(
                step_number=step_number,
                step_name=step_name,
                output_bytes=output_bytes,
                duration_ms=duration_ms,
                was_retry=was_retry,
                timestamp=datetime.utcnow(),
            )
        )
        self._steps_since_distill += 1

    def should_distill(self) -> bool:
        """Check if distillation should be triggered."""
        if not self.raw_buffer:
            return False

        if self.distill_every > 0 and self._steps_since_distill >= self.distill_every:
            return True

        if self.distill_threshold > 0 and self.raw_buffer_bytes >= self.distill_threshold:
            return True

        return False

    def accept_digest(self, digest: ContextDigest) -> None:
        """Store a digest produced by the developer's distill function."""
        self.digests.append(digest)
        self.raw_buffer.clear()
        self.raw_buffer_bytes = 0
        self._steps_since_distill = 0
        logger.info(
            f"Accepted digest at step {digest.step_number} "
            f"(compressed {digest.raw_chunk_count} chunks, {digest.raw_byte_count} bytes)"
        )

    @property
    def latest_digest(self) -> Optional[ContextDigest]:
        """Get the most recent digest, if any."""
        return self.digests[-1] if self.digests else None

    @property
    def total_context_bytes(self) -> int:
        """Total bytes of all context (annotations + buffer + digests)."""
        annotation_bytes = sum(
            len(a.text.encode("utf-8")) for a in self.annotations
        )
        digest_bytes = sum(
            len(str(d.payload).encode("utf-8")) for d in self.digests
        )
        return annotation_bytes + self.raw_buffer_bytes + digest_bytes

    def to_dict(self) -> dict:
        """Serialize the full ledger for snapshot storage."""
        return {
            "annotations": [a.to_dict() for a in self.annotations],
            "raw_buffer": self.raw_buffer,
            "raw_buffer_bytes": self.raw_buffer_bytes,
            "digests": [d.to_dict() for d in self.digests],
            "steps_since_distill": self._steps_since_distill,
        }

    @staticmethod
    def from_dict(d: dict) -> "ReasoningLedger":
        """Restore ledger from snapshot."""
        ledger = ReasoningLedger()
        ledger.annotations = [
            ContextEntry.from_dict(a) for a in d.get("annotations", [])
        ]
        ledger.raw_buffer = d.get("raw_buffer", [])
        ledger.raw_buffer_bytes = d.get("raw_buffer_bytes", 0)
        ledger.digests = [
            ContextDigest.from_dict(dig) for dig in d.get("digests", [])
        ]
        ledger._steps_since_distill = d.get("steps_since_distill", 0)
        return ledger

    def get_restore_context(self) -> dict:
        """
        Compile context for restore — the raw materials the developer
        uses to reconstruct agent context after a crash.

        This is NOT interpretation. It's everything we captured,
        structured for the developer to use however they want.
        """
        return {
            # Latest distilled reasoning (if developer provided distill fn)
            "digest": self.latest_digest.to_dict() if self.latest_digest else None,
            # All digests for full trail
            "digest_history": [d.to_dict() for d in self.digests],
            # Raw reasoning accumulated since last distill
            "undigested": list(self.raw_buffer),
            "undigested_bytes": self.raw_buffer_bytes,
            # Developer annotations, associated with their steps
            "annotations": [a.to_dict() for a in self.annotations],
            # Observable signals
            "steps_completed": len(self.step_signals),
            "total_context_bytes": self.total_context_bytes,
        }
