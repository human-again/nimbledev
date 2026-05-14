import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliSurfaceTest(unittest.TestCase):
    def test_help_exposes_full_product_surface(self) -> None:
        result = subprocess.run(
            [".venv/bin/python", "main.py", "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        self.assertIn("review-pr", output)
        self.assertIn("read-issue", output)
        self.assertIn("analyze", output)
        self.assertIn("fix", output)
        self.assertIn("serve-mcp", output)


if __name__ == "__main__":
    unittest.main()
