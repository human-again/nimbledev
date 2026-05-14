"""
agents/reviewer.py
------------------
Evaluates a proposed fix and returns approval or revision requests.
"""

import json
import re
import anthropic
from rich.console import Console
from rich.panel import Panel

from config.settings import ANTHROPIC_API_KEY, MODEL
from agents.schemas import CodeAnalysis, ProposedFix, ReviewDecision, Objection

console = Console()

SYSTEM_PROMPT = """You are the Reviewer agent for NimbleDev, a multi-agent system that fixes open source bugs.

You will receive:
1. A CodeAnalysis — the structured diagnosis of the bug (root cause, files to change, risks)
2. A ProposedFix — the Fix Writer's corrected code for each file

YOUR JOB: Evaluate whether the fix is correct and safe to submit as a PR.

REVIEW CHECKLIST — answer each question:
1. Does the fix address the ROOT CAUSE identified in CodeAnalysis (not just a symptom)?
2. Does the fixed code have any new bugs, off-by-one errors, or broken edge cases?
3. Does the fix match the project's existing code style?
4. Are the test_suggestions adequate for the bug being fixed?
5. Could this change break any related functionality outside the changed files?

DECISION RULES:
- "approved": the fix correctly addresses the root cause with no new issues
- "needs_revision": there is a specific, concrete problem that must be fixed first

IMPORTANT: Do not ask for revisions for style nits or minor improvements. Only request
revisions for issues that could cause bugs, test failures, or PR rejection.

OUTPUT FORMAT — a single JSON block, no prose before or after:

```json
{
  "verdict": "approved | needs_revision",
  "overall_comment": "2-3 sentence assessment",
  "objections": [
    {
      "file_path": "path/to/file.py",
      "issue": "what is wrong with the fix for this file",
      "suggestion": "how to correct it"
    }
  ]
}
```

If verdict is "approved", objections must be an empty list [].
Output ONLY the JSON block."""


def _extract_json(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    raise ValueError("No JSON object found in agent response")


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 40:
            v_str = v_str[:40] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)


def run(code_analysis: CodeAnalysis, proposed_fix: ProposedFix) -> ReviewDecision:
    """
    Run the Reviewer agent.

    Args:
        code_analysis:  The CodeAnalysis from Code Analyst (what the bug is)
        proposed_fix:   The ProposedFix from Fix Writer (what the fix is)

    Returns:
        ReviewDecision — either approved or needs_revision with specific objections
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build a compact but complete view of the fix for the reviewer
    files_section = ""
    for f in proposed_fix.files:
        files_section += (
            f"\n### {f.path}\n"
            f"**Explanation:** {f.explanation}\n\n"
            f"**Before (relevant section):**\n```\n{f.original_content}\n```\n\n"
            f"**After (full file):**\n```\n{f.fixed_content[:3000]}"
        )
        if len(f.fixed_content) > 3000:
            files_section += f"\n... (truncated, {len(f.fixed_content)} chars total)"
        files_section += "\n```\n"

    user_message = (
        f"## Code Analysis\n\n"
        f"{code_analysis.to_prompt()}\n\n"
        f"{'─' * 60}\n\n"
        f"## Proposed Fix\n\n"
        f"**Summary:** {proposed_fix.summary}\n"
        f"**Confidence:** {proposed_fix.confidence}\n"
        f"**Caveats:** {proposed_fix.caveats}\n\n"
        f"**Test suggestions:**\n"
        + "\n".join(f"  - {t}" for t in proposed_fix.test_suggestions)
        + f"\n\n{files_section}\n\n"
        f"Review this fix and produce your JSON decision."
    )

    messages = [{"role": "user", "content": user_message}]

    console.print(Panel(
        f"[bold]Reviewer Agent[/bold]\n"
        f"Evaluating fix for: [cyan]{code_analysis.issue_summary[:80]}[/cyan]\n"
        f"Files under review: [cyan]{len(proposed_fix.files)}[/cyan]",
        border_style="yellow"
    ))

    # The Reviewer is a single-shot agent — no tools, no loop needed
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    console.print("\n[dim]Parsing review decision...[/dim]")
    try:
        json_str = _extract_json(raw_text)
        decision = ReviewDecision.model_validate_json(json_str)

        verdict_colour = "green" if decision.verdict == "approved" else "red"
        console.print(Panel(
            f"[{verdict_colour}]Verdict: {decision.verdict.upper()}[/{verdict_colour}]\n"
            f"{decision.overall_comment}\n"
            + (
                f"\nObjections ({len(decision.objections)}):\n"
                + "\n".join(f"  • [{o.file_path}] {o.issue}" for o in decision.objections)
                if decision.objections else ""
            ),
            border_style=verdict_colour
        ))
        return decision

    except (ValueError, json.JSONDecodeError) as e:
        console.print(f"[red]Failed to parse review: {e}[/red]")
        raise RuntimeError(f"Reviewer produced invalid output: {e}") from e
    except Exception as e:
        console.print(f"[red]Schema validation failed: {e}[/red]")
        raise RuntimeError(f"Reviewer output failed validation: {e}") from e
