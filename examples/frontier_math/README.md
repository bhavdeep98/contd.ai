# FrontierMath Solver with Contd.ai

This example demonstrates how to use contd.ai to solve [FrontierMath](https://arxiv.org/abs/2411.04872) problems using reasoning models with thinking token capture.

## What is FrontierMath?

FrontierMath is a benchmark of exceptionally challenging mathematics problems where:
- Current SOTA models solve **under 2%** of problems
- Problems span number theory, real analysis, algebraic geometry, category theory
- A typical problem takes human mathematicians **hours to days**
- Problems require multi-step reasoning with backtracking

## Why Contd.ai?

Reasoning models (DeepSeek R1, Claude Extended Thinking) generate massive thinking token chains. Contd.ai turns this into an advantage:

1. **Durability**: Never lose progress on long reasoning chains (crashes resume exactly)
2. **Thinking Token Capture**: All reasoning preserved via `ctx.ingest()`
3. **Distillation**: Compress 100K+ tokens into structured mathematical insights
4. **Backtracking**: Time-travel to savepoints when reasoning hits dead ends
5. **Human Review**: Visualize reasoning, approve/reject steps via web UI
6. **Cost Tracking**: Monitor token usage across multi-hour runs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FrontierMath Problem                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Reasoning Model (Local or API)                  │
│  • DeepSeek R1 (via Ollama or API)                          │
│  • Claude Extended Thinking                                  │
│  • Returns: thinking_tokens + final_answer                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Contd.ai Workflow                          │
│  • ctx.ingest(thinking_tokens) - Capture reasoning          │
│  • ctx.annotate() - Developer breadcrumbs                    │
│  • Distillation every 5 steps - Compress to insights        │
│  • Savepoints at decision points - Enable backtracking      │
│  • Health monitoring - Detect context degradation           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Durable Persistence                         │
│  • Postgres: Event journal, leases                           │
│  • S3: Snapshots with reasoning ledger                       │
│  • Resume on crash with full reasoning context               │
└─────────────────────────────────────────────────────────────┘
```

## Files

- `solver.py` - Main FrontierMath solver workflow
- `models.py` - Unified interface for reasoning models (DeepSeek, Claude, local)
- `distill.py` - Mathematical reasoning distillation functions
- `benchmark.py` - Benchmark runner for FrontierMath problems
- `config.py` - Configuration for models and solver parameters
- `problems/` - Sample FrontierMath problems for testing
- `results/` - Benchmark results and analysis

## Setup

### 1. Install Dependencies

```bash
pip install contd[all]
pip install openai anthropic  # For API models
```

### 2. Configure Database

```bash
# Start Postgres and S3 (MinIO)
cd docker
docker-compose up -d

# Initialize schema
psql -d contd_db -f ../contd/persistence/schema.sql
```

### 3. Configure Models

**Option A: Local with Ollama**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull DeepSeek R1
ollama pull deepseek-r1

# Configure
export REASONING_MODEL=ollama
export OLLAMA_BASE_URL=http://localhost:11434
```

**Option B: DeepSeek API**
```bash
export REASONING_MODEL=deepseek-api
export DEEPSEEK_API_KEY=your_key_here
```

**Option C: Claude Extended Thinking**
```bash
export REASONING_MODEL=claude
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

### Solve a Single Problem

```bash
python solver.py --problem "problems/number_theory_01.txt"
```

### Run Benchmark

```bash
python benchmark.py --problems-dir problems/ --max-problems 10
```

### Resume a Crashed Workflow

```bash
python solver.py --resume wf-abc123
```

### Time-Travel to Savepoint

```bash
# List savepoints
contd inspect wf-abc123 --savepoints

# Branch from savepoint
contd time-travel wf-abc123 savepoint-step-15
```

### View Reasoning in Browser

```bash
# Start API server
python -m contd.api.server

# Open ledger viewer
open http://localhost:8000/ledger-viewer
# Enter workflow ID to see thinking tokens timeline
```

## Example Output

```
=== FrontierMath Solver ===
Problem: Prove that for all primes p > 3, p^2 - 1 is divisible by 24

📖 Step 0: Initial analysis
  Captured 2,341 chars of reasoning
  Decision: Try algebraic factorization

📖 Step 1: Factorization
  Captured 3,127 chars of reasoning
  Decision: Factor as (p-1)(p+1)

🔄 Distilled 5,468 chars → 847 chars
  Key insight: Consecutive even numbers

📖 Step 2: Divisibility analysis
  Captured 2,891 chars of reasoning
  Decision: One of p-1, p+1 divisible by 4

💾 Savepoint created at step 3
  Goal: Prove divisibility by 3

📖 Step 3: Modular arithmetic
  Captured 4,102 chars of reasoning
  Decision: p ≡ 1 or 2 (mod 3)

✅ Solution found at step 4
  Verified: Correct
  Total reasoning: 12,461 chars compressed to 2,103 chars
  Cost: $0.23
```

## Configuration

Edit `config.py` to customize:

```python
SOLVER_CONFIG = {
    "max_steps": 100,              # Maximum reasoning steps
    "distill_every": 5,            # Distill every N steps
    "context_budget": 200_000,     # Context budget in bytes
    "cost_budget": 10.00,          # Max cost per problem in USD
    "thinking_budget": 32_000,     # Thinking tokens for Claude
    "savepoint_on_decision": True, # Create savepoints at decisions
}
```

## Benchmark Results

Results are saved to `results/benchmark_TIMESTAMP.json`:

```json
{
  "total_problems": 50,
  "solved": 3,
  "solve_rate": 0.06,
  "avg_steps": 47.2,
  "avg_cost": 4.32,
  "avg_time_seconds": 1834.5,
  "problems": [...]
}
```

## Advanced Usage

### Meta-Reasoning and Self-Reflection

The solver includes meta-reasoning capabilities where the model periodically reflects on its own reasoning:

```python
solver = FrontierMathSolver(
    model_config,
    solver_config,
    reflection_interval=10  # Reflect every 10 steps
)
```

**What happens during reflection:**
1. Model reviews its thinking history (last 5 steps of raw reasoning)
2. Model sees compressed digests from earlier steps
3. Model evaluates progress and effectiveness
4. Model decides: continue, modify, or change approach
5. Model can detect when it's stuck and suggest backtracking

**The model sees:**
- Raw thinking tokens from recent steps
- Distilled insights from earlier steps
- All decision annotations
- Previous reflection summaries

**Example reflection prompt:**
```
You've been working on this for 25 steps.

EARLIER REASONING (COMPRESSED):
Digest 1: Proven: [p^2-1 = (p-1)(p+1)], Strategy: algebraic factorization
Digest 2: Proven: [one of p-1, p+1 divisible by 4], Strategy: divisibility analysis

RECENT REASONING (LAST 5 STEPS):
Step 21: Trying modular arithmetic approach...
Step 22: p ≡ 1 or 2 (mod 3)...
Step 23: Therefore p^2 ≡ 1 (mod 3)...

KEY DECISIONS:
Step 15: Chose algebraic factorization
Step 20: Switched to modular arithmetic

Now reflect: Are you making progress? Should you continue or try something else?
```

**Run the demo:**
```bash
python demo_reflection.py
```

### Custom Distillation Function

```python
def my_math_distill(raw_chunks: list[str], previous: dict | None) -> dict:
    """Custom distillation for specific math domain."""
    # Use LLM to extract mathematical structure
    return {
        "proven_lemmas": extract_lemmas(raw_chunks),
        "failed_approaches": extract_failures(raw_chunks),
        "current_strategy": extract_strategy(raw_chunks)
    }

# Use in solver
solver = FrontierMathSolver(distill_fn=my_math_distill)
```

### Human-in-the-Loop Review

```python
# Enable review mode
solver = FrontierMathSolver(require_review=True)

# Solver pauses at each savepoint
# Review via web UI at http://localhost:8000/ledger-viewer
# Approve/reject reasoning steps
```

## Performance Tips

1. **Use distillation aggressively** - Compress every 3-5 steps to prevent context rot
2. **Create savepoints at decisions** - Enable backtracking without full replay
3. **Monitor context health** - Watch for declining output or high retry rates
4. **Use local models for iteration** - Ollama for fast testing, API for final runs
5. **Set cost budgets** - Prevent runaway spending on hard problems

## Troubleshooting

**Problem: Thinking tokens not captured**
- Ensure model returns `reasoning_content` (DeepSeek) or `thinking` blocks (Claude)
- Check model adapter in `models.py`

**Problem: Context degradation**
- Reduce `distill_every` to compress more frequently
- Increase `context_budget` if hitting limits
- Check health signals via `ctx.context_health()`

**Problem: Solver gets stuck**
- Review reasoning via ledger viewer
- Time-travel to earlier savepoint
- Try different reasoning strategy

## References

- [FrontierMath Paper](https://arxiv.org/abs/2411.04872)
- [DeepSeek R1 API Docs](https://api-docs.deepseek.com/guides/reasoning_model)
- [Claude Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Contd.ai Documentation](../../docs/)

## License

Same as parent project (BSL 1.1)
