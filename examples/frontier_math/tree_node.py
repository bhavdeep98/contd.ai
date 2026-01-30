"""
TreeNode: Core data structure for tree-of-thoughts reasoning.

Each node represents a reasoning state in the exploration tree.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class TreeNode:
    """
    A node in the reasoning tree.
    
    Represents a single reasoning state with:
    - Position in tree (id, parent, depth)
    - Reasoning content (approach, thinking, answer)
    - Evaluation (promise score)
    - Contd.ai integration (savepoint_id)
    """
    
    # Tree structure
    node_id: str
    parent_id: Optional[str] = None
    depth: int = 0
    children: List[str] = field(default_factory=list)
    
    # Reasoning state
    approach: str = ""  # What approach this node explores
    reasoning: str = ""  # Model's thinking tokens
    answer: str = ""  # Current answer/conclusion
    
    # Evaluation
    promise_score: float = 0.5  # How promising (0-1)
    is_terminal: bool = False  # Reached conclusion?
    is_verified: bool = False  # Answer verified correct?
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    tokens_used: int = 0
    cost: float = 0.0
    
    # Contd.ai integration
    savepoint_id: Optional[str] = None
    
    def __repr__(self) -> str:
        return (
            f"TreeNode(id={self.node_id}, depth={self.depth}, "
            f"score={self.promise_score:.2f}, terminal={self.is_terminal})"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "children": self.children,
            "approach": self.approach,
            "reasoning": self.reasoning[:200] + "..." if len(self.reasoning) > 200 else self.reasoning,
            "answer": self.answer[:200] + "..." if len(self.answer) > 200 else self.answer,
            "promise_score": self.promise_score,
            "is_terminal": self.is_terminal,
            "is_verified": self.is_verified,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "savepoint_id": self.savepoint_id,
        }


class ReasoningTree:
    """
    Manages the tree of reasoning nodes.
    
    Provides operations for:
    - Adding/retrieving nodes
    - Traversing paths
    - Pruning branches
    - Statistics
    """
    
    def __init__(self):
        self.nodes: Dict[str, TreeNode] = {}
        self.root: Optional[TreeNode] = None
    
    def add_node(self, node: TreeNode) -> None:
        """Add a node to the tree."""
        self.nodes[node.node_id] = node
        
        if node.parent_id is None:
            self.root = node
        else:
            # Add to parent's children
            if node.parent_id in self.nodes:
                parent = self.nodes[node.parent_id]
                if node.node_id not in parent.children:
                    parent.children.append(node.node_id)
    
    def get_node(self, node_id: str) -> Optional[TreeNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_path(self, node_id: str) -> List[TreeNode]:
        """Get path from root to node."""
        path = []
        current_id = node_id
        
        while current_id is not None:
            node = self.nodes.get(current_id)
            if node is None:
                break
            path.append(node)
            current_id = node.parent_id
        
        return list(reversed(path))
    
    def get_children(self, node_id: str) -> List[TreeNode]:
        """Get all children of a node."""
        node = self.nodes.get(node_id)
        if node is None:
            return []
        
        return [self.nodes[child_id] for child_id in node.children if child_id in self.nodes]
    
    def get_leaves(self) -> List[TreeNode]:
        """Get all leaf nodes (no children)."""
        return [node for node in self.nodes.values() if not node.children]
    
    def prune(self, threshold: float) -> int:
        """
        Remove nodes with promise_score below threshold.
        Returns number of nodes pruned.
        """
        to_remove = []
        
        for node_id, node in self.nodes.items():
            if node.promise_score < threshold and node != self.root:
                to_remove.append(node_id)
        
        for node_id in to_remove:
            self._remove_subtree(node_id)
        
        return len(to_remove)
    
    def _remove_subtree(self, node_id: str) -> None:
        """Remove a node and all its descendants."""
        node = self.nodes.get(node_id)
        if node is None:
            return
        
        # Remove from parent's children
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node_id in parent.children:
                parent.children.remove(node_id)
        
        # Recursively remove children
        for child_id in list(node.children):
            self._remove_subtree(child_id)
        
        # Remove this node
        del self.nodes[node_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tree statistics."""
        if not self.nodes:
            return {
                "total_nodes": 0,
                "max_depth": 0,
                "avg_branching": 0.0,
                "terminal_nodes": 0,
                "verified_nodes": 0,
            }
        
        depths = [node.depth for node in self.nodes.values()]
        branching = [len(node.children) for node in self.nodes.values() if node.children]
        
        return {
            "total_nodes": len(self.nodes),
            "max_depth": max(depths) if depths else 0,
            "avg_branching": sum(branching) / len(branching) if branching else 0.0,
            "terminal_nodes": sum(1 for node in self.nodes.values() if node.is_terminal),
            "verified_nodes": sum(1 for node in self.nodes.values() if node.is_verified),
            "total_cost": sum(node.cost for node in self.nodes.values()),
            "total_tokens": sum(node.tokens_used for node in self.nodes.values()),
        }
    
    def visualize(self, max_depth: Optional[int] = None) -> str:
        """
        Generate ASCII tree visualization.
        
        Args:
            max_depth: Maximum depth to display (None for all)
        """
        if self.root is None:
            return "Empty tree"
        
        lines = []
        self._visualize_node(self.root, "", True, lines, max_depth, 0)
        return "\n".join(lines)
    
    def _visualize_node(
        self, 
        node: TreeNode, 
        prefix: str, 
        is_last: bool, 
        lines: List[str],
        max_depth: Optional[int],
        current_depth: int
    ) -> None:
        """Helper for tree visualization."""
        if max_depth is not None and current_depth > max_depth:
            return
        
        # Node representation
        marker = "└── " if is_last else "├── "
        score_str = f"[{node.promise_score:.2f}]"
        terminal_str = " ✓" if node.is_terminal else ""
        verified_str = " ✓✓" if node.is_verified else ""
        
        node_str = f"{node.node_id}: {node.approach[:40]}"
        lines.append(f"{prefix}{marker}{node_str} {score_str}{terminal_str}{verified_str}")
        
        # Children
        children = self.get_children(node.node_id)
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            extension = "    " if is_last else "│   "
            self._visualize_node(
                child, 
                prefix + extension, 
                is_last_child, 
                lines,
                max_depth,
                current_depth + 1
            )
