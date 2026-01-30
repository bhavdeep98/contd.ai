"""
Complete example showing the full FrontierMath solving workflow.

This demonstrates:
1. Problem loading
2. Solver initialization
3. Durable execution with thinking token capture
4. Context preservation and distillation
5. Savepoints and backtracking
6. Result verification
7. Ledger visualization
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import ModelConfig, SolverConfig
from solver import FrontierMathSolver
from models import create_model

def main():
    print("=" * 70)
    print("FrontierMath Solver - Complete Workflow Example")
    print("=" * 70)
    
    # Step 1: Configure the solver
    print("\n📋 Step 1: Configuration")
    print("-" * 70)
    
    model_config = ModelConfig.from_env()
    solver_config = SolverConfig.from_env()
    
    print(f"Model Provider: {model_config.provider}")
    print(f"Model Name: {model_config.model_name}")
    print(f"Max Steps: {solver_config.max_steps}")
    print(f"Cost Budget: ${solver_config.cost_budget}")
    print(f"Distill Every: {solver_config.distill_every} steps")
    print(f"Context Budget: {solver_config.context_budget:,} bytes")
    
    # Step 2: Load a problem
    print("\n📖 Step 2: Load Problem")
    print("-" * 70)
    
    problem = """Prove that for all primes p > 3, p^2 - 1 is divisible by 24.

Hint: Consider the factorization of p^2 - 1 and properties of consecutive integers."""
    
    print(f"Problem: {problem}")
    
    # Step 3: Initialize solver
    print("\n🔧 Step 3: Initialize Solver")
    print("-" * 70)
    
    solver = FrontierMathSolver(model_config, solver_config)
    print("✅ Solver initialized with:")
    print(f"   - Reasoning model: {model_config.model_name}")
    print(f"   - Thinking token capture: Enabled")
    print(f"   - Context preservation: Enabled")
    print(f"   - Distillation: Every {solver_config.distill_every} steps")
    print(f"   - Savepoints: Enabled")
    
    # Step 4: Solve the problem
    print("\n🧮 Step 4: Solve Problem")
    print("-" * 70)
    print("Starting solver... (this may take a few minutes)")
    print()
    
    try:
        result = solver.solve(problem)
        
        # Step 5: Display results
        print("\n📊 Step 5: Results")
        print("-" * 70)
        
        if result['status'] == 'solved':
            print("✅ PROBLEM SOLVED!")
            print()
            print(f"Answer:")
            print(f"{result['answer']}")
            print()
            print(f"Confidence: {result['confidence']:.1%}")
            print(f"Steps: {result['steps']}")
            print(f"Reasoning captured: {result.get('reasoning_chars', 0):,} chars")
            print(f"Digests created: {result.get('digests_created', 0)}")
            print(f"Cost: ${result.get('cost', 0):.2f}")
            print(f"Verified: {result.get('verified', False)}")
        else:
            print(f"❌ Problem not solved: {result['status']}")
            print(f"Steps completed: {result.get('steps', 0)}")
        
        # Step 6: Context preservation details
        print("\n💾 Step 6: Context Preservation")
        print("-" * 70)
        print("The solver captured:")
        print(f"  • All thinking tokens from the reasoning model")
        print(f"  • Developer annotations at each decision point")
        print(f"  • Compressed digests every {solver_config.distill_every} steps")
        print(f"  • Savepoints at key decision points")
        print()
        print("If the workflow crashed, it would resume with:")
        print("  • Full reasoning context (digests + undigested chunks)")
        print("  • All annotations and decisions")
        print("  • Exact step number and state")
        
        # Step 7: Visualization
        print("\n🎨 Step 7: Visualization")
        print("-" * 70)
        print("To view the reasoning timeline:")
        print()
        print("1. Start the API server:")
        print("   python -m contd.api.server")
        print()
        print("2. Open the ledger viewer:")
        print("   http://localhost:8000/ledger-viewer")
        print()
        print("3. Enter the workflow ID to see:")
        print("   • Timeline of all reasoning steps")
        print("   • Thinking tokens at each step")
        print("   • Annotations and decisions")
        print("   • Distillation points")
        print("   • Savepoints for backtracking")
        
        # Step 8: Advanced features
        print("\n🚀 Step 8: Advanced Features")
        print("-" * 70)
        print()
        print("Backtracking:")
        print("  If the solver hit a dead end, you can time-travel:")
        print("  $ contd time-travel <workflow_id> <savepoint_id>")
        print()
        print("Resume after crash:")
        print("  $ python solver.py --resume <workflow_id>")
        print()
        print("Human review:")
        print("  Enable review mode to approve/reject reasoning steps:")
        print("  $ export SOLVER_REQUIRE_REVIEW=true")
        print()
        print("Custom distillation:")
        print("  Implement your own distill function in distill.py")
        print("  to extract domain-specific insights")
        
        # Summary
        print("\n" + "=" * 70)
        print("WORKFLOW COMPLETE")
        print("=" * 70)
        print()
        print("Key takeaways:")
        print("  ✓ Durable execution - never lose progress")
        print("  ✓ Thinking tokens captured - full reasoning preserved")
        print("  ✓ Context preservation - distillation prevents rot")
        print("  ✓ Savepoints - backtrack when stuck")
        print("  ✓ Human oversight - review via web UI")
        print("  ✓ Cost tracking - monitor spending")
        print()
        print("This is how contd.ai enables solving problems that take")
        print("hours or days of reasoning without losing context.")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("The workflow state is saved. Resume with:")
        print("  python solver.py --resume <workflow_id>")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        print("Check the logs for details")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
