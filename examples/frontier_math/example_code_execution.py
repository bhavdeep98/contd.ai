"""
Example: Using code execution with the FrontierMath solver.

This demonstrates how the model can verify mathematical computations
by executing Python code during the reasoning process.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from solver import FrontierMathSolver
from config import ModelConfig, SolverConfig


def main():
    """
    Solve a problem that benefits from code execution.
    
    The model will be able to verify its reasoning by actually
    computing values rather than just guessing.
    """
    
    # Problem that requires computation
    problem = """
Compute the number of primes p < 1000 for which 2 is a primitive root modulo p.

A primitive root modulo p is a number g such that the powers g^1, g^2, ..., g^(p-1)
produce all non-zero residues modulo p.

Provide the exact count and show your verification.
"""
    
    print("=" * 70)
    print("FrontierMath Solver - Code Execution Example")
    print("=" * 70)
    print()
    print("Problem:")
    print(problem)
    print()
    print("=" * 70)
    print()
    
    # Configure solver with code execution enabled
    model_config = ModelConfig.from_env()
    solver_config = SolverConfig.from_env()
    
    # Reduce max steps for demo
    solver_config.max_steps = 10
    
    solver = FrontierMathSolver(
        model_config=model_config,
        solver_config=solver_config,
        enable_code_execution=True,  # Enable code execution
        enable_sagemath=False  # Don't need SageMath for this problem
    )
    
    print("Solver Configuration:")
    print(f"  Model: {model_config.provider} / {model_config.model_name}")
    print(f"  Code Execution: Enabled")
    print(f"  Max Steps: {solver_config.max_steps}")
    print()
    print("=" * 70)
    print()
    
    # Solve
    result = solver.solve(problem)
    
    # Print result
    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"Status: {result['status']}")
    
    if result['status'] == 'solved':
        print(f"\nAnswer: {result['answer']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Steps: {result['steps']}")
        print(f"Cost: ${result.get('cost', 0):.4f}")
        
        if result.get('verified'):
            print("\n✓ Answer verified by computation")
        else:
            print("\n⚠ Answer not verified (verification not implemented)")
    else:
        print(f"\nPartial progress after {result['steps']} steps")
        print("The solver did not reach a final answer.")
    
    print("=" * 70)
    print()
    print("Note: The model can use <execute_python> tags to verify computations.")
    print("Example:")
    print("""
    <execute_python>
    from sympy import isprime
    
    # Count primes where 2 is primitive root
    count = 0
    for p in range(3, 1000):
        if isprime(p):
            # Check if 2 is primitive root mod p
            order = 1
            val = 2
            while val % p != 1 and order < p:
                val = (val * 2) % p
                order += 1
            if order == p - 1:
                count += 1
    
    print(f"Count: {count}")
    </execute_python>
    """)
    print()


if __name__ == "__main__":
    main()
