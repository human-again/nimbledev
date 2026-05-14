import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

from agents.diff_parser import _extract_json as extract_diff_json
from agents.review_critic import _extract_json as extract_review_json
from agents.schemas import PRReview


class AgentParsingTest(unittest.TestCase):
    def test_extract_json_from_fenced_response(self) -> None:
        text = '```json\n{"pr_title": "Example", "files_changed": []}\n```'
        self.assertEqual('{"pr_title": "Example", "files_changed": []}', extract_diff_json(text))

    def test_extract_json_from_plain_response(self) -> None:
        text = 'before {"overall_verdict": "approve"} after'
        self.assertEqual('{"overall_verdict": "approve"}', extract_review_json(text))

    def test_pr_review_display_includes_core_fields(self) -> None:
        review = PRReview(
            pr_title="Improve parser",
            overall_verdict="request_changes",
            summary="The change is useful but misses an edge case.",
            comments=[
                {
                    "file_path": "parser.py",
                    "line_ref": "42",
                    "severity": "major",
                    "category": "bug",
                    "comment": "Handle empty input before indexing.",
                    "suggestion": "Return early when the input list is empty.",
                }
            ],
            positive_highlights=["Small, focused change."],
            missing_tests=["Empty input should be covered."],
        )

        output = review.to_display()

        self.assertIn("Improve parser", output)
        self.assertIn("REQUEST CHANGES", output)
        self.assertIn("parser.py:42", output)
        self.assertIn("Empty input should be covered.", output)


if __name__ == "__main__":
    unittest.main()
