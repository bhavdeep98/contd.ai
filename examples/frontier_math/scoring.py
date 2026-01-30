"""
Node scoring: Evaluate how promising a reasoning path is.

Provides both heuristic (fast) and LLM-based (accurate) scoring.
"""

from tree_node import TreeNode
from typing import Optional
import re


def score_node_heuristic(node: TreeNode, problem: str = "") -> float:
    """
    Fast heuristic scoring based on reasoning content.
    
    Looks for:
    - Progress indicators (positive)
    - Stuck/confused language (negative)
    - Concrete steps (positive)
    - Contradictions (negative)
    
    Returns score in [0, 1]
    """
    score = 0.5  # baseline
    reasoning = node.reasoning.lower()
    answer = node.answer.lower()
    
    # Positive signals
    positive_markers = [
        "therefore", "thus", "hence", "proven", "verified",
        "computed", "calculated", "found", "determined"
    ]
    for marker in positive_markers:
        if marker in reasoning or marker in answer:
            score += 0.05
    
    # Concrete progress
    if re.search(r'\d+', reasoning):  # Contains numbers
        score += 0.05
    if "step" in reasoning and re.search(r'step \d+', reasoning):
        score += 0.05
    
    # Code/computation
    if "```python" in node.reasoning or "```" in node.reasoning:
        score += 0.1
    
    # Substantial thinking
    if len(reasoning) > 500:
        score += 0.05
    if len(reasoning) > 1000:
        score += 0.05
    
    # Negative signals
    negative_markers = [
        "stuck", "confused", "unclear", "don't know", "not sure",
        "can't", "unable", "impossible", "contradiction", "error"
    ]
    for marker in negative_markers:
        if marker in reasoning or marker in answer:
            score -= 0.1
    
    # Repetition (sign of being stuck)
    words = reasoning.split()
    if len(words) > 50:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:  # High repetition
            score -= 0.15
    
    # Depth penalty (prefer not too deep)
    if node.depth > 10:
        score -= 0.05
    if node.depth > 15:
        score -= 0.1
    
    # Terminal nodes get bonus if they have an answer
    if node.is_terminal and node.answer:
        score += 0.15
    
    return max(0.0, min(1.0, score))


def score_node_llm(node: TreeNode, problem: str, model) -> float:
    """
    LLM-based scoring for more accurate evaluation.
    
    Args:
        node: Node to score
        problem: Original problem statement
        model: Reasoning model to use for evaluation
    
    Returns:
        Score in [0, 1]
    """
    prompt = f"""Problem: {problem}

Current reasoning path:
{node.reasoning[:1000]}

Evaluate how promising this reasoning path is for solving the problem.

Consider:
- Is it making progress toward a solution?
- Are the steps logical and correct?
- Is it stuck or going in circles?
- Does it show understanding of the problem?

Rate from 0.0 to 1.0:
- 0.0-0.3: Dead end, contradictory, or stuck
- 0.4-0.6: Uncertain, needs more exploration
- 0.7-0.9: Promising, making good progress
- 0.9-1.0: Very promising, likely to lead to solution

Respond with just the score (e.g., "0.75"):"""
    
    try:
        response = model.generate(prompt)
        score_text = response.answer.strip()
        
        # Extract number
        match = re.search(r'0?\.\d+|[01]\.?\d*', score_text)
        if match:
            score = float(match.group())
            return max(0.0, min(1.0, score))
        else:
            # Fallback to heuristic
            return score_node_heuristic(node, problem)
    
    except Exception as e:
        print(f"LLM scoring failed: {e}, using heuristic")
        return score_node_heuristic(node, problem)


def score_node(
    node: TreeNode, 
    problem: str = "",
    model = None,
    use_llm: bool = False
) -> float:
    """
    Score a node using heuristic or LLM-based method.
    
    Args:
        node: Node to score
        problem: Original problem
        model: Model for LLM scoring (required if use_llm=True)
        use_llm: Whether to use LLM scoring (slower but more accurate)
    
    Returns:
        Promise score in [0, 1]
    """
    if use_llm and model is not None:
        return score_node_llm(node, problem, model)
    else:
        return score_node_heuristic(node, problem)
