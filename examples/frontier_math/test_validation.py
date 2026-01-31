"""
Test validation functions for Artin problem outputs.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from validate import validate_artin_output, validate_step_output, ValidationError, check_known_values


def test_valid_outputs():
    """Test validation with correct values."""
    print("Test: Valid outputs")
    print("-" * 60)
    
    # Valid case: X = 10^6
    try:
        validate_artin_output(pi_x=78498, pi_2_x=29341, x=1_000_000)
        print("✓ Valid X=10^6 case passed")
    except ValidationError as e:
        print(f"✗ Should be valid: {e}")
        raise
    
    # Valid case: X = 10^7
    try:
        validate_artin_output(pi_x=664579, pi_2_x=248749, x=10_000_000)
        print("✓ Valid X=10^7 case passed")
    except ValidationError as e:
        print(f"✗ Should be valid: {e}")
        raise
    
    # Valid with R(X)
    try:
        validate_artin_output(pi_x=100, pi_2_x=37, r_x=0.37)
        print("✓ Valid with R(X) passed")
    except ValidationError as e:
        print(f"✗ Should be valid: {e}")
        raise
    
    # Valid with N
    try:
        validate_artin_output(pi_x=100, pi_2_x=37, n=34129)
        print("✓ Valid with N passed")
    except ValidationError as e:
        print(f"✗ Should be valid: {e}")
        raise
    
    print()


def test_invalid_pi_2_exceeds_pi():
    """Test that π₂(X) > π(X) is caught."""
    print("Test: π₂(X) > π(X) detection")
    print("-" * 60)
    
    try:
        # This was the actual bug from step 15: π₂(10^7) = 332,136 but π(10^7) = 664,579
        # 332,136 is exactly half, which is impossible (should be ~37%)
        validate_artin_output(pi_x=664579, pi_2_x=332136, x=10_000_000)
        print("✗ Should have raised ValidationError")
        assert False, "Should have caught π₂ = π/2"
    except ValidationError as e:
        print(f"✓ Caught error: {e}")
        assert "too high" in str(e).lower(), f"Should mention ratio is too high, got: {e}"
    
    print()


def test_invalid_negative_values():
    """Test that negative values are caught."""
    print("Test: Negative value detection")
    print("-" * 60)
    
    try:
        validate_artin_output(pi_x=-100, pi_2_x=37)
        print("✗ Should have raised ValidationError for negative π(X)")
        assert False
    except ValidationError as e:
        print(f"✓ Caught negative π(X): {e}")
    
    try:
        validate_artin_output(pi_x=100, pi_2_x=-37)
        print("✗ Should have raised ValidationError for negative π₂(X)")
        assert False
    except ValidationError as e:
        print(f"✓ Caught negative π₂(X): {e}")
    
    try:
        validate_artin_output(pi_x=100, pi_2_x=37, n=-1000)
        print("✗ Should have raised ValidationError for negative N")
        assert False
    except ValidationError as e:
        print(f"✓ Caught negative N: {e}")
    
    print()


def test_invalid_r_x_range():
    """Test that R(X) outside [0,1] is caught."""
    print("Test: R(X) range validation")
    print("-" * 60)
    
    try:
        validate_artin_output(pi_x=100, pi_2_x=37, r_x=1.5)
        print("✗ Should have raised ValidationError for R(X) > 1")
        assert False
    except ValidationError as e:
        print(f"✓ Caught R(X) > 1: {e}")
    
    try:
        validate_artin_output(pi_x=100, pi_2_x=37, r_x=-0.1)
        print("✗ Should have raised ValidationError for R(X) < 0")
        assert False
    except ValidationError as e:
        print(f"✓ Caught R(X) < 0: {e}")
    
    print()


def test_known_value_validation():
    """Test validation against known correct values."""
    print("Test: Known value validation")
    print("-" * 60)
    
    known = check_known_values()
    print(f"Known π(10^6) = {known['pi_10_6']}")
    print(f"Known π(10^7) = {known['pi_10_7']}")
    
    # Correct value should pass
    try:
        validate_artin_output(pi_x=78498, pi_2_x=29341, x=1_000_000)
        print("✓ Correct π(10^6) = 78,498 accepted")
    except ValidationError as e:
        print(f"✗ Should accept correct value: {e}")
        raise
    
    # Incorrect value should fail
    try:
        validate_artin_output(pi_x=80000, pi_2_x=29341, x=1_000_000)
        print("✗ Should have rejected incorrect π(10^6)")
        assert False
    except ValidationError as e:
        print(f"✓ Rejected incorrect π(10^6): {e}")
    
    print()


def test_parse_step_output():
    """Test parsing and validation of model output."""
    print("Test: Parse step output")
    print("-" * 60)
    
    # Valid output from step 16
    output1 = """
    The maximum absolute difference |R(X) - C_Artin| for X in [10^6, 10^7]
    occurs at X = 10^7, where π(10^7) = 664579 and π₂(10^7) = 248749.
    R(10^7) = 248749/664579 ≈ 0.3743 and C_Artin ≈ 0.373955813619202.
    The difference is approximately 0.000339793580798,
    and multiplying by 10^8 and taking the floor gives N = 33979.
    """
    
    result1 = validate_step_output(output1)
    print(f"Parsed output 1:")
    if result1:
        print(f"  X = {result1.get('x')}")
        print(f"  π(X) = {result1.get('pi_x')}")
        print(f"  π₂(X) = {result1.get('pi_2_x')}")
        print(f"  R(X) = {result1.get('r_x')}")
        print(f"  N = {result1.get('n')}")
        print(f"  Valid: {result1.get('valid')}")
        if not result1.get('valid'):
            print(f"  Error: {result1.get('validation_error')}")
    else:
        print("  Failed to parse")
    
    assert result1 is not None, "Should parse output"
    assert result1.get('pi_x') == 664579, f"Expected π(X)=664579, got {result1.get('pi_x')}"
    assert result1.get('pi_2_x') == 248749, f"Expected π₂(X)=248749, got {result1.get('pi_2_x')}"
    assert result1.get('valid') == True, f"Should be valid: {result1.get('validation_error')}"
    print("✓ Valid output parsed correctly")
    print()
    
    # Invalid output from step 15 (impossible π₂ value)
    output2 = """
    The maximum occurs at X = 10^7, where π(10^7) = 664579 and π₂(10^7) = 332136.
    R(10^7) = 332136/664579 ≈ 0.4998 and N = 12581321.
    """
    
    result2 = validate_step_output(output2)
    print(f"Parsed output 2:")
    if result2:
        print(f"  π(X) = {result2.get('pi_x')}")
        print(f"  π₂(X) = {result2.get('pi_2_x')}")
        print(f"  Valid: {result2.get('valid')}")
        if not result2.get('valid'):
            print(f"  Error: {result2.get('validation_error')}")
    
    assert result2 is not None, "Should parse output"
    assert result2.get('valid') == False, "Should detect invalid π₂ value"
    assert "too high" in result2.get('validation_error', '').lower(), "Should mention ratio is too high"
    print("✓ Invalid output detected correctly")
    print()


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("VALIDATION TESTS")
    print("=" * 60)
    print()
    
    tests = [
        ("Valid Outputs", test_valid_outputs),
        ("π₂ > π Detection", test_invalid_pi_2_exceeds_pi),
        ("Negative Values", test_invalid_negative_values),
        ("R(X) Range", test_invalid_r_x_range),
        ("Known Values", test_known_value_validation),
        ("Parse Output", test_parse_step_output),
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
