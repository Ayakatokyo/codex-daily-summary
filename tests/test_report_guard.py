import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "codex-daily-summary" / "scripts" / "report_guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("report_guard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID = """# Codex 工作日报 - 2026-07-19

## 今日概览
完成日报汇总能力的基础实现。

## 项目进展
### Repo A
完成事件提取和脱敏测试。

## 当前阻塞
暂无阻塞。

## 下一日待办
- P1：接入日报发送流程。

## Codex 使用优化建议
- 优先级：P1；当天证据：两次会话包含重复的状态查询；优化建议：合并查询步骤；可直接执行：复用一次提取结果。

## 来源索引
- Repo A：本地 Codex 会话记录。
"""


class ReportGuardTests(unittest.TestCase):
    def test_valid_report_has_no_errors(self):
        module = load_module()

        self.assertEqual([], module.validate_report(VALID))

    def test_reports_missing_section_and_unredacted_sensitive_value(self):
        module = load_module()
        invalid = VALID.replace("## 下一日待办", "## Later") + "\napi_key=sk-live-secret\n"

        errors = module.validate_report(invalid)

        self.assertTrue(any("下一日待办" in error for error in errors))
        self.assertTrue(any("api_key" in error for error in errors))

    def test_chunks_long_reports_at_heading_boundaries(self):
        module = load_module()
        second_report = VALID.replace("Repo A", "Repo B").replace(
            "完成事件提取和脱敏测试。",
            "完成日报校验和分片实现。" + "补充进展。" * 100,
        )

        chunks = module.chunk_report(VALID + "\n" + second_report, max_chars=700)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.startswith("# ") for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
