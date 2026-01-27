"""
Example 03: AI Agent with Tools

A durable AI agent that uses tools to accomplish tasks.
Demonstrates epistemic savepoints for AI reasoning state.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext


# Simulated LLM (replace with real OpenAI/Anthropic client)
def call_llm(prompt: str) -> str:
    """Simulate LLM response."""
    if "weather" in prompt.lower():
        return "TOOL: get_weather(location='San Francisco')"
    elif "calculate" in prompt.lower():
        return "TOOL: calculator(expression='25 * 4')"
    elif "search" in prompt.lower():
        return "TOOL: web_search(query='latest AI news')"
    else:
        return "ANSWER: Based on my analysis, the answer is 42."


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


@step(StepConfig(savepoint=True))
def agent_think(question: str, context: dict, iteration: int) -> dict:
    """
    Agent reasoning step with epistemic savepoint.
    
    Saves the agent's reasoning state so it can be
    inspected or resumed with full context.
    """
    ctx = ExecutionContext.current()
    
    # Build prompt with context
    prompt = f"""
    Question: {question}
    Context: {context}
    Iteration: {iteration}
    
    What should I do next? Use a tool or provide an answer.
    """
    
    # Call LLM
    response = call_llm(prompt)
    
    # Parse response
    if response.startswith("TOOL:"):
        tool_call = response[5:].strip()
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
    
    return {
        "action": action,
        "tool_call": tool_call,
        "response": response,
        "iteration": iteration
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
    Durable AI agent workflow.
    
    The agent:
    1. Thinks about the question
    2. Decides to use a tool or answer
    3. Executes tools as needed
    4. Provides final answer
    
    Each step is checkpointed. If the agent crashes,
    it resumes with full reasoning context via savepoints.
    """
    context = {"question": question}
    
    for i in range(max_iterations):
        # Agent thinks
        thought = agent_think(question, context, i)
        
        if thought["action"] == "answer":
            # Agent has an answer
            return {
                "question": question,
                "answer": thought["response"],
                "iterations": i + 1,
                "context": context
            }
        
        # Execute tool
        context = execute_tool(thought["tool_call"], context)
    
    return {
        "question": question,
        "answer": "Could not determine answer within iteration limit",
        "iterations": max_iterations,
        "context": context
    }


if __name__ == "__main__":
    result = ai_agent("What's the weather in San Francisco?")
    print(f"\nAgent result: {result}")
