"""
Contd Context - Reasoning preservation for durable workflows.

Provides infrastructure for detecting and preventing context rot
in long-running LLM agent workflows. The engine observes and preserves
reasoning state — it does not interpret or manage LLM interactions.

Three primitives:
- annotate(): Developer-supplied reasoning breadcrumbs (always available)
- ingest(): Accept raw reasoning tokens when the model exposes them
- distill(): Periodic compression of accumulated reasoning via developer-provided function

The engine stores these durably and returns them on restore,
giving the developer raw materials to reconstruct agent context.
"""

from .ledger import ReasoningLedger, ContextEntry, ContextDigest
from .health import ContextHealth, HealthSignals
from .recipes import distill_on_decline, savepoint_on_drift, warn_on_budget

__all__ = [
    "ReasoningLedger",
    "ContextEntry",
    "ContextDigest",
    "ContextHealth",
    "HealthSignals",
    "distill_on_decline",
    "savepoint_on_drift",
    "warn_on_budget",
]
