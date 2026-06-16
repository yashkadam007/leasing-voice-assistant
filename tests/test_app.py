from fastapi.testclient import TestClient

from leasing_voice_assistant.app import create_app, health


def test_health_returns_service_status() -> None:
    assert health() == {"status": "ok", "service": "leasing-voice-assistant"}


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "leasing-voice-assistant"}
