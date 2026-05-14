"""
agents/schemas.py
-----------------
Shared Pydantic schemas for all agent-to-agent handoffs.

Two pipelines share this file:

  Pipeline A — Issue Fix (Modules 1-5):
    IssueAnalysis  (Issue Reader → Code Analyst)
    CodeAnalysis   (Code Analyst → Fix Writer)

  Pipeline B — PR Review (assignment):
    DiffSummary    (Diff Parser → Review Critic)
    PRReview       (Review Critic → output / human)

TEACHING NOTE — Why Pydantic over dataclasses:
  Pydantic validates data at parse time, not silently.

  With dataclasses:
    FileChange(change_type="very modify")  # silently accepted, bug flows downstream

  With Pydantic:
    FileChange(change_type="very modify")  # ValidationError raised immediately:
    # change_type: Input should be 'modify', 'create' or 'delete'

  In agent pipelines this matters a lot. The LLM will occasionally drift from
  your schema. You want that caught immediately with a clear error, not 3 agents
  later with a confusing KeyError. Pydantic gives you that for free.

  Other benefits we get here:
  - model.model_dump_json()  — built-in JSON serialisation
  - model.model_validate_json(raw)  — parse + validate in one call
  - Literal types  — constrain to exact allowed values
  - Field(description=...)  — documents fields, also useful in prompts
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
import json


# ── Pipeline A: Issue Fix ──────────────────────────────────────────────────────

class FileChange(BaseModel):
    """A single file the Fix Writer needs to touch."""
    path: str = Field(description="Repo-relative path, e.g. 'src/auth/middleware.py'")
    reason: str = Field(description="Why this file is relevant to the fix")
    relevant_lines: Optional[str] = Field(
        default=None,
        description="Line range or function name, e.g. '42-67' or 'validate_token'"
    )
    change_type: Literal["modify", "create", "delete"] = Field(
        description="What kind of change is needed"
    )
    change_description: str = Field(
        description="Plain English: exactly what to change and why"
    )


class CodeAnalysis(BaseModel):
    """
    Structured handoff: Code Analyst → Fix Writer.

    Everything the Fix Writer needs to produce a correct patch without
    re-reading the issue or re-exploring the repo.
    """
    issue_summary: str = Field(description="One sentence describing the bug")
    root_cause: str = Field(description="The specific technical reason the bug occurs")
    reproduction_steps: str = Field(description="How to trigger the bug")

    files_to_change: list[FileChange] = Field(description="Ordered by importance")
    fix_approach: str = Field(description="Plain English strategy for the overall fix")
    test_files: list[str] = Field(description="Existing test files to check or update")

    estimated_complexity: Literal["trivial", "small", "medium", "large"]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str = Field(description="Why you are or aren't confident")
    risks: str = Field(description="What could go wrong with this fix")

    def to_prompt(self) -> str:
        """Format for injection into the Fix Writer's context."""
        files_summary = "\n".join(
            f"  - {f.path} ({f.change_type}): {f.change_description}"
            for f in self.files_to_change
        )
        return (
            f"## Code analysis (from Code Analyst agent)\n\n"
            f"**Issue:** {self.issue_summary}\n"
            f"**Root cause:** {self.root_cause}\n"
            f"**Complexity:** {self.estimated_complexity} | "
            f"**Confidence:** {self.confidence} ({self.confidence_reason})\n\n"
            f"**Files to change:**\n{files_summary}\n\n"
            f"**Fix approach:** {self.fix_approach}\n\n"
            f"**Risks:** {self.risks}\n\n"
            f"<full_analysis>\n{self.model_dump_json(indent=2)}\n</full_analysis>"
        )


# ── Pipeline B: PR Review ──────────────────────────────────────────────────────

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


# ── Pipeline A: Fix Writer + Reviewer ─────────────────────────────────────────

class FixedFile(BaseModel):
    """A single file with its corrected content."""
    path: str = Field(description="Repo-relative path, e.g. 'src/auth/middleware.py'")
    original_content: str = Field(description="The relevant section before the fix")
    fixed_content: str = Field(description="The full updated file content (not just a diff)")
    explanation: str = Field(description="Why this change fixes the bug")


class ProposedFix(BaseModel):
    """
    Structured handoff: Fix Writer → Reviewer.

    Contains everything needed to evaluate and apply the fix.
    """
    summary: str = Field(description="One sentence: what the fix does")
    files: list[FixedFile] = Field(description="All files changed, with full updated content")
    test_suggestions: list[str] = Field(description="New test cases that should be added")
    confidence: Literal["high", "medium", "low"]
    caveats: str = Field(description="Known limitations or edge cases the fix doesn't handle")

    def to_prompt(self) -> str:
        """Format for injection into the Reviewer's context."""
        files_summary = "\n".join(
            f"  - {f.path}: {f.explanation}"
            for f in self.files
        )
        return (
            f"## Proposed Fix (from Fix Writer agent)\n\n"
            f"**Summary:** {self.summary}\n"
            f"**Confidence:** {self.confidence}\n"
            f"**Caveats:** {self.caveats}\n\n"
            f"**Files changed:**\n{files_summary}\n\n"
            f"**Test suggestions:**\n"
            + "\n".join(f"  - {t}" for t in self.test_suggestions)
            + f"\n\n<full_fix>\n{self.model_dump_json(indent=2)}\n</full_fix>"
        )


class Objection(BaseModel):
    """A specific issue the Reviewer found with the proposed fix."""
    file_path: str = Field(description="Which file has the problem")
    issue: str = Field(description="What's wrong with the fix")
    suggestion: str = Field(description="How to correct it")


class ReviewDecision(BaseModel):
    """
    Structured handoff: Reviewer → Fix Writer (if needs_revision) or done.

    TEACHING NOTE — The critic/generator pattern:
      Reviewer sees the full CodeAnalysis + ProposedFix and asks:
        1. Does this fix address the actual root cause?
        2. Does it introduce any new bugs?
        3. Does it match the project's code style?
        4. Are the test suggestions adequate?
      If any answer is "no", it returns specific Objections for the Fix Writer.
    """
    verdict: Literal["approved", "needs_revision"]
    overall_comment: str = Field(description="2-3 sentence assessment of the fix")
    objections: list[Objection] = Field(
        description="Specific issues to fix (empty if approved)"
    )

    def to_prompt(self) -> str:
        """Format objections for re-injection into Fix Writer."""
        if self.verdict == "approved":
            return f"## Review: APPROVED\n\n{self.overall_comment}"
        lines = [
            f"## Review: NEEDS REVISION\n\n{self.overall_comment}\n\n**Objections to address:**"
        ]
        for i, obj in enumerate(self.objections, 1):
            lines.append(f"\n{i}. [{obj.file_path}]")
            lines.append(f"   Issue: {obj.issue}")
            lines.append(f"   Fix:   {obj.suggestion}")
        return "\n".join(lines)
