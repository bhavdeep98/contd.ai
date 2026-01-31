"""
Test distillation functions to verify they work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from distill import simple_math_distill, _extract_proven_facts, _extract_failed_approaches, _extract_strategy, _extract_insights


def test_extract_proven_facts():
    """Test extraction of proven facts from reasoning text."""
    text = """
    We start by analyzing the problem. Therefore, p^2 - 1 = (p-1)(p+1).
    This is a key factorization. Thus, we have two consecutive even numbers.
    We have shown that one of them must be divisible by 4.
    """
    
    facts = _extract_proven_facts(text)
    print(f"✓ Extracted {len(facts)} proven facts:")
    for i, fact in enumerate(facts, 1):
        print(f"  {i}. {fact}")
    
    assert len(facts) > 0, "Should extract at least one fact"
    assert any("p^2 - 1" in fact or "consecutive" in fact for fact in facts), "Should find key facts"
    print()


def test_extract_failed_approaches():
    """Test extraction of failed approaches."""
    text = """
    First I tried direct computation but this approach fails because the numbers are too large.
    The algebraic method doesn't work because we get a contradiction with the prime factorization.
    This is a dead end since we cannot proceed with modular arithmetic here.
    """
    
    failures = _extract_failed_approaches(text)
    print(f"✓ Extracted {len(failures)} failed approaches:")
    for i, failure in enumerate(failures, 1):
        print(f"  {i}. {failure}")
    
    assert len(failures) > 0, "Should extract at least one failure"
    print()


def test_extract_strategy():
    """Test extraction of current strategy."""
    text = """
    We've tried several approaches. The current strategy is to use modular arithmetic
    to analyze the divisibility properties. Next step: prove divisibility by 3.
    """
    
    strategy = _extract_strategy(text)
    print(f"✓ Extracted strategy: {strategy}")
    
    assert len(strategy) > 0, "Should extract a strategy"
    assert "modular" in strategy.lower() or "divisibility" in strategy.lower(), "Should find strategy keywords"
    print()


def test_extract_insights():
    """Test extraction of key insights."""
    text = """
    Key insight: consecutive even numbers have special divisibility properties.
    Notice that p ≡ 1 or 2 (mod 3) for all primes p > 3.
    Importantly, this means p^2 ≡ 1 (mod 3).
    """
    
    insights = _extract_insights(text)
    print(f"✓ Extracted {len(insights)} insights:")
    for i, insight in enumerate(insights, 1):
        print(f"  {i}. {insight}")
    
    assert len(insights) > 0, "Should extract at least one insight"
    print()


def test_simple_distill_basic():
    """Test basic distillation without previous digest."""
    reasoning_chunks = [
        """
        We need to compute π_2(X) for X in [10^6, 10^7]. Therefore, we must count primes
        where 2 is a primitive root. The current approach is to use known values from literature.
        Key insight: Artin's constant predicts the density should be around 0.374.
        """,
        """
        Direct computation doesn't work because the range is too large. Thus, we need to
        use asymptotic analysis. Notice that the ratio R(X) fluctuates around C_Artin.
        """
    ]
    
    digest = simple_math_distill(reasoning_chunks)
    
    print("✓ Basic distillation result:")
    print(f"  Proven facts: {len(digest['proven_facts'])}")
    for fact in digest['proven_facts']:
        print(f"    - {fact}")
    print(f"  Failed approaches: {len(digest['failed_approaches'])}")
    for failure in digest['failed_approaches']:
        print(f"    - {failure}")
    print(f"  Strategy: {digest['current_strategy']}")
    print(f"  Insights: {len(digest['key_insights'])}")
    for insight in digest['key_insights']:
        print(f"    - {insight}")
    print(f"  Chunks processed: {digest['chunks_processed']}")
    print(f"  Total chars: {digest['total_chars']}")
    
    assert digest['chunks_processed'] == 2, "Should process 2 chunks"
    assert digest['total_chars'] > 0, "Should have non-zero chars"
    print()


def test_simple_distill_with_previous():
    """Test distillation with previous digest (accumulation)."""
    reasoning_chunks_1 = [
        "Therefore, p^2 - 1 = (p-1)(p+1). Key insight: these are consecutive even numbers."
    ]
    
    digest_1 = simple_math_distill(reasoning_chunks_1)
    
    reasoning_chunks_2 = [
        "Thus, one of p-1 or p+1 is divisible by 4. Notice that p ≡ 1 or 2 (mod 3)."
    ]
    
    digest_2 = simple_math_distill(reasoning_chunks_2, digest_1)
    
    print("✓ Distillation with accumulation:")
    print(f"  First digest - proven facts: {len(digest_1['proven_facts'])}")
    print(f"  Second digest - proven facts: {len(digest_2['proven_facts'])}")
    
    assert len(digest_2['proven_facts']) >= len(digest_1['proven_facts']), "Should accumulate facts"
    print(f"  ✓ Facts accumulated correctly")
    print()


def test_distill_empty_input():
    """Test distillation with empty or minimal input."""
    reasoning_chunks = [""]
    
    digest = simple_math_distill(reasoning_chunks)
    
    print("✓ Empty input handling:")
    print(f"  Proven facts: {len(digest['proven_facts'])}")
    print(f"  Strategy: {digest['current_strategy']}")
    
    assert digest['chunks_processed'] == 1, "Should process 1 chunk"
    assert digest['current_strategy'] is not None, "Should have default strategy"
    print()


def test_distill_limit_growth():
    """Test that distillation limits growth to prevent unbounded accumulation."""
    # Create 15 facts (more than the 10 limit)
    reasoning_chunks = [
        f"Therefore, fact number {i}." for i in range(15)
    ]
    
    digest = simple_math_distill(reasoning_chunks)
    
    print("✓ Growth limiting:")
    print(f"  Input facts: 15")
    print(f"  Stored facts: {len(digest['proven_facts'])}")
    
    assert len(digest['proven_facts']) <= 10, "Should limit to 10 facts"
    print(f"  ✓ Growth limited correctly")
    print()


def run_all_tests():
    """Run all distillation tests."""
    print("=" * 60)
    print("DISTILLATION FUNCTION TESTS")
    print("=" * 60)
    print()
    
    tests = [
        ("Extract Proven Facts", test_extract_proven_facts),
        ("Extract Failed Approaches", test_extract_failed_approaches),
        ("Extract Strategy", test_extract_strategy),
        ("Extract Insights", test_extract_insights),
        ("Basic Distillation", test_simple_distill_basic),
        ("Distillation with Previous", test_simple_distill_with_previous),
        ("Empty Input", test_distill_empty_input),
        ("Growth Limiting", test_distill_limit_growth),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"Test: {name}")
            print("-" * 60)
            test_func()
            passed += 1
            print(f"✓ PASSED\n")
        except AssertionError as e:
            failed += 1
            print(f"✗ FAILED: {e}\n")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {e}\n")
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
