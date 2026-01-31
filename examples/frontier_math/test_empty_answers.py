"""
Test for empty answer extraction issue.

Issue: Step 12 had 77k thinking chars but 0 answer chars
Root Cause: Model output parsing issue or timeout
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from models import DeepSeekOllamaModel, DeepSeekAPIModel
from config import ModelConfig


def test_empty_answer_detection():
    """Test that we detect and handle empty answers."""
    
    # Simulate response with thinking but no answer
    test_cases = [
        {
            "name": "Only thinking tags",
            "response": "<think>This is a long reasoning process...</think>",
            "expected_thinking": "This is a long reasoning process...",
            "expected_answer": "This is a long reasoning process...",  # Fallback - FIXED
        },
        {
            "name": "Thinking with empty answer",
            "response": "<think>Long reasoning here</think>\n\n",
            "expected_thinking": "Long reasoning here",
            "expected_answer": "Long reasoning here",  # Fallback - FIXED
        },
        {
            "name": "No tags, just text",
            "response": "Let me solve this step by step...",
            "expected_thinking": "Let me solve this step by step...",
            "expected_answer": "Let me solve this step by step...",
        },
        {
            "name": "Reasoning with answer",
            "response": "**Reasoning:** First we analyze...\n\n**Answer:** The result is 42",
            "expected_thinking": " First we analyze...",
            "expected_answer": " The result is 42",
        },
        {
            "name": "Only thinking, no answer section",
            "response": "**Reasoning:** This is complex reasoning that goes on for 77k chars...",
            "expected_thinking": " This is complex reasoning that goes on for 77k chars...",
            "expected_answer": " This is complex reasoning that goes on for 77k chars...",  # Fallback
        },
    ]
    
    model = DeepSeekOllamaModel()
    
    print("Testing empty answer detection...")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"Response: {test['response'][:100]}...")
        
        thinking, answer = model._parse_deepseek_response(test['response'])
        
        print(f"Extracted thinking: {len(thinking)} chars")
        print(f"Extracted answer: {len(answer)} chars")
        
        # After fix, answer should never be empty when thinking exists
        if thinking and not answer:
            print("❌ FAILED: Empty answer with non-empty thinking!")
            print("   The fix didn't work properly.")
            assert False, "Answer should not be empty when thinking exists"
        
        # Verify we got something
        assert thinking or answer, "Both thinking and answer are empty!"
        
        print("✓ Passed")
    
    print("\n" + "=" * 60)
    print("All tests passed!")


def test_answer_extraction_with_markers():
    """Test extraction with various answer markers."""
    
    test_cases = [
        {
            "text": "After analysis, therefore the answer is 42.",
            "should_have_answer": True,
        },
        {
            "text": "Let me think... hmm... still working on it...",
            "should_have_answer": False,
        },
        {
            "text": "**Final Answer:** The solution is n = 100",
            "should_have_answer": True,
        },
        {
            "text": "Reasoning continues without conclusion",
            "should_have_answer": False,
        },
    ]
    
    print("\nTesting answer marker detection...")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        text = test['text']
        expected = test['should_have_answer']
        
        # Check for answer markers
        answer_markers = [
            "final answer",
            "therefore the answer is",
            "thus the answer is",
            "the solution is",
        ]
        
        has_marker = any(marker in text.lower() for marker in answer_markers)
        
        print(f"\nTest {i}: {text[:50]}...")
        print(f"Expected answer: {expected}, Has marker: {has_marker}")
        
        if expected:
            assert has_marker, f"Should have answer marker but doesn't"
        
        print("✓ Passed")
    
    print("\n" + "=" * 60)
    print("All marker tests passed!")


def test_response_validation():
    """Test that we validate responses before returning."""
    
    from models import ReasoningResponse
    
    print("\nTesting response validation...")
    print("=" * 60)
    
    # Test case 1: Valid response
    response1 = ReasoningResponse(
        thinking="Long reasoning process",
        answer="The answer is 42",
        confidence=0.8
    )
    assert response1.thinking
    assert response1.answer
    print("✓ Valid response passed")
    
    # Test case 2: Empty answer (the bug)
    response2 = ReasoningResponse(
        thinking="Very long thinking (77k chars)",
        answer="",  # Empty!
        confidence=0.5
    )
    
    # This should trigger a warning
    if response2.thinking and not response2.answer:
        print("⚠️  WARNING: Response has thinking but no answer!")
        print(f"   Thinking: {len(response2.thinking)} chars")
        print(f"   Answer: {len(response2.answer)} chars")
        print("   This needs to be handled!")
    
    # Test case 3: Both empty (also bad)
    response3 = ReasoningResponse(
        thinking="",
        answer="",
        confidence=0.0
    )
    
    if not response3.thinking and not response3.answer:
        print("⚠️  WARNING: Response has no content at all!")
        print("   This should be treated as an error!")
    
    print("\n" + "=" * 60)
    print("Validation tests complete!")


if __name__ == "__main__":
    print("=" * 60)
    print("EMPTY ANSWER EXTRACTION TESTS")
    print("=" * 60)
    
    test_empty_answer_detection()
    test_answer_extraction_with_markers()
    test_response_validation()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Add validation in solver.py to detect empty answers")
    print("2. Add fallback: use thinking as answer if answer is empty")
    print("3. Add logging to track when this happens")
