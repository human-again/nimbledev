import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERN = (
    r"TEACHING NOTE|Module [0-9]:|Your First Agent|"
    r"Deterministic Code vs Agentic Loops|The Agentic Loop|"
    r"Agent specialisation|critic/generator"
)
TARGETS = ["main.py", "agents", "tools", "config"]


class CommentToneTest(unittest.TestCase):
    def test_code_does_not_contain_tutorial_language(self) -> None:
        result = subprocess.run(
            ["rg", "-n", PATTERN, *TARGETS],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stdout)


if __name__ == "__main__":
    unittest.main()
