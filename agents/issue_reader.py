"""
agents/issue_reader.py
----------------------
Reads a GitHub issue and produces structured analysis for the next agent.
"""

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich import print as rprint

from config.settings import ANTHROPIC_API_KEY, MODEL
from tools.github import TOOL_SCHEMAS, dispatch

console = Console()

SYSTEM_PROMPT = """You are the Issue Reader agent for NimbleDev, a multi-agent system that fixes open source bugs.

Your job is to deeply understand a GitHub issue and produce a structured analysis that the next agent (Code Analyst) can use to find and fix the bug.

When given an issue, you should:
1. Read the issue carefully using get_issue
2. Explore the repo structure using get_repo_structure to understand the codebase layout
3. Search for relevant code using search_repo_code — look for the function, class, or error mentioned in the issue
4. Read the most relevant files using get_file_content

Then produce a structured analysis with these sections:
- **Issue Summary**: What is broken, in plain English
- **Reproduction**: How to trigger the bug (from the issue body/comments)
- **Likely Location**: Which files and functions are probably involved
- **Fix Hypothesis**: Your best guess at what the fix involves (don't write code yet)
- **Files to Study**: A prioritized list of files the next agent should read

Be thorough but focused. Don't read every file — only the ones genuinely relevant to this issue."""


def run(owner: str, repo: str, issue_number: int) -> str:
    """
    Run the Issue Reader agent against a specific GitHub issue.

    Args:
        owner: GitHub repo owner, e.g. 'psf'
        repo: Repo name, e.g. 'requests'
        issue_number: The issue number to analyze

    Returns:
        A structured analysis string for the next agent to consume
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Seed the agent with the issue and repository context.
    messages = [
        {
            "role": "user",
            "content": (
                f"Please analyze this GitHub issue and produce a structured report.\n\n"
                f"Repo: {owner}/{repo}\n"
                f"Issue: #{issue_number}\n\n"
                f"Start by reading the issue, then explore the codebase to understand where the bug lives."
            ),
        }
    ]

    console.print(Panel(
        f"[bold]Issue Reader Agent[/bold]\n"
        f"Target: [cyan]{owner}/{repo}[/cyan] — Issue [cyan]#{issue_number}[/cyan]",
        border_style="blue"
    ))

    iteration = 0
    max_iterations = 10  # Safety cap

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]── Turn {iteration} ──[/dim]")

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    console.print(Panel(block.text, title="[green]Analysis Complete[/green]", border_style="green"))
                    return block.text
            return "(Agent finished but produced no text output)"

        elif response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                console.print(f"  [yellow]→ Calling:[/yellow] [bold]{block.name}[/bold]({_fmt_args(block.input)})")

                result = dispatch(block.name, block.input)

                # Show a preview of the result
                preview = result[:200] + "..." if len(result) > 200 else result
                console.print(f"  [dim]{preview}[/dim]")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            # Feed tool results back into the conversation
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            console.print(f"[red]Unexpected stop_reason: {response.stop_reason}[/red]")
            break

    return "Error: Agent hit the iteration limit without producing an answer."


def _fmt_args(args: dict) -> str:
    """Format tool arguments for display, truncating long values."""
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 40:
            v_str = v_str[:40] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)
