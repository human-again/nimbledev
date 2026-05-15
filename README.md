# NimbleDev PR Review Assistant

NimbleDev is a small agentic AI tool for the pull request review phase of the SDLC. Given a GitHub PR URL, it fetches PR metadata, changed files, diffs, and selected context files, then returns a structured review with a verdict, actionable comments, positive highlights, and missing-test suggestions.


## Quickstart

Requirements: Python 3.10, an Anthropic API key, and a GitHub token with repo read access. `setup.sh` uses `pip` inside `.venv`; `uv.lock` is included for developers who prefer `uv`-based reproducible installs.

```bash
git clone <repo>
cd nimbledev
./setup.sh
```

If `python3.10` is not installed, `setup.sh` stops with install guidance. After setup, fill in `.env`:

```bash
LLM_PROVIDER=anthropic
MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=...
GITHUB_TOKEN=...
```

Run a review:

```bash
.venv/bin/python main.py --help
.venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
```

Run tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Problem Chosen

PR review is a high-leverage but inconsistent SDLC step. Reviewers often lack time to inspect edge cases, test coverage, security concerns, and design impact with the same depth on every change. NimbleDev applies a repeatable agent workflow to produce a first-pass review that helps human reviewers focus faster.

## Agent Design

The workflow uses two specialized agents with a small shared GitHub tool layer, a local model-provider adapter, and Pydantic schemas as contracts. Each agent receives only the tools it needs: the Diff Parser can fetch PR metadata, changed files, and the diff; the Review Critic can fetch the diff and requested context files.

```text
GitHub PR URL
  -> Diff Parser
     Fetches metadata, changed files, diff, and useful context.
     Produces DiffSummary.
  -> Review Critic
     Evaluates bugs, security, performance, design, style, and tests.
     Produces PRReview.
  -> Formatted CLI report
```

The split keeps comprehension separate from judgment. The Diff Parser answers "what changed and where should we look?" The Review Critic answers "is this safe, clear, tested, and ready to merge?" Each handoff is validated with Pydantic so malformed agent output gets one validation-feedback retry before failing explicitly. That corrective retry is JSON-only: tools are disabled so the model cannot drift back into more context fetching while repairing its structured output.

The final review schema also enforces the severity/verdict invariant in code: any `critical` or `major` comment requires `overall_verdict` to be `request_changes`. This keeps the local schema contract aligned with the prompt instructions.

The two agents do not have equal autonomy. The Diff Parser is intentionally close to a constrained tool workflow: fetch metadata, files, and diff, then summarize. The Critic has the more agentic part of the system because it decides which listed context files to read, when it has enough evidence, and how to weigh findings into a verdict.

## Model Provider Boundary

The current implementation ships only the Anthropic provider, but the agents do not import Anthropic directly. They call a local `LLMClient` adapter created from `LLM_PROVIDER`, so provider-specific SDK details are isolated in one place. `MODEL` is the preferred model-name setting; `ANTHROPIC_MODEL` remains supported for backwards compatibility.

This reduces structural vendor lock-in, but does not eliminate provider lock-in completely. A second provider would still need its own adapter plus contract tests for tool-use blocks, stop reasons, token usage, JSON reliability, and prompt behavior.

## Assumptions and Trade-offs

This is intentionally CLI-only: no UI, authentication flow, database, or deployment. GitHub access goes through the REST API rather than a local clone, which keeps setup simple but means API rate limits and truncated large files matter. Diff and file-content tools return structured truncation metadata (`content`, `truncated`, `total_chars`) so the agents can account for partial context. Agent output is requested as JSON, validated locally, and retried once with validation feedback.

## What I Would Improve

With more time, I would add a fixture-based eval suite for review quality: canned PR diffs, mocked tool responses, and expected behavioral assertions such as catching seeded bugs, choosing the right verdict, avoiding unsupported findings, and noting truncation limits. I would score schema validity, issue detection, severity/verdict correctness, tool-use discipline, and false-positive rate rather than exact review wording. I would also add parallel context retrieval, richer trace logging with cost estimates, and repository-specific review memory so future reviews can reuse past project conventions.

## Contributing

Contributions are welcome, including bug fixes, test improvements, eval additions, and provider-adapter follow-ups.

Before opening a PR:
1. Read [CONTRIBUTING.md](./CONTRIBUTING.md).
2. Run `.venv/bin/python -m unittest discover -s tests -v`.
3. Keep changes focused and include tests for behavior changes.

## PRs Welcome

PRs are actively welcome. If you want to contribute but are unsure where to start, open an issue with:
1. The problem you want to solve.
2. The proposed approach.
3. Any tradeoffs or open questions.

## How I Used AI Tools

I used AI coding assistance to iterate on the agent boundaries, schemas, prompts, setup flow, and test strategy. The most useful prompts were architectural: deciding where diff comprehension should end, what the critic should own, and which fields were necessary in each schema. I then used the assistant to stress-test scope and keep the final branch focused on one shippable SDLC use case.
