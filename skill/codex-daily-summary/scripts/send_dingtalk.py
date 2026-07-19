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
from typing import Callable, Any


CONFIG_DIRECTORY = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex-daily-summary"
DEFAULT_CONFIG = CONFIG_DIRECTORY / "config.json"
DEFAULT_STATE = CONFIG_DIRECTORY / "state.json"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class DeliveryUnknown(RuntimeError):
    """The remote service may have accepted the message; do not retry automatically."""


def _load_report_guard():
    path = Path(__file__).with_name("report_guard.py")
    spec = importlib.util.spec_from_file_location("codex_daily_summary_report_guard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load report guard")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_dws() -> str:
    preferred = Path("/opt/homebrew/bin/dws")
    if preferred.is_file() and os.access(preferred, os.X_OK):
        return str(preferred)
    resolved = shutil.which("dws")
    if resolved is None:
        raise FileNotFoundError("dws executable not found")
    return resolved


def default_runner(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def build_command(dws: str, config: dict[str, str], title: str, body: str) -> list[str]:
    return [
        dws,
        "chat",
        "message",
        "send-by-bot",
        "--robot-code",
        config["robotCode"],
        "--users",
        config["recipientUserId"],
        "--title",
        title,
        "--text",
        body,
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
    with path.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("deliveries"), dict):
        raise ValueError("invalid delivery ledger")
    return ledger


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    _atomic_write(path, ledger)


def load_config(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    required = ("robotCode", "recipientUserId", "timezone")
    if not isinstance(config, dict) or any(not isinstance(config.get(key), str) or not config[key] for key in required):
        raise ValueError("invalid DingTalk delivery configuration")
    if config["timezone"] != "Asia/Shanghai":
        raise ValueError("DingTalk delivery timezone must be Asia/Shanghai")
    return {key: config[key] for key in required}


def _unknown(ledger: dict[str, Any], state_path: Path, key: str, error: BaseException) -> None:
    ledger["deliveries"][key] = {"status": "UNKNOWN"}
    save_ledger(state_path, ledger)
    raise DeliveryUnknown("delivery outcome is unknown; inspect DingTalk before retrying") from error


def _successful_response(result: CommandResult) -> dict[str, Any] | None:
    if result.returncode != 0:
        return None
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(response, dict):
        return None
    return response


def deliver(
    report: str,
    report_date: str,
    source_digest: str,
    config_path: Path = DEFAULT_CONFIG,
    state_path: Path = DEFAULT_STATE,
    runner: Callable[[list[str]], CommandResult] = default_runner,
    dws: str | None = None,
) -> list[dict[str, Any]]:
    config = load_config(Path(config_path))
    guard = _load_report_guard()
    errors = guard.validate_report(report)
    if errors:
        raise ValueError("invalid report: " + "; ".join(errors))
    chunks = guard.chunk_report(report, max_chars=20_000)
    ledger = load_ledger(Path(state_path))
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

        executable = dws or (resolve_dws() if runner is default_runner else "dws")

        ledger["deliveries"][key] = {"status": "PENDING"}
        save_ledger(Path(state_path), ledger)
        try:
            result = runner(build_command(executable, config, f"Codex 工作日报 - {report_date}", chunk))
        except (TimeoutError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            _unknown(ledger, Path(state_path), key, error)

        response = _successful_response(result)
        if response is None:
            if result.returncode == 0:
                _unknown(ledger, Path(state_path), key, ValueError("invalid JSON response"))
            ledger["deliveries"][key] = {"status": "FAILED"}
            save_ledger(Path(state_path), ledger)
            raise RuntimeError("DingTalk delivery command failed")
        if response.get("success") is not True:
            ledger["deliveries"][key] = {"status": "FAILED"}
            save_ledger(Path(state_path), ledger)
            raise RuntimeError("DingTalk rejected the delivery")

        sent = {"status": "SENT", "sentAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        if "processQueryKey" in response:
            sent["processQueryKey"] = response["processQueryKey"]
        elif isinstance(response.get("result"), dict) and "processQueryKey" in response["result"]:
            sent["processQueryKey"] = response["result"]["processQueryKey"]
        ledger["deliveries"][key] = sent
        save_ledger(Path(state_path), ledger)
        deliveries.append(sent)
    return deliveries


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a validated Codex daily report to the configured DingTalk user.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source-digest", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    deliver(args.report.read_text(encoding="utf-8"), args.date, args.source_digest, args.config, args.state)
    print("DingTalk delivery recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
