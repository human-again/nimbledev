# NimbleDev PR Review Assistant

NimbleDev is a small agentic AI tool for the pull request review phase of the SDLC. Given a GitHub PR URL, it fetches PR metadata, changed files, diffs, and selected context files, then returns a structured review with a verdict, actionable comments, positive highlights, and missing-test suggestions.

## Quickstart

Requirements: Python 3.10, an Anthropic API key, and a GitHub token with repo read access.

```bash
git clone <repo>
cd nimbledev
./setup.sh
```

If `python3.10` is not installed, `setup.sh` stops with install guidance. After setup, fill in `.env`:

```bash
ANTHROPIC_API_KEY=...
GITHUB_TOKEN=...
```

Run a review:

```bash
.venv/bin/python main.py --help
.venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
```

## Problem Chosen

PR review is a high-leverage but inconsistent SDLC step. Reviewers often lack time to inspect edge cases, test coverage, security concerns, and design impact with the same depth on every change. NimbleDev applies a repeatable agent workflow to produce a first-pass review that helps human reviewers focus faster.

## Agent Design

The workflow uses two specialized agents with a small shared GitHub tool layer and Pydantic schemas as contracts.

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

The split keeps comprehension separate from judgment. The Diff Parser answers "what changed and where should we look?" The Review Critic answers "is this safe, clear, tested, and ready to merge?" Each handoff is validated with Pydantic so malformed agent output fails early instead of silently contaminating the next stage.

## Assumptions and Trade-offs

This is intentionally CLI-only: no UI, authentication flow, database, or deployment. GitHub access goes through the REST API rather than a local clone, which keeps setup simple but means API rate limits and truncated large files matter. Agent output is requested as JSON and validated locally; a production version should add retry-on-validation-error and stronger structured-output controls. The pipeline is sequential for clarity, though context file reads could be parallelized later.

## What I Would Improve

With more time, I would add parse-failure retries, deterministic fixture-based integration tests, stricter cross-field validators such as requiring `request_changes` for critical findings, parallel context retrieval, trace logging with token/cost metrics, and repository-specific review memory so future reviews can reuse past project conventions.

## How I Used AI Tools

I used AI coding assistance to iterate on the agent boundaries, schemas, prompts, setup flow, and test strategy. The most useful prompts were architectural: deciding where diff comprehension should end, what the critic should own, and which fields were necessary in each schema. I then used the assistant to stress-test scope, remove tutorial-style clutter, and keep the final branch focused on one shippable SDLC use case.
