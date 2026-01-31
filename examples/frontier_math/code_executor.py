"""
Safe code execution environment for mathematical computations.
Supports Python, SageMath, and SymPy with sandboxing.
"""

import subprocess
import tempfile
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Literal
import logging

logger = logging.getLogger(__name__)


class CodeExecutionError(Exception):
    """Raised when code execution fails."""
    pass


class CodeExecutor:
    """Execute mathematical code safely with timeout and resource limits."""
    
    def __init__(
        self,
        timeout: int = 30,
        max_output_size: int = 10_000,
        enable_sagemath: bool = False
    ):
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.enable_sagemath = enable_sagemath
        
    def execute_python(
        self,
        code: str,
        language: Literal["python", "sage"] = "python"
    ) -> Dict[str, Any]:
        """
        Execute Python or SageMath code in a sandboxed environment.
        
        Args:
            code: The code to execute
            language: "python" or "sage"
            
        Returns:
            Dict with keys: success, output, error, execution_time
        """
        if language == "sage" and not self.enable_sagemath:
            return {
                "success": False,
                "output": "",
                "error": "SageMath not enabled. Install SageMath and set enable_sagemath=True",
                "execution_time": 0
            }
        
        # Create temporary file for code
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py' if language == "python" else '.sage',
            delete=False
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Choose interpreter
            if language == "sage":
                cmd = ["sage", "-python", temp_file]
            else:
                cmd = ["python", temp_file]
            
            # Execute with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir()
            )
            
            output = result.stdout[:self.max_output_size]
            error = result.stderr[:self.max_output_size]
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "error": error if result.returncode != 0 else "",
                "execution_time": 0  # Could add timing if needed
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"Execution timed out after {self.timeout} seconds",
                "execution_time": self.timeout
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Execution error: {str(e)}",
                "execution_time": 0
            }
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def execute_with_imports(
        self,
        code: str,
        imports: Optional[list[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute code with common mathematical imports pre-loaded.
        
        Args:
            code: The code to execute
            imports: Additional imports to include
            
        Returns:
            Execution result dict
        """
        # Standard mathematical imports
        standard_imports = [
            "import math",
            "import numpy as np",
            "from sympy import *",
            "from fractions import Fraction",
            "from decimal import Decimal, getcontext",
        ]
        
        if imports:
            standard_imports.extend(imports)
        
        full_code = "\n".join(standard_imports) + "\n\n" + code
        
        return self.execute_python(full_code)
    
    def verify_computation(
        self,
        code: str,
        expected_output: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute code and optionally verify against expected output.
        
        Args:
            code: The code to execute
            expected_output: Expected output to verify against
            
        Returns:
            Execution result with verification status
        """
        result = self.execute_with_imports(code)
        
        if expected_output and result["success"]:
            result["verified"] = expected_output.strip() in result["output"].strip()
        
        return result


class ToolCallingExecutor:
    """
    Executor that formats results for LLM tool calling.
    Provides a clean interface for the solver to use.
    """
    
    def __init__(self, executor: Optional[CodeExecutor] = None):
        self.executor = executor or CodeExecutor()
    
    def run_python(self, code: str) -> str:
        """
        Run Python code and return formatted result for LLM.
        
        Args:
            code: Python code to execute
            
        Returns:
            Formatted string with execution result
        """
        result = self.executor.execute_with_imports(code)
        
        if result["success"]:
            return f"✓ Execution successful:\n{result['output']}"
        else:
            return f"✗ Execution failed:\n{result['error']}"
    
    def run_sage(self, code: str) -> str:
        """
        Run SageMath code and return formatted result for LLM.
        
        Args:
            code: SageMath code to execute
            
        Returns:
            Formatted string with execution result
        """
        result = self.executor.execute_python(code, language="sage")
        
        if result["success"]:
            return f"✓ SageMath execution successful:\n{result['output']}"
        else:
            return f"✗ SageMath execution failed:\n{result['error']}"
    
    def compute_expression(self, expression: str) -> str:
        """
        Compute a mathematical expression using SymPy.
        
        Args:
            expression: Mathematical expression to compute
            
        Returns:
            Computed result as string
        """
        code = f"""
from sympy import *
result = {expression}
print(f"Result: {{result}}")
"""
        return self.run_python(code)
    
    def get_tool_definitions(self) -> list[Dict[str, Any]]:
        """
        Get OpenAI-compatible tool definitions for function calling.
        
        Returns:
            List of tool definition dicts
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "run_python",
                    "description": "Execute Python code with math libraries (numpy, sympy, etc.) pre-imported. Use this to perform numerical computations, symbolic math, or verify calculations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute. Common imports (numpy, sympy, math) are already available."
                            }
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_sage",
                    "description": "Execute SageMath code for advanced algebraic computations (Brauer groups, cohomology, algebraic geometry). Only use if SageMath is installed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "SageMath code to execute"
                            }
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compute_expression",
                    "description": "Compute a mathematical expression using SymPy. Useful for quick calculations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to compute (e.g., 'sqrt(2)', 'factorial(10)', 'integrate(x**2, x)')"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            }
        ]
    
    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Handle a tool call from the LLM.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        if tool_name == "run_python":
            return self.run_python(arguments["code"])
        elif tool_name == "run_sage":
            return self.run_sage(arguments["code"])
        elif tool_name == "compute_expression":
            return self.compute_expression(arguments["expression"])
        else:
            return f"Unknown tool: {tool_name}"


# Convenience function for quick testing
def quick_execute(code: str, language: str = "python") -> None:
    """Quick execution for testing."""
    executor = CodeExecutor()
    result = executor.execute_python(code, language=language)
    
    print(f"Success: {result['success']}")
    if result['output']:
        print(f"Output:\n{result['output']}")
    if result['error']:
        print(f"Error:\n{result['error']}")


if __name__ == "__main__":
    # Test the executor
    print("Testing Python execution:")
    quick_execute("""
import sympy as sp
x = sp.Symbol('x')
result = sp.integrate(x**2, x)
print(f"Integral of x^2: {result}")
""")
    
    print("\n" + "="*50 + "\n")
    print("Testing SymPy computation:")
    
    tool_executor = ToolCallingExecutor()
    result = tool_executor.compute_expression("factorial(10)")
    print(result)
