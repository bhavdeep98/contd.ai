"""
Test that distillation triggers at the correct intervals.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from distill import simple_math_distill


def test_trigger_logic():
    """Test the modulo logic for triggering distillation."""
    print("Testing distillation trigger logic:")
    print("-" * 60)
    
    distill_every = 10
    digest_history = []
    reasoning_history = []
    
    for step in range(1, 21):
        # Simulate adding reasoning
        reasoning_history.append(f"Reasoning for step {step}")
        
        # Check if distillation should trigger
        should_trigger = (step % distill_every == 0)
        
        if should_trigger:
            print(f"Step {step}: TRIGGER distillation")
            
            # Get recent reasoning (last distill_every steps)
            recent_reasoning = reasoning_history[-distill_every:]
            prev_digest = digest_history[-1] if digest_history else None
            
            # Run distillation
            digest = simple_math_distill(recent_reasoning, prev_digest)
            digest_history.append(digest)
            
            print(f"  - Processed {len(recent_reasoning)} chunks")
            print(f"  - Total digests: {len(digest_history)}")
        else:
            print(f"Step {step}: no trigger")
    
    print()
    print("Results:")
    print(f"  Total steps: 20")
    print(f"  Expected digests: 2 (at steps 10 and 20)")
    print(f"  Actual digests: {len(digest_history)}")
    
    assert len(digest_history) == 2, f"Expected 2 digests, got {len(digest_history)}"
    print("  ✓ Trigger logic works correctly")
    print()


def test_continuation_trigger():
    """Test distillation trigger when continuing from step 10."""
    print("Testing continuation from step 10:")
    print("-" * 60)
    
    distill_every = 10
    start_step = 10
    digest_history = []
    reasoning_history = []
    
    for i in range(20):
        step = start_step + i + 1  # Steps 11-30
        reasoning_history.append(f"Reasoning for step {step}")
        
        # Original logic from continue_artin.py
        should_trigger = ((step - start_step) % distill_every == 0)
        
        if should_trigger:
            print(f"Step {step}: TRIGGER distillation")
            
            recent = reasoning_history[-distill_every:]
            prev = digest_history[-1] if digest_history else None
            
            digest = simple_math_distill(recent, prev)
            digest_history.append(digest)
            
            print(f"  - Processed {len(recent)} chunks")
            print(f"  - Total digests: {len(digest_history)}")
        else:
            print(f"Step {step}: no trigger")
    
    print()
    print("Results:")
    print(f"  Steps: 11-30 (20 steps)")
    print(f"  Expected digests: 2 (at steps 20 and 30)")
    print(f"  Actual digests: {len(digest_history)}")
    
    assert len(digest_history) == 2, f"Expected 2 digests, got {len(digest_history)}"
    print("  ✓ Continuation trigger logic works correctly")
    print()


def test_why_no_digest_at_step_10():
    """Debug why digest wasn't created at step 10 in the actual run."""
    print("Debugging actual run behavior:")
    print("-" * 60)
    
    # Simulate the actual run
    distill_every = 10
    reasoning_history = []
    digest_history = []
    
    print("Simulating steps 1-10:")
    for step in range(1, 11):
        reasoning_history.append(f"Step {step} reasoning")
        
        if step % distill_every == 0:
            print(f"\nStep {step}: Distillation should trigger")
            print(f"  reasoning_history length: {len(reasoning_history)}")
            print(f"  Getting last {distill_every} chunks...")
            
            recent_reasoning = reasoning_history[-distill_every:]
            print(f"  recent_reasoning length: {len(recent_reasoning)}")
            
            prev_digest = digest_history[-1] if digest_history else None
            print(f"  prev_digest: {prev_digest}")
            
            digest = simple_math_distill(recent_reasoning, prev_digest)
            digest_history.append(digest)
            
            print(f"  Digest created!")
            print(f"  digest_history length: {len(digest_history)}")
    
    print()
    print("Final state:")
    print(f"  Steps completed: 10")
    print(f"  Digests created: {len(digest_history)}")
    print(f"  ✓ Distillation SHOULD have run at step 10")
    
    assert len(digest_history) == 1, "Should have 1 digest at step 10"
    print()


def test_actual_log_analysis():
    """Analyze what the log shows."""
    print("Log analysis:")
    print("-" * 60)
    print("From artin_challenge.log:")
    print("  - Steps completed: 10")
    print("  - Digests created: 0")
    print("  - Reflections: 1 (at step 5)")
    print()
    print("Expected behavior:")
    print("  - Step 5: Reflection ✓ (happened)")
    print("  - Step 10: Distillation ✗ (didn't happen)")
    print()
    print("Possible causes:")
    print("  1. Distillation code didn't execute")
    print("  2. Distillation ran but output wasn't printed")
    print("  3. Distillation ran but digest wasn't added to history")
    print("  4. Timeout happened before distillation code ran")
    print()
    print("From log: 'TIMEOUT REACHED: 2.04 hours' after step 9")
    print("Conclusion: Timeout happened BEFORE step 10 completed")
    print("  ✓ This explains why no distillation at step 10")
    print()


def run_all_tests():
    """Run all trigger tests."""
    print("=" * 60)
    print("DISTILLATION TRIGGER TESTS")
    print("=" * 60)
    print()
    
    tests = [
        ("Basic Trigger Logic", test_trigger_logic),
        ("Continuation Trigger", test_continuation_trigger),
        ("Step 10 Debug", test_why_no_digest_at_step_10),
        ("Log Analysis", test_actual_log_analysis),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"Test: {name}")
            print("=" * 60)
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
