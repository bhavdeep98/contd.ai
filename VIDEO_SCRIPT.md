# Contd.ai Video Walkthrough Script
## "Walking Through Contd.ai: Durable Execution for AI Agents"

---

## SCENE 1: Introduction (0:00 - 0:45)

**Visual:** Screen recording of the GitHub repository homepage, zooming into the tagline and key features.

**Audio Script:**
> "Welcome to this walkthrough of Contd.ai — the lightweight framework for building durable AI agent workflows. If you're building long-running agents that need to pause, resume, and recover from crashes without losing context, this is the engine for you.
>
> Today, we're going to walk through the `examples/` directory, starting simple and building up to production-ready patterns. By the end, you'll understand how to build workflows that are resumable by default."

**Overlay Text:**
- ✅ Durable Execution
- ✅ Multi-Tenancy
- ✅ Epistemic Savepoints
- ✅ Time-Travel Debugging

---

## SCENE 2: The Basic Syntax — Your First Pipeline (0:45 - 2:30)

**Visual:** Display `examples/01_basic_pipeline.py` with syntax highlighting. Highlight decorators as you explain.

**Audio Script:**
> "Let's start with the fundamentals. Contd.ai uses two core decorators: `@step` and `@workflow`. Here's a basic data pipeline:"

**Code Snippet (show on screen):**
```python
from contd.sdk import workflow, step

@step()
def fetch_data(source: str) -> dict:
    """Fetch data from a source."""
    print(f"Fetching data from {source}...")
    return {
        "items": [
            {"id": 1, "name": "Item A", "value": 100},
            {"id": 2, "name": "Item B", "value": 200},
        ]
    }

@step()
def transform_data(data: dict) -> dict:
    """Transform the fetched data."""
    items = data.get("items", [])
    transformed = [
        {**item, "value_doubled": item["value"] * 2}
        for item in items
    ]
    return {"transformed_items": transformed}

@step()
def aggregate_results(data: dict) -> dict:
    """Aggregate the transformed data."""
    items = data.get("transformed_items", [])
    total = sum(item["value_doubled"] for item in items)
    return {"total_value": total, "item_count": len(items)}

@workflow()
def data_pipeline(source: str) -> dict:
    """
    A basic data processing pipeline.
    Each step is automatically checkpointed.
    """
    raw_data = fetch_data(source)
    transformed = transform_data(raw_data)
    aggregated = aggregate_results(transformed)
    return aggregated
```

**Audio (continued):**
> "Notice how natural this looks — it's just Python. But here's the magic: each `@step` is automatically checkpointed. If this workflow crashes after `transform_data` completes, it will resume from there, not from the beginning. No lost work, no re-fetching data."

**Overlay Text:**
- `@step` = Atomic unit of work (checkpointed)
- `@workflow` = Orchestrates steps
- State persisted after every step

---

## SCENE 3: Resilience — Retry & Timeout Patterns (2:30 - 4:00)

**Visual:** Display `examples/02_retry_timeout.py`. Highlight the `StepConfig` and `RetryPolicy`.

**Audio Script:**
> "Real-world APIs fail. Networks timeout. Contd.ai handles this with built-in retry policies and timeouts. Let's look at how to make your steps resilient:"

**Code Snippet:**
```python
from datetime import timedelta
from contd.sdk import workflow, step, StepConfig, RetryPolicy

@step(StepConfig(
    retry=RetryPolicy(
        max_attempts=3,
        backoff_base=2.0,      # Exponential backoff
        backoff_max=30.0,
        backoff_jitter=0.5    # Randomization to prevent thundering herd
    )
))
def flaky_api_call(endpoint: str) -> dict:
    """
    Call an unreliable API with automatic retry.
    
    Retry schedule:
    - Attempt 1: immediate
    - Attempt 2: ~2 seconds delay
    - Attempt 3: ~4 seconds delay
    """
    import random
    if random.random() < 0.5:
        raise ConnectionError("API temporarily unavailable")
    return {"data": "success", "endpoint": endpoint}

@step(StepConfig(timeout=timedelta(seconds=5)))
def slow_operation() -> dict:
    """Operation with timeout protection."""
    import time
    time.sleep(2)  # Completes in 2 seconds
    return {"status": "done"}

@step(StepConfig(
    timeout=timedelta(seconds=10),
    retry=RetryPolicy(
        max_attempts=2,
        retryable_exceptions=[TimeoutError, ConnectionError]
    )
))
def robust_external_call(url: str) -> dict:
    """Combined timeout and retry for external calls."""
    return {"response": "OK", "url": url}
```

**Audio (continued):**
> "The `RetryPolicy` gives you exponential backoff with jitter — industry best practice for distributed systems. You can also specify which exceptions are retryable. Combine this with timeouts, and your workflows become production-ready."

**Overlay Text:**
- Exponential backoff prevents API overload
- Jitter prevents thundering herd
- Timeout protects against hanging operations

---

## SCENE 4: AI Agents with Tools (4:00 - 6:30)

**Visual:** Display `examples/03_ai_agent.py`. This is where it gets interesting.

**Audio Script:**
> "Now let's build an actual AI agent. This agent can think, use tools, and most importantly — save its reasoning state with epistemic savepoints."

**Code Snippet (Part 1 - Tools):**
```python
from contd.sdk import workflow, step, StepConfig, ExecutionContext

@step()
def get_weather(location: str) -> dict:
    """Get weather for a location."""
    return {"location": location, "temperature": 68, "conditions": "Sunny"}

@step()
def calculator(expression: str) -> dict:
    """Evaluate a mathematical expression."""
    result = eval(expression)
    return {"expression": expression, "result": result}

@step()
def web_search(query: str) -> dict:
    """Search the web."""
    return {
        "query": query,
        "results": [
            {"title": "AI Breakthrough 2025", "url": "https://example.com/1"},
        ]
    }
```

**Audio (continued):**
> "First, we define our tools as steps. Each tool is independently checkpointed — if the agent crashes after calling `get_weather`, that result is preserved."

**Code Snippet (Part 2 - Agent Reasoning with Epistemic Savepoint):**
```python
@step(StepConfig(savepoint=True))
def agent_think(question: str, context: dict, iteration: int) -> dict:
    """
    Agent reasoning step with epistemic savepoint.
    Saves the agent's reasoning state for inspection and recovery.
    """
    ctx = ExecutionContext.current()
    
    # Call LLM (simulated)
    response = call_llm(f"Question: {question}\nContext: {context}")
    
    # Parse response
    if response.startswith("TOOL:"):
        tool_call = response[5:].strip()
        action = "use_tool"
    else:
        action = "answer"
    
    # 🔑 Create epistemic savepoint - THIS IS THE KEY FEATURE
    ctx.create_savepoint({
        "goal_summary": f"Answering: {question}",
        "hypotheses": [
            f"Tool {tool_call} will help" if action == "use_tool" 
            else "Have enough info to answer"
        ],
        "questions": ["Is this the right approach?"],
        "decisions": [f"Decided to {action}"],
        "next_step": tool_call if action == "use_tool" else "provide_answer"
    })
    
    return {"action": action, "tool_call": tool_call, "iteration": iteration}
```

**Audio (continued):**
> "Here's the killer feature: epistemic savepoints. When the agent thinks, we capture not just the execution state, but the agent's reasoning state — its hypotheses, questions, and decisions. If the agent crashes mid-reasoning, we can restore exactly where it was mentally, not just computationally."

**Code Snippet (Part 3 - Agent Loop):**
```python
@workflow()
def ai_agent(question: str, max_iterations: int = 5) -> dict:
    """
    Durable AI agent workflow.
    Each step is checkpointed. If the agent crashes,
    it resumes with full reasoning context via savepoints.
    """
    context = {"question": question}
    
    for i in range(max_iterations):
        # Agent thinks (creates epistemic savepoint)
        thought = agent_think(question, context, i)
        
        if thought["action"] == "answer":
            return {
                "question": question,
                "answer": thought["response"],
                "iterations": i + 1
            }
        
        # Execute tool and update context
        context = execute_tool(thought["tool_call"], context)
    
    return {"answer": "Could not determine answer", "iterations": max_iterations}
```

**Overlay Text:**
- Epistemic Savepoints = Agent's "mental state"
- Hypotheses, goals, decisions preserved
- Time-travel debugging for AI reasoning

---

## SCENE 5: RAG Pipeline (6:30 - 8:30)

**Visual:** Display `examples/04_rag_pipeline.py`. Show the full pipeline flow.

**Audio Script:**
> "Let's build a production RAG pipeline. This is where durability really shines — if your LLM call fails, you don't have to re-embed and re-retrieve."

**Code Snippet:**
```python
from contd.sdk import workflow, step, StepConfig, RetryPolicy

@step()
def embed_query(query: str) -> dict:
    """Convert query to embedding vector."""
    # In production: call OpenAI embeddings API
    embedding = [0.1, 0.2, 0.3]  # Simulated
    return {"query": query, "embedding": embedding}

@step()
def retrieve_documents(query_embedding: list, top_k: int = 3) -> dict:
    """Retrieve relevant documents from vector database."""
    # Calculate similarities, return top_k docs
    return {
        "documents": [
            {"id": 1, "text": "Contd.ai provides durable execution..."},
            {"id": 2, "text": "Workflows can be paused and resumed..."},
        ],
        "scores": [0.95, 0.87]
    }

@step()
def rerank_documents(query: str, documents: list) -> dict:
    """Rerank documents for better relevance."""
    # In production: use a cross-encoder model
    return {"reranked_documents": documents}

@step(StepConfig(
    retry=RetryPolicy(max_attempts=3, backoff_base=2.0)
))
def generate_response(query: str, context_docs: list) -> dict:
    """Generate response using LLM with retrieved context."""
    # In production: call OpenAI/Anthropic API
    context = "\n".join([doc["text"] for doc in context_docs])
    response = f"Based on the documentation: {context_docs[0]['text']}"
    return {"query": query, "response": response, "sources": [1, 2]}

@workflow()
def rag_pipeline(query: str) -> dict:
    """
    Complete RAG pipeline - each step checkpointed.
    If generation fails, retrieval results are preserved.
    """
    embedded = embed_query(query)
    retrieved = retrieve_documents(embedded["embedding"])
    reranked = rerank_documents(query, retrieved["documents"])
    response = generate_response(query, reranked["reranked_documents"])
    return {"answer": response["response"], "sources": response["sources"]}
```

**Audio (continued):**
> "Notice the retry policy on `generate_response`. LLM APIs can be flaky. If the generation fails, we retry — but we don't re-embed or re-retrieve. Those expensive operations are already checkpointed."

**Overlay Text:**
- Embed → Retrieve → Rerank → Generate
- Each step independently recoverable
- No wasted API calls on retry

---

## SCENE 6: Saga Pattern — E-Commerce Order Processing (8:30 - 11:00)

**Visual:** Display `examples/05_order_processing.py`. Show a diagram of the saga flow.

**Audio Script:**
> "Contd.ai isn't just for AI. Here's an e-commerce order workflow implementing the Saga Pattern — the gold standard for distributed transactions."

**Code Snippet (Main Flow):**
```python
@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def validate_order(order: dict) -> dict:
    """Validate order details."""
    if not order.get("items"):
        raise OrderError("Order has no items")
    return {"validated": True, "order_id": order["id"]}

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def reserve_inventory(order: dict) -> dict:
    """Reserve inventory for order items."""
    reservations = []
    for item in order["items"]:
        reservations.append({
            "sku": item["sku"],
            "quantity": item["quantity"],
            "reservation_id": f"res-{item['sku']}-{order['id']}"
        })
    return {"reservations": reservations}

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def charge_payment(order: dict) -> dict:
    """Process payment for the order."""
    return {"payment_id": f"pay-{order['id']}", "status": "charged"}

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def create_shipment(order: dict, reservations: list) -> dict:
    """Create shipment for the order."""
    return {"shipment_id": f"ship-{order['id']}", "tracking_number": f"TRK{order['id']}"}
```

**Code Snippet (Compensation Steps):**
```python
# Compensation steps (for rollback)
@step()
def release_inventory(reservations: list) -> dict:
    """Release reserved inventory (compensation)."""
    return {"released": [r["reservation_id"] for r in reservations]}

@step()
def refund_payment(payment: dict) -> dict:
    """Refund payment (compensation)."""
    return {"refund_id": f"ref-{payment['payment_id']}", "status": "refunded"}

@step()
def cancel_shipment(shipment: dict) -> dict:
    """Cancel shipment (compensation)."""
    return {"canceled": True, "shipment_id": shipment["shipment_id"]}
```

**Code Snippet (Saga Workflow with Compensation):**
```python
@workflow()
def process_order(order: dict) -> dict:
    """
    Process an e-commerce order with saga pattern.
    If any step fails, compensating transactions maintain consistency.
    """
    completed = {}
    
    try:
        validate_order(order)
        
        inventory = reserve_inventory(order)
        completed["inventory"] = inventory
        
        payment = charge_payment(order)
        completed["payment"] = payment
        
        shipment = create_shipment(order, inventory["reservations"])
        completed["shipment"] = shipment
        
        return {"status": "completed", "order_id": order["id"]}
        
    except Exception as e:
        print(f"Order failed: {e}. Running compensations...")
        
        # Compensate in REVERSE order
        if "shipment" in completed:
            cancel_shipment(completed["shipment"])
        if "payment" in completed:
            refund_payment(completed["payment"])
        if "inventory" in completed:
            release_inventory(completed["inventory"]["reservations"])
        
        return {"status": "failed", "error": str(e), "compensated": list(completed.keys())}
```

**Audio (continued):**
> "The saga pattern handles distributed transactions. If shipping fails after payment, we automatically refund and release inventory. Each compensation step is also checkpointed — if the compensation itself fails, we can resume it."

**Overlay Text:**
- Saga Pattern = Distributed transaction management
- Compensations run in reverse order
- Each compensation is also durable

---

## SCENE 7: Human-in-the-Loop — Approval Workflows (11:00 - 13:00)

**Visual:** Display `examples/07_approval_workflow.py`. Show the approval chain diagram.

**Audio Script:**
> "Sometimes you need a human in the loop. Contd.ai can pause indefinitely waiting for external signals — like manager approvals."

**Code Snippet:**
```python
@step()
def determine_approvers(request: dict) -> dict:
    """Determine required approvers based on request amount."""
    if request["amount"] < 1000:
        approvers = ["manager"]
    elif request["amount"] < 10000:
        approvers = ["manager", "director"]
    else:
        approvers = ["manager", "director", "vp"]
    
    return {"approvers": approvers}

@step(StepConfig(savepoint=True))
def wait_for_approval(approver: str, request: dict, timeout_seconds: int = 60) -> dict:
    """
    Wait for approval from an approver.
    Creates savepoint while waiting so workflow state is preserved.
    """
    ctx = ExecutionContext.current()
    
    # Create savepoint while waiting
    ctx.create_savepoint({
        "goal_summary": f"Waiting for {approver} approval",
        "hypotheses": ["Approver will respond within timeout"],
        "questions": [f"Will {approver} approve?"],
        "decisions": [],
        "next_step": "process_approval_response"
    })
    
    # In production: poll database for approval status
    # Workflow can be suspended here and resumed when approval arrives
    
    return {"approver": approver, "decision": "approved", "comments": "Looks good!"}

@workflow()
def approval_workflow(request: dict) -> dict:
    """
    Multi-step approval workflow.
    Savepoints created while waiting for approvals.
    """
    submitted = submit_request(request)
    approval_config = determine_approvers(submitted)
    
    approvals = []
    for approver in approval_config["approvers"]:
        notify_approver(approver, submitted)
        approval = wait_for_approval(approver, submitted)
        approvals.append(approval)
        
        # Short-circuit on rejection
        if approval["decision"] != "approved":
            break
    
    result = process_approval_result(submitted, approvals)
    
    if result["final_status"] == "approved":
        execute_approved_request(submitted)
    
    return result
```

**Audio (continued):**
> "The workflow creates a savepoint while waiting. If the server restarts, the workflow resumes exactly where it was — still waiting for that approval. The lease system ensures no duplicate processing."

**Overlay Text:**
- Workflows can pause indefinitely
- Savepoints preserve waiting state
- Lease management prevents duplicates

---

## SCENE 8: Batch Processing with Progress Tracking (13:00 - 14:30)

**Visual:** Display `examples/08_batch_processing.py`. Show progress bar animation.

**Audio Script:**
> "Processing millions of records? Contd.ai handles batch processing with progress tracking via savepoints."

**Code Snippet:**
```python
@step(StepConfig(savepoint=True))
def process_batch(batch_num: int, item_ids: list, total_batches: int) -> dict:
    """
    Process a single batch of items.
    Creates a savepoint after each batch for progress tracking.
    """
    ctx = ExecutionContext.current()
    
    results = []
    for item_id in item_ids:
        # Process each item
        results.append({"id": item_id, "status": "processed"})
    
    # Create savepoint with progress
    progress = (batch_num + 1) / total_batches * 100
    ctx.create_savepoint({
        "goal_summary": f"Batch processing: {progress:.1f}% complete",
        "decisions": [f"Completed batch {batch_num + 1}"],
        "next_step": f"Process batch {batch_num + 2}" if batch_num + 1 < total_batches else "Finalize"
    })
    
    return {"batch_num": batch_num, "processed": len(results)}

@workflow()
def batch_processing_workflow(source: str, batch_size: int = 10) -> dict:
    """
    Process large dataset in batches.
    If workflow crashes, resumes from last completed batch.
    """
    batch_info = fetch_batch_ids(source, batch_size)
    
    batch_results = []
    for i, batch_ids in enumerate(batch_info["batches"]):
        result = process_batch(i, batch_ids, batch_info["num_batches"])
        batch_results.append(result)
    
    return aggregate_results(batch_results)
```

**Audio (continued):**
> "Each batch creates a savepoint. If you're processing 10 million records and crash at batch 500, you resume from batch 500 — not from zero. The savepoint even tracks your progress percentage."

**Overlay Text:**
- Savepoint after each batch
- Resume from last completed batch
- Progress tracking built-in

---

## SCENE 9: Research Agent — Multi-Source AI (14:30 - 17:00)

**Visual:** Display `examples/10_research_agent.py`. Show the multi-source architecture.

**Audio Script:**
> "Let's build something more sophisticated — a research agent that queries multiple sources and synthesizes findings. This showcases epistemic savepoints for complex reasoning."

**Code Snippet (Multi-Source Search):**
```python
@step()
def search_academic_sources(topics: list) -> dict:
    """Search academic papers and publications."""
    return {
        "source": "academic",
        "results": [
            {"title": "Durable Execution for AI Workflows", "citations": 45},
            {"title": "State Management in Long-Running Processes", "citations": 128}
        ]
    }

@step()
def search_news_sources(topics: list) -> dict:
    """Search recent news articles."""
    return {
        "source": "news",
        "results": [
            {"title": "AI Workflow Automation Trends in 2025", "publisher": "Tech Daily"},
        ]
    }

@step()
def search_documentation(topics: list) -> dict:
    """Search technical documentation."""
    return {
        "source": "documentation",
        "results": [
            {"title": "Contd.ai Documentation", "url": "https://docs.contd.ai"},
        ]
    }
```

**Code Snippet (Synthesis with Epistemic Savepoint):**
```python
@step(StepConfig(savepoint=True))
def synthesize_findings(query_info: dict, academic: dict, news: dict, docs: dict) -> dict:
    """
    Synthesize findings from all sources.
    Creates epistemic savepoint capturing the agent's reasoning state.
    """
    ctx = ExecutionContext.current()
    
    synthesis = {
        "key_findings": [
            "Durable execution is becoming standard for AI workflows",
            "State management is critical for long-running processes",
        ],
        "themes": ["durability", "state management", "enterprise AI"],
        "gaps": ["Limited research on epistemic state preservation"],
        "confidence": 0.85
    }
    
    # 🔑 Epistemic savepoint captures reasoning
    ctx.create_savepoint({
        "goal_summary": f"Research synthesis for: {query_info['original_query']}",
        "hypotheses": [
            "Durable execution frameworks will become mainstream",
            "AI agents need better state management tools",
        ],
        "questions": [
            "What are the performance implications of durability?",
            "How do different frameworks compare?",
        ],
        "decisions": [
            "Focus on practical implementation aspects",
            "Include both academic and industry perspectives"
        ],
        "next_step": "generate_report"
    })
    
    return {"synthesis": synthesis, "sources_used": 3}

@workflow()
def research_agent(query: str) -> dict:
    """
    Multi-source research agent.
    Epistemic savepoints capture reasoning for time-travel debugging.
    """
    query_info = parse_research_query(query)
    
    # Search multiple sources (could be parallelized)
    academic = search_academic_sources(query_info["topics"])
    news = search_news_sources(query_info["topics"])
    docs = search_documentation(query_info["topics"])
    
    # Synthesize with epistemic savepoint
    synthesis = synthesize_findings(query_info, academic, news, docs)
    
    # Generate and save report
    report = generate_report(query_info, synthesis)
    return {"report": report, "confidence": synthesis["synthesis"]["confidence"]}
```

**Audio (continued):**
> "The synthesis step captures the agent's hypotheses and questions. If you need to debug why the agent reached a certain conclusion, you can time-travel back to this savepoint and inspect its reasoning state."

**Overlay Text:**
- Multi-source aggregation
- Epistemic savepoints for reasoning
- Time-travel debugging for AI decisions

---

## SCENE 10: Code Review Agent (17:00 - 19:30)

**Visual:** Display `examples/11_code_review_agent.py`. Show the analysis pipeline.

**Audio Script:**
> "Here's a practical example — an automated code review agent that analyzes PRs for quality, security, and test coverage."

**Code Snippet:**
```python
@step(StepConfig(savepoint=True))
def analyze_code_quality(files: list) -> dict:
    """Analyze code quality issues."""
    ctx = ExecutionContext.current()
    
    issues = []
    for file in files:
        if "password" in file["patch"].lower():
            issues.append({
                "file": file["path"],
                "type": "security",
                "severity": "high",
                "message": "Ensure password handling follows security best practices"
            })
    
    ctx.create_savepoint({
        "goal_summary": "Code quality analysis",
        "hypotheses": ["Code follows best practices"],
        "decisions": [f"Found {len(issues)} potential issues"],
        "next_step": "security_analysis"
    })
    
    return {"issues": issues, "quality_score": max(0, 100 - len(issues) * 10)}

@step(StepConfig(savepoint=True))
def analyze_security(files: list) -> dict:
    """Analyze security vulnerabilities."""
    ctx = ExecutionContext.current()
    
    vulnerabilities = []
    for file in files:
        patch = file["patch"].lower()
        if "password" in patch and "hash" not in patch:
            vulnerabilities.append({
                "type": "credential_handling",
                "severity": "critical",
                "message": "Password should be hashed before storage"
            })
    
    ctx.create_savepoint({
        "goal_summary": "Security vulnerability analysis",
        "hypotheses": ["Authentication implementation is secure"],
        "questions": ["Are there injection vulnerabilities?"],
        "decisions": [f"Found {len(vulnerabilities)} security concerns"],
        "next_step": "test_coverage_analysis"
    })
    
    return {"vulnerabilities": vulnerabilities, "security_score": max(0, 100 - len(vulnerabilities) * 20)}

@step()
def create_review_summary(pr: dict, quality: dict, security: dict, coverage: dict) -> dict:
    """Create overall review summary."""
    overall_score = (
        quality["quality_score"] * 0.3 +
        security["security_score"] * 0.5 +
        coverage["average_coverage"] * 0.2
    )
    
    if security["security_score"] < 50:
        recommendation = "request_changes"
        summary = "🔴 Changes requested due to security concerns"
    elif overall_score < 80:
        recommendation = "comment"
        summary = "🟡 Approved with suggestions"
    else:
        recommendation = "approve"
        summary = "🟢 Looks good!"
    
    return {"recommendation": recommendation, "summary": summary, "overall_score": overall_score}

@workflow()
def code_review_agent(pr_url: str) -> dict:
    """
    Automated code review workflow.
    Savepoints capture analysis state for debugging.
    """
    pr = fetch_pull_request(pr_url)
    
    quality = analyze_code_quality(pr["files_changed"])
    security = analyze_security(pr["files_changed"])
    coverage = analyze_test_coverage(pr)
    
    comments = generate_review_comments(quality, security, coverage)
    summary = create_review_summary(pr, quality, security, coverage)
    
    return {"review": summary, "comments": comments["comments"]}
```

**Audio (continued):**
> "Each analysis step creates a savepoint. If you want to understand why the agent flagged a security issue, you can inspect the savepoint to see its reasoning. The weighted scoring system gives you a clear recommendation."

**Overlay Text:**
- Quality + Security + Coverage analysis
- Weighted scoring system
- Savepoints for each analysis phase

---

## SCENE 11: Customer Support Automation (19:30 - 22:00)

**Visual:** Display `examples/12_customer_support.py`. Show the full support pipeline.

**Audio Script:**
> "Our most complex example — a full customer support automation system. This combines classification, knowledge base search, AI response generation, and intelligent routing."

**Code Snippet (Classification & Context):**
```python
@step()
def classify_ticket(ticket: dict) -> dict:
    """Classify ticket category and priority using AI."""
    body_lower = ticket["body"].lower()
    
    # Priority classification
    if "urgent" in body_lower or "emergency" in body_lower:
        priority = "high"
    elif "asap" in body_lower:
        priority = "medium"
    else:
        priority = "low"
    
    # Category classification
    if "billing" in body_lower or "payment" in body_lower:
        category = "billing"
    elif "bug" in body_lower or "error" in body_lower:
        category = "technical"
    elif "cancel" in body_lower or "refund" in body_lower:
        category = "cancellation"
    else:
        category = "general_inquiry"
    
    return {**ticket, "priority": priority, "category": category, "confidence": 0.85}

@step()
def fetch_customer_context(customer_id: str) -> dict:
    """Fetch customer history and context."""
    return {
        "customer_id": customer_id,
        "name": "John Doe",
        "plan": "premium",
        "tenure_months": 24,
        "previous_tickets": 3,
        "satisfaction_score": 4.2
    }

@step()
def search_knowledge_base(category: str, query: str) -> dict:
    """Search knowledge base for relevant articles."""
    articles = {
        "billing": [{"id": "KB-001", "title": "How to update payment method"}],
        "technical": [{"id": "KB-010", "title": "Troubleshooting common errors"}],
        "cancellation": [{"id": "KB-020", "title": "Cancellation policy"}],
    }
    return {"articles": articles.get(category, []), "category": category}
```

**Code Snippet (AI Response Generation with Epistemic Savepoint):**
```python
@step(StepConfig(savepoint=True))
def generate_response(ticket: dict, customer: dict, kb_results: dict) -> dict:
    """Generate response using AI with context."""
    ctx = ExecutionContext.current()
    
    # Build personalized response
    response = f"""Hi {customer['name']},

Thank you for reaching out about your {ticket['category']} inquiry.

I've reviewed your account and found these resources helpful:
{chr(10).join(f"- {a['title']}" for a in kb_results['articles'][:2])}

Best regards,
Support Team"""
    
    # Epistemic savepoint captures reasoning
    ctx.create_savepoint({
        "goal_summary": f"Respond to {ticket['category']} ticket",
        "hypotheses": [
            f"Customer needs help with {ticket['category']}",
            "KB articles will be helpful"
        ],
        "questions": ["Is this the right response?", "Should we escalate?"],
        "decisions": [
            f"Using {len(kb_results['articles'])} KB articles",
            "Response tone: professional"
        ],
        "next_step": "determine_routing"
    })
    
    return {"response": response, "confidence": 0.8}

@step()
def determine_routing(ticket: dict, response: dict) -> dict:
    """Determine if ticket needs human review."""
    needs_human = (
        ticket["priority"] == "high" or
        response["confidence"] < 0.7 or
        ticket["category"] == "cancellation"
    )
    
    team_mapping = {
        "billing": "billing_team",
        "technical": "tech_support",
        "cancellation": "retention_team",
    }
    
    return {
        "needs_human_review": needs_human,
        "assigned_team": team_mapping.get(ticket["category"], "general_support"),
        "auto_send": not needs_human
    }
```

**Code Snippet (Full Workflow):**
```python
@workflow()
def customer_support_workflow(ticket_data: dict) -> dict:
    """
    Automated customer support workflow:
    1. Receive and normalize ticket
    2. Classify category and priority
    3. Fetch customer context
    4. Search knowledge base
    5. Generate AI response
    6. Determine routing (auto vs human)
    7. Send or queue response
    
    High-priority and sensitive tickets routed to humans.
    """
    ticket = receive_ticket(ticket_data)
    classified = classify_ticket(ticket)
    customer = fetch_customer_context(classified["customer_id"])
    kb_results = search_knowledge_base(classified["category"], classified["body"])
    response = generate_response(classified, customer, kb_results)
    routing = determine_routing(classified, response)
    send_result = send_response(classified, response, routing)
    
    return {
        "ticket_id": classified["ticket_id"],
        "category": classified["category"],
        "priority": classified["priority"],
        "auto_responded": send_result["sent"],
        "assigned_team": routing["assigned_team"]
    }
```

**Audio (continued):**
> "This workflow handles the full support lifecycle. Low-confidence responses and high-priority tickets are automatically routed to humans. The epistemic savepoint captures why the AI chose a particular response — invaluable for quality assurance."

**Overlay Text:**
- Classify → Context → KB Search → Generate → Route
- Auto-escalation for sensitive tickets
- Full audit trail via savepoints

---

## SCENE 12: The CLI — Running & Debugging (22:00 - 24:30)

**Visual:** Terminal window showing CLI commands being typed with output.

**Audio Script:**
> "Now let's see how to run and debug these workflows using the Contd CLI."

**CLI Demo:**
```bash
# Initialize a new project
$ contd init
Initialized contd project at /home/user/my-project
  Config: contd.json
  Backend: sqlite
  Data dir: .contd/

# Run a workflow
$ contd run data_pipeline --input '{"source": "https://api.example.com/data"}'
Starting workflow: data_pipeline
  Workflow ID: data_pipeline-a1b2c3d4
  Input: {"source": "https://api.example.com/data"}...

Workflow completed in 2.34s
Result: {"total_value": 1200, "item_count": 3}

# Check workflow status
$ contd status data_pipeline-a1b2c3d4
Workflow: data_pipeline-a1b2c3d4
  Organization: default
  Events: 8
  Snapshots: 4
  Status: COMPLETED

# Inspect workflow state and savepoints
$ contd inspect data_pipeline-a1b2c3d4 --verbose
Workflow: data_pipeline-a1b2c3d4
==================================================

Current State:
  Step: 4
  Version: 1
  Variables: {"raw_data": {...}, "transformed": {...}}

Savepoints/Snapshots:
  [a1b2c3d4...] Step 1 - Event seq 2 - 2025-01-27 10:00:01
  [e5f6g7h8...] Step 2 - Event seq 4 - 2025-01-27 10:00:02
  [i9j0k1l2...] Step 3 - Event seq 6 - 2025-01-27 10:00:03
  [m3n4o5p6...] Step 4 - Event seq 8 - 2025-01-27 10:00:04
```

**CLI Demo (Time-Travel Debugging):**
```bash
# 🔑 TIME-TRAVEL DEBUGGING - The killer feature
$ contd time-travel data_pipeline-a1b2c3d4 e5f6g7h8 --dry-run
Loading savepoint: e5f6g7h8
  Workflow: data_pipeline-a1b2c3d4
  Step: 2
  Variables: ['raw_data', 'transformed']

[DRY RUN] Would create new workflow from this state
  New workflow ID would be: data_pipeline-a1b2c3d4-tt-x9y8z7w6

# Actually create the time-traveled workflow
$ contd time-travel data_pipeline-a1b2c3d4 e5f6g7h8
Loading savepoint: e5f6g7h8
  Workflow: data_pipeline-a1b2c3d4
  Step: 2
  Variables: ['raw_data', 'transformed']

Created new workflow from savepoint:
  New workflow ID: data_pipeline-a1b2c3d4-tt-x9y8z7w6
  New snapshot ID: snap-abc123

Resume with: contd resume data_pipeline-a1b2c3d4-tt-x9y8z7w6

# View execution logs
$ contd logs data_pipeline-a1b2c3d4 -n 20 -l DEBUG
Logs for workflow: data_pipeline-a1b2c3d4
============================================================
[2025-01-27 10:00:00] [INFO   ] STEP_STARTED - fetch_data
[2025-01-27 10:00:01] [INFO   ] STEP_COMPLETED - fetch_data [234ms]
[2025-01-27 10:00:01] [INFO   ] STEP_STARTED - transform_data
[2025-01-27 10:00:02] [INFO   ] STEP_COMPLETED - transform_data [156ms]
[2025-01-27 10:00:02] [INFO   ] STEP_STARTED - aggregate_results
[2025-01-27 10:00:03] [INFO   ] STEP_COMPLETED - aggregate_results [89ms]

# List all workflows
$ contd list --status running
Workflows (org: default)
======================================================================
ID                             Status       Last Activity
----------------------------------------------------------------------
ai_agent-b2c3d4e5              RUNNING      2025-01-27 10:15:23
research_agent-f6g7h8i9        RUNNING      2025-01-27 10:14:45
```

**Audio (continued):**
> "Time-travel debugging is the killer feature. You can fork a workflow from any savepoint, creating a new instance that starts from that exact state. This means you can debug logic errors without re-running expensive API calls. You can even inspect the agent's epistemic state at any point in its reasoning."

**Overlay Text:**
- `contd init` — Initialize project
- `contd run` — Execute workflow
- `contd inspect` — View state & savepoints
- `contd time-travel` — Fork from any savepoint
- `contd logs` — View execution history

---

## SCENE 13: Multi-Language SDKs (24:30 - 25:30)

**Visual:** Show the SDK directory structure and code snippets from each language.

**Audio Script:**
> "Contd.ai isn't Python-only. We provide SDKs for TypeScript, Go, and Java — all connecting to the same durable execution engine."

**Code Snippets (Side by Side):**

**TypeScript:**
```typescript
import { workflow, step, ContdClient } from '@contd.ai/sdk';

const fetchData = step(async (source: string) => {
  const response = await fetch(source);
  return response.json();
});

const processData = step(async (data: any) => {
  return data.items.map(item => ({
    ...item,
    processed: true
  }));
});

const dataPipeline = workflow(async (source: string) => {
  const raw = await fetchData(source);
  const processed = await processData(raw);
  return { result: processed };
});
```

**Go:**
```go
package main

import "github.com/bhavdeep98/contd.ai/sdks/go"

func FetchData(ctx *contd.Context, source string) (map[string]interface{}, error) {
    // Fetch data from source
    return map[string]interface{}{"items": []string{"a", "b", "c"}}, nil
}

func ProcessData(ctx *contd.Context, data map[string]interface{}) (map[string]interface{}, error) {
    // Process the data
    return map[string]interface{}{"processed": true}, nil
}

func DataPipeline(ctx *contd.Context, source string) (map[string]interface{}, error) {
    raw, _ := ctx.Step("fetch", func() (interface{}, error) {
        return FetchData(ctx, source)
    })
    processed, _ := ctx.Step("process", func() (interface{}, error) {
        return ProcessData(ctx, raw.(map[string]interface{}))
    })
    return processed.(map[string]interface{}), nil
}
```

**Audio (continued):**
> "Same concepts, same durability guarantees, your language of choice. The TypeScript SDK uses decorators, Go uses context-based step execution, and Java provides annotation-based workflows."

**Overlay Text:**
| Language | Package | Install |
|----------|---------|---------|
| Python | `contd` | `pip install contd` |
| TypeScript | `@contd.ai/sdk` | `npm install @contd.ai/sdk` |
| Go | `contd` | `go get github.com/bhavdeep98/contd.ai/sdks/go` |

---

## SCENE 14: Conclusion (25:30 - 26:30)

**Visual:** Return to GitHub repo, show the examples directory, then the architecture diagram.

**Audio Script:**
> "That's Contd.ai — durable execution for AI agents and beyond. We covered:
> - Basic pipelines with automatic checkpointing
> - Retry and timeout patterns for resilience
> - AI agents with epistemic savepoints
> - RAG pipelines that don't waste API calls
> - Saga pattern for distributed transactions
> - Human-in-the-loop approvals
> - Batch processing with progress tracking
> - Multi-source research agents
> - Code review automation
> - Customer support workflows
>
> All 12 examples are in the `examples/` directory. Clone the repo, run `pip install -e .`, and start building durable workflows today.
>
> Thanks for watching!"

**Final Overlay Text:**
- 🔗 github.com/bhavdeep98/contd.ai
- 📚 12+ production-ready examples
- 🛠️ Python, TypeScript, Go, Java SDKs
- ⏱️ Time-travel debugging
- 🧠 Epistemic savepoints for AI reasoning

---

## KEY CONCEPTS SUMMARY (For Overlay Graphics)

| Concept | Description |
|---------|-------------|
| **Durable Execution** | Workflows are resumable by default. State persisted after every step. |
| **@step** | Atomic unit of work. Automatically checkpointed. |
| **@workflow** | Orchestrates steps. Defines the execution flow. |
| **Epistemic Savepoints** | Capture AI reasoning state (hypotheses, goals, decisions). |
| **Hybrid Recovery** | Fast restoration using snapshots + event replay. |
| **Time-Travel Debugging** | Fork workflows from any savepoint to debug without re-running. |
| **Saga Pattern** | Distributed transactions with compensating actions. |
| **Retry Policy** | Exponential backoff with jitter for resilient API calls. |
| **Multi-Tenancy** | Built-in organization isolation for data and execution. |

---

## EXAMPLE COMPLEXITY PROGRESSION

1. **01_basic_pipeline.py** — Sequential steps, basic checkpointing
2. **02_retry_timeout.py** — Error handling, resilience patterns
3. **03_ai_agent.py** — Tool use, epistemic savepoints
4. **04_rag_pipeline.py** — Multi-step AI pipeline
5. **05_order_processing.py** — Saga pattern, compensations
6. **06_data_etl.py** — ETL with validation and enrichment
7. **07_approval_workflow.py** — Human-in-the-loop, waiting
8. **08_batch_processing.py** — Large-scale processing, progress
9. **09_webhook_integration.py** — External callbacks, async
10. **10_research_agent.py** — Multi-source AI reasoning
11. **11_code_review_agent.py** — Automated analysis pipeline
12. **12_customer_support.py** — Full production workflow

---

*Script prepared for Contd.ai demo video. Total runtime: ~26 minutes.*
