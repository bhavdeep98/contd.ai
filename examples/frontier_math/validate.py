"""
Validation functions for Artin's Primitive Root problem outputs.
Catches mathematically impossible values.
"""


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_artin_output(pi_x, pi_2_x, r_x=None, n=None, x=None):
    """
    Validate outputs for Artin's Primitive Root problem.
    
    Args:
        pi_x: Total number of primes <= X
        pi_2_x: Number of primes where 2 is primitive root
        r_x: Ratio pi_2_x / pi_x (optional, will compute if not provided)
        n: Final answer N = floor(10^8 * |R(X) - C_Artin|) (optional)
        x: The value of X (optional, for context)
    
    Raises:
        ValidationError: If any value is mathematically impossible
    """
    errors = []
    
    # Basic sanity checks
    if pi_x <= 0:
        errors.append(f"π(X) must be positive, got {pi_x}")
    
    if pi_2_x < 0:
        errors.append(f"π₂(X) cannot be negative, got {pi_2_x}")
    
    # π₂(X) cannot exceed π(X)
    if pi_2_x > pi_x:
        errors.append(f"π₂(X)={pi_2_x} cannot exceed π(X)={pi_x}")
    
    # π₂(X) should not be close to π(X)/2 (that would mean 50% are primitive roots)
    # Artin's constant is ~37%, so anything above 45% is suspicious
    if pi_x > 0 and pi_2_x > 0.45 * pi_x:
        errors.append(f"π₂(X)={pi_2_x} is {pi_2_x/pi_x:.1%} of π(X)={pi_x}, seems too high (expected ~37%)")
    
    # Compute R(X) if not provided
    if r_x is None and pi_x > 0:
        r_x = pi_2_x / pi_x
    
    # R(X) must be between 0 and 1
    if r_x is not None:
        if not (0 <= r_x <= 1):
            errors.append(f"R(X)={r_x} must be in [0, 1]")
    
    # N must be non-negative integer
    if n is not None:
        if n < 0:
            errors.append(f"N={n} cannot be negative")
        if not isinstance(n, int) and n != int(n):
            errors.append(f"N={n} must be an integer")
    
    # Additional context-specific checks
    if x is not None:
        # Known values for validation
        if x == 1_000_000:
            # π(10^6) = 78,498 (known value)
            if pi_x != 78498:
                errors.append(f"π(10^6) should be 78,498, got {pi_x}")
        
        elif x == 10_000_000:
            # π(10^7) = 664,579 (known value)
            if pi_x != 664579:
                errors.append(f"π(10^7) should be 664,579, got {pi_x}")
    
    # π₂(X) should be roughly 37% of π(X) (Artin's constant ≈ 0.374)
    # Allow wide margin since this is just a heuristic
    if pi_x > 0:
        ratio = pi_2_x / pi_x
        if ratio < 0.1 or ratio > 0.6:
            errors.append(f"π₂/π ratio={ratio:.3f} seems unusual (expected ~0.37)")
    
    if errors:
        raise ValidationError("; ".join(errors))
    
    return True


def validate_step_output(answer_text):
    """
    Parse and validate output from a reasoning step.
    
    Args:
        answer_text: The answer text from the model
    
    Returns:
        dict with extracted values, or None if parsing fails
    """
    import re
    
    result = {}
    
    # Try to extract π(X)
    pi_match = re.search(r'π\(10\^?[₇7]\)\s*=\s*(\d+(?:[,\s]\d+)*)', answer_text)
    if not pi_match:
        pi_match = re.search(r'π\((\d{7,})\)\s*=\s*(\d+(?:[,\s]\d+)*)', answer_text)
    
    if pi_match:
        if len(pi_match.groups()) == 2:
            x_str = pi_match.group(1).replace(',', '').replace(' ', '')
            pi_str = pi_match.group(2).replace(',', '').replace(' ', '')
            result['x'] = int(x_str) if x_str.isdigit() else 10_000_000
            result['pi_x'] = int(pi_str)
        else:
            pi_str = pi_match.group(1).replace(',', '').replace(' ', '')
            result['pi_x'] = int(pi_str)
            result['x'] = 10_000_000  # Assume 10^7
    
    # Try to extract π₂(X)
    pi2_match = re.search(r'π[_₂2]\(10\^?[₇7]\)\s*=\s*(\d+(?:[,\s]\d+)*)', answer_text)
    if pi2_match:
        pi2_str = pi2_match.group(1).replace(',', '').replace(' ', '')
        result['pi_2_x'] = int(pi2_str)
    else:
        # Try to extract from fraction like "248749/664579"
        frac_match = re.search(r'(\d+(?:[,\s]\d+)*)\s*/\s*(\d+(?:[,\s]\d+)*)', answer_text)
        if frac_match:
            numerator = frac_match.group(1).replace(',', '').replace(' ', '')
            denominator = frac_match.group(2).replace(',', '').replace(' ', '')
            result['pi_2_x'] = int(numerator)
            # If we haven't found pi_x yet, use denominator
            if 'pi_x' not in result:
                result['pi_x'] = int(denominator)
    
    # Try to extract R(X)
    r_match = re.search(r'R\([^)]+\)\s*[=≈]\s*(0\.\d+)', answer_text)
    if r_match:
        result['r_x'] = float(r_match.group(1))
    
    # Try to extract N
    n_match = re.search(r'N\s*=\s*(\d+(?:,\d+)*)', answer_text)
    if n_match:
        n_str = n_match.group(1).replace(',', '')
        result['n'] = int(n_str)
    
    # Try validation if we have enough info
    if 'pi_x' in result and 'pi_2_x' in result:
        try:
            validate_artin_output(
                pi_x=result['pi_x'],
                pi_2_x=result['pi_2_x'],
                r_x=result.get('r_x'),
                n=result.get('n'),
                x=result.get('x')
            )
            result['valid'] = True
        except ValidationError as e:
            result['valid'] = False
            result['validation_error'] = str(e)
    
    return result if result else None


def check_known_values():
    """Return known correct values for reference."""
    return {
        'pi_10_6': 78498,
        'pi_10_7': 664579,
        'c_artin': 0.3739558136,
        'x_range': (1_000_000, 10_000_000),
    }
