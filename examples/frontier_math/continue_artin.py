"""
Continue Artin Challenge from where it left off.
Loads previous reasoning history and continues solving.
"""

import sys
import os
import time
from datetime import datetime

# Fix encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace', line_buffering=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("CONTINUING ARTIN CHALLENGE FROM STEP 10")
print("=" * 80)

api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    print("\nError: DEEPSEEK_API_KEY not set")
    sys.exit(1)

print(f"\nAPI Key: {api_key[:8]}...{api_key[-4:]}")

# Load problem
with open("problems/artin_primitive_root.txt", "r") as f:
    problem = f.read()

from config import ModelConfig, SolverConfig
from models import create_model
from reflection import ReflectionManager, build_reflection_prompt, parse_reflection_response
from distill import simple_math_distill

# Configuration
model_config = ModelConfig(
    provider="deepseek-api",
    model_name="deepseek-reasoner",
    api_key=api_key
)

solver_config = SolverConfig(
    max_steps=20,  # Continue for 20 more steps
    distill_every=10,
    reflection_interval=5,
    cost_budget=0.0
)

print(f"\nContinuing from step 10 for {solver_config.max_steps} more steps")
print("=" * 80)

# Initialize
model = create_model(model_config)
reflection_mgr = ReflectionManager()

# Simulated previous state (in real contd.ai this would be loaded from persistence)
start_step = 10
total_cost = 0.05  # Previous cost
reasoning_history = []  # Would load from persistence
digest_history = []
annotations = []

# Add summary of previous work
previous_summary = """Previous 10 steps explored:
- X = 10^6: π(10^6) = 78,498, π₂(10^6) ≈ 29,239-29,341
- X = 10^7: π(10^7) = 664,579, π₂(10^7) ≈ 248,749-248,750
- Proposed N values: 17,559 to 4,197,835 (inconsistent)
- No actual computation performed yet
- Need to verify which X maximizes |R(X) - C_Artin|"""

start_time = time.time()
timeout_seconds = 1 * 60 * 60  # 1 hour

print(f"\nStarting continuation at {datetime.now().strftime('%H:%M:%S')}\n")

try:
    for i in range(solver_config.max_steps):
        step = start_step + i + 1
        elapsed = time.time() - start_time
        
        if elapsed > timeout_seconds:
            print(f"\nTIMEOUT REACHED: {elapsed/3600:.2f} hours")
            break
        
        print(f"\n{'='*80}")
        print(f"STEP {step} | Elapsed: {elapsed/60:.1f}min | Cost: ${total_cost:.2f}")
        print(f"{'='*80}")
        
        # Build prompt with context
        if step == start_step + 1:
            prompt = f"""{problem}

PREVIOUS WORK (Steps 1-10):
{previous_summary}

Continue solving. Focus on:
1. Determining which X (10^6 or 10^7) actually maximizes the difference
2. Computing the exact value of N
3. Showing your calculation clearly"""
        else:
            context = ""
            if digest_history:
                context += f"\nCompressed history: {digest_history[-1]}"
            if reasoning_history:
                context += f"\nLast reasoning: {reasoning_history[-1][:500]}..."
            
            prompt = f"""Continue: {problem}

{context}

Continue your analysis."""
        
        print(f"Generating response...")
        step_start = time.time()
        
        try:
            response = model.generate(prompt)
            step_duration = time.time() - step_start
            
            if response.metadata and 'usage' in response.metadata:
                usage = response.metadata['usage']
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                step_cost = (input_tokens * 0.14 + output_tokens * 0.28) / 1_000_000
                total_cost += step_cost
                
                print(f"Response received ({step_duration:.1f}s)")
                print(f"  Tokens: {input_tokens} in, {output_tokens} out")
                print(f"  Cost: ${step_cost:.4f} (total: ${total_cost:.2f})")
            
            print(f"  Thinking: {len(response.thinking)} chars")
            print(f"  Answer: {len(response.answer)} chars")
            
            reasoning_history.append(response.thinking)
            
            print(f"\n  Answer preview:")
            print(f"  {response.answer[:400]}")
            
            # Distillation
            if (step - start_step) % solver_config.distill_every == 0:
                print(f"\n  Running distillation...")
                recent = reasoning_history[-solver_config.distill_every:]
                prev = digest_history[-1] if digest_history else None
                
                digest = simple_math_distill(recent, prev)
                digest_history.append(digest)
                
                print(f"  Distilled {len(recent)} steps")
                print(f"    Proven facts: {len(digest.get('proven_facts', []))}")
                for fact in digest.get('proven_facts', [])[:2]:
                    print(f"      - {fact[:80]}")
                print(f"    Strategy: {digest.get('current_strategy', 'N/A')[:80]}")
            
            # Reflection
            if (step - start_step) % solver_config.reflection_interval == 0:
                print(f"\n  Running reflection...")
                
                refl_prompt = build_reflection_prompt(
                    problem=problem,
                    reasoning_history=reasoning_history[-5:],
                    digest_history=digest_history,
                    annotations=annotations,
                    current_step=step
                )
                
                refl_response = model.generate(refl_prompt)
                parsed = parse_reflection_response(refl_response.answer)
                
                reflection_mgr.add_reflection(step, parsed)
                
                print(f"  Reflection:")
                print(f"    Progress: {parsed.get('progress', 'unknown')}")
                print(f"    Recommendation: {parsed.get('recommendation', 'continue')}")
                
                if refl_response.metadata and 'usage' in refl_response.metadata:
                    usage = refl_response.metadata['usage']
                    refl_cost = (usage.get('prompt_tokens', 0) * 0.14 + 
                                usage.get('completion_tokens', 0) * 0.28) / 1_000_000
                    total_cost += refl_cost
        
        except Exception as e:
            print(f"\n  Error: {e}")
            if 'insufficient' in str(e).lower() or 'quota' in str(e).lower():
                print("  Budget exhausted")
                break
            continue

except KeyboardInterrupt:
    print(f"\n\nInterrupted at step {step}")

# Summary
elapsed_total = time.time() - start_time
print(f"\n{'='*80}")
print("CONTINUATION SUMMARY")
print(f"{'='*80}")
print(f"Steps: {start_step} -> {step}")
print(f"New steps: {step - start_step}")
print(f"Time: {elapsed_total/60:.1f} minutes")
print(f"Total cost: ${total_cost:.2f}")
print(f"Reflections: {len(reflection_mgr.reflections)}")
print(f"Digests: {len(digest_history)}")
print("=" * 80)
