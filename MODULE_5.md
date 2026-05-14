# Module 5: PR Agent — Deterministic Code vs Agentic Loops

## What We Built

The **PR Agent** (`agents/pr_agent.py`) takes an approved `ProposedFix` and opens a real GitHub pull request through a deterministic sequence of API calls.

New tool functions in `tools/github.py`:
- `fork_repo()` — fork upstream repo to GITHUB_USERNAME
- `create_branch()` — create a feature branch on the fork
- `get_file_sha()` — get current blob SHA (required by GitHub's update API)
- `push_file()` — create or update a file on a branch
- `open_pull_request()` — open the PR from fork to upstream
- `get_default_branch_sha()` — get the HEAD SHA to base new branches on

## How to Run It

The PR Agent runs as the final step of `uv run main.py fix <url>`.

To skip the PR submission (dry run):
```python
from agents.pr_agent import run as open_pr
pr_url = open_pr(owner, repo, issue_number, fix, analysis, dry_run=True)
```

## Key New Concept: When NOT to Use an Agent

### The Fork-Based PR Flow

Open source contributions follow a specific pattern:
1. Fork the upstream repo to your account (so you can push to it)
2. Create a feature branch on **your fork**
3. Push commits to your branch
4. Open a PR from `your_fork:branch` → `upstream:main`

```
upstream: psf/requests
    ↓ fork
your fork: your_username/requests
    ↓ create branch
    fix/issue-6730-missing-timeout-in-session
    ↓ push files
    ↓ open PR
PR: psf/requests ← your_username:fix/issue-6730-missing-timeout-in-session
```

### Why This Is Deterministic Code, Not an Agent

The PR Agent is **not** an agentic loop. It's a fixed sequence:

```
fork → get_sha → create_branch → push_files → open_pr
```

**Use an agent when:** the task requires exploration, reasoning, or dynamic decisions based on intermediate results.

**Use deterministic code when:** the steps are fixed and the only question is "did this API call succeed?"

The PR Agent knows exactly what to do — there's no decision to make about *what* to do next. An agent loop would add cost, latency, and unpredictability for no benefit.

### Human-in-the-Loop Checkpoints

Before touching anything, the agent prints the full plan and asks for confirmation:

```
PR Plan:
  Step 1: Fork psf/requests → your_username/requests
  Step 2: Create branch fix/issue-6730-slug
  Step 3: Push src/requests/auth.py
  Step 4: Open PR: psf/requests ← your_username:fix/issue-6730-slug

Type "yes" to continue, or anything else to cancel:
```

This is cheap to implement and invaluable when something looks wrong.

### Branch Naming Convention

We use: `fix/issue-{number}-{slug}`
- `fix/` signals a bugfix branch (vs `feat/`, `docs/`, `chore/`)
- `issue-{number}` links the branch to the GitHub issue
- `{slug}` is a short human-readable description

This makes branches self-documenting in the GitHub UI.

## Things to Try

1. Run with `dry_run=True` and inspect the plan output
2. Change the PR body template in `_build_pr_body()` to add your own sections
3. Modify the branch naming to include the date

## What's Next

Module 6: **Observability** — structured logging, token tracking, and run summaries across the full multi-agent pipeline.
