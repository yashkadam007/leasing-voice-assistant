"""Speech-to-text provider adapters."""

from leasing_voice_assistant.providers.stt.base import STTAdapter
from leasing_voice_assistant.providers.stt.deepgram import DeepgramSTTAdapter

__all__ = ["DeepgramSTTAdapter", "STTAdapter"]
