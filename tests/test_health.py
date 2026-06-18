from fastapi.testclient import TestClient

from leasing_voice_assistant.api.main import create_app
from leasing_voice_assistant.core.config import Settings
from leasing_voice_assistant.db.seed import seed_database
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from leasing_voice_assistant.repositories.properties import PropertiesRepository
from leasing_voice_assistant.repositories.prospects import ProspectsRepository


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


def test_prospects_endpoint_returns_captured_interests(tmp_path) -> None:
    database_path = tmp_path / "verification.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_sqlite_engine(database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        properties = PropertiesRepository(session)
        prospects = ProspectsRepository(session)
        aurora = properties.search("Aurora Heights")[0].property
        unit = properties.get_unit_by_number(aurora.id, "8A")
        prospect = prospects.upsert_by_phone("415-555-1212", name="Sam Rivera")
        assert unit is not None
        prospects.create_interest(
            prospect_id=prospect.id,
            unit_id=unit.id,
            notes="Asked for a bay view.",
        )
        session.commit()

    app = create_app(Settings(app_env="test", database_url=database_url))
    client = TestClient(app)

    response = client.get("/prospects")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["prospects"][0]["phone_number"] == "+14155551212"
    assert body["prospects"][0]["name"] == "Sam Rivera"
    assert body["prospects"][0]["interests"] == [
        {
            "id": 1,
            "property_id": None,
            "property_name": None,
            "unit_id": unit.id,
            "unit_number": "8A",
            "notes": "Asked for a bay view.",
            "created_at": body["prospects"][0]["interests"][0]["created_at"],
        }
    ]


def test_prospects_endpoint_returns_empty_list_for_database_without_prospects(tmp_path) -> None:
    database_path = tmp_path / "empty-verification.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_sqlite_engine(database_url)
    initialize_database(engine)
    app = create_app(Settings(app_env="test", database_url=database_url))
    client = TestClient(app)

    response = client.get("/prospects")

    assert response.status_code == 200
    assert response.json() == {"count": 0, "prospects": []}
