import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

from tools.github import (
    CRITIC_TOOLS,
    DIFF_PARSER_TOOLS,
    PR_REVIEW_TOOLS,
    TOOL_FUNCTIONS,
    dispatch,
    get_pr_diff,
)


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

    def test_agents_receive_specialized_tool_sets(self) -> None:
        self.assertEqual(
            {"get_pull_request", "get_pr_files", "get_pr_diff"},
            {tool["name"] for tool in DIFF_PARSER_TOOLS},
        )
        self.assertEqual(
            {"get_pr_diff", "get_file_content"},
            {tool["name"] for tool in CRITIC_TOOLS},
        )

    @patch("tools.github.requests.get")
    def test_truncated_diff_returns_structured_metadata(self, mock_get: Mock) -> None:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "a" * 12001

        result = get_pr_diff("octo", "repo", 1)

        self.assertIn('"truncated": true', result)
        self.assertIn('"total_chars": 12001', result)
        self.assertIn('"content"', result)

    def test_unknown_tool_is_rejected(self) -> None:
        blocked_tool = "get_" + "issue"
        self.assertEqual(
            f"Error: Unknown tool '{blocked_tool}'",
            dispatch(blocked_tool, {"owner": "octo", "repo": "repo", "issue_number": 1}),
        )


if __name__ == "__main__":
    unittest.main()
