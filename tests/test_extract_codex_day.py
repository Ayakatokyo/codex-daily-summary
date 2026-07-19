import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import date


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "codex-daily-summary" / "scripts" / "extract_codex_day.py"


def load_module():
    spec = importlib.util.spec_from_file_location("extract_codex_day", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventParsingTests(unittest.TestCase):
    def test_keeps_user_and_final_answer_only(self):
        module = load_module()
        records = [
            {
                "type": "response_item",
                "timestamp": "2026-07-19T09:00:00Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"text": "Fix login"}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-07-19T09:00:01Z",
                "payload": {"type": "reasoning", "content": [{"text": "private reasoning"}]},
            },
            {
                "type": "response_item",
                "timestamp": "2026-07-19T09:00:02Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "commentary",
                    "content": [{"text": "working"}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-07-19T09:00:03Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [{"text": "Fixed login and tests pass"}],
                },
            },
        ]

        messages = module.extract_messages(records)

        self.assertEqual(["user", "assistant"], [message["role"] for message in messages])
        self.assertEqual("Fixed login and tests pass", messages[1]["text"])

    def test_strips_injected_context_and_redacts_secrets(self):
        module = load_module()

        result = module.sanitize_text(
            "<environment_context>private</environment_context>Fix API\napi_key=sk-secret-value"
        )

        self.assertNotIn("environment_context", result)
        self.assertNotIn("sk-secret-value", result)
        self.assertIn("[REDACTED]", result)

    def test_fully_redacts_quoted_and_json_like_secret_values(self):
        module = load_module()

        result = module.sanitize_text(
            'api_key="sk-secret-value"\n"api_key": "sk json secret"'
        )

        self.assertNotIn("sk-secret-value", result)
        self.assertNotIn("sk json secret", result)
        self.assertEqual('api_key=[REDACTED]\n"api_key": [REDACTED]', result)

    def test_redacts_escaped_quotes_in_quoted_secret_values(self):
        module = load_module()

        result = module.sanitize_text('"api_key": "sk secret\\"suffix"')

        self.assertNotIn("sk secret", result)
        self.assertNotIn("suffix", result)
        self.assertEqual('"api_key": [REDACTED]', result)

    def test_ignores_summary_control_message(self):
        module = load_module()

        self.assertTrue(module.is_control_message("总结今天的 Codex 工作"))


class DailyExtractionTests(unittest.TestCase):
    def test_extracts_active_and_archived_threads_for_local_day(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            active_path = home / "sessions" / "2026" / "07" / "19" / "active.jsonl"
            archived_path = home / "archived_sessions" / "archived.jsonl"
            active_path.parent.mkdir(parents=True)
            archived_path.parent.mkdir(parents=True)
            active_path.write_text(
                "\n".join(
                    [
                        json.dumps({"timestamp": "2026-07-18T16:01:00Z", "type": "turn_context", "payload": {"model": "daily-model", "effort": "high"}}),
                        json.dumps({"timestamp": "2026-07-18T16:01:01Z", "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"text": "Active work"}]}}),
                    ]
                ) + "\n",
                encoding="utf-8",
            )
            archived_path.write_text(
                json.dumps({"timestamp": "2026-07-18T16:05:00Z", "type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"text": "Archived work"}]}}) + "\n",
                encoding="utf-8",
            )

            database = sqlite3.connect(home / "state_9.sqlite")
            database.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, cwd TEXT, title TEXT, archived INTEGER, model TEXT, reasoning_effort TEXT)"
            )
            database.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("active", str(active_path), "/workspace/active", "Active", 0, "db-model", "low"),
                    ("archived", str(archived_path), "/workspace/archived", "Archived", 1, "db-model", "low"),
                ],
            )
            database.commit()
            database.close()

            result = module.extract_day(home, date(2026, 7, 19), "Asia/Shanghai")

        self.assertEqual("2026-07-19", result["date"])
        self.assertEqual("Asia/Shanghai", result["timezone"])
        self.assertEqual(2, len(result["threads"]))
        self.assertEqual("daily-model", result["threads"][0]["model"])
        self.assertRegex(result["source_digest"], r"^[0-9a-f]{64}$")

    def test_source_digest_changes_when_message_text_changes(self):
        module = load_module()

        first = module.source_digest([{"id": "thread", "messages": [{"text": "first"}]}])
        second = module.source_digest([{"id": "thread", "messages": [{"text": "second"}]}])

        self.assertNotEqual(first, second)

    def test_falls_back_to_session_files_without_state_database(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            session = home / "sessions" / "2026" / "07" / "19" / "fallback.jsonl"
            session.parent.mkdir(parents=True)
            session.write_text(
                json.dumps({"timestamp": "2026-07-19T09:00:00Z", "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"text": "Fallback work"}]}}) + "\n",
                encoding="utf-8",
            )

            result = module.extract_day(home, date(2026, 7, 19), "Asia/Shanghai")

        self.assertEqual(1, len(result["threads"]))
        self.assertEqual("fallback", result["threads"][0]["title"])


if __name__ == "__main__":
    unittest.main()
