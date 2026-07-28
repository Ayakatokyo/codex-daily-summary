import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Iterable
from zoneinfo import ZoneInfo


INJECTED_BLOCK = re.compile(
    r"<(?P<tag>environment_context|permissions instructions|app-context|"
    r"collaboration_mode|plugins_instructions|skills_instructions)\b[^>]*>"
    r".*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
SECRET = re.compile(
    r'(?P<prefix>\b(?:api[ _-]?key|access[ _-]?token|client[ _-]?secret|'
    r'password|webhook|robotCode|recipientUserId|recipientOpenId|openId)\b(?:["\'])?(?P<separator>\s*[:=]\s*))'
    r'(?P<value>"(?:\\.|[^"\\\r\n])*"|\'(?:\\.|[^\'\\\r\n])*\'|\S+)',
    re.IGNORECASE,
)
CONTROL_MESSAGES = {
    "总结今天的 codex 工作",
    "生成今天的 codex 日报并发到钉钉",
}


def sanitize_text(text: str) -> str:
    text = INJECTED_BLOCK.sub("", text)
    text = SECRET.sub(lambda match: f"{match.group('prefix')}[REDACTED]", text)
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def safe_thread_title(thread_id: object) -> str:
    return f"Thread {hashlib.sha256(str(thread_id).encode('utf-8')).hexdigest()[:12]}"


def is_control_message(text: str) -> bool:
    normalized = text.strip().lower().rstrip("。.!！?？").strip()
    return normalized in CONTROL_MESSAGES


def _content_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    return "".join(
        item["text"]
        for item in content
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    )


def extract_messages(records: Iterable[dict]) -> list[dict]:
    messages = []
    seen = set()

    for record in records:
        if record.get("type") != "response_item":
            continue

        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue

        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue
        if role == "assistant" and payload.get("phase") not in {None, "final_answer"}:
            continue

        text = sanitize_text(_content_text(payload.get("content")))
        if not text or (role == "user" and is_control_message(text)):
            continue

        key = (role, text)
        if key in seen:
            continue
        seen.add(key)
        messages.append(
            {
                "role": role,
                "timestamp": record.get("timestamp"),
                "text": text,
            }
        )

    return messages


def find_state_db(codex_home: Path) -> Path | None:
    required_columns = {"id", "rollout_path", "cwd", "title"}
    candidates = sorted(
        codex_home.glob("state_*.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(threads)")
                }
            finally:
                connection.close()
        except sqlite3.Error:
            continue
        if required_columns.issubset(columns):
            return path
    return None


def source_digest(threads: list[dict]) -> str:
    canonical = json.dumps(
        threads,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path, warnings: list[str]) -> list[dict]:
    records = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"{path.name}:{line_number}: invalid JSON")
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError as error:
        warnings.append(f"{path.name}: unable to read ({error})")
    return records


def _thread_rows(codex_home: Path) -> list[dict]:
    database = find_state_db(codex_home)
    if database is not None:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute("SELECT * FROM threads ORDER BY rowid")]
        finally:
            connection.close()
        if rows:
            return [
                {
                    "id": row["id"],
                    "rollout_path": row["rollout_path"],
                    "cwd": row["cwd"],
                    "title": row["title"],
                    "archived": bool(row.get("archived", False)),
                    "model": row.get("model"),
                    "reasoning_effort": row.get("reasoning_effort"),
                }
                for row in rows
            ]

    archived_root = codex_home / "archived_sessions"
    paths = sorted((codex_home / "sessions").glob("**/*.jsonl")) if (codex_home / "sessions").exists() else []
    if archived_root.exists():
        paths.extend(sorted(archived_root.glob("**/*.jsonl")))
    return [
        {
            "id": path.stem,
            "rollout_path": str(path),
            "cwd": "",
            "title": path.stem,
            "archived": archived_root in path.parents,
            "model": None,
            "reasoning_effort": None,
        }
        for path in paths
    ]


def _parse_timestamp(value: object) -> datetime.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(datetime.timezone.utc)


def extract_day(codex_home: Path, target_date: datetime.date, timezone_name: str) -> dict:
    codex_home = Path(codex_home)
    timezone = ZoneInfo(timezone_name)
    local_start = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=timezone)
    utc_start = local_start.astimezone(datetime.timezone.utc)
    utc_end = (local_start + datetime.timedelta(days=1)).astimezone(datetime.timezone.utc)
    warnings: list[str] = []
    rows = _thread_rows(codex_home)

    if not rows:
        raise FileNotFoundError("No compatible Codex state database or session files found")

    threads = []
    for row in rows:
        path = Path(row["rollout_path"])
        records = _read_jsonl(path, warnings)
        day_records = [
            record
            for record in records
            if (timestamp := _parse_timestamp(record.get("timestamp"))) is not None
            and utc_start <= timestamp < utc_end
        ]
        messages = extract_messages(day_records)
        if not messages:
            continue

        turn_context = next(
            (
                record.get("payload", {})
                for record in reversed(day_records)
                if record.get("type") == "turn_context"
                and isinstance(record.get("payload"), dict)
            ),
            {},
        )
        threads.append(
            {
                "id": row["id"],
                "title": safe_thread_title(row["id"]),
                "cwd": row["cwd"],
                "archived": row["archived"],
                "model": turn_context.get("model") or row["model"],
                "reasoning_effort": (
                    turn_context.get("effort")
                    or turn_context.get("reasoning_effort")
                    or row["reasoning_effort"]
                ),
                "messages": messages,
            }
        )

    return {
        "date": target_date.isoformat(),
        "timezone": timezone_name,
        "threads": threads,
        "warnings": warnings,
        "source_digest": source_digest(threads),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Codex activity for one local day.")
    parser.add_argument("--date", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = extract_day(args.codex_home, args.date, args.timezone)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=args.output.parent,
        delete=False,
    ) as temporary:
        json.dump(result, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, args.output)


if __name__ == "__main__":
    main()
