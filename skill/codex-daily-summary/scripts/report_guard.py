import argparse
import json
from pathlib import Path
import re


TITLE = re.compile(r"^# Codex 工作日报 - \d{4}-\d{2}-\d{2}$")
REQUIRED_HEADINGS = (
    "今日概览",
    "项目进展",
    "当前阻塞",
    "下一日待办",
    "Codex 使用优化建议",
)
FORBIDDEN_HEADINGS = ("来源索引",)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
SENSITIVE_NAME = (
    r"api[ _-]?key|access[ _-]?token|client[ _-]?secret|password|webhook|"
    r"robotCode|recipientUserId"
)
SENSITIVE_ASSIGNMENT = re.compile(
    rf"(?im)(?P<name>{SENSITIVE_NAME})\b(?:[\"'])?\s*[:=]\s*"
    r"(?P<value>\"(?:\\.|[^\"\\\r\n])*\"|'(?:\\.|[^'\\\r\n])*'|\S+)"
)
PRESENTATIONAL_SECRET_KEY = re.compile(
    rf"(?i)(?:[*_~`]+|<[a-z][^>]*>)+(?P<name>{SENSITIVE_NAME})"
    r"(?:[*_~`]+|</[a-z][^>]*>)+(?=\s*[:=])"
)


def _normalize_secret_key_wrappers(text: str) -> str:
    return PRESENTATIONAL_SECRET_KEY.sub(lambda match: match.group("name"), text)


def _assignment_value(match: re.Match[str]) -> str:
    return match.group("value").strip("\"'").rstrip(",;")


def _only_redacted_assignments(text: str) -> bool:
    while text:
        text = text.lstrip(",; ")
        if not text:
            return True
        match = SENSITIVE_ASSIGNMENT.match(text)
        if match is None or _assignment_value(match) != "[REDACTED]":
            return False
        text = text[match.end():].strip()
    return True


def validate_report(report: str) -> list[str]:
    lines = report.splitlines()
    errors = []
    first_line = next((line.strip() for line in lines if line.strip()), "")
    if not TITLE.fullmatch(first_line):
        errors.append("invalid report title")

    headings = {
        match.group(2)
        for match in HEADING.finditer(report)
        if match.group(1) == "##"
    }
    for heading in REQUIRED_HEADINGS:
        if heading not in headings:
            errors.append(f"missing required section: {heading}")
    for heading in FORBIDDEN_HEADINGS:
        if heading in headings:
            errors.append(f"forbidden section: {heading}")

    scan_text = _normalize_secret_key_wrappers(report)
    for match in SENSITIVE_ASSIGNMENT.finditer(scan_text):
        value = _assignment_value(match)
        remainder = scan_text[match.end():].split("\n", 1)[0].strip()
        if value != "[REDACTED]" or (remainder and not _only_redacted_assignments(remainder)):
            errors.append(f"unredacted sensitive assignment: {match.group('name')}")

    return errors


def _report_blocks(report: str) -> tuple[str, list[str]]:
    lines = report.strip().splitlines(keepends=True)
    title = next((line.rstrip("\r\n") for line in lines if line.startswith("# ")), "# Codex 工作日报")
    body_start = next(
        (index + 1 for index, line in enumerate(lines) if line.rstrip("\r\n") == title),
        0,
    )
    body = "".join(lines[body_start:]).lstrip("\r\n")
    return title, [block.strip() for block in re.split(r"(?=^#{2,3}\s+)", body, flags=re.MULTILINE) if block.strip()]


def chunk_report(report: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    report = report.strip()
    if len(report) <= max_chars:
        return [report]

    title, blocks = _report_blocks(report)
    continuation_title = f"{title}（续）"
    chunks = []
    current = title

    for block in blocks:
        if len(f"{continuation_title}\n\n{block}") > max_chars:
            raise ValueError("heading block exceeds max_chars")
        candidate = f"{current}\n\n{block}" if current else block
        if current != title and len(candidate) > max_chars:
            chunks.append(current)
            current = f"{continuation_title}\n\n{block}"
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and split Codex daily reports.")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    errors = validate_report(args.report.read_text(encoding="utf-8"))
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
