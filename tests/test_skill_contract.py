from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill" / "codex-daily-summary"


class SkillContractTests(unittest.TestCase):
    def test_required_skill_files_exist(self):
        required = [
            SKILL / "SKILL.md",
            SKILL / "agents" / "openai.yaml",
            SKILL / "references" / "codex-optimization-rubric.md",
        ]
        self.assertEqual([], [str(path) for path in required if not path.is_file()])

    def test_skill_and_rubric_define_the_required_workflow(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        rubric_text = (SKILL / "references" / "codex-optimization-rubric.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "extract_codex_day.py",
            "report_guard.py",
            "send_dingtalk.py",
            "do not ask for a second confirmation",
            "fixed configured recipient",
            "Codex usage optimization",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill_text)

        for heading in [
            "Model and reasoning",
            "Prompt quality",
            "Context handoff",
            "Conversation boundary",
            "Open-ended review",
        ]:
            with self.subTest(heading=heading):
                self.assertIn(f"## {heading}", rubric_text)

    def test_only_daily_report_or_explicit_send_requests_authorize_delivery(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        openai_yaml = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn(
            "Review-only or no-send requests never authorize delivery.", skill_text
        )
        self.assertIn(
            "Only a manual daily summary request, daily report request, or explicit send request authorizes immediate delivery to the fixed configured recipient.",
            skill_text,
        )
        self.assertIn(
            "Do not condition delivery on a separate delivery request.", skill_text
        )
        self.assertIn(
            "总结今天的 Codex 工作，复盘我的 Codex 使用方式，并直接发送到我的钉钉。",
            openai_yaml,
        )
        self.assertIn("日报请求可推送钉钉", openai_yaml)

    def test_rubric_requires_safe_evidence_and_complete_open_ended_review(self):
        rubric_text = (SKILL / "references" / "codex-optimization-rubric.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "merge repeated issues",
            "sanitized title label, not raw title",
            "short behavioral observation",
            "never raw private transcript",
            "Skill/tool/Codex surface",
            "independent parallelism",
            "acceptance criteria",
            "file/log/reference inputs",
            "feedback loops",
            "repeated work encode Skill/script/AGENTS.md",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rubric_text)


if __name__ == "__main__":
    unittest.main()
