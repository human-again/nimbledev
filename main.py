"""
main.py
-------
NimbleDev CLI — two pipelines, one command interface.

PIPELINE A: Issue Fix
  read-issue <url>    Issue Reader only (Module 1)
  analyze <url>       Issue Reader + Code Analyst (Module 2)
  fix <url>           Full pipeline: Reader → Analyst → Fix Writer → Reviewer → PR

PIPELINE B: PR Review
  review-pr <url>     Diff Parser + Review Critic

OTHER
  serve-mcp           Start the NimbleDev MCP server (Module 8)

Examples:
  .venv/bin/python main.py read-issue https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py analyze https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py fix https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
  .venv/bin/python main.py serve-mcp
"""

import sys
import re
from rich.console import Console
from rich.panel import Panel

console = Console()


# ── URL parsers ────────────────────────────────────────────────────────────────

def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub issue URL → (owner, repo, issue_number)."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        console.print(
            f"[red]Error:[/red] Not a valid GitHub issue URL: {url}\n"
            f"Expected: https://github.com/OWNER/REPO/issues/NUMBER"
        )
        sys.exit(1)
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL → (owner, repo, pr_number)."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        console.print(
            f"[red]Error:[/red] Not a valid GitHub PR URL: {url}\n"
            f"Expected: https://github.com/OWNER/REPO/pull/NUMBER"
        )
        sys.exit(1)
    owner, repo, number = match.groups()
    return owner, repo, int(number)


# ── Pipeline A: Issue Fix ──────────────────────────────────────────────────────

def cmd_read_issue(url: str) -> str:
    """Module 1 — Issue Reader only."""
    owner, repo, issue_number = parse_issue_url(url)
    from agents.issue_reader import run
    return run(owner, repo, issue_number)


def cmd_analyze(url: str) -> None:
    """
    Modules 1 + 2 — Issue Reader → Code Analyst.

    Demonstrates sequential agent chaining: the output of the first agent
    becomes the input of the second.
    """
    owner, repo, issue_number = parse_issue_url(url)

    console.print("\n[bold cyan]── Stage 1: Issue Reader ──[/bold cyan]")
    from agents.issue_reader import run as read_issue
    issue_analysis = read_issue(owner, repo, issue_number)

    console.print("\n[bold cyan]── Stage 2: Code Analyst ──[/bold cyan]")
    from agents.code_analyst import run as analyze_code
    code_analysis = analyze_code(owner, repo, issue_number, issue_analysis)

    console.print("\n[bold]Structured handoff (Fix Writer input):[/bold]")
    console.print(code_analysis.to_prompt())


def cmd_fix(url: str) -> None:
    """
    Run the full issue-fix pipeline:
    Issue Reader → Code Analyst → Fix Writer → Reviewer loop → PR Agent.
    """
    owner, repo, issue_number = parse_issue_url(url)

    # ── Observability setup ────────────────────────────────────────────────────
    from observability.tracker import RunTracker
    from observability.logger import new_trace_id
    trace_id = new_trace_id()
    tracker = RunTracker(trace_id=trace_id, command="fix")

    console.print(Panel(
        f"[bold]NimbleDev Full Fix Pipeline[/bold]\n"
        f"Repo: [cyan]{owner}/{repo}[/cyan] — Issue [cyan]#{issue_number}[/cyan]\n"
        f"Trace ID: [dim]{trace_id}[/dim]",
        border_style="cyan"
    ))

    # ── Memory: retrieve past similar analyses ─────────────────────────────────
    from memory.store import MemoryStore
    analysis_memory = MemoryStore("code_analyses")
    query = f"fix issue {issue_number} in {owner}/{repo}"
    past_analyses = analysis_memory.retrieve(query, n_results=3)
    memory_context = analysis_memory.format_for_prompt(past_analyses) if past_analyses else ""

    # ── Stage 1: Issue Reader ──────────────────────────────────────────────────
    console.print("\n[bold cyan]── Stage 1: Issue Reader ──[/bold cyan]")
    stats = tracker.start_agent("issue_reader")
    from agents.issue_reader import run as read_issue
    issue_analysis = read_issue(owner, repo, issue_number)
    tracker.finish_agent(stats)

    # ── Stage 2: Code Analyst ──────────────────────────────────────────────────
    console.print("\n[bold cyan]── Stage 2: Code Analyst ──[/bold cyan]")
    stats = tracker.start_agent("code_analyst")
    from agents.code_analyst import run as analyze_code
    # Inject past memory context if available
    analysis_input = issue_analysis
    if memory_context:
        analysis_input = f"{memory_context}\n\n{'─'*60}\n\n{issue_analysis}"
    code_analysis = analyze_code(owner, repo, issue_number, analysis_input)
    tracker.finish_agent(stats)

    # Store this analysis in memory for future runs
    memory_text = (
        f"repo: {owner}/{repo}, issue: #{issue_number}, "
        f"root_cause: {code_analysis.root_cause}, "
        f"fix_approach: {code_analysis.fix_approach}"
    )
    analysis_memory.store(
        id=f"{owner}/{repo}#{issue_number}",
        text=memory_text,
        metadata={
            "repo": f"{owner}/{repo}",
            "issue_number": issue_number,
            "root_cause": code_analysis.root_cause[:200],
            "fix_approach": code_analysis.fix_approach[:200],
            "confidence": code_analysis.confidence,
        }
    )

    # ── Stage 3 + 4: Fix Writer → Reviewer feedback loop ──────────────────────
    console.print("\n[bold cyan]── Stage 3: Fix Writer → Reviewer Loop ──[/bold cyan]")
    from agents.fix_writer import run as write_fix
    from agents.reviewer import run as review_fix

    fix = None
    review = None
    prior_fix = None
    objections = None

    max_attempts = 3
    for attempt in range(max_attempts):
        console.print(f"\n[dim]Fix attempt {attempt + 1}/{max_attempts}[/dim]")

        stats = tracker.start_agent(f"fix_writer_attempt_{attempt + 1}")
        fix = write_fix(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            code_analysis=code_analysis,
            prior_fix=prior_fix,
            objections=objections,
        )
        tracker.finish_agent(stats)

        stats = tracker.start_agent(f"reviewer_attempt_{attempt + 1}")
        review = review_fix(code_analysis, fix)
        tracker.finish_agent(stats)

        if review.verdict == "approved":
            console.print(f"\n[green]Fix approved on attempt {attempt + 1}[/green]")
            break

        console.print(f"\n[yellow]Needs revision — {len(review.objections)} objection(s)[/yellow]")
        prior_fix = fix
        objections = review.objections
    else:
        console.print("\n[red]Max attempts reached — using last fix as-is[/red]")

    # ── Stage 5: PR Agent ──────────────────────────────────────────────────────
    console.print("\n[bold cyan]── Stage 5: PR Agent ──[/bold cyan]")
    stats = tracker.start_agent("pr_agent")
    from agents.pr_agent import run as open_pr
    pr_url = open_pr(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        proposed_fix=fix,
        code_analysis=code_analysis,
    )
    tracker.finish_agent(stats)

    # ── Summary ────────────────────────────────────────────────────────────────
    tracker.print_summary()
    tracker.save_log()

    if pr_url:
        console.print(f"\n[bold green]Done![/bold green] PR: [cyan]{pr_url}[/cyan]")


# ── Pipeline B: PR Review ──────────────────────────────────────────────────────

def cmd_review_pr(url: str) -> None:
    """
    PR Review pipeline — Diff Parser → Review Critic.

    Two agents with distinct roles:
      Diff Parser:   comprehension — what changed and where to look
      Review Critic: evaluation   — is the change good, what needs fixing
    """
    owner, repo, pr_number = parse_pr_url(url)

    console.print("\n[bold cyan]── Stage 1: Diff Parser ──[/bold cyan]")
    from agents.diff_parser import run as parse_diff
    diff_summary = parse_diff(owner, repo, pr_number)

    console.print("\n[bold cyan]── Stage 2: Review Critic ──[/bold cyan]")
    from agents.review_critic import run as critique
    review = critique(owner, repo, pr_number, diff_summary)

    console.print("\n")
    console.print(review.to_display())


def cmd_serve_mcp() -> None:
    """
    Start the GitHub MCP server over stdio.
    """
    try:
        from mcp_server.github_mcp import mcp
        console.print("[bold]Starting NimbleDev GitHub MCP Server...[/bold]")
        console.print("[dim]Connect with: npx @modelcontextprotocol/inspector .venv/bin/python main.py serve-mcp[/dim]")
        mcp.run()
    except ImportError as e:
        console.print(f"[red]Error:[/red] MCP not installed. Run ./setup.sh to install dependencies.")
        console.print(f"[dim]{e}[/dim]")
        sys.exit(1)


# ── CLI ────────────────────────────────────────────────────────────────────────

HELP = """
[bold]NimbleDev[/bold] — Multi-agent SDLC assistant

[bold]Pipeline A — Issue Fix:[/bold]
  read-issue <url>    Analyse a GitHub issue (Module 1)
  analyze <url>       Issue Reader + Code Analyst (Module 2)
  fix <url>           Full pipeline: Reader → Analyst → Fix Writer → Reviewer → PR (Modules 3-5)

[bold]Pipeline B — PR Review:[/bold]
  review-pr <url>     Full PR review: Diff Parser + Review Critic

[bold]MCP Server (Module 8):[/bold]
  serve-mcp           Start the GitHub MCP server

[bold]Examples:[/bold]
  .venv/bin/python main.py read-issue https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py analyze    https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py fix        https://github.com/psf/requests/issues/6730
  .venv/bin/python main.py review-pr  https://github.com/psf/requests/pull/6745
  .venv/bin/python main.py serve-mcp
"""

COMMANDS = {
    "read-issue": (cmd_read_issue, "issue URL"),
    "analyze":    (cmd_analyze,    "issue URL"),
    "fix":        (cmd_fix,        "issue URL"),
    "review-pr":  (cmd_review_pr,  "PR URL"),
    "serve-mcp":  (cmd_serve_mcp,  None),
}


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        console.print(HELP)
        return

    command = args[0]

    if command not in COMMANDS:
        console.print(f"[red]Error:[/red] Unknown command '{command}'. Run with --help for available commands.")
        sys.exit(1)

    fn, url_type = COMMANDS[command]

    # Commands that take no URL argument
    if url_type is None:
        fn()
        return

    if len(args) < 2:
        console.print(f"[red]Error:[/red] Please provide a {url_type}.")
        sys.exit(1)

    fn(args[1])


if __name__ == "__main__":
    main()
