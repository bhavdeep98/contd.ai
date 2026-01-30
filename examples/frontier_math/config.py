"""
Configuration for FrontierMath solver.
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    """Configuration for reasoning models."""
    
    # Model selection
    provider: str = "ollama"  # ollama, deepseek-api, claude
    model_name: str = "deepseek-r1"
    
    # API configuration
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    # Model parameters
    temperature: float = 0.7
    max_tokens: int = 16000
    thinking_budget: int = 32000  # For Claude extended thinking
    
    @classmethod
    def from_env(cls) -> "ModelConfig":
        """Load configuration from environment variables."""
        provider = os.getenv("REASONING_MODEL", "ollama")
        
        if provider == "ollama":
            return cls(
                provider="ollama",
                model_name="deepseek-r1",
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            )
        elif provider == "deepseek-api":
            return cls(
                provider="deepseek-api",
                model_name="deepseek-reasoner",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com",
            )
        elif provider == "claude":
            return cls(
                provider="claude",
                model_name=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                thinking_budget=int(os.getenv("CLAUDE_THINKING_BUDGET", "32000")),
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")


@dataclass
class SolverConfig:
    """Configuration for the FrontierMath solver."""
    
    # Workflow parameters
    max_steps: int = 100
    max_time_seconds: int = 7200  # 2 hours
    
    # Context preservation
    distill_every: int = 5
    distill_threshold: int = 50_000  # bytes
    context_budget: int = 200_000  # bytes
    
    # Meta-reasoning
    reflection_interval: int = 10  # Reflect every N steps
    reflection_on_health_warning: bool = True
    
    # Cost management
    cost_budget: float = 10.00  # USD per problem
    
    # Savepoints
    savepoint_on_decision: bool = True
    savepoint_on_approach_change: bool = True
    
    # Verification
    verify_intermediate_steps: bool = False
    verify_final_answer: bool = True
    
    # Human-in-the-loop
    require_review: bool = False
    pause_on_low_confidence: bool = False
    confidence_threshold: float = 0.7
    
    @classmethod
    def from_env(cls) -> "SolverConfig":
        """Load configuration from environment variables."""
        return cls(
            max_steps=int(os.getenv("SOLVER_MAX_STEPS", "100")),
            max_time_seconds=int(os.getenv("SOLVER_MAX_TIME", "7200")),
            distill_every=int(os.getenv("SOLVER_DISTILL_EVERY", "5")),
            context_budget=int(os.getenv("SOLVER_CONTEXT_BUDGET", "200000")),
            cost_budget=float(os.getenv("SOLVER_COST_BUDGET", "10.00")),
            reflection_interval=int(os.getenv("SOLVER_REFLECTION_INTERVAL", "10")),
            require_review=os.getenv("SOLVER_REQUIRE_REVIEW", "false").lower() == "true",
        )


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    
    # Problem selection
    problems_dir: str = "problems"
    max_problems: Optional[int] = None
    problem_filter: Optional[str] = None  # Regex pattern
    
    # Execution
    parallel: bool = False
    max_workers: int = 4
    timeout_per_problem: int = 7200  # 2 hours
    
    # Results
    results_dir: str = "results"
    save_reasoning: bool = True
    save_ledger: bool = True
    
    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        """Load configuration from environment variables."""
        return cls(
            problems_dir=os.getenv("BENCHMARK_PROBLEMS_DIR", "problems"),
            max_problems=int(os.getenv("BENCHMARK_MAX_PROBLEMS")) if os.getenv("BENCHMARK_MAX_PROBLEMS") else None,
            parallel=os.getenv("BENCHMARK_PARALLEL", "false").lower() == "true",
            results_dir=os.getenv("BENCHMARK_RESULTS_DIR", "results"),
        )


# Default configurations
DEFAULT_MODEL_CONFIG = ModelConfig.from_env()
DEFAULT_SOLVER_CONFIG = SolverConfig.from_env()
DEFAULT_BENCHMARK_CONFIG = BenchmarkConfig.from_env()
