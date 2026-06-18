"""Developer helper for placing one-off LiveKit SIP test calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_TEMPLATE_PATH = Path("sip-participant.example.json")
DEFAULT_ROOM_PREFIX = "leasing-test-call"
DEFAULT_PARTICIPANT_PREFIX = "test-caller"


def build_unique_suffix() -> str:
    """Return a compact suffix suitable for LiveKit room and participant names."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def build_test_call_config(
    template: dict[str, Any],
    *,
    suffix: str | None = None,
    room_prefix: str | None = None,
    participant_prefix: str | None = None,
) -> dict[str, Any]:
    """Return a SIP participant payload with call-unique room and identity fields."""
    unique_suffix = suffix or build_unique_suffix()
    next_config = dict(template)
    base_room = _clean_prefix(room_prefix) or _clean_prefix(template.get("room_name"))
    base_participant = _clean_prefix(participant_prefix) or _clean_prefix(
        template.get("participant_identity")
    )

    next_config["room_name"] = f"{base_room or DEFAULT_ROOM_PREFIX}-{unique_suffix}"
    next_config["participant_identity"] = (
        f"{base_participant or DEFAULT_PARTICIPANT_PREFIX}-{unique_suffix}"
    )
    return next_config


def load_template(path: Path) -> dict[str, Any]:
    """Read a SIP participant template JSON file."""
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def create_sip_participant(config: dict[str, Any]) -> int:
    """Create a SIP participant using the LiveKit CLI."""
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="leasing-sip-participant-",
            suffix=".json",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(config, file, indent=2)
            file.write("\n")

        result = subprocess.run(
            ["lk", "sip", "participant", "create", str(temp_path)],
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        print("lk CLI was not found on PATH", file=sys.stderr)
        return 127
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Generate unique SIP participant config and create a LiveKit test call."""
    parser = argparse.ArgumentParser(
        description="Create a LiveKit SIP test call with a unique room and participant identity."
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help="SIP participant JSON template path.",
    )
    parser.add_argument("--room-prefix", help="Override the generated room name prefix.")
    parser.add_argument(
        "--participant-prefix",
        help="Override the generated participant identity prefix.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated JSON instead of calling the LiveKit CLI.",
    )
    args = parser.parse_args(argv)

    config = build_test_call_config(
        load_template(args.template),
        room_prefix=args.room_prefix,
        participant_prefix=args.participant_prefix,
    )
    if args.dry_run:
        print(json.dumps(config, indent=2))
        return 0
    return create_sip_participant(config)


def _clean_prefix(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip().strip("-")
    return clean or None


if __name__ == "__main__":
    raise SystemExit(main())
