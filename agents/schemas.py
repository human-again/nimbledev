"""
agents/schemas.py
-----------------
Shared Pydantic schemas for the PR review handoff.

This branch ships only the PR review pipeline.
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
# ── Pipeline: PR Review ────────────────────────────────────────────────────────

class ReviewComment(BaseModel):
    """A single inline review comment on the PR."""
    file_path: str = Field(description="File this comment refers to")
    line_ref: Optional[str] = Field(
        default=None,
        description="Line number or range, e.g. '42' or '38-45'. None if file-level."
    )
    severity: Literal["critical", "major", "minor", "nit"] = Field(
        description=(
            "critical=bug/security risk that must block merge, "
            "major=significant issue worth fixing before merge, "
            "minor=improvement that's worth doing, "
            "nit=style or preference"
        )
    )
    category: Literal["bug", "security", "performance", "style", "test", "design", "documentation"]
    comment: str = Field(description="The review comment — specific, actionable, and kind")
    suggestion: Optional[str] = Field(
        default=None,
        description="Concrete suggestion or code snippet for how to fix it"
    )


class DiffSummary(BaseModel):
    """
    Structured handoff: Diff Parser → Review Critic.

    The Diff Parser's job is to understand *what* changed. The Review Critic's
    job is to evaluate *whether* those changes are good. Keeping them separate
    means the Critic starts with a clean structured picture instead of raw diff text.
    """
    pr_title: str
    pr_description: str
    files_changed: list[str] = Field(description="List of all files modified")
    additions: int = Field(description="Total lines added")
    deletions: int = Field(description="Total lines deleted")

    change_summary: str = Field(
        description="Plain English: what this PR does and why"
    )
    areas_of_concern: list[str] = Field(
        description="Specific areas the Critic should scrutinise — e.g. error handling, auth logic"
    )
    context_files: list[str] = Field(
        description="Files outside the diff that the Critic should read for context"
    )


class PRReview(BaseModel):
    """
    Final structured output of the PR Review pipeline.
    This is what gets printed / returned to the user.
    """
    pr_title: str
    overall_verdict: Literal["approve", "request_changes", "comment"] = Field(
        description=(
            "approve=ready to merge, "
            "request_changes=has critical or major issues, "
            "comment=observations only"
        )
    )
    summary: str = Field(
        description="2-3 sentence high-level assessment of the PR"
    )
    comments: list[ReviewComment] = Field(
        description="Inline review comments, ordered by severity (critical first)"
    )
    positive_highlights: list[str] = Field(
        description="Things done well — good review culture includes praise"
    )
    missing_tests: list[str] = Field(
        description="Scenarios or edge cases that should have test coverage"
    )

    @model_validator(mode="after")
    def require_changes_for_blocking_comments(self) -> "PRReview":
        has_blocking_comment = any(
            c.severity in {"critical", "major"} for c in self.comments
        )
        if has_blocking_comment and self.overall_verdict != "request_changes":
            raise ValueError(
                "overall_verdict must be 'request_changes' when critical or major comments exist"
            )
        return self

    def critical_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "critical")

    def major_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "major")

    def to_display(self) -> str:
        """Render a human-readable review report."""
        verdict_icon = {
            "approve": "✅ APPROVE",
            "request_changes": "❌ REQUEST CHANGES",
            "comment": "💬 COMMENT",
        }[self.overall_verdict]

        lines = [
            f"{'═' * 60}",
            f"PR REVIEW: {self.pr_title}",
            f"Verdict: {verdict_icon}",
            f"{'═' * 60}",
            f"\nSUMMARY\n{self.summary}",
        ]

        if self.positive_highlights:
            lines.append("\n✓ WHAT'S GOOD")
            for h in self.positive_highlights:
                lines.append(f"  • {h}")

        if self.comments:
            lines.append(f"\nREVIEW COMMENTS ({len(self.comments)} total, "
                         f"{self.critical_count()} critical, {self.major_count()} major)")
            for c in self.comments:
                loc = f"{c.file_path}" + (f":{c.line_ref}" if c.line_ref else "")
                lines.append(f"\n  [{c.severity.upper()}] [{c.category}] {loc}")
                lines.append(f"  {c.comment}")
                if c.suggestion:
                    lines.append(f"  → {c.suggestion}")

        if self.missing_tests:
            lines.append("\n⚠ MISSING TEST COVERAGE")
            for t in self.missing_tests:
                lines.append(f"  • {t}")

        lines.append(f"\n{'═' * 60}")
        return "\n".join(lines)
