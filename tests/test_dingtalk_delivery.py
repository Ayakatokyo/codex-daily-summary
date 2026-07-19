import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "codex-daily-summary" / "scripts" / "send_dingtalk.py"
CONFIGURE_SCRIPT = ROOT / "skill" / "codex-daily-summary" / "scripts" / "configure_dingtalk.py"


def load_module():
    spec = importlib.util.spec_from_file_location("send_dingtalk", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_configure_module():
    spec = importlib.util.spec_from_file_location("configure_dingtalk", CONFIGURE_SCRIPT)
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
"""


class DingTalkDeliveryTests(unittest.TestCase):
    def test_default_paths_use_xdg_config_home_and_share_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            config_home = Path(directory) / "xdg"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                sender = load_module()
                configurator = load_configure_module()

            expected_directory = config_home / "codex-daily-summary"
            self.assertEqual(expected_directory / "config.json", sender.DEFAULT_CONFIG)
            self.assertEqual(expected_directory / "state.json", sender.DEFAULT_STATE)
            self.assertEqual(sender.DEFAULT_CONFIG, configurator.DEFAULT_CONFIG)

    def test_default_paths_fall_back_to_home_config_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            with patch.dict(os.environ, {"HOME": str(home)}, clear=True):
                sender = load_module()
                configurator = load_configure_module()

            expected_directory = home / ".config" / "codex-daily-summary"
            self.assertEqual(expected_directory / "config.json", sender.DEFAULT_CONFIG)
            self.assertEqual(expected_directory / "state.json", sender.DEFAULT_STATE)
            self.assertEqual(sender.DEFAULT_CONFIG, configurator.DEFAULT_CONFIG)

    def test_configure_rejects_exit_zero_envelope_with_success_false(self):
        module = load_configure_module()

        def unsuccessful_runner(command):
            if command[1:4] == ["contact", "user", "get-self"]:
                return 0, '{"success": false, "result": {"userId": "user-a"}}', ""
            return 0, '{"success": false, "result": {"robotCode": "robot-a"}}', ""

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"

            with self.assertRaises(RuntimeError):
                module.configure(config, dws="dws", runner=unsuccessful_runner)

            self.assertFalse(config.exists())

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
        calls = []

        def timeout_runner(command):
            calls.append(command)
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

            with self.assertRaises(module.DeliveryUnknown):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-b", config, state, runner=timeout_runner)

            ledger = json.loads(state.read_text(encoding="utf-8"))

        self.assertEqual("UNKNOWN", ledger["deliveries"]["2026-07-19:digest-b:1"]["status"])
        self.assertEqual(1, len(calls))

    def test_pending_delivery_rejects_retry_without_running_command(self):
        module = load_module()
        calls = []

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"success": true}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(
                json.dumps({"robotCode": "robot-a", "recipientUserId": "me-a", "timezone": "Asia/Shanghai"}),
                encoding="utf-8",
            )
            state.write_text(
                json.dumps({"deliveries": {"2026-07-19:digest-c:1": {"status": "PENDING"}}}),
                encoding="utf-8",
            )

            with self.assertRaises(module.DeliveryUnknown):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-c", config, state, runner=runner)

        self.assertEqual([], calls)

    def test_missing_dws_leaves_no_pending_delivery_and_does_not_run_runner(self):
        module = load_module()
        calls = []

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"success": true}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(
                json.dumps({"robotCode": "robot-a", "recipientUserId": "me-a", "timezone": "Asia/Shanghai"}),
                encoding="utf-8",
            )
            module.default_runner = runner
            module.resolve_dws = lambda: (_ for _ in ()).throw(FileNotFoundError("dws missing"))

            with self.assertRaises(FileNotFoundError):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-missing", config, state, runner=module.default_runner)

            self.assertFalse(state.exists())

        self.assertEqual([], calls)

    def test_deliver_preserves_nested_process_query_key(self):
        module = load_module()

        def success_runner(command):
            return module.CommandResult(
                0,
                '{"success": true, "result": {"processQueryKey": "pk-nested"}}',
                "",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            state = root / "state.json"
            config.write_text(
                json.dumps({"robotCode": "robot-a", "recipientUserId": "me-a", "timezone": "Asia/Shanghai"}),
                encoding="utf-8",
            )

            deliveries = module.deliver(VALID_REPORT, "2026-07-19", "digest-d", config, state, runner=success_runner)
            ledger = json.loads(state.read_text(encoding="utf-8"))

        self.assertEqual("pk-nested", deliveries[0]["processQueryKey"])
        self.assertTrue(ledger["deliveries"]["2026-07-19:digest-d:1"]["sentAt"])


if __name__ == "__main__":
    unittest.main()
