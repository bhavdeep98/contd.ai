"""
Simple beam search solver - MVP implementation.

Explores multiple reasoning paths using beam search:
1. Generate k alternative approaches
2. Score each approach
3. Keep top k, discard rest
4. Repeat until solution or max depth
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tree_node import TreeNode, ReasoningTree
from scoring import score_node
from models import ReasoningModel
from typing import List, Optional, Tuple
import re


def generate_initial_approaches(problem: str, model: ReasoningModel, k: int = 3) -> List[str]:
    """
    Generate k different initial approaches to the problem.
    
    Args:
        problem: Problem statement
        model: Reasoning model
        k: Number of approaches to generate
    
    Returns:
        List of approach descriptions
    """
    prompt = f"""Problem: {problem}

Generate {k} DIFFERENT approaches to solve this problem. Make them diverse:
- Try different mathematical techniques
- Consider computational vs. analytical methods
- Explore different problem reformulations

Format your response as:
1. [First approach]
2. [Second approach]
3. [Third approach]

Be specific about what each approach would do."""
    
    response = model.generate(prompt)
    
    # Parse approaches
    approaches = []
    lines = response.answer.split('\n')
    for line in lines:
        # Look for numbered items
        match = re.match(r'^\d+\.\s*(.+)$', line.strip())
        if match:
            approaches.append(match.group(1))
    
    # Fallback if parsing failed
    if not approaches:
        approaches = [
            "Computational approach: Write code to solve directly",
            "Analytical approach: Use mathematical theory",
            "Hybrid approach: Combine computation and analysis"
        ][:k]
    
    return approaches[:k]


def continue_reasoning(node: TreeNode, problem: str, model: ReasoningModel) -> Tuple[str, str]:
    """
    Continue reasoning from a node.
    
    Args:
        node: Current node
        problem: Original problem
        model: Reasoning model
    
    Returns:
        (thinking, answer) tuple
    """
    # Build context from path
    context = f"Approach: {node.approach}\n\n"
    if node.reasoning:
        context += f"Previous reasoning:\n{node.reasoning[-500:]}\n\n"
    
    prompt = f"""{problem}

{context}

Continue your reasoning. Take the next step toward solving this problem.
Show your thinking process."""
    
    response = model.generate(prompt)
    return response.thinking, response.answer


def check_solution(node: TreeNode, problem: str) -> bool:
    """
    Check if node contains a solution.
    
    Simple heuristic: looks for answer indicators.
    """
    answer_lower = node.answer.lower()
    
    # Look for solution indicators
    indicators = [
        "answer is", "solution is", "result is",
        "therefore", "n =", "= ", "equals"
    ]
    
    has_indicator = any(ind in answer_lower for ind in indicators)
    has_number = bool(re.search(r'\d+', node.answer))
    
    return has_indicator and has_number


def beam_search_solver(
    problem: str,
    model: ReasoningModel,
    beam_width: int = 3,
    max_depth: int = 5,
    max_nodes: int = 50,
    use_llm_scoring: bool = False
) -> Tuple[Optional[TreeNode], ReasoningTree]:
    """
    Solve problem using beam search.
    
    Args:
        problem: Problem statement
        model: Reasoning model
        beam_width: Number of paths to explore at each level
        max_depth: Maximum tree depth
        max_nodes: Maximum total nodes to explore
        use_llm_scoring: Use LLM for scoring (slower but more accurate)
    
    Returns:
        (solution_node, tree) tuple
    """
    tree = ReasoningTree()
    
    # Generate initial approaches
    print(f"Generating {beam_width} initial approaches...")
    approaches = generate_initial_approaches(problem, model, beam_width)
    
    # Create root node
    root = TreeNode(
        node_id="root",
        parent_id=None,
        depth=0,
        approach="Problem analysis",
        reasoning="",
        promise_score=1.0
    )
    tree.add_node(root)
    
    # Create initial nodes for each approach
    frontier = []
    for i, approach in enumerate(approaches):
        node = TreeNode(
            node_id=f"0-{i}",
            parent_id="root",
            depth=1,
            approach=approach,
            reasoning="",
            promise_score=0.5
        )
        tree.add_node(node)
        frontier.append(node)
    
    print(f"Starting beam search (width={beam_width}, max_depth={max_depth})...")
    nodes_explored = 0
    
    while frontier and nodes_explored < max_nodes:
        # Process current level
        current_level = []
        
        for node in frontier:
            if node.depth >= max_depth:
                continue
            
            nodes_explored += 1
            print(f"\n{'='*60}")
            print(f"Node {nodes_explored}: {node.node_id} (depth={node.depth})")
            print(f"Approach: {node.approach}")
            print(f"{'='*60}")
            
            # Continue reasoning
            print("Generating reasoning...")
            thinking, answer = continue_reasoning(node, problem, model)
            
            # Update node
            node.reasoning = thinking
            node.answer = answer
            
            print(f"Thinking: {len(thinking)} chars")
            print(f"Answer preview: {answer[:200]}...")
            
            # Check if solution
            if check_solution(node, problem):
                print("\n🎯 Possible solution found!")
                node.is_terminal = True
                return node, tree
            
            # Score node
            score = score_node(node, problem, model, use_llm_scoring)
            node.promise_score = score
            print(f"Promise score: {score:.2f}")
            
            # Add to next level if promising
            if score > 0.3:  # threshold
                current_level.append(node)
        
        # Select top k for next iteration
        current_level.sort(key=lambda n: n.promise_score, reverse=True)
        frontier = current_level[:beam_width]
        
        print(f"\nFrontier size: {len(frontier)}")
        if frontier:
            print("Top nodes:")
            for node in frontier:
                print(f"  {node.node_id}: {node.promise_score:.2f} - {node.approach[:50]}")
        
        # Generate children for frontier nodes
        next_frontier = []
        for node in frontier:
            # For simplicity, just continue the same approach
            # (In full version, would generate alternative sub-approaches)
            child = TreeNode(
                node_id=f"{node.node_id}-c",
                parent_id=node.node_id,
                depth=node.depth + 1,
                approach=f"Continue: {node.approach}",
                reasoning="",
                promise_score=node.promise_score
            )
            tree.add_node(child)
            next_frontier.append(child)
        
        frontier = next_frontier
    
    print(f"\n{'='*60}")
    print("Search complete - no solution found")
    print(f"Nodes explored: {nodes_explored}")
    print(f"{'='*60}")
    
    # Return best node
    all_nodes = list(tree.nodes.values())
    if all_nodes:
        best = max(all_nodes, key=lambda n: n.promise_score)
        return best, tree
    
    return None, tree


if __name__ == "__main__":
    # Simple test
    from config import ModelConfig
    from models import create_model
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Simple test problem
    problem = """
    Find the smallest positive integer n such that n^2 + n + 41 is not prime.
    """
    
    print("="*60)
    print("BEAM SEARCH SOLVER - MVP TEST")
    print("="*60)
    print(f"\nProblem: {problem.strip()}")
    print()
    
    # Create model
    model_config = ModelConfig(
        provider="deepseek-api",
        model_name="deepseek-reasoner",
        api_key=os.environ.get("DEEPSEEK_API_KEY")
    )
    model = create_model(model_config)
    
    # Solve
    solution, tree = beam_search_solver(
        problem=problem,
        model=model,
        beam_width=2,  # Small for testing
        max_depth=3,
        max_nodes=10,
        use_llm_scoring=False
    )
    
    # Results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    if solution:
        print(f"\nBest node: {solution.node_id}")
        print(f"Score: {solution.promise_score:.2f}")
        print(f"Terminal: {solution.is_terminal}")
        print(f"\nAnswer:\n{solution.answer}")
    
    print("\nTree statistics:")
    stats = tree.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nTree visualization:")
    print(tree.visualize(max_depth=3))
