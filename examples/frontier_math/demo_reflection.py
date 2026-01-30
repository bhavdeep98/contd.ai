"""
Demo: Meta-Reasoning and Self-Reflection

This demonstrates how the model can reflect on its own reasoning
to evaluate progress and adjust its approach.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import ModelConfig, SolverConfig
from solver import FrontierMathSolver

def main():
    print("=" * 70)
    print("FrontierMath Solver - Meta-Reasoning Demo")
    print("=" * 70)
    print()
    print("This demo shows how the model reflects on its own reasoning:")
    print("  • Every 10 steps, the model reviews its thinking history")
    print("  • It evaluates progress and effectiveness of current approach")
    print("  • It decides whether to continue or change direction")
    print("  • It can detect when it's stuck and suggest backtracking")
    print()
    print("=" * 70)
    
    # Configure with frequent reflection
    model_config = ModelConfig.from_env()
    solver_config = SolverConfig.from_env()
    solver_config.reflection_interval = 5  # Reflect every 5 steps for demo
    solver_config.max_steps = 30  # Shorter for demo
    
    print(f"\nConfiguration:")
    print(f"  Model: {model_config.provider} / {model_config.model_name}")
    print(f"  Reflection interval: Every {solver_config.reflection_interval} steps")
    print(f"  Max steps: {solver_config.max_steps}")
    print()
    
    # Problem that might require approach changes
    problem = """Find all integer solutions to the equation x^3 + y^3 = z^3 + 3.

Show your reasoning and prove that your solution set is complete."""
    
    print("Problem:")
    print(problem)
    print()
    print("=" * 70)
    print("Starting solver...")
    print("=" * 70)
    
    # Create solver with reflection
    solver = FrontierMathSolver(
        model_config,
        solver_config,
        reflection_interval=solver_config.reflection_interval
    )
    
    # Solve
    result = solver.solve(problem)
    
    # Show results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Status: {result['status']}")
    print(f"Steps: {result.get('steps', 0)}")
    
    if result['status'] == 'solved':
        print(f"\n✅ Solution found!")
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Confidence: {result['confidence']:.1%}")
    
    # Show reflection summary
    print("\n" + "=" * 70)
    print("REFLECTION SUMMARY")
    print("=" * 70)
    
    reflections = solver.reflection_manager.reflections
    print(f"Total reflections: {len(reflections)}")
    
    for i, refl in enumerate(reflections):
        print(f"\nReflection {i+1} (Step {refl['step']}):")
        print(f"  Progress: {refl.get('progress', 'unknown')}")
        print(f"  Recommendation: {refl.get('recommendation', 'unknown')}")
        
        if refl.get('should_backtrack'):
            print("  ⚠️  Model indicated it was stuck")
        if refl.get('should_change_approach'):
            print("  💡 Model suggested changing approach")
    
    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    print()
    print("What happened:")
    print("  1. Model worked on the problem for several steps")
    print("  2. At step 5, it reflected on its reasoning")
    print("  3. It reviewed its thinking history and evaluated progress")
    print("  4. It decided whether to continue or change approach")
    print("  5. This process repeated every 5 steps")
    print()
    print("Benefits of meta-reasoning:")
    print("  ✓ Model can detect when it's going in circles")
    print("  ✓ Model can recognize dead ends early")
    print("  ✓ Model can adjust strategy based on what's working")
    print("  ✓ Model has access to its full reasoning history")
    print("  ✓ Prevents wasted computation on ineffective approaches")
    print()
    print("The model sees:")
    print("  • Compressed digests from earlier steps")
    print("  • Raw thinking tokens from recent steps (last 5)")
    print("  • All decision annotations")
    print("  • Previous reflection summaries")
    print()
    print("This enables true self-correction and adaptive problem-solving!")
    print("=" * 70)


if __name__ == "__main__":
    main()
