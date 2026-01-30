"""
FrontierMath Solver with Contd.ai

A complete implementation demonstrating how to use contd.ai's durable execution
and context preservation features to solve challenging mathematics problems
using reasoning models with thinking token capture.
"""

from .solver import FrontierMathSolver
from .benchmark import FrontierMathBenchmark
from .config import ModelConfig, SolverConfig, BenchmarkConfig
from .models import create_model, ReasoningResponse
from .distill import simple_math_distill, llm_math_distill

__all__ = [
    "FrontierMathSolver",
    "FrontierMathBenchmark",
    "ModelConfig",
    "SolverConfig",
    "BenchmarkConfig",
    "create_model",
    "ReasoningResponse",
    "simple_math_distill",
    "llm_math_distill",
]
