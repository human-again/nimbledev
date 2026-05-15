"""
agents/review_critic.py
-----------------------
Evaluates a pull request from a structured diff summary and returns a review.
"""

from rich.console import Console
from rich.panel import Panel

from config.settings import MODEL
from agents.llm import create_llm_client
from tools.github import CRITIC_TOOLS, dispatch
from agents.json_utils import extract_json_object
from agents.schemas import DiffSummary, PRReview

console = Console()

SYSTEM_PROMPT = """You are the Review Critic agent for NimbleDev's PR Review pipeline.

You will receive a structured DiffSummary from the Diff Parser agent. Your job is to perform a thorough, professional code review and produce structured output.

WHAT YOU MUST DO:
1. Read the DiffSummary carefully — it tells you what changed and where to focus
2. Fetch the full diff using get_pr_diff to read the actual code changes
3. Use get_file_content to read any context files listed in the DiffSummary
4. Evaluate the changes for: bugs, security issues, performance, style, test coverage, design
5. Be specific — reference file paths and line numbers wherever possible

WHAT YOU MUST PRODUCE:
A single JSON block — no prose before or after:

```json
{
  "pr_title": "the PR title from the DiffSummary",
  "overall_verdict": "approve | request_changes | comment",
  "summary": "2-3 sentence high-level assessment",
  "comments": [
    {
      "file_path": "path/to/file.py",
      "line_ref": "42",
      "severity": "critical | major | minor | nit",
      "category": "bug | security | performance | style | test | design | documentation",
      "comment": "Specific, actionable, kind comment",
      "suggestion": "Concrete fix suggestion or null"
    }
  ],
  "positive_highlights": [
    "Something done well"
  ],
  "missing_tests": [
    "Scenario or edge case that needs a test"
  ]
}
```

SEVERITY GUIDE:
- critical: bug or security issue that must block merge
- major: significant issue worth fixing before merge
- minor: improvement worth doing, but not blocking
- nit: style or personal preference

RULES:
- get_pr_diff and get_file_content return JSON with content, truncated, and total_chars. If truncated is true, account for that limitation in your summary or missing_tests rather than over-claiming certainty.
- overall_verdict must be "request_changes" if any critical or major comments exist
- overall_verdict must be "approve" only if the PR is ready to merge as-is
- Always include at least one positive highlight — good review culture
- Comments must be ordered: critical first, then major, minor, nit
- Be kind and specific — write comments as you would to a colleague
- Output ONLY the JSON block. No introduction, no explanation after."""


def _extract_json(text: str) -> str:
    return extract_json_object(text)


def run(owner: str, repo: str, pr_number: int, diff_summary: DiffSummary) -> PRReview:
    """Run the Review Critic agent and return the final structured review."""
    client = create_llm_client()

    messages = [
        {
            "role": "user",
            "content": (
                f"Please review this pull request.\n\n"
                f"Repo: {owner}/{repo} — PR #{pr_number}\n\n"
                f"The Diff Parser has already analysed the PR structure. "
                f"Here is its structured summary:\n\n"
                f"```json\n{diff_summary.model_dump_json(indent=2)}\n```\n\n"
                f"Now fetch the diff and any context files, then produce your review."
            ),
        }
    ]

    console.print(Panel(
        f"[bold]Review Critic Agent[/bold]\n"
        f"Target: [cyan]{owner}/{repo}[/cyan] — PR [cyan]#{pr_number}[/cyan]\n"
        f"[dim]Areas of concern: {len(diff_summary.areas_of_concern)}[/dim]",
        border_style="yellow"
    ))

    iteration = 0
    max_iterations = 12
    parse_failures = 0
    max_parse_retries = 1
    correcting_output = False

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]── Turn {iteration} ──[/dim]")

        response = client.create_message(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[] if correcting_output else CRITIC_TOOLS,
            messages=messages,
        )
        _print_usage(response)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            raw_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            console.print("\n[dim]Parsing PRReview...[/dim]")
            try:
                json_str = _extract_json(raw_text)
                review = PRReview.model_validate_json(json_str)
                console.print(Panel(
                    f"[green]Review complete[/green]\n"
                    f"Verdict: [bold]{review.overall_verdict.upper()}[/bold]\n"
                    f"Comments: {len(review.comments)} "
                    f"({review.critical_count()} critical, {review.major_count()} major)",
                    border_style="green"
                ))
                return review
            except Exception as e:
                console.print(f"[red]Parse failed: {e}[/red]")
                if parse_failures < max_parse_retries:
                    parse_failures += 1
                    correcting_output = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response did not validate as a PRReview. "
                            f"Validation error: {e}\n\n"
                            "Return only a corrected JSON object matching the requested schema."
                        ),
                    })
                    continue
                raise RuntimeError(f"Review Critic produced invalid output: {e}") from e

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

    raise RuntimeError("Review Critic hit iteration limit without producing output.")


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 40:
            v_str = v_str[:40] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)


def _print_usage(response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if input_tokens is not None and output_tokens is not None:
        console.print(f"[dim]Tokens: in={input_tokens}, out={output_tokens}[/dim]")
