"""
Convergence detection for FrontierMath solver.

Tracks answer history and detects when the model has converged
on a stable solution (or is oscillating between a few answers).
"""

from typing import List, Dict, Any, Optional
from collections import Counter
import re
import logging

logger = logging.getLogger(__name__)


class ConvergenceDetector:
    """
    Detects when the solver has converged on an answer.
    
    Tracks recent answers and identifies:
    - Stable convergence (same answer N times)
    - Oscillation (cycling between 2-3 answers)
    - Divergence (all different answers)
    """
    
    def __init__(
        self,
        window_size: int = 5,
        convergence_threshold: int = 3,
        oscillation_threshold: int = 4
    ):
        """
        Initialize convergence detector.
        
        Args:
            window_size: Number of recent answers to track
            convergence_threshold: Number of identical answers to declare convergence
            oscillation_threshold: Number of oscillations to detect cycling
        """
        self.window_size = window_size
        self.convergence_threshold = convergence_threshold
        self.oscillation_threshold = oscillation_threshold
        
        self.answer_history: List[str] = []
        self.extracted_values: List[Dict[str, Any]] = []
        
    def add_answer(self, answer: str, step: int) -> None:
        """
        Add an answer to the history.
        
        Args:
            answer: The answer text from the model
            step: The step number
        """
        # Extract key values from answer
        extracted = self._extract_values(answer)
        extracted['step'] = step
        extracted['raw_answer'] = answer
        
        self.answer_history.append(answer)
        self.extracted_values.append(extracted)
        
        # Keep only recent history
        if len(self.answer_history) > self.window_size:
            self.answer_history.pop(0)
            self.extracted_values.pop(0)
    
    def check_convergence(self) -> Dict[str, Any]:
        """
        Check if the solver has converged.
        
        Returns:
            Dict with keys:
                - converged: bool
                - reason: str (stable, oscillating, diverging, insufficient_data)
                - confidence: float (0-1)
                - final_answer: str or None
                - details: dict with additional info
        """
        if len(self.answer_history) < self.convergence_threshold:
            return {
                "converged": False,
                "reason": "insufficient_data",
                "confidence": 0.0,
                "final_answer": None,
                "details": {
                    "answers_collected": len(self.answer_history),
                    "needed": self.convergence_threshold
                }
            }
        
        # Check for stable convergence
        stable_result = self._check_stable_convergence()
        if stable_result["converged"]:
            return stable_result
        
        # Check for oscillation
        oscillation_result = self._check_oscillation()
        if oscillation_result["converged"]:
            return oscillation_result
        
        # Still diverging
        return {
            "converged": False,
            "reason": "diverging",
            "confidence": 0.0,
            "final_answer": None,
            "details": {
                "unique_answers": len(set(self.answer_history)),
                "recent_answers": self.answer_history[-3:]
            }
        }
    
    def _check_stable_convergence(self) -> Dict[str, Any]:
        """Check if the last N answers are identical."""
        recent = self.answer_history[-self.convergence_threshold:]
        
        # Check exact match
        if len(set(recent)) == 1:
            return {
                "converged": True,
                "reason": "stable",
                "confidence": 1.0,
                "final_answer": recent[0],
                "details": {
                    "consecutive_matches": self.convergence_threshold,
                    "answer": recent[0]
                }
            }
        
        # Check extracted values match
        recent_values = self.extracted_values[-self.convergence_threshold:]
        if self._values_match(recent_values):
            return {
                "converged": True,
                "reason": "stable_values",
                "confidence": 0.9,
                "final_answer": recent[-1],
                "details": {
                    "consecutive_matches": self.convergence_threshold,
                    "extracted_values": recent_values[-1]
                }
            }
        
        return {"converged": False}
    
    def _check_oscillation(self) -> Dict[str, Any]:
        """Check if answers are oscillating between a few values."""
        if len(self.answer_history) < self.oscillation_threshold:
            return {"converged": False}
        
        recent = self.answer_history[-self.oscillation_threshold:]
        counter = Counter(recent)
        
        # Oscillating between 2 values
        if len(counter) == 2:
            most_common = counter.most_common(1)[0]
            return {
                "converged": True,
                "reason": "oscillating",
                "confidence": 0.6,
                "final_answer": most_common[0],
                "details": {
                    "oscillation_pattern": dict(counter),
                    "most_common": most_common[0],
                    "occurrences": most_common[1]
                }
            }
        
        # Oscillating between 3 values
        if len(counter) == 3 and len(self.answer_history) >= self.window_size:
            most_common = counter.most_common(1)[0]
            return {
                "converged": True,
                "reason": "oscillating_3way",
                "confidence": 0.5,
                "final_answer": most_common[0],
                "details": {
                    "oscillation_pattern": dict(counter),
                    "most_common": most_common[0],
                    "occurrences": most_common[1]
                }
            }
        
        return {"converged": False}
    
    def _extract_values(self, answer: str) -> Dict[str, Any]:
        """
        Extract key numerical values from answer.
        
        Looks for patterns like:
        - X = 10^6
        - π₂(X) = 123
        - N = 456
        """
        values = {}
        
        # Extract X value
        x_patterns = [
            r'X\s*=\s*10\^(\d+)',
            r'X\s*=\s*(\d+)',
            r'answer.*?(\d+)',
        ]
        for pattern in x_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                values['X'] = match.group(1)
                break
        
        # Extract π₂ value
        pi2_patterns = [
            r'π₂\s*\(\s*[^)]+\s*\)\s*=\s*(\d+)',
            r'pi_2.*?=\s*(\d+)',
        ]
        for pattern in pi2_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                values['pi_2'] = match.group(1)
                break
        
        # Extract N value
        n_patterns = [
            r'N\s*=\s*(\d+)',
            r'smallest.*?(\d+)',
        ]
        for pattern in n_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                values['N'] = match.group(1)
                break
        
        return values
    
    def _values_match(self, value_dicts: List[Dict[str, Any]]) -> bool:
        """Check if extracted values match across multiple answers."""
        if not value_dicts:
            return False
        
        # Get keys that exist in all dicts
        common_keys = set(value_dicts[0].keys())
        for d in value_dicts[1:]:
            common_keys &= set(d.keys())
        
        # Remove metadata keys
        common_keys.discard('step')
        common_keys.discard('raw_answer')
        
        if not common_keys:
            return False
        
        # Check if all values match
        first = value_dicts[0]
        for d in value_dicts[1:]:
            for key in common_keys:
                if d.get(key) != first.get(key):
                    return False
        
        return True
    
    def get_summary(self) -> str:
        """Get a human-readable summary of convergence status."""
        result = self.check_convergence()
        
        if result["converged"]:
            reason = result["reason"]
            confidence = result["confidence"]
            
            if reason == "stable":
                return f"✓ Converged (stable, {confidence:.0%} confidence): Same answer {self.convergence_threshold} times"
            elif reason == "stable_values":
                return f"✓ Converged (stable values, {confidence:.0%} confidence): Key values match"
            elif reason == "oscillating":
                pattern = result["details"]["oscillation_pattern"]
                return f"⚠ Converged (oscillating, {confidence:.0%} confidence): Cycling between {len(pattern)} answers"
            elif reason == "oscillating_3way":
                pattern = result["details"]["oscillation_pattern"]
                return f"⚠ Converged (3-way oscillation, {confidence:.0%} confidence): Cycling between {len(pattern)} answers"
        else:
            reason = result["reason"]
            if reason == "insufficient_data":
                return f"○ Not converged: Need {result['details']['needed']} answers, have {result['details']['answers_collected']}"
            elif reason == "diverging":
                return f"○ Not converged: Still exploring ({result['details']['unique_answers']} unique answers)"
        
        return "○ Not converged"
    
    def should_stop(self, min_confidence: float = 0.8) -> bool:
        """
        Determine if the solver should stop.
        
        Args:
            min_confidence: Minimum confidence to stop (0-1)
            
        Returns:
            True if solver should stop
        """
        result = self.check_convergence()
        return result["converged"] and result["confidence"] >= min_confidence
    
    def get_final_answer(self) -> Optional[str]:
        """Get the final converged answer, if any."""
        result = self.check_convergence()
        if result["converged"]:
            return result["final_answer"]
        return None


def test_convergence_detector():
    """Test the convergence detector."""
    print("Testing ConvergenceDetector")
    print("=" * 60)
    
    detector = ConvergenceDetector(window_size=5, convergence_threshold=3)
    
    # Test 1: Stable convergence
    print("\nTest 1: Stable Convergence")
    detector.answer_history = []
    detector.extracted_values = []
    
    for i in range(5):
        detector.add_answer("The answer is X = 10^6", i)
    
    result = detector.check_convergence()
    print(f"Result: {result['reason']}")
    print(f"Converged: {result['converged']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Summary: {detector.get_summary()}")
    
    # Test 2: Oscillation
    print("\nTest 2: Oscillation Between Two Answers")
    detector.answer_history = []
    detector.extracted_values = []
    
    answers = ["X = 10^6", "X = 10^7", "X = 10^6", "X = 10^7", "X = 10^6"]
    for i, ans in enumerate(answers):
        detector.add_answer(ans, i)
    
    result = detector.check_convergence()
    print(f"Result: {result['reason']}")
    print(f"Converged: {result['converged']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Summary: {detector.get_summary()}")
    
    # Test 3: Still diverging
    print("\nTest 3: Still Diverging")
    detector.answer_history = []
    detector.extracted_values = []
    
    answers = ["X = 10^5", "X = 10^6", "X = 10^7", "X = 10^8"]
    for i, ans in enumerate(answers):
        detector.add_answer(ans, i)
    
    result = detector.check_convergence()
    print(f"Result: {result['reason']}")
    print(f"Converged: {result['converged']}")
    print(f"Summary: {detector.get_summary()}")
    
    print("\n" + "=" * 60)
    print("Tests completed")


if __name__ == "__main__":
    test_convergence_detector()
