"""Text-to-speech provider adapters."""

from leasing_voice_assistant.providers.tts.base import TTSAdapter
from leasing_voice_assistant.providers.tts.deepgram import DeepgramTTSAdapter

__all__ = ["DeepgramTTSAdapter", "TTSAdapter"]
