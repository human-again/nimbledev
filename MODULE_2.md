# Module 2: Agent-to-Agent Handoffs — The Code Analyst

Module 1 gave you one agent that understands a bug. Module 2 adds a second agent that goes deeper — reading actual source files, finding exact lines, and producing a precise specification ready for a code writer.

This is where multi-agent systems start to make sense: each agent is narrow and excellent at one thing, and they chain together by passing structured data.

---

## What we built

```
nimbledev/
├── agents/
│   ├── schemas.py          ← NEW: shared data contracts between agents
│   └── code_analyst.py     ← NEW: the Code Analyst agent
├── tools/
│   └── github.py           ← UPDATED: two new tools added
└── main.py                 ← UPDATED: new `analyze` command
```

---

## Run it

```bash
# Module 1 only (unchanged)
uv run main.py read-issue https://github.com/psf/requests/issues/6730

# Module 1 + 2 in sequence
uv run main.py analyze https://github.com/psf/requests/issues/6730
```

You'll see both agents run back-to-back. The Issue Reader's output is printed, then the Code Analyst picks it up and goes deeper. At the end you'll see the structured `CodeAnalysis` JSON that the Fix Writer will consume in Module 3.

---

## The three new concepts

### 1. Structured output — the agent produces typed data, not prose

In Module 1 the Issue Reader returned plain text. That's fine for a human to read, but fragile for another agent to parse. In Module 2, the Code Analyst is required to produce a specific JSON object:

```python
@dataclass
class CodeAnalysis:
    issue_summary: str
    root_cause: str
    files_to_change: list[FileChange]
    fix_approach: str
    confidence: str       # "high" | "medium" | "low"
    ...
```

We enforce this by:
- Embedding the exact JSON schema in the system prompt
- Telling the agent to produce *only* the JSON, no prose
- Parsing and validating the response in Python

If the agent drifts from the schema, `from_json()` raises an exception immediately — which is exactly what you want. Silent data corruption in agent pipelines is much harder to debug than a loud parse error.

### 2. Context injection — agents build on each other's work

The Code Analyst's first message is the Issue Reader's complete output, injected verbatim:

```python
messages = [
    {
        "role": "user",
        "content": (
            f"The Issue Reader agent has already analyzed this issue.\n"
            f"Here is its output:\n\n{issue_reader_output}\n\n"
            f"Now go deeper..."
        ),
    }
]
```

This is the core pattern for chaining agents: **the output of agent N becomes the context of agent N+1**. The Code Analyst doesn't re-read the issue or re-explore the repo from scratch — it inherits all of the Issue Reader's findings and focuses its energy on the deeper diagnostic work.

This matters a lot for efficiency. Each agent call costs tokens and time. You want each agent to add *new* knowledge, not re-derive what's already known.

### 3. Agent specialisation — narrow jobs, better outputs

Why two agents instead of one that does everything?

One big agent told to "understand the issue AND find the exact lines AND plan the fix AND review it" will do all four things poorly. The system prompt becomes incoherent, the output tries to be everything at once, and there's no clean place to add a human review step.

Two narrow agents, each with a tight job description, consistently outperform one generalist. The prompts are cleaner, the outputs are more reliable, and you can independently improve, test, or replace either agent without touching the other.

This is the fundamental design principle of multi-agent systems: **decompose the problem, specialise the agents**.

---

## New tools

Two tools were added to `tools/github.py` for surgical inspection:

| Tool | What it does |
|---|---|
| `get_file_at_lines` | Read a specific line range with line numbers — e.g. lines 42–67 |
| `get_recent_commits` | Get recent commit history for a file — useful for spotting regressions |

The Code Analyst uses these after the Issue Reader has already identified the relevant files. Rather than loading entire files again, it zooms in on specific functions or sections. This is important context management: the more precisely you can load only what's relevant, the more tokens you have for reasoning.

---

## The handoff format

After both agents run, `code_analysis.to_prompt()` produces the handoff the Fix Writer will receive:

```
## Code analysis (from Code Analyst agent)

**Issue:** requests.get() raises UnicodeDecodeError on binary responses
**Root cause:** ...
**Complexity:** small | **Confidence:** high (stack trace points directly to line 312)

**Files to change:**
  - requests/models.py (modify): update decode logic to handle binary content-types

**Fix approach:** ...

<full_analysis>
{ ... full JSON ... }
</full_analysis>
```

The human-readable summary is for the human reviewer in the loop. The `<full_analysis>` JSON block is for the Fix Writer — it can parse it with `CodeAnalysis.from_json()` and get typed, structured data without any text parsing.

---

## Things to try

**Compare the two agents' outputs side by side.** Run `analyze` on an issue, then compare what the Issue Reader produced vs what the Code Analyst added. Notice how the analyst is much more specific about files and lines.

**Break the structured output deliberately.** Edit the system prompt in `code_analyst.py` to remove the JSON schema and see what the agent produces. Then watch the `from_json()` parse fail. This is how you build intuition for why output contracts matter.

**Try a complex issue.** The Code Analyst should produce a `confidence: "low"` when the root cause isn't clear from the code. Find an issue with an ambiguous description and see how it responds.

**Inspect the token usage.** Add `console.print(response.usage)` inside the loop to see how many input/output tokens each turn consumes. This builds intuition for how context length affects cost.

---

## What's next

Module 3: the **Fix Writer** — it receives the `CodeAnalysis` and writes actual code changes. This is where we introduce patch formatting, handling context limits for large files, and the first time NimbleDev produces output that could go into a real PR.

```
Module 1 ✅  Issue Reader    → understands the bug
Module 2 ✅  Code Analyst    → finds exact lines, structured spec
Module 3 🔜  Fix Writer      → writes the code change
Module 4     Reviewer        → critiques the fix, feedback loop
Module 5     PR Agent        → forks, commits, opens PR
Module 6     Observability   → logging, tracing, dashboards
Module 7     RAG + Memory    → vector DB, long-term context
Module 8     MCP             → enterprise tool server standard
Module 9     Cloud deploy    → AWS Lambda + Bedrock + webhooks
```
