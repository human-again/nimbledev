import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

from agents import diff_parser
from agents import review_critic
from agents.schemas import DiffSummary


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.calls = 0
        self.responses = responses
        self.tools_by_call: list[list[dict]] = []

    def create_message(self, **kwargs):
        self.tools_by_call.append(kwargs["tools"])
        self.calls += 1
        text = self.responses[self.calls - 1]
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=text)],
        )


class AgentRetryTest(unittest.TestCase):
    def test_review_critic_retries_once_after_invalid_json_output(self) -> None:
        fake_client = FakeClient([
            '{"pr_title": "Example", "overall_verdict": "approve"}',
            """
            {
              "pr_title": "Example",
              "overall_verdict": "comment",
              "summary": "Looks mostly fine.",
              "comments": [],
              "positive_highlights": ["Focused change."],
              "missing_tests": []
            }
            """,
        ])
        summary = DiffSummary(
            pr_title="Example",
            pr_description="Test PR",
            files_changed=["app.py"],
            additions=1,
            deletions=0,
            change_summary="Adds a line.",
            areas_of_concern=[],
            context_files=[],
        )

        with patch.object(review_critic, "create_llm_client", return_value=fake_client):
            review = review_critic.run("octo", "repo", 1, summary)

        self.assertEqual("comment", review.overall_verdict)
        self.assertEqual(2, fake_client.calls)
        self.assertNotEqual([], fake_client.tools_by_call[0])
        self.assertEqual([], fake_client.tools_by_call[1])

    def test_diff_parser_retries_once_after_invalid_json_output(self) -> None:
        fake_client = FakeClient([
            '{"pr_title": "Example"}',
            """
            {
              "pr_title": "Example",
              "pr_description": "Test PR",
              "files_changed": ["app.py"],
              "additions": 1,
              "deletions": 0,
              "change_summary": "Adds a line.",
              "areas_of_concern": [],
              "context_files": []
            }
            """,
        ])

        with patch.object(diff_parser, "create_llm_client", return_value=fake_client):
            summary = diff_parser.run("octo", "repo", 1)

        self.assertEqual("Example", summary.pr_title)
        self.assertEqual(2, fake_client.calls)
        self.assertNotEqual([], fake_client.tools_by_call[0])
        self.assertEqual([], fake_client.tools_by_call[1])


if __name__ == "__main__":
    unittest.main()
