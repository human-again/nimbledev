import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OnboardingArtifactsTest(unittest.TestCase):
    def test_env_example_lists_required_keys(self) -> None:
        env_example = ROOT / ".env.example"
        self.assertTrue(env_example.exists(), ".env.example should exist")

        content = env_example.read_text()
        self.assertIn("LLM_PROVIDER=anthropic", content)
        self.assertIn("MODEL=", content)
        self.assertIn("ANTHROPIC_API_KEY=", content)
        self.assertIn("GITHUB_TOKEN=", content)
        self.assertIn("ANTHROPIC_MODEL=", content)
        self.assertNotIn("GITHUB_USERNAME=", content)

    def test_setup_script_exists_and_uses_python_310(self) -> None:
        setup_script = ROOT / "setup.sh"
        self.assertTrue(setup_script.exists(), "setup.sh should exist")

        content = setup_script.read_text()
        self.assertIn("python3.10", content)
        self.assertIn("pip install -e .", content)
        self.assertIn("LLM_PROVIDER", content)
        self.assertIn("MODEL", content)

    def test_readme_documents_test_command(self) -> None:
        readme = ROOT / "README.md"
        content = readme.read_text()
        self.assertIn(".venv/bin/python -m unittest discover -s tests -v", content)


if __name__ == "__main__":
    unittest.main()
