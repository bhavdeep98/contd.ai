# Contd.ai Quick Start Video Script
## "Contd.ai in 5 Minutes: Durable AI Workflows"

---

## SCENE 1: The Problem (0:00 - 0:30)

**Visual:** Animation showing an AI agent crashing mid-task, losing all progress.

**Audio:**
> "Your AI agent is halfway through a complex task — it's made 10 API calls, processed data, and then... crash. Everything's lost. You start over.
>
> Contd.ai solves this. It's a durable execution engine that makes your workflows resumable by default. Let's see how it works."

---

## SCENE 2: Core Concepts — Steps & Workflows (0:30 - 1:30)

**Visual:** Code editor showing the basic example.

**Audio:**
> "Contd.ai has two building blocks: steps and workflows."

**Code:**
```python
from contd.sdk import workflow, step

@step()
def fetch_data(source: str) -> dict:
    """Each step is automatically checkpointed."""
    return {"items": [{"id": 1, "value": 100}, {"id": 2, "value": 200}]}

@step()
def transform_data(data: dict) -> dict:
    """If we crash here, fetch_data won't re-run."""
    return {"doubled": [item["value"] * 2 for item in data["items"]]}

@step()
def save_results(data: dict) -> dict:
    return {"saved": True, "count": len(data["doubled"])}

@workflow()
def my_pipeline(source: str) -> dict:
    raw = fetch_data(source)       # ✓ Checkpointed
    transformed = transform_data(raw)  # ✓ Checkpointed
    return save_results(transformed)   # ✓ Checkpointed
```

**Audio (continued):**
> "A `@step` is an atomic unit of work — automatically saved after completion. A `@workflow` orchestrates steps. If your workflow crashes after step 2, it resumes from step 3, not from the beginning."

**Overlay:** `@step` = Checkpoint | `@workflow` = Orchestrator

---

## SCENE 3: Resilience — Retries & Timeouts (1:30 - 2:15)

**Visual:** Show retry configuration.

**Audio:**
> "Real APIs fail. Contd.ai handles this with built-in retry policies."

**Code:**
```python
from contd.sdk import step, StepConfig, RetryPolicy
from datetime import timedelta

@step(StepConfig(
    retry=RetryPolicy(
        max_attempts=3,
        backoff_base=2.0,  # Exponential: 2s, 4s, 8s...
    ),
    timeout=timedelta(seconds=30)
))
def call_external_api(url: str) -> dict:
    """Retries automatically on failure, times out after 30s."""
    response = requests.get(url)
    return response.json()
```

**Audio (continued):**
> "Exponential backoff, configurable retries, timeout protection — all declarative. Your step just focuses on the logic."

**Overlay:** Retry + Timeout = Production-Ready

---

## SCENE 4: The Killer Feature — Epistemic Savepoints (2:15 - 3:30)

**Visual:** Show AI agent code with savepoint creation.

**Audio:**
> "Here's what makes Contd.ai special for AI agents: epistemic savepoints. They capture not just execution state, but your agent's reasoning state."

**Code:**
```python
from contd.sdk import step, StepConfig, ExecutionContext

@step(StepConfig(savepoint=True))
def agent_think(question: str, context: dict) -> dict:
    """Agent reasoning with epistemic savepoint."""
    ctx = ExecutionContext.current()
    
    # Your LLM call here
    decision = call_llm(f"Question: {question}, Context: {context}")
    
    # 🔑 Save the agent's mental state
    ctx.create_savepoint({
        "goal_summary": f"Answering: {question}",
        "hypotheses": ["User needs billing help", "May need escalation"],
        "decisions": ["Check knowledge base first"],
        "next_step": "search_kb"
    })
    
    return {"decision": decision}
```

**Audio (continued):**
> "When you create a savepoint, you're capturing what the agent was thinking — its hypotheses, questions, and decisions. If it crashes, it resumes with full context. And you can inspect this state for debugging."

**Overlay:** Epistemic Savepoint = Agent's "Mental State"

---

## SCENE 5: Time-Travel Debugging (3:30 - 4:15)

**Visual:** Terminal showing CLI commands.

**Audio:**
> "The best part? Time-travel debugging. You can fork any workflow from any savepoint."

**CLI Demo:**
```bash
# See all savepoints
$ contd inspect my-workflow-123
Savepoints:
  [abc123] Step 2 - "Searching knowledge base"
  [def456] Step 4 - "Generating response"
  [ghi789] Step 6 - "Routing decision"

# Fork from step 4 to debug
$ contd time-travel my-workflow-123 def456
Created new workflow: my-workflow-123-tt-xyz789
Resume with: contd resume my-workflow-123-tt-xyz789
```

**Audio (continued):**
> "Your agent made a wrong decision at step 4? Fork from that savepoint, tweak the logic, and re-run — without re-calling all those expensive APIs from steps 1-3."

**Overlay:** Time-Travel = Debug Without Re-Running

---

## SCENE 6: Get Started (4:15 - 5:00)

**Visual:** Quick setup commands, then show examples directory.

**Audio:**
> "Getting started takes 30 seconds."

**CLI:**
```bash
# Install
pip install contd

# Initialize project
contd init

# Run your first workflow
contd run my_pipeline --input '{"source": "api.example.com"}'
```

**Audio (continued):**
> "We have 12 production-ready examples in the repo: RAG pipelines, order processing with saga pattern, approval workflows, research agents, code review bots, and more.
>
> Contd.ai — durable execution for AI agents. Your workflows crash, but your progress doesn't. Check out the GitHub repo to get started."

**Final Screen:**
```
github.com/bhavdeep98/contd.ai

✓ Durable Execution — Resumable by default
✓ Epistemic Savepoints — Capture AI reasoning
✓ Time-Travel Debugging — Fork from any point
✓ Multi-Language — Python, TypeScript, Go, Java

pip install contd
```

---

## QUICK REFERENCE (For Overlay Graphics)

| Concept | One-Liner |
|---------|-----------|
| **@step** | Atomic, checkpointed unit of work |
| **@workflow** | Orchestrates steps into a flow |
| **RetryPolicy** | Automatic retries with backoff |
| **Epistemic Savepoint** | Captures agent's reasoning state |
| **Time-Travel** | Fork workflow from any savepoint |

---

*Total runtime: ~5 minutes*
