# NimbleDev — Multi-Agent SDLC Assistant

A multi-agent AI system that improves two phases of the software development lifecycle: **PR code review** and **open source issue fixing**. Built with Python and the Anthropic SDK (Claude claude-sonnet-4-6).

## Quickstart

This repo is meant to run directly from the checkout. If you already have Python 3.10 installed:

```bash
git clone <repo>
cd nimbledev
./setup.sh
```

If `python3.10` is missing, `setup.sh` stops and tells you how to install it.

After setup:

```bash
# fill in ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_USERNAME
open .env   # or edit it in your editor

# inspect available commands
.venv/bin/python main.py --help

# PR review
.venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745

# issue analysis
.venv/bin/python main.py analyze https://github.com/psf/requests/issues/6730

# full issue-to-PR pipeline
.venv/bin/python main.py fix https://github.com/psf/requests/issues/6730
```

Your GitHub token needs the `repo` scope for reading public repos.

---

## Problem chosen

Two real SDLC pain points, one shared agent platform:

**PR Review** — Code review is slow and inconsistent. Reviewers miss edge cases, forget to check tests, and apply different standards across PRs. An agent-based reviewer delivers structured, repeatable feedback in seconds — covering bugs, security issues, style, and missing test coverage in every review.

**Issue Fix** — Triaging and fixing open source issues requires understanding an unfamiliar codebase quickly. Agents that read issues, map the relevant code, and plan fixes accelerate contributor ramp-up and reduce the time from "bug reported" to "PR opened."

---

## Agent design and workflow

NimbleDev runs two independent pipelines sharing a common tool layer and schema library.

### Pipeline A — PR Review

```
GitHub PR URL
     │
     ▼
┌─────────────────┐
│  Diff Parser    │  Fetches PR metadata, file list, and diff.
│                 │  Produces a structured DiffSummary: what changed,
│                 │  which areas need scrutiny, which context files to read.
└────────┬────────┘
         │ DiffSummary (Pydantic)
         ▼
┌─────────────────┐
│  Review Critic  │  Reads the diff and context files. Evaluates the changes.
│                 │  Produces a structured PRReview: verdict, per-comment
│                 │  severity/category/line-ref, highlights, missing tests.
└────────┬────────┘
         │ PRReview (Pydantic)
         ▼
  Formatted review report (stdout)
```

### Pipeline B — Issue Fix

```
GitHub Issue URL
     │
     ▼
┌─────────────────┐
│  Issue Reader   │  Reads the issue + comments. Explores repo structure.
│                 │  Produces a plain-text analysis: bug summary, likely
│                 │  location, fix hypothesis, files to study.
└────────┬────────┘
         │ text analysis
         ▼
┌─────────────────┐
│  Code Analyst   │  Reads full source files, finds exact lines.
│                 │  Produces a structured CodeAnalysis: root cause,
│                 │  files_to_change with line refs, fix approach, confidence.
└────────┬────────┘
         │ CodeAnalysis (Pydantic)
         ▼
  Fix Writer, Reviewer, PR Agent  ← roadmap (Modules 3-5)
```

### Key design decisions

**Specialised agents over one large agent.** Each agent has a single, well-defined job. The Diff Parser comprehends; the Review Critic evaluates. Mixing these in one agent produces muddy reasoning and harder-to-debug output.

**Pydantic schemas as agent contracts.** Every agent-to-agent handoff uses a validated Pydantic model. If an agent produces `severity: "very critical"` instead of `"critical"`, a `ValidationError` is raised immediately rather than flowing silently downstream.

**Tool subsets per pipeline.** Agents only see the tools relevant to their job (`ISSUE_FIX_TOOLS` vs `PR_REVIEW_TOOLS`). This reduces noise in tool selection and keeps system prompts focused.

**Agentic loop with safety cap.** Every agent runs a `while` loop — ask Claude, execute tools, feed results back — capped at a maximum iteration count to prevent runaway agents.

---

## Setup

```bash
git clone <repo>
cd nimbledev
./setup.sh
```

```bash
# Then edit .env and run:
.venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
.venv/bin/python main.py analyze https://github.com/psf/requests/issues/6730
```

---

## Assumptions and trade-offs

**No UI or auth layer.** CLI only — scope is the agent logic, not the interface.

**GitHub API as the tool layer.** All codebase access goes through the GitHub REST API. No local git clone needed, but rate limits apply and large files get truncated at 8,000 characters.

**JSON-in-prompt for structured output.** The system prompt embeds the exact JSON schema and instructs the agent to produce only that. A more robust approach is Anthropic's native forced tool-use output — saved for a later iteration.

**Sequential pipeline, no parallelism.** Agents run serially. For production, context-file reads could fan out in parallel, cutting latency significantly.

**No retry logic on parse failure.** If an agent produces malformed JSON, the pipeline raises immediately. A production system would re-prompt the agent with the validation error and ask it to self-correct.

---

## What I would improve with more time

- Pydantic cross-field validators (e.g. enforce `overall_verdict = "request_changes"` when any `critical` comment exists)
- Parallel tool calls in the Review Critic to halve latency on context file reads
- Retry loop on parse failure — re-prompt with the validation error rather than crashing
- Complete the issue-fix pipeline end-to-end with Fix Writer, Reviewer, and PR Agent (Modules 3-5)
- Structured logging with trace IDs and per-agent token usage for observability
- RAG layer — embed past reviews into a vector store so agents can reference prior decisions

---

## How I used AI tools

NimbleDev was built iteratively with Claude (Anthropic) as a coding assistant throughout.

**Architecture first** — used Claude to map the two-pipeline design and identify the right agent boundaries before writing any code. Key design question: where does comprehension end and evaluation begin?

**Schema-driven development** — wrote `schemas.py` first (Pydantic models for all handoffs), then built agents around those contracts. Claude helped identify which fields were genuinely needed vs. speculative.

**System prompt iteration** — each agent's system prompt went through multiple drafts. Claude helped identify ambiguities (e.g. the severity guide needed explicit definitions of "major" vs "minor" or agents were inconsistent).

**Honest about the meta** — NimbleDev is a PR reviewer built with the help of an AI assistant. The AI was most valuable for schema design, prompt drafting, and edge case identification. The architectural decisions — agent boundaries, pipeline structure, Pydantic over dataclasses — were made by the developer and stress-tested in conversation.
