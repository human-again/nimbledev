"""
agents/diff_parser.py
---------------------
Builds a structured summary of a pull request for downstream review.
"""

import re
import anthropic
from rich.console import Console
from rich.panel import Panel

from config.settings import ANTHROPIC_API_KEY, MODEL
from tools.github import PR_REVIEW_TOOLS, dispatch
from agents.schemas import DiffSummary

console = Console()

SYSTEM_PROMPT = """You are the Diff Parser agent for NimbleDev's PR Review pipeline.

Your job is to read a GitHub pull request and produce a structured summary that the Review Critic agent will use to perform a thorough code review.

WHAT YOU MUST DO:
1. Fetch the PR metadata using get_pull_request
2. Fetch the list of changed files using get_pr_files
3. Fetch the full diff using get_pr_diff
4. Read any files that appear complex or critical using get_file_content
5. Identify which areas of the code deserve the closest scrutiny

WHAT YOU MUST PRODUCE:
A single JSON block — no prose before or after:

```json
{
  "pr_title": "the PR title",
  "pr_description": "the PR description (or '(no description)' if empty)",
  "files_changed": ["list", "of", "changed", "file", "paths"],
  "additions": 42,
  "deletions": 7,
  "change_summary": "Plain English: what this PR does and why, based on the diff and description",
  "areas_of_concern": [
    "Specific area 1 the Critic should scrutinise — be concrete, e.g. 'error handling in auth.py lines 34-67'",
    "Specific area 2"
  ],
  "context_files": ["files/outside/the/diff.py", "that/help/understand/the/change.py"]
}
```

RULES:
- areas_of_concern should be specific and actionable — not generic like "check for bugs"
- context_files are files NOT in the diff but helpful for reviewing it (e.g. callers, tests, interfaces)
- Output ONLY the JSON block. No introduction, no explanation after."""


def _extract_json(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    raise ValueError("No JSON object found in agent response")


def run(owner: str, repo: str, pr_number: int) -> DiffSummary:
    """Run the Diff Parser agent and return a structured handoff."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    messages = [
        {
            "role": "user",
            "content": (
                f"Please inspect this pull request and produce a structured diff summary.\n\n"
                f"Repo: {owner}/{repo}\n"
                f"PR: #{pr_number}\n\n"
                f"Start by fetching the PR metadata, then the file list, then the diff."
            ),
        }
    ]

    console.print(Panel(
        f"[bold]Diff Parser Agent[/bold]\n"
        f"Target: [cyan]{owner}/{repo}[/cyan] — PR [cyan]#{pr_number}[/cyan]",
        border_style="blue"
    ))

    iteration = 0
    max_iterations = 10

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]── Turn {iteration} ──[/dim]")

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=PR_REVIEW_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            raw_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            console.print("\n[dim]Parsing DiffSummary...[/dim]")
            try:
                json_str = _extract_json(raw_text)
                summary = DiffSummary.model_validate_json(json_str)
                console.print(Panel(
                    f"[green]Diff parsed[/green]\n"
                    f"Files changed: {len(summary.files_changed)}\n"
                    f"+{summary.additions} / -{summary.deletions}\n"
                    f"Areas of concern: {len(summary.areas_of_concern)}",
                    border_style="green"
                ))
                return summary
            except Exception as e:
                console.print(f"[red]Parse failed: {e}[/red]")
                raise RuntimeError(f"Diff Parser produced invalid output: {e}") from e

        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                console.print(f"  [yellow]→[/yellow] [bold]{block.name}[/bold]({_fmt_args(block.input)})")
                result = dispatch(block.name, block.input)
                preview = result[:200] + "..." if len(result) > 200 else result
                console.print(f"  [dim]{preview}[/dim]")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            messages.append({"role": "user", "content": tool_results})

        else:
            console.print(f"[red]Unexpected stop_reason: {response.stop_reason}[/red]")
            break

    raise RuntimeError("Diff Parser hit iteration limit without producing output.")


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 40:
            v_str = v_str[:40] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)
