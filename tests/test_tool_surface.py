import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

from tools.github import PR_REVIEW_TOOLS, TOOL_FUNCTIONS, dispatch


class ToolSurfaceTest(unittest.TestCase):
    def test_pr_review_tools_are_explicit_and_limited(self) -> None:
        expected = {
            "get_pull_request",
            "get_pr_files",
            "get_pr_diff",
            "get_file_content",
        }

        self.assertEqual(expected, {tool["name"] for tool in PR_REVIEW_TOOLS})
        self.assertEqual(expected, set(TOOL_FUNCTIONS))

    def test_unknown_tool_is_rejected(self) -> None:
        blocked_tool = "get_" + "issue"
        self.assertEqual(
            f"Error: Unknown tool '{blocked_tool}'",
            dispatch(blocked_tool, {"owner": "octo", "repo": "repo", "issue_number": 1}),
        )


if __name__ == "__main__":
    unittest.main()
