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


if __name__ == "__main__":
    unittest.main()
