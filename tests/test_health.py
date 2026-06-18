from fastapi.testclient import TestClient

from leasing_voice_assistant.api.main import create_app
from leasing_voice_assistant.core.config import Settings


def test_health_endpoint_returns_ok() -> None:
    app = create_app(Settings(app_env="test"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "Leasing Voice Assistant",
        "environment": "test",
    }
