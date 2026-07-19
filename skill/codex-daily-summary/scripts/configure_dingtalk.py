import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable


CONFIG_DIRECTORY = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex-daily-summary"
DEFAULT_CONFIG = CONFIG_DIRECTORY / "config.json"


def resolve_dws() -> str:
    preferred = Path("/opt/homebrew/bin/dws")
    if preferred.is_file() and os.access(preferred, os.X_OK):
        return str(preferred)
    resolved = shutil.which("dws")
    if resolved is None:
        raise FileNotFoundError("dws executable not found")
    return resolved


def default_runner(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def _walk_values(value: Any, key: str) -> list[str]:
    values = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key and isinstance(current_value, str) and current_value:
                values.append(current_value)
            values.extend(_walk_values(current_value, key))
    elif isinstance(value, list):
        for item in value:
            values.extend(_walk_values(item, key))
    return values


def unique_values(envelope: Any, key: str) -> set[str]:
    return set(_walk_values(envelope, key))


def _read_envelope(command: list[str], runner: Callable[[list[str]], tuple[int, str, str]]) -> Any:
    code, stdout, _ = runner(command)
    if code != 0:
        raise RuntimeError("DingTalk read-only query failed")
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("DingTalk read-only query returned invalid JSON") from error
    if not isinstance(envelope, dict) or envelope.get("success") is not True:
        raise RuntimeError("DingTalk read-only query was unsuccessful")
    return envelope


def _atomic_write(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def configure(
    config_path: Path = DEFAULT_CONFIG,
    selected_robot: str | None = None,
    dws: str | None = None,
    runner: Callable[[list[str]], tuple[int, str, str]] = default_runner,
) -> None:
    executable = dws or resolve_dws()
    user_envelope = _read_envelope([executable, "contact", "user", "get-self", "--format", "json"], runner)
    bot_envelope = _read_envelope([executable, "chat", "bot", "search", "--format", "json"], runner)
    users = unique_values(user_envelope, "userId")
    bots = unique_values(bot_envelope, "robotCode")
    if len(users) != 1:
        raise ValueError("expected exactly one DingTalk user")
    if not bots:
        raise ValueError("no DingTalk bot available")
    if selected_robot is None:
        if len(bots) != 1:
            raise ValueError("select a DingTalk bot explicitly")
        selected_robot = next(iter(bots))
    if selected_robot not in bots:
        raise ValueError("selected DingTalk bot is unavailable")
    _atomic_write(
        config_path,
        {
            "recipientUserId": next(iter(users)),
            "robotCode": selected_robot,
            "timezone": "Asia/Shanghai",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the fixed DingTalk report recipient.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--robot-code")
    args = parser.parse_args()
    configure(args.config, args.robot_code)
    print("DingTalk delivery configuration saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
