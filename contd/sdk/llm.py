"""
Contd LLM Step Support

LLM-aware step decorator with token tracking, cost management,
and budget enforcement. Treats LLM calls as first-class citizens
rather than generic function calls.

Key differences from regular steps:
- Token tracking (input/output/total)
- Cost calculation based on model pricing
- Budget enforcement (fail workflow if exceeded)
- LLM-specific metrics
"""

from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field
from functools import wraps
from datetime import timedelta
from enum import Enum
import time
import logging

from contd.sdk.decorators import step, StepConfig
from contd.sdk.types import RetryPolicy
from contd.sdk.context import ExecutionContext
from contd.sdk.errors import TokenBudgetExceeded

logger = logging.getLogger(__name__)

# Lazy import for metrics
_llm_metrics = None


def _get_llm_metrics():
    global _llm_metrics
    if _llm_metrics is None:
        try:
            from contd.observability.llm_metrics import llm_metrics_collector

            _llm_metrics = llm_metrics_collector
        except ImportError:
            _llm_metrics = None
    return _llm_metrics


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"


# Pricing per 1M tokens (input, output) as of Jan 2026
# Users can override with custom pricing
MODEL_PRICING: Dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    # Anthropic
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3.5-sonnet": (3.00, 15.00),
    "claude-3.5-haiku": (0.80, 4.00),
    # Google
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
}


@dataclass
class TokenUsage:
    """Token usage from an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class LLMStepConfig:
    """
    Configuration for @llm_step decorator.

    Extends StepConfig with LLM-specific options.

    Attributes:
        model: Model identifier (e.g., "gpt-4o", "claude-3-sonnet")
        provider: LLM provider for response parsing
        max_tokens: Maximum output tokens for the call
        track_tokens: Whether to track token usage (default: True)
        token_budget: Maximum total tokens for this step (None = unlimited)
        cost_budget: Maximum cost in dollars for this step (None = unlimited)
        custom_pricing: Override default pricing (input_per_1m, output_per_1m)

        # Inherited from StepConfig
        checkpoint: Create checkpoint after step completion
        retry: Retry policy for transient failures
        timeout: Maximum step execution time
        savepoint: Create rich savepoint with epistemic metadata
    """

    # LLM-specific
    model: str = "gpt-4o"
    provider: LLMProvider = LLMProvider.OPENAI
    max_tokens: Optional[int] = None
    track_tokens: bool = True
    token_budget: Optional[int] = None
    cost_budget: Optional[float] = None
    custom_pricing: Optional[tuple[float, float]] = None

    # Inherited step config
    checkpoint: bool = True
    retry: Optional[RetryPolicy] = None
    timeout: Optional[timedelta] = None
    savepoint: bool = False


@dataclass
class TokenTracker:
    """
    Accumulates token usage across LLM steps in a workflow.

    Stored in ExecutionContext for workflow-wide tracking.
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_dollars: float = 0.0
    calls_by_model: Dict[str, int] = field(default_factory=dict)
    tokens_by_model: Dict[str, TokenUsage] = field(default_factory=dict)

    # Budget limits (set at workflow level)
    workflow_token_budget: Optional[int] = None
    workflow_cost_budget: Optional[float] = None

    def add_usage(
        self,
        model: str,
        usage: TokenUsage,
        cost: float,
    ):
        """Add token usage from an LLM call."""
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_tokens += usage.total_tokens
        self.total_cost_dollars += cost

        # Track by model
        self.calls_by_model[model] = self.calls_by_model.get(model, 0) + 1

        if model not in self.tokens_by_model:
            self.tokens_by_model[model] = TokenUsage()

        model_usage = self.tokens_by_model[model]
        self.tokens_by_model[model] = TokenUsage(
            input_tokens=model_usage.input_tokens + usage.input_tokens,
            output_tokens=model_usage.output_tokens + usage.output_tokens,
        )

    def check_budget(self, workflow_id: str):
        """
        Check if workflow budget is exceeded.

        Raises:
            TokenBudgetExceeded: If token or cost budget exceeded
        """
        if (
            self.workflow_token_budget
            and self.total_tokens > self.workflow_token_budget
        ):
            raise TokenBudgetExceeded(
                workflow_id=workflow_id,
                budget_type="tokens",
                budget_limit=self.workflow_token_budget,
                current_usage=self.total_tokens,
            )

        if (
            self.workflow_cost_budget
            and self.total_cost_dollars > self.workflow_cost_budget
        ):
            raise TokenBudgetExceeded(
                workflow_id=workflow_id,
                budget_type="cost",
                budget_limit=self.workflow_cost_budget,
                current_usage=self.total_cost_dollars,
            )


def calculate_cost(
    model: str,
    usage: TokenUsage,
    custom_pricing: Optional[tuple[float, float]] = None,
) -> float:
    """
    Calculate cost for token usage.

    Args:
        model: Model identifier
        usage: Token usage from the call
        custom_pricing: Optional (input_per_1m, output_per_1m) override

    Returns:
        Cost in dollars
    """
    if custom_pricing:
        input_price, output_price = custom_pricing
    elif model in MODEL_PRICING:
        input_price, output_price = MODEL_PRICING[model]
    else:
        # Unknown model - log warning and use zero cost
        logger.warning(f"Unknown model '{model}' - cannot calculate cost")
        return 0.0

    input_cost = (usage.input_tokens / 1_000_000) * input_price
    output_cost = (usage.output_tokens / 1_000_000) * output_price

    return input_cost + output_cost


def extract_token_usage(
    response: Any,
    provider: LLMProvider,
) -> Optional[TokenUsage]:
    """
    Extract token usage from LLM response.

    Supports common response formats from major providers.

    Args:
        response: Raw response from LLM call
        provider: LLM provider for parsing

    Returns:
        TokenUsage if extractable, None otherwise
    """
    if response is None:
        return None

    # Handle dict responses
    if isinstance(response, dict):
        # OpenAI format: {"usage": {"prompt_tokens": X, "completion_tokens": Y}}
        if "usage" in response:
            usage = response["usage"]
            return TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0)
                or usage.get("input_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0)
                or usage.get("output_tokens", 0),
            )

        # Direct format: {"input_tokens": X, "output_tokens": Y}
        if "input_tokens" in response or "output_tokens" in response:
            return TokenUsage(
                input_tokens=response.get("input_tokens", 0),
                output_tokens=response.get("output_tokens", 0),
            )

    # Handle object responses (OpenAI SDK, Anthropic SDK)
    if hasattr(response, "usage"):
        usage = response.usage

        # OpenAI SDK format
        if hasattr(usage, "prompt_tokens"):
            return TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )

        # Anthropic SDK format
        if hasattr(usage, "input_tokens"):
            return TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            )

    return None


def get_token_tracker(ctx: ExecutionContext) -> TokenTracker:
    """Get or create TokenTracker for the current workflow."""
    if not hasattr(ctx, "_token_tracker") or ctx._token_tracker is None:
        ctx._token_tracker = TokenTracker()
    return ctx._token_tracker


def llm_step(config: Optional[LLMStepConfig] = None):
    """
    Mark a function as an LLM workflow step.

    Wraps @step with LLM-specific functionality:
    - Extracts token usage from response
    - Calculates and tracks cost
    - Enforces token/cost budgets
    - Emits LLM-specific metrics

    The decorated function should return the raw LLM response
    (or a dict containing it) so token usage can be extracted.

    Example:
        >>> @llm_step(LLMStepConfig(
        ...     model="gpt-4o",
        ...     token_budget=10000,
        ...     cost_budget=0.50
        ... ))
        ... def analyze_document(doc: str) -> dict:
        ...     response = openai.chat.completions.create(
        ...         model="gpt-4o",
        ...         messages=[{"role": "user", "content": doc}]
        ...     )
        ...     return {"response": response, "analysis": response.choices[0].message.content}
    """
    cfg = config or LLMStepConfig()

    # Build underlying StepConfig
    step_cfg = StepConfig(
        checkpoint=cfg.checkpoint,
        retry=cfg.retry,
        timeout=cfg.timeout,
        savepoint=cfg.savepoint,
    )

    def decorator(fn: Callable) -> Callable:
        # First apply the @step decorator to the original function
        step_wrapped = step(step_cfg)(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = ExecutionContext.current()
            tracker = get_token_tracker(ctx)
            metrics = _get_llm_metrics()

            start_time = time.monotonic()

            # Execute via the step-wrapped function (handles idempotency, journaling, etc.)
            result = step_wrapped(*args, **kwargs)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Extract token usage (post-processing only, no re-execution)
            if cfg.track_tokens:
                # Try to extract from result
                usage = None

                if isinstance(result, dict):
                    # Check for nested response object
                    for key in ["response", "completion", "result", "llm_response"]:
                        if key in result:
                            usage = extract_token_usage(result[key], cfg.provider)
                            if usage:
                                break

                    # Try the dict itself
                    if not usage:
                        usage = extract_token_usage(result, cfg.provider)
                else:
                    usage = extract_token_usage(result, cfg.provider)

                if usage:
                    # Calculate cost
                    cost = calculate_cost(cfg.model, usage, cfg.custom_pricing)

                    # Add to tracker
                    tracker.add_usage(cfg.model, usage, cost)

                    # Check step-level budget
                    if cfg.token_budget and usage.total_tokens > cfg.token_budget:
                        raise TokenBudgetExceeded(
                            workflow_id=ctx.workflow_id,
                            budget_type="step_tokens",
                            budget_limit=cfg.token_budget,
                            current_usage=usage.total_tokens,
                        )

                    if cfg.cost_budget and cost > cfg.cost_budget:
                        raise TokenBudgetExceeded(
                            workflow_id=ctx.workflow_id,
                            budget_type="step_cost",
                            budget_limit=cfg.cost_budget,
                            current_usage=cost,
                        )

                    # Check workflow-level budget
                    tracker.check_budget(ctx.workflow_id)

                    # Emit metrics
                    if metrics:
                        metrics.record_llm_call(
                            workflow_name=ctx.workflow_name,
                            step_name=fn.__name__,
                            model=cfg.model,
                            provider=cfg.provider.value,
                            input_tokens=usage.input_tokens,
                            output_tokens=usage.output_tokens,
                            cost_dollars=cost,
                            duration_ms=duration_ms,
                        )

                    logger.debug(
                        f"LLM step {fn.__name__}: {usage.total_tokens} tokens, ${cost:.4f}"
                    )
                else:
                    logger.warning(
                        f"Could not extract token usage from {fn.__name__} response"
                    )

            return result

        # Attach LLM metadata
        wrapper.__contd_llm_step__ = True
        wrapper.__contd_llm_config__ = cfg
        wrapper.__contd_step__ = True
        wrapper.__contd_config__ = step_cfg

        return wrapper

    return decorator


__all__ = [
    "LLMStepConfig",
    "LLMProvider",
    "TokenUsage",
    "TokenTracker",
    "llm_step",
    "get_token_tracker",
    "calculate_cost",
    "extract_token_usage",
    "MODEL_PRICING",
]
