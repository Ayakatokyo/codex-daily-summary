import importlib.util
from pathlib import Path
import unittest


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

    def test_ignores_summary_control_message(self):
        module = load_module()

        self.assertTrue(module.is_control_message("总结今天的 Codex 工作"))


if __name__ == "__main__":
    unittest.main()
