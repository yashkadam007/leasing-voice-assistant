from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.worker.main import build_worker_config


def test_worker_entrypoint_builds_without_provider_credentials() -> None:
    config = build_worker_config(Settings(app_env="test"))

    assert config == {
        "environment": "test",
        "livekit_url": None,
        "stt_provider": "deepgram",
        "tts_provider": "deepgram",
        "llm_provider": "openrouter",
    }
