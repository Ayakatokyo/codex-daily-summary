import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable


INJECTED_BLOCK = re.compile(
    r"<(?P<tag>environment_context|permissions instructions|app-context|"
    r"collaboration_mode|plugins_instructions|skills_instructions)\b[^>]*>"
    r".*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
SECRET = re.compile(
    r'(?P<prefix>\b(?:api[ _-]?key|access[ _-]?token|client[ _-]?secret|'
    r'password|webhook|robotCode|recipientUserId)\b(?:["\'])?(?P<separator>\s*[:=]\s*))'
    r'(?P<value>"[^"\r\n]*"|\'[^\'\r\n]*\'|\S+)',
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
