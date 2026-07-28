import importlib.util
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


extract_codex_day = load_module("extract_codex_day", "scripts/extract_codex_day.py")
report_guard = load_module("report_guard", "scripts/report_guard.py")


class SanitizationTest(unittest.TestCase):
    def test_extract_redacts_feishu_recipient_fields(self):
        text = 'recipientOpenId: "ou_abc123"\nopenId: "ou_xyz789"'

        sanitized = extract_codex_day.sanitize_text(text)

        self.assertIn('recipientOpenId: [REDACTED]', sanitized)
        self.assertIn('openId: [REDACTED]', sanitized)
        self.assertNotIn("ou_abc123", sanitized)
        self.assertNotIn("ou_xyz789", sanitized)

    def test_report_guard_flags_feishu_recipient_fields(self):
        report = """# Codex 工作日报 - 2026-07-28

## 今日概览
- recipientOpenId: "ou_abc123"

## 项目进展
- 已完成公开分享版检查。

## 当前阻塞
- 无明确阻塞。

## 下一日待办
- 完成剩余加固。

## Codex 使用优化建议
- P1：继续补齐脱敏规则。
"""

        errors = report_guard.validate_report(report)

        self.assertIn("unredacted sensitive assignment: recipientOpenId", errors)

    def test_report_guard_flags_absolute_local_paths(self):
        report = """# Codex 工作日报 - 2026-07-28

## 今日概览
- 输出文件位于 /Users/example/private/report.md

## 项目进展
- 已完成公开分享版检查。

## 当前阻塞
- 无明确阻塞。

## 下一日待办
- 完成剩余加固。

## Codex 使用优化建议
- P1：继续补齐脱敏规则。
"""

        errors = report_guard.validate_report(report)

        self.assertIn("report contains an absolute local path", errors)


if __name__ == "__main__":
    unittest.main()
