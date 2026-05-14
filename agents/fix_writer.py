"""
agents/fix_writer.py
--------------------
Module 3: The Fix Writer Agent

Receives CodeAnalysis from the Code Analyst and writes the actual corrected
code — full file content, not patches — for every file that needs to change.

TEACHING NOTE — Code generation agents:

  The Fix Writer is a *code generation* agent: its output is not prose or
  a structured analysis, but working source code. A few design choices matter:

  1. WHY FULL FILE, NOT PATCH FORMAT?
     Patches (unified diffs) are brittle. If the LLM is off by one line,
     the patch fails to apply. Full file content is unambiguous — you just
     overwrite the file. It also means the agent can see the surrounding
     context while writing, reducing the chance of subtle breakage.
     Trade-off: more tokens. Solution: only read files listed in files_to_change.

  2. CONTEXT WINDOW MANAGEMENT
     The Fix Writer reads only the files it needs to change (from CodeAnalysis).
     It does NOT re-read the whole repo. This keeps the context focused and
     avoids hitting token limits. The Code Analyst already did the exploration;
     the Fix Writer builds on that work.

  3. THE "MINIMAL CHANGE" PRINCIPLE
     Agents (like junior developers) tend to over-engineer. The system prompt
     explicitly instructs: change only what's necessary, preserve existing
     style, don't refactor unrelated code. This produces cleaner PRs and
     makes review easier.

  4. READ BEFORE WRITE
     The agent is required to call get_file_content before writing any fix.
     This prevents it from "hallucinating" the current file content and
     ensures fixed_content is a valid modification of the actual file.

  5. STYLE MATCHING
     The agent fetches CONTRIBUTING.md first so it knows the project's
     conventions (line length, docstrings, test framework, etc.).
"""

import json
import re
import anthropic
from rich.console import Console
from rich.panel import Panel

from config.settings import ANTHROPIC_API_KEY, MODEL
from tools.github import FIX_WRITER_TOOLS, dispatch
from agents.schemas import CodeAnalysis, ProposedFix, FixedFile, Objection

console = Console()

SYSTEM_PROMPT = """You are the Fix Writer agent for NimbleDev, a multi-agent system that fixes open source bugs.

You will receive a structured CodeAnalysis from the Code Analyst. Your job is to write the actual fix.

MANDATORY WORKFLOW:
1. Fetch CONTRIBUTING.md first (get_contributing_guide) to understand project conventions
2. For EACH file in files_to_change: call get_file_content to read the current content
3. Write the corrected full file content — NOT a patch, NOT a diff, the COMPLETE file
4. Output a single JSON block matching the schema below

THE "MINIMAL CHANGE" RULE:
- Change only the lines that fix the bug
- Do not refactor unrelated code
- Do not change naming conventions or formatting outside the changed section
- Match the existing indentation, quote style, and import ordering exactly
- If you're unsure about a style choice, look at the surrounding code and copy it

WHAT YOU MUST PRODUCE:
A single JSON block — no prose before or after, just the JSON:

```json
{
  "summary": "one sentence: what the fix does",
  "files": [
    {
      "path": "relative/path/to/file.py",
      "original_content": "the relevant section before the fix (a few lines showing what changed)",
      "fixed_content": "THE COMPLETE UPDATED FILE CONTENT — every line, not just the changed part",
      "explanation": "why this specific change fixes the bug"
    }
  ],
  "test_suggestions": [
    "Test that X when Y happens",
    "Test that Z edge case is handled"
  ],
  "confidence": "high | medium | low",
  "caveats": "known limitations or edge cases this fix doesn't handle"
}
```

RULES:
- fixed_content must be the FULL file content, not a snippet
- confidence must be: "high", "medium", or "low"
- original_content should show the relevant section (5-20 lines) before your change
- If a file doesn't need to change, don't include it in files[]
- Output ONLY the JSON block. No introduction, no explanation after."""


def _extract_json(text: str) -> str:
    """Pull the JSON object out of the LLM's response, tolerating markdown fences."""
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


def run(
    owner: str,
    repo: str,
    issue_number: int,
    code_analysis: CodeAnalysis,
    prior_fix: "ProposedFix | None" = None,
    objections: "list[Objection] | None" = None,
) -> ProposedFix:
    """
    Run the Fix Writer agent.

    Args:
        owner:         GitHub repo owner
        repo:          Repo name
        issue_number:  Issue number (for context)
        code_analysis: Structured output from the Code Analyst
        prior_fix:     If this is a retry, the previous ProposedFix
        objections:    Reviewer's objections from the previous attempt

    Returns:
        ProposedFix with full file content for each changed file
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build the initial user message
    user_content = (
        f"Repo: {owner}/{repo} — Issue #{issue_number}\n\n"
        f"{code_analysis.to_prompt()}\n\n"
        f"Now write the fix. Read each file first, then produce the JSON."
    )

    # If this is a retry, inject reviewer feedback
    if prior_fix and objections:
        objections_text = "\n".join(
            f"  [{o.file_path}] {o.issue} → {o.suggestion}"
            for o in objections
        )
        user_content += (
            f"\n\n{'─' * 60}\n"
            f"PREVIOUS ATTEMPT REJECTED BY REVIEWER\n"
            f"{'─' * 60}\n"
            f"Previous fix summary: {prior_fix.summary}\n\n"
            f"Objections to address:\n{objections_text}\n\n"
            f"Please address ALL objections in your new fix."
        )

    messages = [{"role": "user", "content": user_content}]

    attempt_label = "Retry" if prior_fix else "Initial attempt"
    console.print(Panel(
        f"[bold]Fix Writer Agent[/bold]\n"
        f"Target: [cyan]{owner}/{repo}[/cyan] — Issue [cyan]#{issue_number}[/cyan]\n"
        f"Files to fix: [cyan]{len(code_analysis.files_to_change)}[/cyan] — "
        f"[dim]{attempt_label}[/dim]",
        border_style="yellow"
    ))

    iteration = 0
    max_iterations = 15

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]── Turn {iteration} ──[/dim]")

        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,  # larger budget — full file content is token-heavy
            system=SYSTEM_PROMPT,
            tools=FIX_WRITER_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            console.print("\n[dim]Parsing fix output...[/dim]")
            try:
                json_str = _extract_json(raw_text)
                fix = ProposedFix.model_validate_json(json_str)
                console.print(Panel(
                    f"[green]Fix written[/green]\n"
                    f"Summary: {fix.summary[:100]}\n"
                    f"Files changed: {len(fix.files)}\n"
                    f"Confidence: {fix.confidence}",
                    border_style="green"
                ))
                return fix

            except (ValueError, json.JSONDecodeError) as e:
                console.print(f"[red]Failed to extract JSON: {e}[/red]")
                console.print(f"[dim]Raw output:\n{raw_text[:500]}[/dim]")
                raise RuntimeError(f"Fix Writer produced invalid output: {e}") from e
            except Exception as e:
                console.print(f"[red]Schema validation failed: {e}[/red]")
                raise RuntimeError(f"Fix Writer output failed validation: {e}") from e

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

    raise RuntimeError("Fix Writer hit iteration limit without producing output.")
