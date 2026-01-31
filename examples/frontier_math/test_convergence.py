"""
Test convergence detection functionality.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from convergence import ConvergenceDetector


def test_stable_convergence():
    """Test detection of stable convergence."""
    print("=" * 60)
    print("Test 1: Stable Convergence")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=5,
        convergence_threshold=3
    )
    
    # Simulate model giving same answer 3 times
    answers = [
        "The answer is X = 10^6",
        "The answer is X = 10^6",
        "The answer is X = 10^6"
    ]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Final Answer: {result['final_answer']}")
    print(f"Summary: {detector.get_summary()}")
    print(f"Should Stop: {detector.should_stop()}")
    
    assert result['converged'] == True
    assert result['reason'] == 'stable'
    assert result['confidence'] == 1.0
    assert detector.should_stop() == True
    
    print("✓ Test passed\n")


def test_oscillation_detection():
    """Test detection of oscillation between two answers."""
    print("=" * 60)
    print("Test 2: Oscillation Detection")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=5,
        convergence_threshold=3,
        oscillation_threshold=4
    )
    
    # Simulate model oscillating between two answers
    answers = [
        "X = 10^6",
        "X = 10^7",
        "X = 10^6",
        "X = 10^7",
        "X = 10^6"
    ]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Final Answer: {result['final_answer']}")
    print(f"Oscillation Pattern: {result['details']['oscillation_pattern']}")
    print(f"Summary: {detector.get_summary()}")
    print(f"Should Stop (0.8 threshold): {detector.should_stop(0.8)}")
    print(f"Should Stop (0.5 threshold): {detector.should_stop(0.5)}")
    
    assert result['converged'] == True
    assert result['reason'] == 'oscillating'
    assert result['confidence'] == 0.6
    assert detector.should_stop(0.8) == False  # Below threshold
    assert detector.should_stop(0.5) == True   # Above threshold
    
    print("✓ Test passed\n")


def test_three_way_oscillation():
    """Test detection of 3-way oscillation."""
    print("=" * 60)
    print("Test 3: Three-Way Oscillation")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=6,
        convergence_threshold=3,
        oscillation_threshold=4
    )
    
    # Simulate model cycling between three answers
    answers = [
        "X = 10^5",
        "X = 10^6",
        "X = 10^7",
        "X = 10^5",
        "X = 10^6",
        "X = 10^7"
    ]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Oscillation Pattern: {result['details']['oscillation_pattern']}")
    print(f"Summary: {detector.get_summary()}")
    
    assert result['converged'] == True
    assert result['reason'] == 'oscillating_3way'
    assert result['confidence'] == 0.5
    
    print("✓ Test passed\n")


def test_still_diverging():
    """Test detection when still exploring."""
    print("=" * 60)
    print("Test 4: Still Diverging")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=5,
        convergence_threshold=3
    )
    
    # Simulate model still exploring different answers
    answers = [
        "X = 10^4",
        "X = 10^5",
        "X = 10^6",
        "X = 10^7"
    ]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Unique Answers: {result['details']['unique_answers']}")
    print(f"Summary: {detector.get_summary()}")
    print(f"Should Stop: {detector.should_stop()}")
    
    assert result['converged'] == False
    assert result['reason'] == 'diverging'
    assert detector.should_stop() == False
    
    print("✓ Test passed\n")


def test_insufficient_data():
    """Test when not enough data collected."""
    print("=" * 60)
    print("Test 5: Insufficient Data")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=5,
        convergence_threshold=3
    )
    
    # Only 2 answers
    answers = ["X = 10^6", "X = 10^6"]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Answers Collected: {result['details']['answers_collected']}")
    print(f"Needed: {result['details']['needed']}")
    print(f"Summary: {detector.get_summary()}")
    
    assert result['converged'] == False
    assert result['reason'] == 'insufficient_data'
    
    print("✓ Test passed\n")


def test_value_extraction():
    """Test extraction of numerical values from answers."""
    print("=" * 60)
    print("Test 6: Value Extraction")
    print("=" * 60)
    
    detector = ConvergenceDetector()
    
    # Test various answer formats
    test_cases = [
        ("The answer is X = 10^6", {'X': '6'}),
        ("π₂(10^7) = 123456", {'pi_2': '123456'}),
        ("N = 42 is the smallest", {'N': '42'}),
        ("X = 1000000 and π₂(X) = 50000", {'X': '1000000', 'pi_2': '50000'}),
    ]
    
    for answer, expected in test_cases:
        extracted = detector._extract_values(answer)
        print(f"Answer: {answer}")
        print(f"Extracted: {extracted}")
        print(f"Expected: {expected}")
        
        for key, value in expected.items():
            assert key in extracted, f"Missing key: {key}"
            assert extracted[key] == value, f"Wrong value for {key}: {extracted[key]} != {value}"
        
        print("✓ Passed")
        print()
    
    print("✓ All extraction tests passed\n")


def test_stable_values_convergence():
    """Test convergence based on extracted values matching."""
    print("=" * 60)
    print("Test 7: Stable Values Convergence")
    print("=" * 60)
    
    detector = ConvergenceDetector(
        window_size=5,
        convergence_threshold=3
    )
    
    # Different wording but same values
    answers = [
        "The answer is X = 10^6",
        "I believe X = 10^6 is correct",
        "Therefore, X = 10^6"
    ]
    
    for i, answer in enumerate(answers):
        detector.add_answer(answer, i)
    
    result = detector.check_convergence()
    
    print(f"Converged: {result['converged']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Summary: {detector.get_summary()}")
    
    # Should converge based on extracted values
    assert result['converged'] == True
    assert result['reason'] in ['stable', 'stable_values']
    
    print("✓ Test passed\n")


def run_all_tests():
    """Run all convergence detection tests."""
    print("\n" + "=" * 60)
    print("CONVERGENCE DETECTION TESTS")
    print("=" * 60 + "\n")
    
    tests = [
        test_stable_convergence,
        test_oscillation_detection,
        test_three_way_oscillation,
        test_still_diverging,
        test_insufficient_data,
        test_value_extraction,
        test_stable_values_convergence
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}\n")
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
