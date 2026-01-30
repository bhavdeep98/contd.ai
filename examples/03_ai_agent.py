"""
Example 03: AI Agent with Tools

A durable AI agent that uses tools to accomplish tasks.
Demonstrates:
- @llm_step for LLM calls with token tracking
- Epistemic savepoints for AI reasoning state
- Token budget enforcement
"""

from contd.sdk import (
    workflow,
    step,
    llm_step,
    LLMStepConfig,
    LLMProvider,
    StepConfig,
    ExecutionContext,
    get_token_tracker,
    TokenBudgetExceeded,
)


# Simulated LLM response with token usage
# In production, use real OpenAI/Anthropic client
def call_llm_api(prompt: str, model: str = "gpt-4o") -> dict:
    """
    Simulate LLM API response with token usage.
    
    Real implementation would use:
        response = openai.chat.completions.create(...)
        return response  # Has .usage attribute
    """
    if "weather" in prompt.lower():
        content = "TOOL: get_weather(location='San Francisco')"
    elif "calculate" in prompt.lower():
        content = "TOOL: calculator(expression='25 * 4')"
    elif "search" in prompt.lower():
        content = "TOOL: web_search(query='latest AI news')"
    else:
        content = "ANSWER: Based on my analysis, the answer is 42."
    
    # Simulate token usage (real API returns this)
    return {
        "content": content,
        "usage": {
            "prompt_tokens": len(prompt.split()) * 2,  # Rough estimate
            "completion_tokens": len(content.split()) * 2,
        }
    }


@step()
def get_weather(location: str) -> dict:
    """Get weather for a location."""
    print(f"Getting weather for {location}...")
    return {
        "location": location,
        "temperature": 68,
        "conditions": "Sunny",
        "humidity": 45
    }


@step()
def calculator(expression: str) -> dict:
    """Evaluate a mathematical expression."""
    print(f"Calculating: {expression}")
    result = eval(expression)  # In production, use safe eval
    return {"expression": expression, "result": result}


@step()
def web_search(query: str) -> dict:
    """Search the web."""
    print(f"Searching for: {query}")
    return {
        "query": query,
        "results": [
            {"title": "AI Breakthrough 2025", "url": "https://example.com/1"},
            {"title": "New LLM Released", "url": "https://example.com/2"},
        ]
    }


@llm_step(LLMStepConfig(
    model="gpt-4o",
    provider=LLMProvider.OPENAI,
    track_tokens=True,
    token_budget=5000,  # Max 5k tokens per think step
    savepoint=True,
))
def agent_think(question: str, context: dict, iteration: int) -> dict:
    """
    Agent reasoning step with LLM call.
    
    Uses @llm_step to:
    - Track token usage automatically
    - Enforce per-step token budget
    - Create epistemic savepoint
    """
    ctx = ExecutionContext.current()
    
    # Build prompt with context
    prompt = f"""
    Question: {question}
    Context: {context}
    Iteration: {iteration}
    
    What should I do next? Use a tool or provide an answer.
    """
    
    # Call LLM (returns response with usage info)
    response = call_llm_api(prompt)
    
    # Parse response
    content = response["content"]
    if content.startswith("TOOL:"):
        tool_call = content[5:].strip()
        action = "use_tool"
    else:
        tool_call = None
        action = "answer"
    
    # Create epistemic savepoint
    ctx.create_savepoint({
        "goal_summary": f"Answering: {question}",
        "hypotheses": [
            f"Tool {tool_call} will help" if tool_call else "Have enough info to answer"
        ],
        "questions": ["Is this the right approach?"],
        "decisions": [f"Decided to {action}"],
        "next_step": tool_call if tool_call else "provide_answer"
    })
    
    # Return response with usage for token tracking
    return {
        "action": action,
        "tool_call": tool_call,
        "response": content,
        "iteration": iteration,
        "usage": response["usage"],  # @llm_step extracts this
    }


@step()
def execute_tool(tool_call: str, context: dict) -> dict:
    """Execute a tool based on the agent's decision."""
    print(f"Executing tool: {tool_call}")
    
    # Parse tool call (simplified)
    if "get_weather" in tool_call:
        result = get_weather("San Francisco")
    elif "calculator" in tool_call:
        result = calculator("25 * 4")
    elif "web_search" in tool_call:
        result = web_search("latest AI news")
    else:
        result = {"error": "Unknown tool"}
    
    # Merge result into context
    new_context = {**context, "last_tool_result": result}
    return new_context


@workflow()
def ai_agent(question: str, max_iterations: int = 5) -> dict:
    """
    Durable AI agent workflow with token tracking.
    
    The agent:
    1. Thinks about the question (LLM call with token tracking)
    2. Decides to use a tool or answer
    3. Executes tools as needed
    4. Provides final answer
    
    Features:
    - Each LLM call tracks tokens and cost
    - Per-step and workflow-level budget enforcement
    - Epistemic savepoints capture reasoning state
    - Full recovery on crash/restart
    """
    ctx = ExecutionContext.current()
    context = {"question": question}
    
    # Set workflow-level token budget (optional)
    tracker = get_token_tracker(ctx)
    tracker.workflow_token_budget = 50000  # 50k tokens max for entire workflow
    tracker.workflow_cost_budget = 1.00    # $1 max cost
    
    try:
        for i in range(max_iterations):
            # Agent thinks (LLM call with token tracking)
            thought = agent_think(question, context, i)
            
            if thought["action"] == "answer":
                # Agent has an answer - include token summary
                return {
                    "question": question,
                    "answer": thought["response"],
                    "iterations": i + 1,
                    "context": context,
                    "token_usage": {
                        "total_tokens": tracker.total_tokens,
                        "total_cost": f"${tracker.total_cost_dollars:.4f}",
                        "by_model": {
                            model: usage.total_tokens 
                            for model, usage in tracker.tokens_by_model.items()
                        }
                    }
                }
            
            # Execute tool
            context = execute_tool(thought["tool_call"], context)
        
        return {
            "question": question,
            "answer": "Could not determine answer within iteration limit",
            "iterations": max_iterations,
            "context": context,
            "token_usage": {
                "total_tokens": tracker.total_tokens,
                "total_cost": f"${tracker.total_cost_dollars:.4f}",
            }
        }
        
    except TokenBudgetExceeded as e:
        # Budget exceeded - return partial result
        return {
            "question": question,
            "answer": f"Budget exceeded: {e.message}",
            "iterations": i + 1,
            "context": context,
            "token_usage": {
                "total_tokens": tracker.total_tokens,
                "total_cost": f"${tracker.total_cost_dollars:.4f}",
                "budget_exceeded": True,
            }
        }


if __name__ == "__main__":
    result = ai_agent("What's the weather in San Francisco?")
    print(f"\nAgent result: {result}")
    
    if "token_usage" in result:
        print(f"\nToken usage: {result['token_usage']}")
