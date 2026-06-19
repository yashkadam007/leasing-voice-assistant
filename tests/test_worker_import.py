from leasing_voice_assistant.worker import main


def test_worker_entrypoint_import_does_not_require_credentials() -> None:
    assert callable(main.job_entrypoint)
    assert callable(main.main)
