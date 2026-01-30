"""
Contd LLM Metrics

Metrics specific to LLM operations: token usage, costs, and performance.
"""

from prometheus_client import Counter, Histogram, Gauge
from dataclasses import dataclass
from typing import Optional

# =============================================================================
# LLM TOKEN METRICS
# =============================================================================

llm_tokens_total = Counter(
    "contd_llm_tokens_total",
    "Total LLM tokens consumed",
    ["workflow_name", "step_name", "model", "token_type"],  # input, output
)

llm_tokens_per_call = Histogram(
    "contd_llm_tokens_per_call",
    "Token distribution per LLM call",
    ["model", "token_type"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000],
)

# =============================================================================
# LLM COST METRICS
# =============================================================================

llm_cost_dollars_total = Counter(
    "contd_llm_cost_dollars_total",
    "Total LLM cost in dollars",
    ["workflow_name", "model", "provider"],
)

llm_cost_per_workflow = Histogram(
    "contd_llm_cost_per_workflow_dollars",
    "Cost distribution per workflow",
    ["workflow_name"],
    buckets=[0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 1.0, 2.5, 5.0, 10.0, 25.0],
)

# =============================================================================
# LLM PERFORMANCE METRICS
# =============================================================================

llm_call_duration_milliseconds = Histogram(
    "contd_llm_call_duration_milliseconds",
    "LLM API call latency",
    ["model", "provider"],
    buckets=[100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
)

llm_calls_total = Counter(
    "contd_llm_calls_total",
    "Total LLM API calls",
    ["workflow_name", "step_name", "model", "status"],  # success, failed
)

# =============================================================================
# LLM BUDGET METRICS
# =============================================================================

llm_budget_exceeded_total = Counter(
    "contd_llm_budget_exceeded_total",
    "Budget exceeded events",
    ["workflow_name", "budget_type"],  # tokens, cost, step_tokens, step_cost
)

llm_budget_utilization = Gauge(
    "contd_llm_budget_utilization_percent",
    "Current budget utilization percentage",
    ["workflow_id", "budget_type"],
)

# =============================================================================
# LLM WORKFLOW AGGREGATES
# =============================================================================

llm_workflow_tokens_total = Gauge(
    "contd_llm_workflow_tokens_total",
    "Total tokens for active workflow",
    ["workflow_id", "workflow_name"],
)

llm_workflow_cost_dollars = Gauge(
    "contd_llm_workflow_cost_dollars",
    "Total cost for active workflow",
    ["workflow_id", "workflow_name"],
)


# =============================================================================
# METRICS COLLECTOR
# =============================================================================


@dataclass
class LLMMetricsCollector:
    """
    Collector for LLM-specific metrics.
    """
    
    _instance: Optional["LLMMetricsCollector"] = None
    
    @classmethod
    def get_instance(cls) -> "LLMMetricsCollector":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def record_llm_call(
        self,
        workflow_name: str,
        step_name: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_dollars: float,
        duration_ms: float,
        status: str = "success",
    ):
        """Record a completed LLM call."""
        # Token counts
        llm_tokens_total.labels(
            workflow_name=workflow_name,
            step_name=step_name,
            model=model,
            token_type="input",
        ).inc(input_tokens)
        
        llm_tokens_total.labels(
            workflow_name=workflow_name,
            step_name=step_name,
            model=model,
            token_type="output",
        ).inc(output_tokens)
        
        # Token histograms
        llm_tokens_per_call.labels(model=model, token_type="input").observe(input_tokens)
        llm_tokens_per_call.labels(model=model, token_type="output").observe(output_tokens)
        
        # Cost
        llm_cost_dollars_total.labels(
            workflow_name=workflow_name,
            model=model,
            provider=provider,
        ).inc(cost_dollars)
        
        # Performance
        llm_call_duration_milliseconds.labels(
            model=model,
            provider=provider,
        ).observe(duration_ms)
        
        # Call count
        llm_calls_total.labels(
            workflow_name=workflow_name,
            step_name=step_name,
            model=model,
            status=status,
        ).inc()
    
    def record_budget_exceeded(
        self,
        workflow_name: str,
        budget_type: str,
    ):
        """Record a budget exceeded event."""
        llm_budget_exceeded_total.labels(
            workflow_name=workflow_name,
            budget_type=budget_type,
        ).inc()
    
    def update_workflow_totals(
        self,
        workflow_id: str,
        workflow_name: str,
        total_tokens: int,
        total_cost: float,
    ):
        """Update workflow-level aggregates."""
        llm_workflow_tokens_total.labels(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
        ).set(total_tokens)
        
        llm_workflow_cost_dollars.labels(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
        ).set(total_cost)
    
    def update_budget_utilization(
        self,
        workflow_id: str,
        budget_type: str,
        utilization_percent: float,
    ):
        """Update budget utilization gauge."""
        llm_budget_utilization.labels(
            workflow_id=workflow_id,
            budget_type=budget_type,
        ).set(utilization_percent)


# Global collector instance
llm_metrics_collector = LLMMetricsCollector.get_instance()


__all__ = [
    "LLMMetricsCollector",
    "llm_metrics_collector",
    # Export metrics for direct access
    "llm_tokens_total",
    "llm_cost_dollars_total",
    "llm_calls_total",
    "llm_call_duration_milliseconds",
    "llm_budget_exceeded_total",
]
