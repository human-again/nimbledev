"""
main.py
-------
NimbleDev CLI — PR review pipeline.

PIPELINE: PR Review
  review-pr <url>     Diff Parser + Review Critic

Examples:
  .venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
"""

import sys
import re
from rich.console import Console

console = Console()


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL into owner, repo, and PR number."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        console.print(
            f"[red]Error:[/red] Not a valid GitHub PR URL: {url}\n"
            f"Expected: https://github.com/OWNER/REPO/pull/NUMBER"
        )
        sys.exit(1)
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def cmd_review_pr(url: str) -> None:
    """
    PR Review pipeline: Diff Parser, then Review Critic.

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

HELP = """
[bold]NimbleDev[/bold] — PR review assistant

[bold]Available command:[/bold]
  review-pr <url>     Full PR review: Diff Parser + Review Critic

[bold]Examples:[/bold]
  .venv/bin/python main.py review-pr  https://github.com/psf/requests/pull/6745
"""

COMMANDS = {
    "review-pr":  (cmd_review_pr,  "PR URL"),
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
