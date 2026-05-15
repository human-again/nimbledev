import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_HELP_TERMS = [
    "feature/" + "issue-fix",
    "Roadmap",
    "Issue-" + "fix agents",
    "read-" + "issue",
    "ana" + "lyze",
    "fix",
    "serve-" + "mcp",
]


class CliSurfaceTest(unittest.TestCase):
    def test_help_only_exposes_pr_review_surface(self) -> None:
        result = subprocess.run(
            [".venv/bin/python", "main.py", "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        self.assertIn("review-pr", output)
        for term in FORBIDDEN_HELP_TERMS:
            self.assertNotIn(term, output)


if __name__ == "__main__":
    unittest.main()
