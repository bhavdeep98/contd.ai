# Contd.ai Examples

Real-world AI agent workflow examples demonstrating Contd.ai capabilities.

## Quick Start

```bash
# Install dependencies
pip install -e ..
pip install requests openai

# Run any example
python 03_ai_agent.py
```

## Examples

| # | Example | Description |
|---|---------|-------------|
| 03 | [AI Agent](03_ai_agent.py) | LLM-powered agent with tools |
| 04 | [RAG Pipeline](04_rag_pipeline.py) | Retrieval-augmented generation |
| 10 | [Research Agent](10_research_agent.py) | Multi-source research with savepoints |
| 11 | [Code Review Agent](11_code_review_agent.py) | Automated PR review |
| 12 | [Customer Support](12_customer_support.py) | Support ticket automation |
| 13 | [Context Preservation](13_context_preservation.py) | Reasoning ledger and distillation |
| 14 | [Ledger Visualization](14_ledger_visualization.py) | Human-in-the-loop review |
| - | [**FrontierMath Solver**](frontier_math/) | **Complete benchmark solver** |

## Running Examples

### Local Mode (SQLite)

```bash
# Initialize local database
contd init

# Run example
python 03_ai_agent.py
```

### Server Mode (PostgreSQL)

```bash
# Start server
export DATABASE_URL=postgresql://user:pass@localhost/contd
python -m contd.api.server

# In another terminal
export CONTD_API_KEY=sk_live_...
python 03_ai_agent.py --server
```

## Example Descriptions

### AI Agent (03)
Tool-using LLM agent with durable execution. Demonstrates how agents can use external tools while maintaining state across failures.

### RAG Pipeline (04)
Retrieval-augmented generation workflow. Shows document retrieval, embedding, and LLM response generation with checkpointing.

### Research Agent (10)
Multi-source research agent with epistemic savepoints. Demonstrates saving agent reasoning state (hypotheses, goals, decisions) alongside execution state.

### Code Review Agent (11)
Automated code review using LLM analysis. Reviews pull requests, identifies issues, and suggests improvements.

### Customer Support (12)
Support ticket automation with LLM-powered responses. Handles ticket classification, response generation, and escalation.

### Context Preservation (13)
Demonstrates contd.ai's context preservation features: reasoning ledger, distillation, health monitoring, and restore with context.

### Ledger Visualization (14)
Shows how to use the reasoning ledger API and web UI for human-in-the-loop review of agent reasoning.

### FrontierMath Solver (frontier_math/)
**Complete implementation** demonstrating how to solve challenging mathematics problems using reasoning models (DeepSeek R1, Claude Extended Thinking) with:
- Durable execution across multi-hour reasoning chains
- Thinking token capture via `ctx.ingest()`
- Context preservation and distillation
- Savepoints for backtracking
- Human-in-the-loop review
- Benchmark runner for FrontierMath problems

See [frontier_math/README.md](frontier_math/README.md) for full documentation.
