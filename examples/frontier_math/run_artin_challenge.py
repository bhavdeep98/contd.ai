"""
Artin's Primitive Root Challenge - 2 Hour Stress Test

This script attempts to solve a Tier 3 FrontierMath problem using:
- DeepSeek R1 API with thinking tokens
- Full contd.ai workflow with mock storage
- Reflection every 5 steps
- Distillation every 10 steps
- Cost tracking and timeout

Goal: Test contd.ai's breaking point on a research-level problem
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace', line_buffering=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("ARTIN'S PRIMITIVE ROOT CHALLENGE - 2 HOUR STRESS TEST")
print("=" * 80)

# Check API key
api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    print("\n❌ Error: DEEPSEEK_API_KEY not found")
    print("   Please create a .env file with your API key:")
    print("   DEEPSEEK_API_KEY=your_key_here")
    print("\n   Or copy .env.example to .env and add your key")
    sys.exit(1)

print(f"\n✅ API Key loaded: {api_key[:8]}...{api_key[-4:]}")

# Load problem
with open("problems/artin_primitive_root.txt", "r") as f:
    problem = f.read()

print(f"\n Problem loaded: {len(problem)} chars")
print(f"\n{problem[:300]}...\n")

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
    max_steps=50,  # Stop after 50 steps
    distill_every=10,  # Distill every 10 steps
    reflection_interval=5,  # Reflect every 5 steps
    cost_budget=0.0  # No artificial limit - let API fail naturally
)

print("=" * 80)
print("CONFIGURATION")
print("=" * 80)
print(f"Model: {model_config.model_name}")
print(f"Max steps: {solver_config.max_steps}")
print(f"Reflection interval: {solver_config.reflection_interval}")
print(f"Distillation interval: {solver_config.distill_every}")
print(f"Cost budget: Run until API balance exhausted")
print(f"Time limit: 2 hours")
print("=" * 80)

# Initialize
model = create_model(model_config)
reflection_mgr = ReflectionManager()

# Tracking
start_time = time.time()
timeout_seconds = 2 * 60 * 60  # 2 hours
total_cost = 0.0
reasoning_history = []
digest_history = []
annotations = []
step = 0
budget_exhausted = False
error_count = 0  # Track errors between reflections
max_errors_before_reflection = 3  # Stop at next reflection if 3+ errors

print(f"\n Starting solver at {datetime.now().strftime('%H:%M:%S')}\n")
print("=" * 80)

try:
    while step < solver_config.max_steps:
        step += 1
        elapsed = time.time() - start_time
        
        # Check timeout
        if elapsed > timeout_seconds:
            print(f"\n TIMEOUT REACHED: {elapsed/3600:.2f} hours")
            break
        
        print(f"\n{'='*80}")
        print(f"STEP {step} | Elapsed: {elapsed/60:.1f}min | Cost: ${total_cost:.2f}")
        print(f"{'='*80}")
        
        # Build prompt
        if step == 1:
            prompt = f"""{problem}

Think step-by-step. Show your reasoning process. You can use Python code if needed."""
        else:
            # Include context
            context_summary = ""
            if digest_history:
                context_summary += f"\n\nPrevious reasoning (compressed):\n{digest_history[-1]}"
            if reasoning_history:
                context_summary += f"\n\nLast step reasoning:\n{reasoning_history[-1][:500]}..."
            
            prompt = f"""Continue working on: {problem}

{context_summary}

Continue your reasoning. Build on what you've done."""
        
        # Generate
        print(f" Generating response...")
        step_start = time.time()
        
        try:
            response = model.generate(prompt)
            step_duration = time.time() - step_start
            
            # Estimate cost (DeepSeek pricing: ~$0.14/$0.28 per 1M tokens)
            if response.metadata and 'usage' in response.metadata:
                usage = response.metadata['usage']
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                step_cost = (input_tokens * 0.14 + output_tokens * 0.28) / 1_000_000
                total_cost += step_cost
                
                print(f" Response received ({step_duration:.1f}s)")
                print(f"   Tokens: {input_tokens} in, {output_tokens} out")
                print(f"   Cost: ${step_cost:.4f} (total: ${total_cost:.2f})")
            else:
                print(f" Response received ({step_duration:.1f}s)")
            
            print(f"   Thinking: {len(response.thinking)} chars")
            print(f"   Answer: {len(response.answer)} chars")
            
            # Store reasoning
            reasoning_history.append(response.thinking)
            
            # Show preview
            print(f"\n    Thinking preview:")
            print(f"   {response.thinking[:400]}...")
            
            # Check for solution indicators
            answer_lower = response.answer.lower()
            if any(keyword in answer_lower for keyword in ['therefore', 'answer is', 'n =', 'result is']):
                print(f"\n    Possible solution detected!")
                print(f"   Answer preview: {response.answer[:300]}...")
            
            # Distillation
            if step % solver_config.distill_every == 0:
                print(f"\n    Running distillation...")
                recent_reasoning = reasoning_history[-solver_config.distill_every:]
                prev_digest = digest_history[-1] if digest_history else None
                
                digest = simple_math_distill(recent_reasoning, prev_digest)
                digest_history.append(digest)
                print(f"    Distilled {len(recent_reasoning)} steps into digest")
                print(f"       Proven facts: {len(digest.get('proven_facts', []))}")
                for fact in digest.get('proven_facts', [])[:3]:
                    print(f"         - {fact[:100]}")
                print(f"       Failed approaches: {len(digest.get('failed_approaches', []))}")
                print(f"       Key insights: {len(digest.get('key_insights', []))}")
                print(f"       Strategy: {digest.get('current_strategy', 'N/A')[:100]}")
            
            # Reflection
            if step % solver_config.reflection_interval == 0:
                print(f"\n    Running reflection...")
                
                # Check if we should stop due to errors
                if error_count >= max_errors_before_reflection:
                    print(f"    Too many errors ({error_count}) since last reflection - stopping")
                    annotations.append(f"Step {step}: Stopped due to {error_count} errors")
                    break
                
                reflection_prompt = build_reflection_prompt(
                    problem=problem,
                    reasoning_history=reasoning_history[-5:],
                    digest_history=digest_history,
                    annotations=annotations,
                    current_step=step
                )
                
                refl_response = model.generate(reflection_prompt)
                parsed = parse_reflection_response(refl_response.answer)
                
                reflection_mgr.add_reflection(step, parsed)
                
                print(f"   Reflection:")
                print(f"     Progress: {parsed.get('progress', 'unknown')}")
                print(f"     Recommendation: {parsed.get('recommendation', 'continue')}")
                
                if parsed.get('should_backtrack'):
                    print(f"       Suggests backtracking!")
                    annotations.append(f"Step {step}: Reflection suggests backtrack")
                
                # Reset error count after reflection
                error_count = 0
                
                # Update cost for reflection
                if refl_response.metadata and 'usage' in refl_response.metadata:
                    usage = refl_response.metadata['usage']
                    refl_cost = (usage.get('prompt_tokens', 0) * 0.14 + 
                                usage.get('completion_tokens', 0) * 0.28) / 1_000_000
                    total_cost += refl_cost
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for budget/quota errors
            if any(keyword in error_str for keyword in ['insufficient', 'quota', 'balance', 'limit', 'exceeded']):
                print(f"\n    API BUDGET EXHAUSTED: {e}")
                budget_exhausted = True
                break
            
            print(f"\n    Error in step {step}: {e}")
            annotations.append(f"Step {step}: Error - {str(e)[:100]}")
            error_count += 1  # Increment error counter
            continue

except KeyboardInterrupt:
    print(f"\n\n  Interrupted by user at step {step}")
except Exception as e:
    error_str = str(e).lower()
    if any(keyword in error_str for keyword in ['insufficient', 'quota', 'balance', 'limit', 'exceeded']):
        print(f"\n\n API BUDGET EXHAUSTED: {e}")
        budget_exhausted = True
    else:
        print(f"\n\n Unexpected error: {e}")
        import traceback
        traceback.print_exc()

# Final summary
elapsed_total = time.time() - start_time
print(f"\n{'='*80}")
print("FINAL SUMMARY")
print(f"{'='*80}")
print(f"Steps completed: {step}")
print(f"Total time: {elapsed_total/3600:.2f} hours ({elapsed_total/60:.1f} minutes)")
print(f"Total cost: ${total_cost:.2f}")
print(f"Budget exhausted: {'Yes' if budget_exhausted else 'No'}")
print(f"Reasoning history: {len(reasoning_history)} entries")
print(f"Digests created: {len(digest_history)}")
print(f"Reflections: {len(reflection_mgr.reflections)}")
print(f"Annotations: {len(annotations)}")

if reflection_mgr.reflections:
    print(f"\n Reflection Summary:")
    for i, refl in enumerate(reflection_mgr.reflections[-5:]):  # Last 5
        print(f"  Step {refl['step']}: {refl.get('recommendation', 'N/A')}")

print(f"\n{'='*80}")
print("CONTD.AI STRESS TEST COMPLETE")
print(f"{'='*80}")
print(f"\nThis test demonstrated:")
print(f"   Long-running workflow ({elapsed_total/60:.1f} minutes)")
print(f"   Iterative reasoning ({step} steps)")
print(f"   Context preservation (reasoning history + digests)")
print(f"   Periodic reflection ({len(reflection_mgr.reflections)} reflections)")
print(f"   Cost tracking (${total_cost:.2f})")
print(f"   Timeout handling")
print(f"\nNext: Integrate full contd.ai workflow with persistence and recovery")
print("=" * 80)

