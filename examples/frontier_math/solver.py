"""
FrontierMath Solver using Contd.ai

Solves challenging mathematics problems using reasoning models
with durable execution and thinking token capture.
"""

import sys
import os
import time
import argparse
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add parent directory to path for contd imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from contd.sdk import workflow, step
from contd.sdk.context import ExecutionContext
from contd.sdk.decorators import WorkflowConfig, StepConfig

from config import ModelConfig, SolverConfig
from models import create_model, ReasoningResponse
from distill import simple_math_distill
from reflection import (
    ReflectionManager,
    build_reflection_prompt,
    parse_reflection_response
)
from code_executor import ToolCallingExecutor, CodeExecutor
from convergence import ConvergenceDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FrontierMathSolver:
    """Solver for FrontierMath problems with durable execution."""
    
    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        solver_config: Optional[SolverConfig] = None,
        distill_fn=None,
        reflection_interval: int = 10,
        enable_code_execution: bool = True,
        enable_sagemath: bool = False,
        enable_convergence_detection: bool = True
    ):
        self.model_config = model_config or ModelConfig.from_env()
        self.solver_config = solver_config or SolverConfig.from_env()
        self.distill_fn = distill_fn or simple_math_distill
        self.model = create_model(self.model_config)
        self.reflection_manager = ReflectionManager(reflection_interval)
        
        # Initialize code executor
        self.enable_code_execution = enable_code_execution
        if enable_code_execution:
            code_executor = CodeExecutor(
                timeout=30,
                enable_sagemath=enable_sagemath
            )
            self.tool_executor = ToolCallingExecutor(code_executor)
            logger.info("✓ Code execution enabled (Python + SymPy)")
            if enable_sagemath:
                logger.info("✓ SageMath execution enabled")
        else:
            self.tool_executor = None
            logger.info("✗ Code execution disabled")
        
        # Initialize convergence detector
        self.enable_convergence_detection = enable_convergence_detection
        if enable_convergence_detection:
            self.convergence_detector = ConvergenceDetector(
                window_size=5,
                convergence_threshold=3,
                oscillation_threshold=4
            )
            logger.info("✓ Convergence detection enabled")
        else:
            self.convergence_detector = None
            logger.info("✗ Convergence detection disabled")
        
        logger.info(f"Initialized solver with {self.model_config.provider} / {self.model_config.model_name}")
        logger.info(f"Reflection enabled every {reflection_interval} steps")
    
    def solve(self, problem: str, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Solve a FrontierMath problem.
        
        Args:
            problem: The problem statement
            workflow_id: Optional workflow ID for resume
            
        Returns:
            Result dictionary with answer, reasoning, and metadata
        """
        logger.info("=" * 60)
        logger.info("FrontierMath Solver")
        logger.info("=" * 60)
        logger.info(f"Problem: {problem[:100]}...")
        
        # Create workflow
        result = self._solve_workflow(
            problem=problem,
            workflow_id=workflow_id,
            model=self.model,
            config=self.solver_config,
            distill_fn=self.distill_fn
        )
        
        return result
    
    @workflow(WorkflowConfig(
        distill=None,  # Set dynamically
        distill_every=5,
        context_budget=200_000,
    ))
    def _solve_workflow(
        self,
        problem: str,
        workflow_id: Optional[str],
        model,
        config: SolverConfig,
        distill_fn
    ) -> Dict[str, Any]:
        """Main solving workflow."""
        ctx = ExecutionContext.current()
        
        # Configure context preservation
        ctx.configure_context(
            distill=distill_fn,
            distill_every=config.distill_every,
            distill_threshold=config.distill_threshold,
            context_budget=config.context_budget,
            on_health_warning=self._health_warning_handler
        )
        
        # Check if resuming
        restored = ctx.get_restore_context()
        if restored:
            logger.info(f"📚 Resuming with context:")
            logger.info(f"   - {len(restored.get('annotations', []))} annotations")
            logger.info(f"   - {len(restored.get('digest_history', []))} digests")
            logger.info(f"   - {len(restored.get('undigested', []))} undigested chunks")
            
            # Extract context for model
            problem_context = self._build_context_from_restore(restored)
        else:
            problem_context = {"problem": problem}
        
        # Solving loop
        start_time = time.time()
        reasoning_history = []  # Track raw reasoning for reflection
        
        for step_num in range(config.max_steps):
            # Check timeout
            if time.time() - start_time > config.max_time_seconds:
                logger.warning(f"⏱️  Timeout reached at step {step_num}")
                return self._timeout_result(problem_context, step_num)
            
            # Check if model should reflect on its reasoning
            health = ctx.context_health()
            if self.reflection_manager.should_reflect(step_num, health):
                logger.info(f"\n🤔 Step {step_num}: Model reflecting on its reasoning...")
                reflection_result = self._reflection_step(
                    problem=problem,
                    reasoning_history=reasoning_history,
                    context=problem_context,
                    step_num=step_num,
                    model=model
                )
                
                # Check if model thinks it should backtrack
                if reflection_result.get('should_backtrack'):
                    logger.warning("⚠️  Model reflection suggests backtracking")
                    self._create_branch_point(problem_context, step_num)
                
                # Add reflection summary to context
                problem_context['last_reflection'] = reflection_result
            
            # Regular reasoning step
            result = self._reasoning_step(
                problem=problem,
                context=problem_context,
                step_num=step_num,
                model=model,
                config=config
            )
            
            # Store reasoning for future reflection
            if result.get('thinking'):
                reasoning_history.append(result['thinking'])
                # Keep only last 10 for memory efficiency
                reasoning_history = reasoning_history[-10:]
            
            # Track answer for convergence detection
            if self.enable_convergence_detection and result.get('answer'):
                self.convergence_detector.add_answer(result['answer'], step_num)
                convergence_result = self.convergence_detector.check_convergence()
                
                # Log convergence status
                if step_num % 3 == 0:  # Log every 3 steps
                    logger.info(f"  Convergence: {self.convergence_detector.get_summary()}")
                
                # Check if we should stop due to convergence
                if convergence_result['converged']:
                    confidence = convergence_result['confidence']
                    reason = convergence_result['reason']
                    
                    if confidence >= 0.8:
                        logger.info(f"✅ Converged at step {step_num} ({reason}, {confidence:.0%} confidence)")
                        return self._convergence_result(convergence_result, problem, step_num)
                    elif confidence >= 0.6 and reason == "oscillating":
                        logger.warning(f"⚠️  Oscillation detected at step {step_num}")
                        logger.warning(f"   Pattern: {convergence_result['details']['oscillation_pattern']}")
                        # Continue for a few more steps to see if it stabilizes
                        if step_num >= config.max_steps * 0.7:  # After 70% of max steps
                            logger.info(f"✅ Stopping due to persistent oscillation")
                            return self._convergence_result(convergence_result, problem, step_num)
            
            # Check if we found an answer
            if self._is_answer(result):
                logger.info(f"✅ Solution found at step {step_num}")
                return self._verify_and_return(result, problem, step_num)
            
            # Check if we hit a dead end
            if self._is_dead_end(result):
                logger.warning(f"🚫 Dead end at step {step_num}")
                self._create_branch_point(problem_context, step_num)
            
            # Update context
            problem_context.update(result)
        
        # Max steps reached
        logger.warning(f"⚠️  Max steps ({config.max_steps}) reached")
        return self._max_steps_result(problem_context, config.max_steps)
    
    @step(StepConfig(checkpoint=True))
    def _reasoning_step(
        self,
        problem: str,
        context: Dict,
        step_num: int,
        model,
        config: SolverConfig
    ) -> Dict[str, Any]:
        """Single reasoning step with thinking token capture."""
        ctx = ExecutionContext.current()
        
        logger.info(f"\n📖 Step {step_num}: Reasoning")
        
        # Build prompt
        prompt = self._build_prompt(problem, context, step_num)
        
        # Add tool instructions if code execution is enabled
        if self.enable_code_execution:
            prompt += self._get_tool_instructions()
        
        # Generate with model
        try:
            response: ReasoningResponse = model.generate(prompt, context)
            
            # FIX: Validate response - detect empty answers
            if response.thinking and not response.answer:
                logger.warning(f"⚠️  Empty answer at step {step_num}!")
                logger.warning(f"   Thinking: {len(response.thinking)} chars")
                logger.warning(f"   Answer: {len(response.answer)} chars")
                logger.warning(f"   Using thinking as fallback answer")
                # Use thinking as answer if answer is empty
                response.answer = response.thinking
            
            # Check if both are empty (critical error)
            if not response.thinking and not response.answer:
                logger.error(f"❌ Both thinking and answer are empty at step {step_num}!")
                return {
                    "error": "Empty response from model",
                    "step": step_num,
                    "thinking": "",
                    "answer": "Model returned empty response",
                    "confidence": 0.0
                }
                
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            return {"error": str(e), "step": step_num}
        
        # Check if model wants to execute code
        tool_results = []
        if self.enable_code_execution:
            tool_results = self._handle_tool_calls(response.answer)
            
            # If tools were called, give model the results and continue
            if tool_results:
                logger.info(f"  Executed {len(tool_results)} tool calls")
                
                # Add tool results to context for next iteration
                context['tool_results'] = tool_results
                
                # Ingest tool results into context
                for tool_result in tool_results:
                    ctx.ingest(f"[TOOL: {tool_result['tool']}]\n{tool_result['result']}")
        
        # Capture thinking tokens
        if response.thinking:
            ctx.ingest(response.thinking)
            logger.info(f"  Captured {len(response.thinking)} chars of reasoning")
        
        # Extract decision from answer
        decision = self._extract_decision(response.answer)
        ctx.annotate(f"Step {step_num}: {decision}")
        logger.info(f"  Decision: {decision}")
        
        # Check confidence
        if config.pause_on_low_confidence and response.confidence < config.confidence_threshold:
            logger.warning(f"  ⚠️  Low confidence ({response.confidence:.2f})")
            if config.require_review:
                logger.info("  Pausing for human review...")
                # In production, this would pause the workflow
        
        return {
            "step": step_num,
            "thinking": response.thinking,
            "answer": response.answer,
            "confidence": response.confidence,
            "decision": decision,
            "metadata": response.metadata,
            "tool_results": tool_results
        }
    
    @step(StepConfig(checkpoint=True))
    def _reflection_step(
        self,
        problem: str,
        reasoning_history: List[str],
        context: Dict,
        step_num: int,
        model
    ) -> Dict[str, Any]:
        """
        Meta-reasoning step where model reflects on its own reasoning.
        
        The model reviews its thinking history and evaluates:
        - Progress toward solution
        - Effectiveness of current approach
        - Whether to continue or change direction
        """
        ctx = ExecutionContext.current()
        
        # Get ledger data for reflection
        ledger = ctx.ledger if hasattr(ctx, 'ledger') else None
        digest_history = ledger.digests if ledger else []
        annotations = ledger.annotations if ledger else []
        
        # Build reflection prompt with full reasoning access
        prompt = build_reflection_prompt(
            problem=problem,
            reasoning_history=reasoning_history,
            digest_history=[d.to_dict() for d in digest_history],
            annotations=[a.to_dict() for a in annotations],
            current_step=step_num
        )
        
        logger.info(f"  Reflection prompt: {len(prompt)} chars")
        logger.info(f"  Including {len(reasoning_history)} recent reasoning steps")
        logger.info(f"  Including {len(digest_history)} digests")
        
        # Generate reflection
        try:
            response: ReasoningResponse = model.generate(prompt, context)
            
            # FIX: Validate reflection response
            if response.thinking and not response.answer:
                logger.warning(f"⚠️  Empty reflection answer at step {step_num}")
                logger.warning(f"   Using thinking as fallback")
                response.answer = response.thinking
                
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return {"error": str(e), "step": step_num}
        
        # Parse reflection
        reflection = parse_reflection_response(response.answer)
        reflection['step'] = step_num
        reflection['raw_thinking'] = response.thinking
        
        # Store in reflection manager
        self.reflection_manager.add_reflection(step_num, reflection)
        
        # Annotate the reflection
        ctx.annotate(f"REFLECTION: Progress={reflection.get('progress')}, Rec={reflection.get('recommendation')}")
        
        # Ingest reflection thinking
        if response.thinking:
            ctx.ingest(f"[REFLECTION]\n{response.thinking}")
        
        logger.info(f"  Progress assessment: {reflection.get('progress')}")
        logger.info(f"  Recommendation: {reflection.get('recommendation')}")
        
        if reflection.get('should_backtrack'):
            logger.warning("  ⚠️  Model suggests backtracking")
        if reflection.get('should_change_approach'):
            logger.info("  💡 Model suggests trying different approach")
        
        return reflection
    
    @step(StepConfig(savepoint=True))
    def _create_branch_point(self, context: Dict, step_num: int) -> Dict:
        """Create savepoint for potential backtracking."""
        ctx = ExecutionContext.current()
        
        logger.info(f"💾 Creating savepoint at step {step_num}")
        
        ctx.create_savepoint({
            "goal_summary": f"Savepoint at step {step_num}",
            "hypotheses": context.get("hypotheses", []),
            "questions": context.get("open_questions", []),
            "decisions": context.get("decisions", []),
            "next_step": f"step_{step_num + 1}"
        })
        
        return context
    
    def _build_prompt(self, problem: str, context: Dict, step_num: int) -> str:
        """Build prompt for reasoning model."""
        prompt = f"""You are solving a challenging mathematics problem. Think step-by-step.

Problem:
{problem}

"""
        
        # Add context from previous steps
        if "digest" in context and context["digest"]:
            digest = context["digest"]
            prompt += f"""Previous progress:
- Proven facts: {digest.get('proven_facts', [])}
- Failed approaches: {digest.get('failed_approaches', [])}
- Current strategy: {digest.get('current_strategy', 'Unknown')}
- Key insights: {digest.get('key_insights', [])}

"""
        
        # Add tool results from previous step
        if "tool_results" in context and context["tool_results"]:
            prompt += "Previous computation results:\n"
            for tool_result in context["tool_results"]:
                tool_name = tool_result.get("tool", "unknown")
                result = tool_result.get("result", "")
                prompt += f"- {tool_name}: {result}\n"
            prompt += "\n"
        
        # Add reflection context if available
        if "last_reflection" in context:
            refl = context["last_reflection"]
            prompt += f"""Your last self-reflection (Step {refl.get('step', '?')}):
- Progress: {refl.get('progress', 'uncertain')}
- Recommendation: {refl.get('recommendation', 'continue')}

"""
            if refl.get('should_change_approach'):
                prompt += "⚠️ You previously suggested trying a different approach.\n\n"
        
        # Add reflection summary
        refl_summary = self.reflection_manager.get_reflection_summary()
        if refl_summary:
            prompt += refl_summary
        
        if step_num == 0:
            prompt += "Begin by analyzing the problem structure and identifying the key mathematical concepts involved.\n"
        else:
            prompt += f"Continue from step {step_num}. Build on previous insights.\n"
        
        prompt += "\nProvide your reasoning and then your answer."
        
        return prompt
    
    def _build_context_from_restore(self, restored: Dict) -> Dict:
        """Build problem context from restored ledger."""
        context = {}
        
        if restored.get("digest"):
            context["digest"] = restored["digest"]
        
        if restored.get("annotations"):
            context["annotations"] = restored["annotations"]
        
        return context
    
    def _get_tool_instructions(self) -> str:
        """Get instructions for using code execution tools."""
        return """

AVAILABLE TOOLS:
You can execute Python code to verify calculations. Use the following format:

<execute_python>
# Your Python code here
# Common imports (numpy, sympy, math) are pre-loaded
result = ...
print(result)
</execute_python>

For SageMath computations (algebraic geometry, Brauer groups, etc.):
<execute_sage>
# Your SageMath code here
</execute_sage>

For quick calculations:
<compute>expression</compute>

Example:
<execute_python>
from sympy import *
x = Symbol('x')
result = integrate(x**2, x)
print(f"Integral: {result}")
</execute_python>

Use these tools to verify your mathematical reasoning with actual computations.
"""
    
    def _handle_tool_calls(self, answer: str) -> List[Dict[str, Any]]:
        """
        Parse and execute tool calls from model response.
        
        Args:
            answer: Model's answer text
            
        Returns:
            List of tool execution results
        """
        if not self.tool_executor:
            return []
        
        results = []
        
        # Parse Python execution requests
        import re
        
        # Match <execute_python>...</execute_python>
        python_pattern = r'<execute_python>(.*?)</execute_python>'
        python_matches = re.findall(python_pattern, answer, re.DOTALL)
        
        for code in python_matches:
            code = code.strip()
            logger.info(f"  Executing Python code ({len(code)} chars)")
            result = self.tool_executor.run_python(code)
            results.append({
                "tool": "python",
                "code": code,
                "result": result
            })
            logger.info(f"  Result: {result[:100]}...")
        
        # Match <execute_sage>...</execute_sage>
        sage_pattern = r'<execute_sage>(.*?)</execute_sage>'
        sage_matches = re.findall(sage_pattern, answer, re.DOTALL)
        
        for code in sage_matches:
            code = code.strip()
            logger.info(f"  Executing SageMath code ({len(code)} chars)")
            result = self.tool_executor.run_sage(code)
            results.append({
                "tool": "sage",
                "code": code,
                "result": result
            })
            logger.info(f"  Result: {result[:100]}...")
        
        # Match <compute>...</compute>
        compute_pattern = r'<compute>(.*?)</compute>'
        compute_matches = re.findall(compute_pattern, answer, re.DOTALL)
        
        for expr in compute_matches:
            expr = expr.strip()
            logger.info(f"  Computing: {expr}")
            result = self.tool_executor.compute_expression(expr)
            results.append({
                "tool": "compute",
                "expression": expr,
                "result": result
            })
            logger.info(f"  Result: {result[:100]}...")
        
        return results
    
    def _extract_decision(self, answer: str) -> str:
        """Extract key decision from answer."""
        # Simple extraction - take first sentence
        sentences = answer.split(".")
        if sentences:
            return sentences[0].strip()[:100]
        return "Continue analysis"
    
    def _is_answer(self, result: Dict) -> bool:
        """Check if result contains a final answer."""
        answer = result.get("answer", "").lower()
        
        # Look for answer indicators
        answer_indicators = [
            "final answer",
            "therefore the answer is",
            "thus the answer is",
            "the solution is",
            "qed",
            "proven"
        ]
        
        return any(indicator in answer for indicator in answer_indicators)
    
    def _is_dead_end(self, result: Dict) -> bool:
        """Check if reasoning hit a dead end."""
        answer = result.get("answer", "").lower()
        thinking = result.get("thinking", "").lower()
        
        # Look for dead end indicators
        dead_end_indicators = [
            "contradiction",
            "doesn't work",
            "cannot proceed",
            "dead end",
            "stuck"
        ]
        
        return any(indicator in answer or indicator in thinking for indicator in dead_end_indicators)
    
    def _verify_and_return(self, result: Dict, problem: str, steps: int) -> Dict:
        """Verify answer and return result."""
        ctx = ExecutionContext.current()
        
        # Get final context
        health = ctx.context_health()
        tracker = ctx._token_tracker if hasattr(ctx, '_token_tracker') else None
        
        return {
            "status": "solved",
            "answer": result.get("answer"),
            "confidence": result.get("confidence", 0.0),
            "steps": steps,
            "reasoning_chars": health.buffer_bytes if health else 0,
            "digests_created": len(ctx.ledger.digests) if hasattr(ctx, 'ledger') else 0,
            "cost": tracker.total_cost_dollars if tracker else 0.0,
            "verified": False,  # Would implement actual verification
        }
    
    def _convergence_result(self, convergence_result: Dict, problem: str, steps: int) -> Dict:
        """Return result for convergence."""
        ctx = ExecutionContext.current()
        
        # Get final context
        health = ctx.context_health()
        tracker = ctx._token_tracker if hasattr(ctx, '_token_tracker') else None
        
        return {
            "status": "converged",
            "answer": convergence_result.get("final_answer"),
            "confidence": convergence_result.get("confidence", 0.0),
            "convergence_reason": convergence_result.get("reason"),
            "convergence_details": convergence_result.get("details"),
            "steps": steps,
            "reasoning_chars": health.buffer_bytes if health else 0,
            "digests_created": len(ctx.ledger.digests) if hasattr(ctx, 'ledger') else 0,
            "cost": tracker.total_cost_dollars if tracker else 0.0,
            "verified": False,
        }
    
    def _timeout_result(self, context: Dict, steps: int) -> Dict:
        """Return result for timeout."""
        return {
            "status": "timeout",
            "steps": steps,
            "partial_context": context
        }
    
    def _max_steps_result(self, context: Dict, steps: int) -> Dict:
        """Return result for max steps reached."""
        return {
            "status": "max_steps",
            "steps": steps,
            "partial_context": context
        }
    
    def _health_warning_handler(self, ctx: ExecutionContext, health):
        """Handle context health warnings."""
        logger.warning(f"⚠️  Context health warning:")
        logger.warning(f"   - Output trend: {health.output_trend}")
        logger.warning(f"   - Retry rate: {health.retry_rate:.1%}")
        logger.warning(f"   - Budget used: {health.budget_used:.0%}")
        
        if health.recommendation == "distill":
            logger.info("   → Triggering distillation")
            ctx.request_distill()
        elif health.recommendation == "savepoint":
            logger.info("   → Creating savepoint")
            ctx.create_savepoint({
                "goal_summary": "Auto-savepoint due to health warning",
                "hypotheses": [],
                "questions": ["Why is context degrading?"],
            })


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="FrontierMath Solver")
    parser.add_argument("--problem", type=str, help="Problem statement or file path")
    parser.add_argument("--resume", type=str, help="Resume workflow ID")
    parser.add_argument("--model", type=str, help="Model provider (ollama, deepseek-api, claude)")
    parser.add_argument("--max-steps", type=int, help="Maximum reasoning steps")
    parser.add_argument("--cost-budget", type=float, help="Cost budget in USD")
    parser.add_argument("--no-code-execution", action="store_true", help="Disable code execution")
    parser.add_argument("--enable-sagemath", action="store_true", help="Enable SageMath execution")
    parser.add_argument("--no-convergence-detection", action="store_true", help="Disable convergence detection")
    
    args = parser.parse_args()
    
    # Load problem
    if args.problem:
        if os.path.isfile(args.problem):
            with open(args.problem, 'r') as f:
                problem = f.read().strip()
        else:
            problem = args.problem
    else:
        # Default test problem
        problem = "Prove that for all primes p > 3, p^2 - 1 is divisible by 24."
    
    # Configure
    model_config = ModelConfig.from_env()
    if args.model:
        model_config.provider = args.model
    
    solver_config = SolverConfig.from_env()
    if args.max_steps:
        solver_config.max_steps = args.max_steps
    if args.cost_budget:
        solver_config.cost_budget = args.cost_budget
    
    # Solve
    solver = FrontierMathSolver(
        model_config,
        solver_config,
        reflection_interval=solver_config.reflection_interval,
        enable_code_execution=not args.no_code_execution,
        enable_sagemath=args.enable_sagemath,
        enable_convergence_detection=not args.no_convergence_detection
    )
    result = solver.solve(problem, workflow_id=args.resume)
    
    # Print result
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Status: {result['status']}")
    if result['status'] in ['solved', 'converged']:
        print(f"Answer: {result['answer']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Steps: {result['steps']}")
        print(f"Cost: ${result.get('cost', 0):.2f}")
        if result['status'] == 'converged':
            print(f"Convergence Reason: {result.get('convergence_reason')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
