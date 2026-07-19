import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "codex-daily-summary" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALID_REPORT = """# Codex 工作日报 - 2026-07-19

## 今日概览
- 完成投递能力。

## 项目进展
### Codex Daily Summary
- 添加飞书单聊投递。

## 当前阻塞
- 无。

## 下一日待办
- [P1] Codex Daily Summary：验证配置；配置文件存在且权限正确。

## Codex 使用优化建议
### 记录投递状态
- 优先级：中
- 当天证据：日报需要可追溯投递结果。
- 优化建议：保留独立渠道账本。
- 可直接执行：检查渠道状态文件。
"""


class FeishuDeliveryTests(unittest.TestCase):
    def test_configure_writes_verified_current_user_only(self):
        module = load("configure_feishu")

        def runner(command):
            self.assertEqual(["lark-cli", "auth", "status", "--json", "--verify"], command)
            return 0, json.dumps({"verified": True, "identities": {"user": {"status": "active", "openId": "ou-current"}}}), ""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feishu-config.json"
            module.configure(path, executable="lark-cli", runner=runner)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}, payload)

    def test_configure_rejects_unverified_or_missing_open_id(self):
        module = load("configure_feishu")

        def runner(command):
            return 0, json.dumps({"verified": False, "identities": {"user": {"status": "active"}}}), ""

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feishu-config.json"
            with self.assertRaises(RuntimeError):
                module.configure(path, executable="lark-cli", runner=runner)
            self.assertFalse(path.exists())

    def test_build_command_uses_fixed_current_user_and_stable_idempotency_key(self):
        module = load("send_feishu")
        command = module.build_command("lark-cli", {"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}, "Body", "2026-07-19", "digest-a", 1)
        serialized = " ".join(command)
        self.assertIn("--as bot", serialized)
        self.assertIn("--user-id ou-current", serialized)
        self.assertIn("--markdown Body", serialized)
        self.assertIn("cdsf-20260719-digest-a-1", serialized)
        self.assertNotIn("stranger", serialized)

    def test_idempotency_key_stays_within_feishu_field_limit(self):
        module = load("send_feishu")
        digest = "7ba2f4ffdbe6c6375cfc73f7efba8edf5c19502be1f8a6fd1cac2e477f7b7f0c"
        command = module.build_command("lark-cli", {"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}, "Body", "2026-07-18", digest, 12)
        key = command[command.index("--idempotency-key") + 1]
        self.assertLessEqual(len(key), 50)
        self.assertIn(digest[:32], key)
        self.assertIn("-12", key)

    def test_sent_digest_is_not_sent_twice(self):
        module = load("send_feishu")
        calls = []

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"ok": true, "data": {"message_id": "om-1"}}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "feishu-config.json"
            state = root / "feishu-state.json"
            config.write_text(json.dumps({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}), encoding="utf-8")
            module.deliver(VALID_REPORT, "2026-07-19", "digest-a", config, state, runner=runner)
            module.deliver(VALID_REPORT, "2026-07-19", "digest-a", config, state, runner=runner)

        self.assertEqual(1, len(calls))

    def test_delivery_chunks_markdown_for_feishu_field_limits(self):
        module = load("send_feishu")
        calls = []
        paragraph = "内容" * 450
        report = f"""# Codex 工作日报 - 2026-07-19

## 今日概览
{paragraph}

## 项目进展
{paragraph}

## 当前阻塞
无。

## 下一日待办
{paragraph}

## Codex 使用优化建议
{paragraph}
"""

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"ok": true}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "feishu-config.json"
            state = root / "feishu-state.json"
            config.write_text(json.dumps({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}), encoding="utf-8")
            module.deliver(report, "2026-07-19", "digest-a", config, state, runner=runner)

        self.assertGreater(len(calls), 1)
        for command in calls:
            body = command[command.index("--markdown") + 1]
            self.assertLessEqual(len(body), 1200)

    def test_delivery_splits_long_sections_without_losing_tail_content(self):
        module = load("send_feishu")
        calls = []
        tail = "TAIL-END-OF-REPORT"
        report = VALID_REPORT.replace(
            "检查渠道状态文件。",
            ("长段落内容" * 260) + tail,
        )

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"ok": true}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "feishu-config.json"
            state = root / "feishu-state.json"
            config.write_text(json.dumps({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}), encoding="utf-8")
            module.deliver(report, "2026-07-19", "digest-a", config, state, runner=runner)

        sent_bodies = [command[command.index("--markdown") + 1] for command in calls]
        self.assertGreater(len(sent_bodies), 1)
        self.assertTrue(all(len(body) <= 1200 for body in sent_bodies))
        self.assertIn(tail, "\n".join(sent_bodies))

    def test_delivery_converts_fenced_code_blocks_for_feishu_markdown(self):
        module = load("send_feishu")
        calls = []
        report = VALID_REPORT.replace("检查渠道状态文件。", "```sh\npython -m unittest discover -s tests -v\n   ```")

        def runner(command):
            calls.append(command)
            return module.CommandResult(0, '{"ok": true}', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "feishu-config.json"
            state = root / "feishu-state.json"
            config.write_text(json.dumps({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}), encoding="utf-8")
            module.deliver(report, "2026-07-19", "digest-a", config, state, runner=runner)

        body = calls[0][calls[0].index("--markdown") + 1]
        self.assertNotIn("```", body)
        self.assertIn("    python -m unittest discover -s tests -v", body)

    def test_timeout_becomes_unknown_without_retry(self):
        module = load("send_feishu")
        calls = []

        def runner(command):
            calls.append(command)
            raise TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "feishu-config.json"
            state = root / "feishu-state.json"
            config.write_text(json.dumps({"recipientOpenId": "ou-current", "timezone": "Asia/Shanghai"}), encoding="utf-8")
            with self.assertRaises(module.DeliveryUnknown):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-b", config, state, runner=runner)
            with self.assertRaises(module.DeliveryUnknown):
                module.deliver(VALID_REPORT, "2026-07-19", "digest-b", config, state, runner=runner)
            ledger = json.loads(state.read_text(encoding="utf-8"))

        self.assertEqual("UNKNOWN", ledger["deliveries"]["2026-07-19:digest-b:1"]["status"])
        self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()
