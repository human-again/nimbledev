"""
agents/code_analyst.py
----------------------
Module 2: The Code Analyst Agent

Receives the Issue Reader's analysis and goes deeper — reads full files,
pinpoints exact lines, and produces a structured CodeAnalysis spec that
the Fix Writer can act on directly.

TEACHING NOTE — Agent-to-agent handoffs:
  This is the first time one agent's output becomes another's input.
  The handoff has three parts:

  1. OUTPUT CONTRACT: The Code Analyst must produce a CodeAnalysis object
     (defined in schemas.py). We enforce this by embedding the JSON schema
     in the system prompt and parsing the response. If parsing fails,
     we know the agent went off-script.

  2. CONTEXT INJECTION: The Issue Reader's analysis is injected into the
     Code Analyst's first user message. The analyst doesn't re-read the
     issue from GitHub — it trusts the prior agent's work and goes deeper.
     This is the core pattern for chaining agents efficiently.

  3. SPECIALISATION: Each agent has a narrow, well-defined job. The Code
     Analyst doesn't write code (that's the Fix Writer's job). It only
     diagnoses. Narrow jobs mean better prompts, clearer outputs, and
     easier debugging when something goes wrong.

TEACHING NOTE — Structured output via JSON in system prompt:
  We ask Claude to produce a specific JSON shape by:
    a) Showing the exact schema in the system prompt
    b) Asking for ONLY the JSON block, no prose around it
    c) Parsing and validating it in Python after

  A more robust approach (which we'll use in later modules) is Anthropic's
  native structured output via `response_format`. For now, JSON-in-prompt
  keeps the concept visible and easy to understand.
"""

import json
import re
import anthropic
from rich.console import Console
from rich.panel import Panel

from config.settings import ANTHROPIC_API_KEY, MODEL
from tools.github import TOOL_SCHEMAS, dispatch
from agents.schemas import CodeAnalysis, FileChange

console = Console()

# The full set of tools — Code Analyst gets everything Issue Reader had,
# plus get_file_at_lines and get_recent_commits for surgical inspection.
ALL_TOOL_SCHEMAS = TOOL_SCHEMAS  # already includes all 6 tools

SYSTEM_PROMPT = """You are the Code Analyst agent for NimbleDev, a multi-agent system that fixes open source bugs.

You will receive a structured analysis from the Issue Reader agent. Your job is to go deeper:
read the actual source files, find the exact lines that need to change, and produce a precise
fix specification that the Fix Writer can implement without any further investigation.

WHAT YOU MUST DO:
1. Read the full content of every file flagged by the Issue Reader
2. Find the exact function, class, or lines where the bug lives
3. Understand the surrounding code well enough to know what a correct fix looks like
4. Check recent commits to understand if this was a regression
5. Look at existing tests to understand what test coverage exists

WHAT YOU MUST PRODUCE:
A single JSON block matching this exact schema — no prose before or after, just the JSON:

```json
{
  "issue_summary": "one sentence describing the bug",
  "root_cause": "the specific technical reason the bug occurs",
  "reproduction_steps": "how to trigger the bug",
  "files_to_change": [
    {
      "path": "relative/path/to/file.py",
      "reason": "why this file needs to change",
      "relevant_lines": "e.g. '42-67' or 'function validate_token lines 89-112'",
      "change_type": "modify",
      "change_description": "exactly what needs to change in plain English"
    }
  ],
  "fix_approach": "plain English description of the overall fix strategy",
  "test_files": ["path/to/test_file.py"],
  "estimated_complexity": "trivial | small | medium | large",
  "confidence": "high | medium | low",
  "confidence_reason": "why you are or aren't confident",
  "risks": "what could go wrong with this fix"
}
```

RULES:
- change_type must be one of: "modify", "create", "delete"
- estimated_complexity must be one of: "trivial", "small", "medium", "large"
- confidence must be one of: "high", "medium", "low"
- relevant_lines should be as specific as possible — line numbers if you can find them
- If you are not confident enough to specify a fix, say so in confidence_reason and set confidence to "low"
- Output ONLY the JSON block. No introduction, no explanation after."""


def _extract_json(text: str) -> str:
    """Pull the JSON object out of the LLM's response, tolerating markdown fences."""
    # Try fenced block first
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    # Fall back to first { ... } block
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    raise ValueError("No JSON object found in agent response")


def run(owner: str, repo: str, issue_number: int, issue_reader_output: str) -> CodeAnalysis:
    """
    Run the Code Analyst agent.

    Args:
        owner: GitHub repo owner
        repo: Repo name
        issue_number: Issue number (for context)
        issue_reader_output: The full text output from the Issue Reader agent

    Returns:
        A CodeAnalysis dataclass — the structured handoff to the Fix Writer
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── Context injection ──────────────────────────────────────────────────────
    # We give the Code Analyst the Issue Reader's work as its starting point.
    # It doesn't re-read the issue from GitHub — it builds on what's already known.
    messages = [
        {
            "role": "user",
            "content": (
                f"Repo: {owner}/{repo} — Issue #{issue_number}\n\n"
                f"The Issue Reader agent has already analyzed this issue. "
                f"Here is its output:\n\n"
                f"{'─' * 60}\n"
                f"{issue_reader_output}\n"
                f"{'─' * 60}\n\n"
                f"Now go deeper. Read the actual source files, find the exact lines "
                f"that need to change, and produce the JSON fix specification."
            ),
        }
    ]

    console.print(Panel(
        f"[bold]Code Analyst Agent[/bold]\n"
        f"Target: [cyan]{owner}/{repo}[/cyan] — Issue [cyan]#{issue_number}[/cyan]\n"
        f"[dim]Building on Issue Reader output...[/dim]",
        border_style="yellow"
    ))

    # ── Agentic loop ───────────────────────────────────────────────────────────
    iteration = 0
    max_iterations = 15  # Code Analyst reads more files so needs more turns

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]── Turn {iteration} ──[/dim]")

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOL_SCHEMAS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract the text and parse the JSON
            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            console.print("\n[dim]Parsing structured output...[/dim]")
            try:
                from pydantic import ValidationError
                json_str = _extract_json(raw_text)
                analysis = CodeAnalysis.model_validate_json(json_str)
                console.print(Panel(
                    f"[green]Analysis complete[/green]\n"
                    f"Root cause: {analysis.root_cause[:120]}\n"
                    f"Files to change: {len(analysis.files_to_change)}\n"
                    f"Confidence: {analysis.confidence} — {analysis.confidence_reason[:80]}",
                    border_style="green"
                ))
                return analysis

            except (ValueError, json.JSONDecodeError) as e:
                console.print(f"[red]Failed to extract JSON from agent output: {e}[/red]")
                console.print(f"[dim]Raw output:\n{raw_text[:500]}[/dim]")
                raise RuntimeError(f"Code Analyst produced invalid output: {e}") from e
            except Exception as e:
                # Pydantic ValidationError — field constraint violated
                console.print(f"[red]Schema validation failed: {e}[/red]")
                console.print(f"[dim]Raw output:\n{raw_text[:500]}[/dim]")
                raise RuntimeError(f"Code Analyst output failed validation: {e}") from e

        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                console.print(f"  [yellow]→ Calling:[/yellow] [bold]{block.name}[/bold]({_fmt_args(block.input)})")
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

    raise RuntimeError("Code Analyst hit iteration limit without producing output.")


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 40:
            v_str = v_str[:40] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)
