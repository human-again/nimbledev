# Module 3: Fix Writer — Writing Code with AI

## What We Built

The **Fix Writer** (`agents/fix_writer.py`) is the third agent in the issue fix pipeline. It receives the `CodeAnalysis` from the Code Analyst, reads each relevant file from GitHub, and writes the corrected full file content.

We also added:
- `FixedFile` and `ProposedFix` schemas to `agents/schemas.py`
- `get_contributing_guide()` tool to `tools/github.py`

## How to Run It

The Fix Writer runs as part of the full pipeline (Module 5 onwards). To test it standalone, you can call it from a Python REPL:

```python
from agents.code_analyst import run as analyze_code
from agents.fix_writer import run as write_fix
from agents.issue_reader import run as read_issue

# First get a CodeAnalysis
issue_text = read_issue("psf", "requests", 6730)
analysis = analyze_code("psf", "requests", 6730, issue_text)

# Then write the fix
fix = write_fix("psf", "requests", 6730, analysis)
print(fix.summary)
for f in fix.files:
    print(f"  {f.path}: {f.explanation}")
```

## Key New Concept: Code Generation Agents

### Why Full File, Not Patch Format?

You might expect the Fix Writer to produce a `diff` (a patch showing only the changed lines). We use full file content instead. Why?

**Patches are brittle.** If the LLM is off by one line, the patch fails to apply. Full file content is unambiguous — you just overwrite the file. Also, the LLM can see surrounding context while writing, reducing the chance of subtle mistakes.

```python
class FixedFile(BaseModel):
    path: str
    original_content: str  # the relevant section before (for review)
    fixed_content: str     # THE FULL FILE — every line
    explanation: str       # why this fixes the bug
```

### The "Minimal Change" Principle

The system prompt enforces: *change only what's necessary*. Over-engineering is the enemy of clean PRs. A minimal, focused change is easier to review, easier to revert, and less likely to introduce regressions.

### Read Before Write

The Fix Writer **must** call `get_file_content` before writing any fix. This prevents hallucination — the LLM cannot invent the current file content from memory. It must read the real thing first.

### Context Window Management

The Fix Writer reads **only** the files in `CodeAnalysis.files_to_change`. Not the whole repo. This is deliberate: the Code Analyst already did the exploration. The Fix Writer builds on that work without re-reading everything.

## Things to Try

1. Run the full fix pipeline on a real issue and inspect `fix.files[0].fixed_content`
2. Compare the token count with and without the `get_contributing_guide()` call
3. Try an issue with 3+ files to change and see how the agent handles context

## What's Next

Module 4 adds the **Reviewer** — a critic agent that evaluates the fix and can send it back for revision. Together they form the critic/generator pattern.
