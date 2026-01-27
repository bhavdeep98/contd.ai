"""
Example 10: Research Agent

Multi-source research agent with epistemic savepoints.
Demonstrates complex AI reasoning with durable state.
"""

from contd.sdk import workflow, step, StepConfig, ExecutionContext
from typing import List, Dict
import time


@step()
def parse_research_query(query: str) -> dict:
    """Parse research query into structured components."""
    print(f"Parsing query: {query}")
    
    # Simulate query understanding
    return {
        "original_query": query,
        "topics": ["AI", "machine learning", "workflows"],
        "intent": "comprehensive_research",
        "depth": "detailed",
        "sources_needed": ["academic", "news", "documentation"]
    }


@step()
def search_academic_sources(topics: List[str]) -> dict:
    """Search academic papers and publications."""
    print(f"Searching academic sources for: {topics}")
    
    # Simulate academic search
    return {
        "source": "academic",
        "results": [
            {
                "title": "Durable Execution for AI Workflows",
                "authors": ["Smith, J.", "Johnson, A."],
                "year": 2024,
                "abstract": "This paper presents a framework for durable AI workflow execution...",
                "citations": 45
            },
            {
                "title": "State Management in Long-Running Processes",
                "authors": ["Williams, R."],
                "year": 2023,
                "abstract": "We explore techniques for managing state in distributed systems...",
                "citations": 128
            }
        ]
    }


@step()
def search_news_sources(topics: List[str]) -> dict:
    """Search recent news articles."""
    print(f"Searching news for: {topics}")
    
    return {
        "source": "news",
        "results": [
            {
                "title": "AI Workflow Automation Trends in 2025",
                "publisher": "Tech Daily",
                "date": "2025-01-15",
                "summary": "Companies are increasingly adopting durable execution frameworks..."
            },
            {
                "title": "The Rise of Agent-Based Systems",
                "publisher": "AI Weekly",
                "date": "2025-01-20",
                "summary": "Agent-based AI systems are transforming enterprise workflows..."
            }
        ]
    }


@step()
def search_documentation(topics: List[str]) -> dict:
    """Search technical documentation."""
    print(f"Searching documentation for: {topics}")
    
    return {
        "source": "documentation",
        "results": [
            {
                "title": "Contd.ai Documentation",
                "url": "https://docs.contd.ai",
                "sections": ["Getting Started", "Architecture", "API Reference"]
            },
            {
                "title": "Temporal.io Concepts",
                "url": "https://docs.temporal.io",
                "sections": ["Workflows", "Activities", "Workers"]
            }
        ]
    }


@step(StepConfig(savepoint=True))
def synthesize_findings(
    query_info: dict,
    academic: dict,
    news: dict,
    docs: dict
) -> dict:
    """
    Synthesize findings from all sources.
    
    Creates epistemic savepoint capturing the agent's
    reasoning state and hypotheses.
    """
    ctx = ExecutionContext.current()
    
    print("Synthesizing research findings...")
    
    # Combine all sources
    all_results = {
        "academic": academic["results"],
        "news": news["results"],
        "documentation": docs["results"]
    }
    
    # Generate synthesis (in production: use LLM)
    synthesis = {
        "key_findings": [
            "Durable execution is becoming standard for AI workflows",
            "State management is critical for long-running processes",
            "Agent-based systems are gaining enterprise adoption"
        ],
        "themes": ["durability", "state management", "enterprise AI"],
        "gaps": ["Limited research on epistemic state preservation"],
        "confidence": 0.85
    }
    
    # Create epistemic savepoint
    ctx.create_savepoint({
        "goal_summary": f"Research synthesis for: {query_info['original_query']}",
        "hypotheses": [
            "Durable execution frameworks will become mainstream",
            "AI agents need better state management tools",
            "Enterprise adoption will accelerate in 2025"
        ],
        "questions": [
            "What are the performance implications of durability?",
            "How do different frameworks compare?",
            "What are the security considerations?"
        ],
        "decisions": [
            "Focus on practical implementation aspects",
            "Include both academic and industry perspectives"
        ],
        "next_step": "generate_report"
    })
    
    return {
        "synthesis": synthesis,
        "sources_used": list(all_results.keys()),
        "total_sources": sum(len(v) for v in all_results.values())
    }


@step()
def generate_report(query_info: dict, synthesis: dict) -> dict:
    """Generate final research report."""
    print("Generating research report...")
    
    report = {
        "title": f"Research Report: {query_info['original_query']}",
        "executive_summary": "This report synthesizes findings from academic, news, and documentation sources...",
        "key_findings": synthesis["synthesis"]["key_findings"],
        "themes": synthesis["synthesis"]["themes"],
        "research_gaps": synthesis["synthesis"]["gaps"],
        "recommendations": [
            "Consider adopting durable execution for AI workflows",
            "Implement proper state management from the start",
            "Monitor industry trends for best practices"
        ],
        "confidence_score": synthesis["synthesis"]["confidence"],
        "sources_analyzed": synthesis["total_sources"],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return {"report": report}


@step()
def save_research(report: dict, output_path: str) -> dict:
    """Save research report."""
    print(f"Saving report to {output_path}...")
    
    return {
        "saved": True,
        "path": output_path,
        "format": "json"
    }


@workflow()
def research_agent(query: str, output_path: str = "research_output.json") -> dict:
    """
    Multi-source research agent:
    1. Parse research query
    2. Search multiple sources in parallel
    3. Synthesize findings (with epistemic savepoint)
    4. Generate comprehensive report
    5. Save results
    
    Epistemic savepoints capture the agent's reasoning
    state, allowing inspection and time-travel debugging.
    """
    # Parse query
    query_info = parse_research_query(query)
    
    # Search sources (could be parallelized)
    academic = search_academic_sources(query_info["topics"])
    news = search_news_sources(query_info["topics"])
    docs = search_documentation(query_info["topics"])
    
    # Synthesize
    synthesis = synthesize_findings(query_info, academic, news, docs)
    
    # Generate report
    report = generate_report(query_info, synthesis)
    
    # Save
    saved = save_research(report, output_path)
    
    return {
        "status": "completed",
        "query": query,
        "report": report["report"],
        "saved_to": saved["path"]
    }


if __name__ == "__main__":
    result = research_agent(
        query="What are the best practices for durable AI workflow execution?",
        output_path="ai_workflows_research.json"
    )
    
    print(f"\nResearch Complete!")
    print(f"Title: {result['report']['title']}")
    print(f"\nKey Findings:")
    for finding in result['report']['key_findings']:
        print(f"  • {finding}")
    print(f"\nConfidence: {result['report']['confidence_score'] * 100:.0f}%")
