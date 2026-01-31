"""
Test code execution functionality.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from code_executor import CodeExecutor, ToolCallingExecutor


def test_basic_python():
    """Test basic Python execution."""
    print("=" * 60)
    print("Test 1: Basic Python Execution")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    code = """
import math
result = math.factorial(10)
print(f"10! = {result}")
"""
    
    result = executor.execute_python(code)
    print(f"Success: {result['success']}")
    print(f"Output: {result['output']}")
    print()


def test_sympy():
    """Test SymPy execution."""
    print("=" * 60)
    print("Test 2: SymPy Symbolic Math")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    code = """
from sympy import *
x = Symbol('x')
expr = x**2 + 2*x + 1
factored = factor(expr)
print(f"Expression: {expr}")
print(f"Factored: {factored}")

# Compute integral
integral = integrate(x**3, x)
print(f"Integral of x^3: {integral}")
"""
    
    result = executor.execute_with_imports(code)
    print(f"Success: {result['success']}")
    print(f"Output: {result['output']}")
    print()


def test_number_theory():
    """Test number theory computation."""
    print("=" * 60)
    print("Test 3: Number Theory (Prime Factorization)")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    code = """
from sympy import factorint, isprime

# Factor a large number
n = 2**16 - 1
factors = factorint(n)
print(f"Factors of {n}: {factors}")

# Check if numbers are prime
for p in [17, 19, 21, 23]:
    print(f"{p} is prime: {isprime(p)}")
"""
    
    result = executor.execute_with_imports(code)
    print(f"Success: {result['success']}")
    print(f"Output: {result['output']}")
    print()


def test_tool_calling():
    """Test tool calling interface."""
    print("=" * 60)
    print("Test 4: Tool Calling Interface")
    print("=" * 60)
    
    tool_executor = ToolCallingExecutor()
    
    # Test compute_expression
    result = tool_executor.compute_expression("factorial(10)")
    print("Compute factorial(10):")
    print(result)
    print()
    
    # Test run_python
    code = """
from sympy import symbols, solve
x = symbols('x')
equation = x**2 - 5*x + 6
solutions = solve(equation, x)
print(f"Solutions to {equation} = 0: {solutions}")
"""
    result = tool_executor.run_python(code)
    print("Solve quadratic equation:")
    print(result)
    print()


def test_timeout():
    """Test timeout handling."""
    print("=" * 60)
    print("Test 5: Timeout Handling")
    print("=" * 60)
    
    executor = CodeExecutor(timeout=2)
    
    code = """
import time
print("Starting long computation...")
time.sleep(5)
print("This should not print")
"""
    
    result = executor.execute_python(code)
    print(f"Success: {result['success']}")
    print(f"Error: {result['error']}")
    print()


def test_error_handling():
    """Test error handling."""
    print("=" * 60)
    print("Test 6: Error Handling")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    code = """
# This will cause a division by zero error
result = 1 / 0
print(result)
"""
    
    result = executor.execute_python(code)
    print(f"Success: {result['success']}")
    print(f"Error: {result['error']}")
    print()


def test_brauer_group_computation():
    """Test computation relevant to the Artin problem."""
    print("=" * 60)
    print("Test 7: Brauer Group Computation (Simplified)")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    code = """
from sympy import *

# Simplified computation for demonstration
# In reality, Brauer group computation requires SageMath

# Example: Compute some algebraic properties
p = 7  # prime
K = GF(p)  # Finite field (symbolic)

print(f"Working over finite field F_{p}")
print(f"Field characteristic: {p}")

# Compute some cohomology-related numbers
# This is a toy example - real Brauer groups need SageMath
h1 = p - 1  # Simplified H^1 dimension
h2 = (p - 1) * (p - 2) // 2  # Simplified H^2 dimension

print(f"Simplified H^1 dimension: {h1}")
print(f"Simplified H^2 dimension: {h2}")
print()
print("Note: Real Brauer group computation requires SageMath")
"""
    
    result = executor.execute_with_imports(code)
    print(f"Success: {result['success']}")
    print(f"Output: {result['output']}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CODE EXECUTION TESTS")
    print("=" * 60 + "\n")
    
    test_basic_python()
    test_sympy()
    test_number_theory()
    test_tool_calling()
    test_timeout()
    test_error_handling()
    test_brauer_group_computation()
    
    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
