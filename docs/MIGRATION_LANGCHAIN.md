# Migration Guide: LangChain to Contd.ai

This guide helps you migrate AI agent workflows from LangChain to Contd.ai for durable execution.

## Why Migrate?

| Feature | LangChain | Contd.ai |
|---------|-----------|----------|
| Durability | ❌ In-memory | ✅ Persistent |
| Recovery | ❌ Manual | ✅ Automatic |
| Exactly-once | ❌ No | ✅ Yes |
| Time-travel | ❌ No | ✅ Yes |
| Multi-tenancy | ❌ Manual | ✅ Built-in |

## Basic Chain Migration

### LangChain

```python
from langchain import LLMChain, PromptTemplate
from langchain.llms import OpenAI

llm = OpenAI(temperature=0.7)
prompt = PromptTemplate(
    input_variables=["topic"],
    template="Write a blog post about {topic}"
)
chain = LLMChain(llm=llm, prompt=prompt)

# Execute (not durable!)
result = chain.run("AI agents")
```

### Contd.ai

```python
from contd.sdk import workflow, step
from langchain import LLMChain, PromptTemplate
from langchain.llms import OpenAI

@step()
def generate_content(topic: str) -> dict:
    """Durable LLM call with automatic retry."""
    llm = OpenAI(temperature=0.7)
    prompt = PromptTemplate(
        input_variables=["topic"],
        template="Write a blog post about {topic}"
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(topic)
    return {"content": result}

@workflow()
def blog_workflow(topic: str):
    """Durable workflow - survives crashes!"""
    return generate_content(topic)

# Execute (durable!)
result = blog_workflow("AI agents")
```

## Sequential Chain Migration

### LangChain

```python
from langchain.chains import SequentialChain

research_chain = LLMChain(llm=llm, prompt=research_prompt, output_key="research")
outline_chain = LLMChain(llm=llm, prompt=outline_prompt, output_key="outline")
write_chain = LLMChain(llm=llm, prompt=write_prompt, output_key="article")

overall_chain = SequentialChain(
    chains=[research_chain, outline_chain, write_chain],
    input_variables=["topic"],
    output_variables=["article"]
)

result = overall_chain({"topic": "AI agents"})
```

### Contd.ai

```python
from contd.sdk import workflow, step, StepConfig, RetryPolicy

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def research(topic: str) -> dict:
    chain = LLMChain(llm=llm, prompt=research_prompt)
    return {"research": chain.run(topic)}

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def create_outline(research: str) -> dict:
    chain = LLMChain(llm=llm, prompt=outline_prompt)
    return {"outline": chain.run(research)}

@step(StepConfig(retry=RetryPolicy(max_attempts=3)))
def write_article(outline: str) -> dict:
    chain = LLMChain(llm=llm, prompt=write_prompt)
    return {"article": chain.run(outline)}

@workflow()
def article_workflow(topic: str):
    """Each step is checkpointed - resume from any failure."""
    research_result = research(topic)
    outline_result = create_outline(research_result["research"])
    article_result = write_article(outline_result["outline"])
    return article_result
```

## Agent Migration

### LangChain Agent

```python
from langchain.agents import initialize_agent, Tool
from langchain.llms import OpenAI

tools = [
    Tool(name="Search", func=search_func, description="Search the web"),
    Tool(name="Calculator", func=calc_func, description="Do math"),
]

agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
result = agent.run("What is 25% of the population of France?")
```

### Contd.ai Agent

```python
from contd.sdk import workflow, step, StepConfig, ExecutionContext

@step()
def search(query: str) -> dict:
    """Durable search with caching."""
    result = search_func(query)
    return {"search_result": result}

@step()
def calculate(expression: str) -> dict:
    """Durable calculation."""
    result = calc_func(expression)
    return {"calc_result": result}

@step(StepConfig(savepoint=True))
def agent_think(context: dict, question: str) -> dict:
    """Agent reasoning step with savepoint."""
    ctx = ExecutionContext.current()
    
    # Use LLM to decide next action
    decision = llm.predict(f"Given context: {context}\nQuestion: {question}\nWhat tool to use?")
    
    # Save reasoning state
    ctx.create_savepoint({
        "goal_summary": f"Answering: {question}",
        "hypotheses": [decision],
        "next_step": "execute_tool"
    })
    
    return {"decision": decision, "tool": parse_tool(decision)}

@workflow()
def agent_workflow(question: str):
    """Durable agent - can resume mid-reasoning!"""
    context = {}
    
    for _ in range(10):  # Max iterations
        thought = agent_think(context, question)
        
        if thought["tool"] == "search":
            result = search(thought["query"])
            context.update(result)
        elif thought["tool"] == "calculate":
            result = calculate(thought["expression"])
            context.update(result)
        elif thought["tool"] == "finish":
            return {"answer": thought["answer"]}
    
    return {"answer": "Could not determine answer"}
```

## Memory Migration

### LangChain Memory

```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory()
chain = ConversationChain(llm=llm, memory=memory)

chain.predict(input="Hi, I'm Alice")
chain.predict(input="What's my name?")  # Remembers "Alice"
```

### Contd.ai (Durable Memory)

```python
from contd.sdk import workflow, step, ExecutionContext

@step()
def chat_turn(message: str, history: list) -> dict:
    """Single chat turn with history."""
    response = llm.predict(
        f"History: {history}\nUser: {message}\nAssistant:"
    )
    return {
        "response": response,
        "history": history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response}
        ]
    }

@workflow()
def conversation_workflow(messages: list[str]):
    """Durable conversation - survives restarts!"""
    history = []
    responses = []
    
    for message in messages:
        result = chat_turn(message, history)
        history = result["history"]
        responses.append(result["response"])
    
    return {"responses": responses, "history": history}

# Resume conversation after crash
client.resume(workflow_id)  # Continues from last message!
```

## Callbacks to Observability

### LangChain Callbacks

```python
from langchain.callbacks import StdOutCallbackHandler

handler = StdOutCallbackHandler()
chain.run("topic", callbacks=[handler])
```

### Contd.ai Observability

```python
from contd.observability import setup_observability

# Automatic metrics for all workflows
setup_observability(metrics_port=9090)

# Metrics automatically emitted:
# - contd_workflows_started_total
# - contd_step_duration_milliseconds
# - contd_llm_tokens_total (if configured)

# Custom metrics
from contd.observability.metrics import collector

@step()
def my_step():
    result = do_work()
    collector.record_custom("my_metric", value=42, labels={"type": "custom"})
    return result
```

## Key Differences

| Concept | LangChain | Contd.ai |
|---------|-----------|----------|
| Chain | `LLMChain` | `@workflow` + `@step` |
| Memory | `ConversationBufferMemory` | Workflow state (auto-persisted) |
| Tools | `Tool` class | `@step` decorated functions |
| Callbacks | `CallbackHandler` | Built-in observability |
| Error handling | Try/catch | `RetryPolicy` + automatic recovery |
| State | In-memory | Durable (PostgreSQL/S3) |

## Gradual Migration

You can use LangChain inside Contd.ai steps:

```python
from contd.sdk import workflow, step
from langchain import LLMChain

@step()
def langchain_step(input_data: dict) -> dict:
    """Wrap existing LangChain code in durable step."""
    # Your existing LangChain code
    chain = LLMChain(...)
    result = chain.run(input_data)
    return {"result": result}

@workflow()
def hybrid_workflow(data: dict):
    """Mix LangChain and native Contd steps."""
    lc_result = langchain_step(data)
    native_result = my_native_step(lc_result)
    return native_result
```

## Next Steps

- [Quickstart Guide](QUICKSTART.md) - Get started with Contd.ai
- [API Reference](API_REFERENCE.md) - Full API documentation
- [Examples](../examples/) - Real workflow examples
