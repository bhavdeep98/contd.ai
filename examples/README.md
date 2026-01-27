# Contd.ai Examples

Real-world workflow examples demonstrating Contd.ai capabilities.

## Quick Start

```bash
# Install dependencies
pip install -e ..
pip install requests openai

# Run any example
python 01_basic_pipeline.py
```

## Examples

| # | Example | Description |
|---|---------|-------------|
| 01 | [Basic Pipeline](01_basic_pipeline.py) | Simple data processing workflow |
| 02 | [Retry & Timeout](02_retry_timeout.py) | Error handling patterns |
| 03 | [AI Agent](03_ai_agent.py) | LLM-powered agent with tools |
| 04 | [RAG Pipeline](04_rag_pipeline.py) | Retrieval-augmented generation |
| 05 | [Order Processing](05_order_processing.py) | E-commerce saga pattern |
| 06 | [Data ETL](06_data_etl.py) | Extract-Transform-Load pipeline |
| 07 | [Multi-Step Approval](07_approval_workflow.py) | Human-in-the-loop workflow |
| 08 | [Batch Processing](08_batch_processing.py) | Process large datasets |
| 09 | [Webhook Integration](09_webhook_integration.py) | External service callbacks |
| 10 | [Research Agent](10_research_agent.py) | Multi-source research with savepoints |
| 11 | [Code Review Agent](11_code_review_agent.py) | Automated PR review |
| 12 | [Customer Support](12_customer_support.py) | Support ticket automation |

## Running Examples

### Local Mode (SQLite)

```bash
# Initialize local database
contd init

# Run example
python 01_basic_pipeline.py
```

### Server Mode (PostgreSQL)

```bash
# Start server
export DATABASE_URL=postgresql://user:pass@localhost/contd
python -m contd.api.server

# In another terminal
export CONTD_API_KEY=sk_live_...
python 01_basic_pipeline.py --server
```

## Example Categories

### Basic Patterns
- `01_basic_pipeline.py` - Sequential steps
- `02_retry_timeout.py` - Error handling

### AI/ML Workflows
- `03_ai_agent.py` - Tool-using agent
- `04_rag_pipeline.py` - RAG with vector DB
- `10_research_agent.py` - Multi-source research
- `11_code_review_agent.py` - Code analysis

### Business Workflows
- `05_order_processing.py` - E-commerce
- `07_approval_workflow.py` - Human approval
- `12_customer_support.py` - Ticket handling

### Data Processing
- `06_data_etl.py` - ETL pipeline
- `08_batch_processing.py` - Large datasets

### Integration
- `09_webhook_integration.py` - External callbacks
