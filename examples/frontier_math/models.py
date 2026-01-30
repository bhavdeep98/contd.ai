"""
Unified interface for reasoning models.

Supports:
- DeepSeek R1 (local via Ollama or API)
- Claude Extended Thinking
- Custom models with thinking token support
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResponse:
    """Unified response from reasoning models."""
    
    thinking: str  # Raw thinking tokens
    answer: str  # Final answer
    confidence: float = 0.0  # Confidence score (0-1)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ReasoningModel(ABC):
    """Abstract base class for reasoning models."""
    
    @abstractmethod
    def generate(self, prompt: str, context: Optional[Dict] = None) -> ReasoningResponse:
        """Generate response with thinking tokens."""
        pass
    
    @abstractmethod
    def supports_thinking_tokens(self) -> bool:
        """Check if model exposes thinking tokens."""
        pass


class DeepSeekOllamaModel(ReasoningModel):
    """DeepSeek R1 via Ollama (local)."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-r1"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("requests library required for Ollama. Install: pip install requests")
    
    def generate(self, prompt: str, context: Optional[Dict] = None) -> ReasoningResponse:
        """Generate with Ollama API."""
        url = f"{self.base_url}/api/generate"
        
        # DeepSeek R1 outputs <think> tags by default
        # We just need to make sure we're not hiding them
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 8192,  # Allow longer responses for thinking
            },
            # Ensure we get raw output with <think> tags
            "raw": True,  # Don't apply any template processing
        }
        
        try:
            logger.info(f"Calling Ollama API: {url}")
            response = self.requests.post(url, json=payload, timeout=600)
            response.raise_for_status()
            data = response.json()
            
            # Ollama returns full response in 'response' field
            # DeepSeek R1 should include <think>...</think> tags
            full_response = data.get("response", "")
            logger.info(f"Received response: {len(full_response)} chars")
            
            # Debug: Check if we have think tags
            has_think_tags = "<think>" in full_response and "</think>" in full_response
            logger.info(f"Response has <think> tags: {has_think_tags}")
            
            # Extract thinking and answer
            thinking, answer = self._parse_deepseek_response(full_response)
            
            return ReasoningResponse(
                thinking=thinking,
                answer=answer,
                confidence=self._estimate_confidence(thinking, answer),
                metadata={
                    "model": self.model,
                    "provider": "ollama",
                    "has_think_tags": has_think_tags,
                }
            )
        except self.requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after 600s")
            raise
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    def _parse_deepseek_response(self, response: str) -> tuple[str, str]:
        """Parse DeepSeek R1 response with <think> tags or extract reasoning."""
        # DeepSeek R1 format: <think>reasoning</think>answer
        if "<think>" in response and "</think>" in response:
            start = response.index("<think>") + 7
            end = response.index("</think>")
            thinking = response[start:end].strip()
            answer = response[end + 8:].strip()
            return thinking, answer
        
        # Alternative: Check if response has clear reasoning structure
        # DeepSeek R1 often outputs reasoning without explicit tags
        # Look for patterns like "Reasoning:", "Step-by-step:", etc.
        reasoning_markers = [
            "**Detailed Reasoning:**",
            "**Reasoning:**",
            "**Step-by-step:**",
            "Let me think",
            "Let's solve",
            "To solve this",
        ]
        
        for marker in reasoning_markers:
            if marker in response:
                # Split at the marker - everything before is thinking
                parts = response.split(marker, 1)
                if len(parts) == 2:
                    # The reasoning section is the thinking
                    # Try to find where the final answer starts
                    reasoning_section = parts[1]
                    
                    # Look for answer markers
                    answer_markers = [
                        "**Final Answer:**",
                        "**Answer:**",
                        "Therefore, the answer is",
                        "The answer is",
                        "So the result is",
                    ]
                    
                    for ans_marker in answer_markers:
                        if ans_marker in reasoning_section:
                            split_point = reasoning_section.index(ans_marker)
                            thinking = reasoning_section[:split_point].strip()
                            answer = reasoning_section[split_point:].strip()
                            return thinking, answer
                    
                    # No clear answer marker - treat most as thinking, last paragraph as answer
                    paragraphs = reasoning_section.strip().split('\n\n')
                    if len(paragraphs) > 1:
                        thinking = '\n\n'.join(paragraphs[:-1])
                        answer = paragraphs[-1]
                        return thinking, answer
                    else:
                        # Single block - treat as thinking
                        return reasoning_section.strip(), reasoning_section.strip()
        
        # No clear structure - treat entire response as both thinking and answer
        # This ensures we capture the reasoning even if format is unexpected
        return response.strip(), response.strip()
    
    def _estimate_confidence(self, thinking: str, answer: str) -> float:
        """Estimate confidence from thinking tokens (heuristic)."""
        # Simple heuristic: longer thinking = more confidence
        # In production, could use model's own confidence scores
        if not thinking:
            return 0.5
        
        # Check for uncertainty markers
        uncertainty_markers = ["unsure", "maybe", "possibly", "might", "unclear"]
        has_uncertainty = any(marker in thinking.lower() for marker in uncertainty_markers)
        
        if has_uncertainty:
            return 0.6
        
        # Check for strong confidence markers
        confidence_markers = ["therefore", "thus", "clearly", "obviously", "proven"]
        has_confidence = any(marker in thinking.lower() for marker in confidence_markers)
        
        if has_confidence:
            return 0.9
        
        return 0.75
    
    def supports_thinking_tokens(self) -> bool:
        return True


class DeepSeekAPIModel(ReasoningModel):
    """DeepSeek R1 via official API."""
    
    def __init__(self, api_key: str, model: str = "deepseek-reasoner"):
        self.api_key = api_key
        self.model = model
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
        except ImportError:
            raise ImportError("openai library required for DeepSeek API. Install: pip install openai")
    
    def generate(self, prompt: str, context: Optional[Dict] = None) -> ReasoningResponse:
        """Generate with DeepSeek API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            
            # DeepSeek API returns reasoning_content separately
            message = response.choices[0].message
            thinking = getattr(message, 'reasoning_content', '')
            answer = message.content
            
            return ReasoningResponse(
                thinking=thinking,
                answer=answer,
                confidence=0.8,  # API doesn't provide confidence
                metadata={
                    "model": self.model,
                    "provider": "deepseek-api",
                    "usage": response.usage.model_dump() if response.usage else {}
                }
            )
        except Exception as e:
            logger.error(f"DeepSeek API generation failed: {e}")
            raise
    
    def supports_thinking_tokens(self) -> bool:
        return True


class ClaudeExtendedThinkingModel(ReasoningModel):
    """Claude with Extended Thinking."""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", thinking_budget: int = 32000):
        self.api_key = api_key
        self.model = model
        self.thinking_budget = thinking_budget
        
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic library required for Claude. Install: pip install anthropic")
    
    def generate(self, prompt: str, context: Optional[Dict] = None) -> ReasoningResponse:
        """Generate with Claude Extended Thinking."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                },
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract thinking and text blocks
            thinking = ""
            answer = ""
            
            for block in response.content:
                if block.type == "thinking":
                    thinking = block.thinking
                elif block.type == "text":
                    answer = block.text
            
            return ReasoningResponse(
                thinking=thinking,
                answer=answer,
                confidence=0.85,  # Claude doesn't provide confidence
                metadata={
                    "model": self.model,
                    "provider": "claude",
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    }
                }
            )
        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            raise
    
    def supports_thinking_tokens(self) -> bool:
        return True


def create_model(config) -> ReasoningModel:
    """Factory function to create reasoning model from config."""
    provider = config.provider.lower()
    
    if provider == "ollama":
        return DeepSeekOllamaModel(
            base_url=config.base_url or "http://localhost:11434",
            model=config.model_name
        )
    elif provider == "deepseek-api":
        if not config.api_key:
            raise ValueError("DEEPSEEK_API_KEY required for deepseek-api provider")
        return DeepSeekAPIModel(
            api_key=config.api_key,
            model=config.model_name
        )
    elif provider == "claude":
        if not config.api_key:
            raise ValueError("ANTHROPIC_API_KEY required for claude provider")
        return ClaudeExtendedThinkingModel(
            api_key=config.api_key,
            model=config.model_name,
            thinking_budget=config.thinking_budget
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
