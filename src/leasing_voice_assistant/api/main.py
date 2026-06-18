"""FastAPI control-plane entrypoint."""

from fastapi import FastAPI

from leasing_voice_assistant.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": app_settings.app_name,
            "environment": app_settings.app_env,
        }

    return app


app = create_app()


def run() -> None:
    """Run the API with uvicorn for console-script usage."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "leasing_voice_assistant.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "local",
    )
