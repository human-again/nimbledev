# Module 4: Reviewer + Feedback Loop — The Critic/Generator Pattern

## What We Built

The **Reviewer** (`agents/reviewer.py`) evaluates a `ProposedFix` against the original `CodeAnalysis` and returns a `ReviewDecision` — either `"approved"` or `"needs_revision"` with specific `Objection`s.

New schemas in `agents/schemas.py`:
- `Objection` — a specific issue with a fix (file_path + issue + suggestion)
- `ReviewDecision` — verdict + objections list

The feedback loop in `main.py`'s `cmd_fix()`:
```python
fix = write_fix(...)
for attempt in range(3):
    review = review_fix(code_analysis, fix)
    if review.verdict == "approved":
        break
    fix = write_fix(..., prior_fix=fix, objections=review.objections)
```

## How to Run It

```bash
uv run main.py fix https://github.com/psf/requests/issues/6730
```

This runs the full pipeline: Reader → Analyst → Fix Writer → Reviewer loop.

## Key New Concept: The Critic/Generator Pattern

### Why Two Agents Beat One

A single agent asked to "write a fix and then review it" will rationalise its own choices. It wrote the code; it's mentally committed to it being correct.

Two separate agents — one generating, one critiquing — produce dramatically better results:

- **Generator (Fix Writer):** creative mode, commits to a complete solution
- **Critic (Reviewer):** sceptical mode, looks for edge cases and errors

This mirrors how good software teams work: the author doesn't merge their own PR.

### Cyclic vs Linear Pipelines

Most agent tutorials show linear pipelines: `A → B → C → done`.

Real-world systems often need cyclic pipelines:
```
Fix Writer → Reviewer → Fix Writer → Reviewer → done
```

The key design decisions:

**1. Stopping conditions:** What terminates the loop?
- Happy path: Reviewer says `"approved"`
- Guard: max 3 attempts (prevents infinite loops)

**2. Feedback quality:** Vague feedback is useless. Each `Objection` is concrete:
```python
class Objection(BaseModel):
    file_path: str   # which file
    issue: str       # what's wrong
    suggestion: str  # how to fix it
```

**3. Context carry-over:** The Fix Writer on retry sees both the original `CodeAnalysis` AND the previous `ProposedFix` AND the objections. It can course-correct rather than repeat the same mistake.

### Why the Reviewer Has No Tools

The Reviewer only reads what it was given. No tool calls. No browsing the repo.

**Rule of thumb:** Only give an agent tools when the task requires information it cannot receive through its inputs. The Reviewer evaluates what's handed to it — all the information it needs is in `CodeAnalysis` + `ProposedFix`.

## Things to Try

1. Introduce a deliberate bug in the Fix Writer's output and watch the Reviewer catch it
2. Lower `max_attempts` to 1 and see how often the first attempt gets approved
3. Add a fourth objection category (e.g. "performance") to `Objection`

## What's Next

Module 5: the **PR Agent** — a deterministic sequence that forks the repo, creates a branch, pushes the fixed files, and opens a real pull request.
