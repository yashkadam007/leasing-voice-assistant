"""LiveKit worker entrypoint.

The real room, SIP, provider, and tool behavior will be added by later
milestones. This module stays importable without provider credentials.
"""

from leasing_voice_assistant.core.config import Settings, get_settings
from leasing_voice_assistant.providers.factory import ProviderFactory


def build_worker_config(settings: Settings | None = None) -> dict[str, str | None]:
    """Return the minimal worker configuration shape used by later milestones."""
    app_settings = settings or get_settings()
    return {
        "environment": app_settings.app_env,
        "livekit_url": app_settings.livekit_url,
        "stt_provider": app_settings.stt_provider,
        "tts_provider": app_settings.tts_provider,
        "llm_provider": app_settings.llm_provider,
    }


def build_provider_factory(settings: Settings | None = None) -> ProviderFactory:
    """Return the worker provider factory without constructing runtime clients."""
    return ProviderFactory(settings or get_settings())


def main() -> None:
    """Console-script entrypoint for the worker placeholder."""
    config = build_worker_config()
    print(
        "Leasing voice worker placeholder ready "
        f"(env={config['environment']}, livekit_url={config['livekit_url'] or 'unset'})."
    )
