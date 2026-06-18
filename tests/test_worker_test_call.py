import json

from leasing_voice_assistant.worker.test_call import build_test_call_config, main


def test_build_test_call_config_uses_unique_room_and_participant_identity() -> None:
    config = build_test_call_config(
        {
            "sip_trunk_id": "ST_123",
            "sip_call_to": "+15551234567",
            "room_name": "leasing-test-call",
            "participant_identity": "+15722320839",
        },
        suffix="20260618-120000-abcdef12",
    )

    assert config["sip_trunk_id"] == "ST_123"
    assert config["sip_call_to"] == "+15551234567"
    assert config["room_name"] == "leasing-test-call-20260618-120000-abcdef12"
    assert config["participant_identity"] == "+15722320839-20260618-120000-abcdef12"


def test_build_test_call_config_accepts_explicit_prefixes() -> None:
    config = build_test_call_config(
        {},
        suffix="20260618-120000-abcdef12",
        room_prefix="demo-room",
        participant_prefix="demo-caller",
    )

    assert config["room_name"] == "demo-room-20260618-120000-abcdef12"
    assert config["participant_identity"] == "demo-caller-20260618-120000-abcdef12"


def test_main_dry_run_prints_generated_config(tmp_path, capsys) -> None:
    template_path = tmp_path / "sip-participant.json"
    template_path.write_text(
        json.dumps(
            {
                "sip_trunk_id": "ST_123",
                "sip_call_to": "+15551234567",
                "room_name": "base-room",
                "participant_identity": "base-participant",
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--template", str(template_path), "--dry-run"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["room_name"].startswith("base-room-")
    assert output["participant_identity"].startswith("base-participant-")
