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


if __name__ == "__main__":
    unittest.main()
