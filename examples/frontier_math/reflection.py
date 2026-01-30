"""
Meta-reasoning and self-reflection for the solver.

Allows the model to periodically review its own reasoning history
and evaluate the overall direction it's taking.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def build_reflection_prompt(
    problem: str,
    reasoning_history: List[str],
    digest_history: List[Dict],
    annotations: List[Dict],
    current_step: int
) -> str:
    """
    Build a prompt for the model to reflect on its own reasoning.
    
    This gives the model access to:
    - Its raw thinking tokens from recent steps
    - Distilled insights from earlier steps
    - Annotations showing decision points
    - Current progress
    """
    
    prompt = f"""You are solving a challenging mathematics problem. You've been working on this for {current_step} steps.

ORIGINAL PROBLEM:
{problem}

Now, step back and reflect on your reasoning so far. Review your thinking history and evaluate:
1. What approaches have you tried?
2. What's working and what's not?
3. Are you making progress toward the solution?
4. Should you continue the current approach or try something different?
5. What key insights have you gained?

"""
    
    # Add digest history (compressed reasoning from earlier steps)
    if digest_history:
        prompt += "\n=== EARLIER REASONING (COMPRESSED) ===\n"
        for i, digest in enumerate(digest_history[-3:]):  # Last 3 digests
            prompt += f"\nDigest {i+1} (Step {digest.get('step_number', '?')}):\n"
            payload = digest.get('payload', {})
            
            if 'proven_facts' in payload and payload['proven_facts']:
                prompt += f"  Proven: {payload['proven_facts']}\n"
            if 'failed_approaches' in payload and payload['failed_approaches']:
                prompt += f"  Failed: {payload['failed_approaches']}\n"
            if 'current_strategy' in payload:
                prompt += f"  Strategy: {payload['current_strategy']}\n"
            if 'key_insights' in payload and payload['key_insights']:
                prompt += f"  Insights: {payload['key_insights']}\n"
    
    # Add recent raw reasoning (uncompressed)
    if reasoning_history:
        prompt += "\n=== RECENT REASONING (LAST 5 STEPS) ===\n"
        for i, reasoning in enumerate(reasoning_history[-5:]):
            step_num = current_step - len(reasoning_history) + i + 1
            prompt += f"\nStep {step_num}:\n"
            # Truncate if too long
            if len(reasoning) > 2000:
                prompt += reasoning[:2000] + "\n... [truncated]\n"
            else:
                prompt += reasoning + "\n"
    
    # Add annotations (decision points)
    if annotations:
        prompt += "\n=== KEY DECISIONS ===\n"
        for ann in annotations[-10:]:  # Last 10 decisions
            prompt += f"Step {ann.get('step_number')}: {ann.get('text')}\n"
    
    prompt += """

Now, provide your reflection:

1. PROGRESS ASSESSMENT: Are you making meaningful progress? (Yes/No/Uncertain)

2. CURRENT APPROACH: Summarize your current approach in 1-2 sentences.

3. EFFECTIVENESS: Is this approach working? What evidence supports this?

4. ALTERNATIVE APPROACHES: What other approaches could you try?

5. RECOMMENDATION: Should you:
   a) Continue current approach
   b) Modify current approach (how?)
   c) Try a completely different approach (which one?)
   d) You're stuck and need to backtrack

6. NEXT STEPS: What should you focus on in the next few steps?

Be honest and critical. If you're going in circles or stuck, say so.
"""
    
    return prompt


def should_reflect(
    step_num: int,
    reflection_interval: int,
    health_signals: Optional[Any] = None
) -> bool:
    """
    Determine if the model should reflect at this step.
    
    Triggers reflection:
    - Every N steps (regular interval)
    - When health signals indicate problems
    - After major decision points
    """
    # Regular interval
    if step_num > 0 and step_num % reflection_interval == 0:
        return True
    
    # Health-based triggers
    if health_signals:
        # High retry rate = model struggling
        if hasattr(health_signals, 'retry_rate') and health_signals.retry_rate > 0.3:
            logger.info(f"Triggering reflection due to high retry rate: {health_signals.retry_rate:.1%}")
            return True
        
        # Output declining = losing detail
        if hasattr(health_signals, 'output_trend') and health_signals.output_trend == 'declining':
            logger.info("Triggering reflection due to declining output")
            return True
        
        # Duration spiking = struggling
        if hasattr(health_signals, 'duration_trend') and health_signals.duration_trend == 'spiking':
            logger.info("Triggering reflection due to duration spike")
            return True
    
    return False


def parse_reflection_response(response: str) -> Dict[str, Any]:
    """
    Parse the model's reflection response into structured data.
    
    Extracts:
    - Progress assessment
    - Current approach
    - Recommendation
    - Next steps
    """
    reflection = {
        "raw_response": response,
        "progress": "uncertain",
        "recommendation": "continue",
        "should_backtrack": False,
        "should_change_approach": False,
    }
    
    response_lower = response.lower()
    
    # Parse progress assessment
    if "progress assessment:" in response_lower:
        if "yes" in response_lower.split("progress assessment:")[1].split("\n")[0]:
            reflection["progress"] = "yes"
        elif "no" in response_lower.split("progress assessment:")[1].split("\n")[0]:
            reflection["progress"] = "no"
    
    # Parse recommendation
    if "recommendation:" in response_lower:
        rec_section = response_lower.split("recommendation:")[1].split("\n")[0]
        if "backtrack" in rec_section or "stuck" in rec_section:
            reflection["recommendation"] = "backtrack"
            reflection["should_backtrack"] = True
        elif "different approach" in rec_section or "try" in rec_section:
            reflection["recommendation"] = "change_approach"
            reflection["should_change_approach"] = True
        elif "modify" in rec_section:
            reflection["recommendation"] = "modify"
        else:
            reflection["recommendation"] = "continue"
    
    # Check for stuck indicators
    stuck_indicators = ["stuck", "going in circles", "not making progress", "dead end"]
    if any(indicator in response_lower for indicator in stuck_indicators):
        reflection["should_backtrack"] = True
    
    return reflection


def format_reflection_for_context(reflection: Dict[str, Any]) -> str:
    """
    Format reflection into a concise summary for the model's context.
    
    This gets added to the prompt for subsequent steps.
    """
    summary = f"[SELF-REFLECTION at step {reflection.get('step', '?')}]\n"
    summary += f"Progress: {reflection.get('progress', 'uncertain')}\n"
    summary += f"Recommendation: {reflection.get('recommendation', 'continue')}\n"
    
    if reflection.get('should_backtrack'):
        summary += "⚠️ Model indicated it may be stuck - consider backtracking\n"
    
    if reflection.get('should_change_approach'):
        summary += "💡 Model suggests trying a different approach\n"
    
    return summary


class ReflectionManager:
    """
    Manages meta-reasoning and self-reflection for the solver.
    
    Tracks reflection history and provides context for future reflections.
    """
    
    def __init__(self, reflection_interval: int = 10):
        self.reflection_interval = reflection_interval
        self.reflections: List[Dict[str, Any]] = []
        self.last_reflection_step = 0
    
    def should_reflect(self, step_num: int, health_signals=None) -> bool:
        """Check if reflection should be triggered."""
        return should_reflect(step_num, self.reflection_interval, health_signals)
    
    def add_reflection(self, step_num: int, reflection: Dict[str, Any]):
        """Record a reflection."""
        reflection['step'] = step_num
        self.reflections.append(reflection)
        self.last_reflection_step = step_num
        
        logger.info(f"Reflection recorded at step {step_num}")
        logger.info(f"  Progress: {reflection.get('progress')}")
        logger.info(f"  Recommendation: {reflection.get('recommendation')}")
    
    def get_reflection_summary(self) -> str:
        """Get summary of all reflections for context."""
        if not self.reflections:
            return ""
        
        summary = "\n=== PREVIOUS REFLECTIONS ===\n"
        for refl in self.reflections[-3:]:  # Last 3 reflections
            summary += format_reflection_for_context(refl)
            summary += "\n"
        
        return summary
    
    def should_backtrack(self) -> bool:
        """Check if recent reflections suggest backtracking."""
        if not self.reflections:
            return False
        
        # Check last 2 reflections
        recent = self.reflections[-2:]
        return any(r.get('should_backtrack', False) for r in recent)
    
    def should_change_approach(self) -> bool:
        """Check if recent reflections suggest changing approach."""
        if not self.reflections:
            return False
        
        recent = self.reflections[-2:]
        return any(r.get('should_change_approach', False) for r in recent)
