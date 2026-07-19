#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable


CONFIG_DIRECTORY = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex-daily-summary"
DEFAULT_CONFIG = CONFIG_DIRECTORY / "feishu-config.json"


def resolve_lark() -> str:
    executable = shutil.which("lark-cli")
    if executable is None:
        raise FileNotFoundError("lark-cli executable not found")
    return executable


def default_runner(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return completed.returncode, completed.stdout, completed.stderr


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


def _verified_open_id(envelope: Any) -> str:
    if not isinstance(envelope, dict) or envelope.get("verified") is not True:
        raise RuntimeError("Feishu authentication is not verified")
    identities = envelope.get("identities")
    user = identities.get("user") if isinstance(identities, dict) else None
    open_id = user.get("openId") if isinstance(user, dict) else None
    if not isinstance(open_id, str) or not open_id:
        raise RuntimeError("verified Feishu user openId is unavailable")
    return open_id


def configure(
    config_path: Path = DEFAULT_CONFIG,
    executable: str | None = None,
    runner: Callable[[list[str]], tuple[int, str, str]] = default_runner,
) -> None:
    command = [executable or resolve_lark(), "auth", "status", "--json", "--verify"]
    code, stdout, _ = runner(command)
    if code != 0:
        raise RuntimeError("Feishu authentication status query failed")
    try:
        open_id = _verified_open_id(json.loads(stdout))
    except json.JSONDecodeError as error:
        raise RuntimeError("Feishu authentication status returned invalid JSON") from error
    _atomic_write(Path(config_path), {"recipientOpenId": open_id, "timezone": "Asia/Shanghai"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the fixed Feishu daily report recipient.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    configure(args.config)
    print("Feishu delivery configuration saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
