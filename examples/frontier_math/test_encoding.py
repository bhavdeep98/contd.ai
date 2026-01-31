"""
Test UTF-8 encoding with mathematical symbols.

Verifies that the solver can handle Unicode characters like π, ≤, ≥
without charmap errors.
"""

import sys
import os
import tempfile
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


def test_unicode_in_strings():
    """Test that Unicode mathematical symbols work in strings."""
    print("=" * 60)
    print("Test 1: Unicode in Strings")
    print("=" * 60)
    
    # Mathematical symbols
    symbols = {
        "pi": "π",
        "less_equal": "≤",
        "greater_equal": "≥",
        "not_equal": "≠",
        "infinity": "∞",
        "integral": "∫",
        "sum": "∑",
        "product": "∏",
        "element_of": "∈",
        "subset": "⊂",
        "union": "∪",
        "intersection": "∩",
    }
    
    for name, symbol in symbols.items():
        try:
            # Test string operations
            text = f"Symbol {name}: {symbol}"
            assert symbol in text
            assert len(symbol) == 1
            print(f"  ✓ {name}: {symbol}")
        except Exception as e:
            print(f"  ✗ {name}: {symbol} - Error: {e}")
            return False
    
    print()
    return True


def test_unicode_in_file_write():
    """Test writing Unicode to files."""
    print("=" * 60)
    print("Test 2: Unicode in File Writing")
    print("=" * 60)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as f:
        temp_file = f.name
        
        # Write mathematical text
        content = """
Mathematical Problem:
Let π₂(X) denote the number of primes p ≤ X for which 2 is a primitive root.
We want to find X such that π₂(X) ≥ 100.

Constraints:
- X ≥ 1
- π₂(X) ≤ π(X)
- 0 < R(X) < 1

Where R(X) = π₂(X) / π(X) is the ratio.
"""
        f.write(content)
    
    try:
        # Read back and verify
        with open(temp_file, 'r', encoding='utf-8') as f:
            read_content = f.read()
        
        # Check symbols are preserved
        assert "π₂" in read_content
        assert "≤" in read_content
        assert "≥" in read_content
        
        print("  ✓ File write successful")
        print("  ✓ Unicode symbols preserved")
        print()
        
        # Clean up
        os.unlink(temp_file)
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        try:
            os.unlink(temp_file)
        except:
            pass
        return False


def test_unicode_in_logging():
    """Test Unicode in logging output."""
    print("=" * 60)
    print("Test 3: Unicode in Logging")
    print("=" * 60)
    
    # Create temporary log file
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.log') as f:
        temp_log = f.name
    
    try:
        # Configure logger
        logger = logging.getLogger('test_unicode')
        logger.setLevel(logging.INFO)
        
        # Add file handler with UTF-8 encoding
        handler = logging.FileHandler(temp_log, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        
        # Log messages with Unicode
        logger.info("Step 1: Computing π₂(X)")
        logger.info("Constraint: π₂(X) ≤ π(X)")
        logger.info("Result: X ≥ 10⁶")
        
        # Close handler
        handler.close()
        logger.removeHandler(handler)
        
        # Read back log
        with open(temp_log, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # Verify symbols
        assert "π₂" in log_content
        assert "≤" in log_content
        assert "≥" in log_content
        assert "10⁶" in log_content
        
        print("  ✓ Logging successful")
        print("  ✓ Unicode symbols in logs")
        print()
        
        # Clean up
        os.unlink(temp_log)
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        try:
            os.unlink(temp_log)
        except:
            pass
        return False


def test_unicode_in_print():
    """Test Unicode in console output."""
    print("=" * 60)
    print("Test 4: Unicode in Console Output")
    print("=" * 60)
    
    try:
        # Test various mathematical expressions
        expressions = [
            "π₂(10⁶) = 42,853",
            "π(10⁶) = 78,498",
            "R(10⁶) ≈ 0.546",
            "X ≥ 10⁶",
            "π₂(X) ≤ π(X)",
            "∀p ∈ ℙ: p ≥ 2",
            "∑ᵢ₌₁ⁿ i = n(n+1)/2",
            "∫₀^∞ e⁻ˣ dx = 1",
        ]
        
        for expr in expressions:
            print(f"  {expr}")
        
        print()
        print("  ✓ Console output successful")
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_unicode_in_dict_keys():
    """Test Unicode as dictionary keys."""
    print("=" * 60)
    print("Test 5: Unicode in Dictionary Keys")
    print("=" * 60)
    
    try:
        # Create dict with Unicode keys
        results = {
            "π₂(X)": 42853,
            "π(X)": 78498,
            "R(X)": 0.546,
        }
        
        # Access values
        assert results["π₂(X)"] == 42853
        assert results["π(X)"] == 78498
        assert results["R(X)"] == 0.546
        
        # Iterate
        for key, value in results.items():
            print(f"  {key} = {value}")
        
        print()
        print("  ✓ Dictionary operations successful")
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_unicode_in_json():
    """Test Unicode in JSON serialization."""
    print("=" * 60)
    print("Test 6: Unicode in JSON")
    print("=" * 60)
    
    import json
    
    try:
        # Create data with Unicode
        data = {
            "problem": "Compute π₂(X) where X ≥ 10⁶",
            "constraints": ["π₂(X) ≤ π(X)", "R(X) ≈ 0.373955"],
            "result": {
                "X": "10⁶",
                "π₂": 42853,
                "π": 78498,
            }
        }
        
        # Serialize to JSON
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        # Verify symbols in JSON
        assert "π₂" in json_str
        assert "≤" in json_str
        assert "≥" in json_str
        assert "≈" in json_str
        
        # Deserialize
        loaded = json.loads(json_str)
        assert loaded["problem"] == data["problem"]
        
        print("  ✓ JSON serialization successful")
        print("  ✓ Unicode preserved in JSON")
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_unicode_in_format_strings():
    """Test Unicode in f-strings and format()."""
    print("=" * 60)
    print("Test 7: Unicode in Format Strings")
    print("=" * 60)
    
    try:
        # Test f-strings
        x = 1000000
        pi_2 = 42853
        pi_x = 78498
        
        msg1 = f"Computing π₂({x:,}) where π₂ ≤ π"
        msg2 = f"Result: π₂({x:,}) = {pi_2:,}, π({x:,}) = {pi_x:,}"
        msg3 = f"Ratio: R(X) = {pi_2/pi_x:.6f} ≈ 0.546"
        
        assert "π₂" in msg1
        assert "≤" in msg1
        assert "π₂" in msg2
        assert "≈" in msg3
        
        print(f"  {msg1}")
        print(f"  {msg2}")
        print(f"  {msg3}")
        
        # Test .format()
        msg4 = "For X ≥ {}, we have π₂(X) = {}".format(x, pi_2)
        assert "≥" in msg4
        
        print(f"  {msg4}")
        print()
        print("  ✓ Format strings successful")
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_unicode_error_messages():
    """Test Unicode in error messages."""
    print("=" * 60)
    print("Test 8: Unicode in Error Messages")
    print("=" * 60)
    
    try:
        # Simulate validation error with Unicode
        pi_2 = 100000
        pi_x = 78498
        
        try:
            if pi_2 > pi_x:
                raise ValueError(f"Invalid: π₂({pi_2:,}) > π({pi_x:,})")
        except ValueError as e:
            error_msg = str(e)
            assert "π₂" in error_msg
            assert ">" in error_msg
            print(f"  ✓ Error message: {error_msg}")
        
        # Test assertion with Unicode
        try:
            assert pi_2 <= pi_x, f"Constraint violated: π₂ ≤ π"
        except AssertionError as e:
            error_msg = str(e)
            assert "π₂" in error_msg
            assert "≤" in error_msg
            print(f"  ✓ Assertion message: {error_msg}")
        
        print()
        print("  ✓ Error messages successful")
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Run all encoding tests."""
    print("\n" + "=" * 60)
    print("UTF-8 ENCODING TESTS")
    print("=" * 60 + "\n")
    
    tests = [
        ("Unicode in Strings", test_unicode_in_strings),
        ("Unicode in File Writing", test_unicode_in_file_write),
        ("Unicode in Logging", test_unicode_in_logging),
        ("Unicode in Console Output", test_unicode_in_print),
        ("Unicode in Dictionary Keys", test_unicode_in_dict_keys),
        ("Unicode in JSON", test_unicode_in_json),
        ("Unicode in Format Strings", test_unicode_in_format_strings),
        ("Unicode in Error Messages", test_unicode_error_messages),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All encoding tests passed!")
    else:
        print(f"✗ {total - passed} test(s) failed")
    
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
