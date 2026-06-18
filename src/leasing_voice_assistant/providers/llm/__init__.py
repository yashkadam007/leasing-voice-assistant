"""LLM provider adapters."""

from leasing_voice_assistant.providers.llm.base import LLMAdapter
from leasing_voice_assistant.providers.llm.openrouter import OpenRouterLLMAdapter

__all__ = ["LLMAdapter", "OpenRouterLLMAdapter"]
