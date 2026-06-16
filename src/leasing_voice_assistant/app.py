from typing import TypedDict

from fastapi import FastAPI


class HealthResponse(TypedDict):
    status: str
    service: str


def health() -> HealthResponse:
    return {"status": "ok", "service": "leasing-voice-assistant"}


def create_app() -> FastAPI:
    app = FastAPI(title="Leasing Voice Assistant")

    app.get("/health", response_model=HealthResponse)(health)

    return app


app = create_app()
