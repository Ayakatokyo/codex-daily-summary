#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


CONFIG_DIRECTORY = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex-daily-summary"
DEFAULT_CONFIG = CONFIG_DIRECTORY / "feishu-config.json"
DEFAULT_STATE = CONFIG_DIRECTORY / "feishu-state.json"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class DeliveryUnknown(RuntimeError):
    """The Feishu service may have accepted the message; do not retry automatically."""


def _load_report_guard():
    path = Path(__file__).with_name("report_guard.py")
    spec = importlib.util.spec_from_file_location("codex_daily_summary_report_guard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load report guard")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_lark() -> str:
    executable = shutil.which("lark-cli")
    if executable is None:
        raise FileNotFoundError("lark-cli executable not found")
    return executable


def default_runner(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def build_command(executable: str, config: dict[str, str], body: str, report_date: str, source_digest: str, part: int) -> list[str]:
    return [
        executable,
        "im",
        "+messages-send",
        "--as",
        "bot",
        "--user-id",
        config["recipientOpenId"],
        "--markdown",
        body,
        "--idempotency-key",
        f"codex-daily-summary:feishu:{report_date}:{source_digest}:{part}",
        "--format",
        "json",
    ]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
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


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"deliveries": {}}
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(ledger, dict) or not isinstance(ledger.get("deliveries"), dict):
        raise ValueError("invalid Feishu delivery ledger")
    return ledger


def load_config(path: Path) -> dict[str, str]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("timezone") != "Asia/Shanghai":
        raise ValueError("invalid Feishu delivery configuration")
    open_id = config.get("recipientOpenId")
    if not isinstance(open_id, str) or not open_id:
        raise ValueError("invalid Feishu delivery configuration")
    return {"recipientOpenId": open_id, "timezone": "Asia/Shanghai"}


def _unknown(ledger: dict[str, Any], state_path: Path, key: str, error: BaseException) -> None:
    ledger["deliveries"][key] = {"status": "UNKNOWN"}
    _atomic_write(state_path, ledger)
    raise DeliveryUnknown("delivery outcome is unknown; inspect Feishu before retrying") from error


def _success(result: CommandResult) -> bool | None:
    if result.returncode != 0:
        return False
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return isinstance(response, dict) and response.get("ok") is True


def deliver(
    report: str,
    report_date: str,
    source_digest: str,
    config_path: Path = DEFAULT_CONFIG,
    state_path: Path = DEFAULT_STATE,
    runner: Callable[[list[str]], CommandResult] = default_runner,
    executable: str | None = None,
) -> list[dict[str, Any]]:
    config = load_config(Path(config_path))
    guard = _load_report_guard()
    errors = guard.validate_report(report)
    if errors:
        raise ValueError("invalid report: " + "; ".join(errors))
    chunks = guard.chunk_report(report, max_chars=20_000)
    ledger = load_ledger(Path(state_path))
    resolved = executable or (resolve_lark() if runner is default_runner else "lark-cli")
    deliveries = []
    for part, chunk in enumerate(chunks, start=1):
        key = f"{report_date}:{source_digest}:{part}"
        existing = ledger["deliveries"].get(key)
        if existing is not None:
            if existing.get("status") == "SENT":
                deliveries.append(existing)
                continue
            if existing.get("status") in {"PENDING", "UNKNOWN"}:
                raise DeliveryUnknown("existing delivery has an unresolved outcome")
        ledger["deliveries"][key] = {"status": "PENDING"}
        _atomic_write(Path(state_path), ledger)
        try:
            result = runner(build_command(resolved, config, chunk, report_date, source_digest, part))
        except (TimeoutError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            _unknown(ledger, Path(state_path), key, error)
        success = _success(result)
        if success is None:
            _unknown(ledger, Path(state_path), key, ValueError("invalid JSON response"))
        if success is False:
            ledger["deliveries"][key] = {"status": "FAILED"}
            _atomic_write(Path(state_path), ledger)
            raise RuntimeError("Feishu delivery command failed")
        sent = {"status": "SENT", "sentAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        ledger["deliveries"][key] = sent
        _atomic_write(Path(state_path), ledger)
        deliveries.append(sent)
    return deliveries


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a validated Codex daily report to the configured Feishu user.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source-digest", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    deliver(args.report.read_text(encoding="utf-8"), args.date, args.source_digest, args.config, args.state)
    print("Feishu delivery recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
