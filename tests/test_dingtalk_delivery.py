import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "codex-daily-summary" / "scripts" / "send_dingtalk.py"


def load_module():
    spec = importlib.util.spec_from_file_location("send_dingtalk", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_REPORT = """# Codex 工作日报 - 2026-07-19

## 今日概览
完成日报发送能力。

## 项目进展
发送模块已接入固定收件人。

## 当前阻塞
暂无阻塞。

## 下一日待办
- 验证发送状态。

## Codex 使用优化建议
- 优先级：P1；当天证据：发送流程需要验证；优化建议：记录幂等状态；可直接执行：复用状态文件。

## 来源索引
- 本地 Codex 会话记录。
"""


class DingTalkDeliveryTests(unittest.TestCase):
    def test_build_command_uses_only_fixed_config_recipient_and_robot(self):
        module = load_module()

        command = module.build_command(
            "dws",
            {"robotCode": "robot-a", "recipientUserId": "me-a"},
            "Title",
            "Body",
        )

        serialized = " ".join(command)
        self.assertIn("robot-a", serialized)
        self.assertIn("me-a", serialized)
        self.assertNotIn("stranger", serialized)
        self.assertTrue(command[-1].endswith("json"))

    def test_deliver_skips_duplicate_sent_delivery(self):
        module = load_module()
        calls = []

        def success_runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"success": true, "processQueryKey": "pk-1"}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(
                json.dumps({"robotCode": "robot-a", "recipientUserId": "me-a", "timezone": "Asia/Shanghai"}),
                encoding="utf-8",
            )

            module.deliver(VALID_REPORT, "2026-07-19", "digest-a", config, state, runner=success_runner)
            module.deliver(VALID_REPORT, "2026-07-19", "digest-a", config, state, runner=success_runner)

        self.assertEqual(1, len(calls))

    def test_timeout_records_unknown_delivery_state(self):
        module = load_module()

        def timeout_runner(command):
            raise TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(
                json.dumps({"robotCode": "robot-a", "recipientUserId": "me-a", "timezone": "Asia/Shanghai"}),
                encoding="utf-8",
            )

            with self.assertRaises(module.DeliveryUnknown):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-b", config, state, runner=timeout_runner)

            ledger = json.loads(state.read_text(encoding="utf-8"))

        self.assertEqual("UNKNOWN", ledger["deliveries"]["2026-07-19:digest-b:1"]["status"])


if __name__ == "__main__":
    unittest.main()
