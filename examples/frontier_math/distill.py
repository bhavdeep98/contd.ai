"""
Distillation functions for mathematical reasoning.

Compresses accumulated thinking tokens into structured insights.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def simple_math_distill(raw_chunks: List[str], previous_digest: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Simple heuristic-based distillation for mathematical reasoning.
    
    Extracts:
    - Proven facts/lemmas
    - Failed approaches
    - Current strategy
    - Key insights
    
    This is a baseline. In production, you'd use an LLM for better extraction.
    """
    combined = "\n\n".join(raw_chunks)
    
    # Extract proven facts (look for "therefore", "thus", "proven", "QED")
    proven_facts = _extract_proven_facts(combined)
    
    # Extract failed approaches (look for "doesn't work", "contradiction", "dead end")
    failed_approaches = _extract_failed_approaches(combined)
    
    # Extract current strategy (look for "approach", "strategy", "plan")
    current_strategy = _extract_strategy(combined)
    
    # Extract key insights (look for "insight", "key observation", "notice that")
    key_insights = _extract_insights(combined)
    
    # Merge with previous digest if exists
    if previous_digest:
        proven_facts = previous_digest.get("proven_facts", []) + proven_facts
        failed_approaches = previous_digest.get("failed_approaches", []) + failed_approaches
        key_insights = previous_digest.get("key_insights", []) + key_insights
    
    # Keep only last 10 of each to prevent unbounded growth
    proven_facts = proven_facts[-10:]
    failed_approaches = failed_approaches[-10:]
    key_insights = key_insights[-10:]
    
    return {
        "proven_facts": proven_facts,
        "failed_approaches": failed_approaches,
        "current_strategy": current_strategy,
        "key_insights": key_insights,
        "chunks_processed": len(raw_chunks),
        "total_chars": len(combined),
    }


def llm_math_distill(raw_chunks: List[str], previous_digest: Optional[Dict] = None) -> Dict[str, Any]:
    """
    LLM-based distillation using a cheap model to extract structure.
    
    This is the production-quality approach - uses an LLM to understand
    the mathematical reasoning and extract structured insights.
    """
    combined = "\n\n".join(raw_chunks)
    
    # Build prompt for distillation
    prompt = f"""You are a mathematical reasoning analyzer. Extract structured insights from this reasoning chain.

Previous context: {previous_digest if previous_digest else "None"}

New reasoning:
{combined[:10000]}  # Truncate to avoid token limits

Extract and return JSON with:
{{
    "proven_lemmas": ["list of proven mathematical facts"],
    "failed_approaches": ["list of approaches that didn't work and why"],
    "current_strategy": "description of current approach",
    "key_insights": ["list of important observations"],
    "open_questions": ["list of remaining questions to answer"]
}}

Be concise. Focus on mathematical content, not meta-reasoning.
"""
    
    try:
        # Use a cheap model for distillation (e.g., Claude Haiku, GPT-4o-mini)
        # This is pseudocode - implement based on your model choice
        import json
        from anthropic import Anthropic
        
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-20250414",  # Cheap model
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON response
        result = json.loads(response.content[0].text)
        
        # Merge with previous
        if previous_digest:
            result["proven_lemmas"] = previous_digest.get("proven_lemmas", []) + result.get("proven_lemmas", [])
            result["failed_approaches"] = previous_digest.get("failed_approaches", []) + result.get("failed_approaches", [])
            result["key_insights"] = previous_digest.get("key_insights", []) + result.get("key_insights", [])
        
        # Limit growth
        result["proven_lemmas"] = result.get("proven_lemmas", [])[-10:]
        result["failed_approaches"] = result.get("failed_approaches", [])[-10:]
        result["key_insights"] = result.get("key_insights", [])[-10:]
        
        result["chunks_processed"] = len(raw_chunks)
        result["total_chars"] = len(combined)
        
        return result
        
    except Exception as e:
        logger.error(f"LLM distillation failed: {e}")
        # Fallback to simple distillation
        return simple_math_distill(raw_chunks, previous_digest)


# Helper functions for simple distillation

def _extract_proven_facts(text: str) -> List[str]:
    """Extract proven facts from reasoning text."""
    facts = []
    
    # Look for sentences with proof indicators
    proof_indicators = [
        r"therefore[,:]?\s+(.+?)[\.\n]",
        r"thus[,:]?\s+(.+?)[\.\n]",
        r"proven[,:]?\s+(.+?)[\.\n]",
        r"QED[,:]?\s+(.+?)[\.\n]",
        r"we have shown that\s+(.+?)[\.\n]",
    ]
    
    for pattern in proof_indicators:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            fact = match.group(1).strip()
            if len(fact) > 10 and len(fact) < 200:  # Reasonable length
                facts.append(fact)
    
    return facts[:5]  # Return top 5


def _extract_failed_approaches(text: str) -> List[str]:
    """Extract failed approaches from reasoning text."""
    failures = []
    
    # Look for failure indicators
    failure_indicators = [
        r"doesn't work because\s+(.+?)[\.\n]",
        r"contradiction[,:]?\s+(.+?)[\.\n]",
        r"dead end[,:]?\s+(.+?)[\.\n]",
        r"this approach fails because\s+(.+?)[\.\n]",
        r"cannot proceed because\s+(.+?)[\.\n]",
    ]
    
    for pattern in failure_indicators:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            failure = match.group(1).strip()
            if len(failure) > 10 and len(failure) < 200:
                failures.append(failure)
    
    return failures[:5]


def _extract_strategy(text: str) -> str:
    """Extract current strategy from reasoning text."""
    # Look for strategy statements (usually near the end)
    strategy_indicators = [
        r"(?:current )?(?:approach|strategy|plan)[,:]?\s+(.+?)[\.\n]",
        r"(?:will|should) try to\s+(.+?)[\.\n]",
        r"next step[,:]?\s+(.+?)[\.\n]",
    ]
    
    # Search from end of text (most recent strategy)
    for pattern in strategy_indicators:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            strategy = matches[-1].group(1).strip()
            if len(strategy) > 10 and len(strategy) < 200:
                return strategy
    
    return "Continue mathematical analysis"


def _extract_insights(text: str) -> List[str]:
    """Extract key insights from reasoning text."""
    insights = []
    
    # Look for insight indicators
    insight_indicators = [
        r"(?:key )?insight[,:]?\s+(.+?)[\.\n]",
        r"(?:key )?observation[,:]?\s+(.+?)[\.\n]",
        r"notice that\s+(.+?)[\.\n]",
        r"importantly[,:]?\s+(.+?)[\.\n]",
        r"crucially[,:]?\s+(.+?)[\.\n]",
    ]
    
    for pattern in insight_indicators:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            insight = match.group(1).strip()
            if len(insight) > 10 and len(insight) < 200:
                insights.append(insight)
    
    return insights[:5]


# Export default distillation function
default_distill = simple_math_distill
