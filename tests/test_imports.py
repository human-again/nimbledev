import importlib
import os
import unittest


class ImportTest(unittest.TestCase):
    def test_settings_imports_with_required_environment(self) -> None:
        os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
        os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

        module = importlib.import_module("config.settings")
        self.assertTrue(module.ANTHROPIC_API_KEY)
        self.assertTrue(module.GITHUB_TOKEN)
        self.assertTrue(module.MODEL)


if __name__ == "__main__":
    unittest.main()
