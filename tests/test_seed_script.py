from leasing_voice_assistant.core.config import get_settings
from leasing_voice_assistant.db.seed import main


def test_seed_script_loads_data(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "seed-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    output = capsys.readouterr().out
    assert "Seeded database" in output
    assert database_path.exists()
