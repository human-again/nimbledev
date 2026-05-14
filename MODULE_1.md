# Module 1: Your First Agent — The Issue Reader

Welcome to NimbleDev. By the end of this module you'll have a working agent that reads any GitHub issue, explores the codebase, and produces a structured analysis — ready to hand off to the next agent in the pipeline.

---

## What we built

```
nimbledev/
├── config/
│   └── settings.py        ← All config loaded from .env
├── tools/
│   └── github.py          ← The agent's "hands" — GitHub API functions
├── agents/
│   └── issue_reader.py    ← The agent itself — the agentic loop
├── main.py                ← CLI entry point
└── .env.example           ← Copy this to .env and fill in your secrets
```

---

## Step 1: Configure your secrets

Copy `.env.example` to `.env` and fill it in:

```bash
cd nimbledev
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...       # From console.anthropic.com
GITHUB_TOKEN=ghp_...               # From github.com/settings/tokens
GITHUB_USERNAME=your-username      # Your GitHub handle
```

Your GitHub token needs the `repo` scope (for reading public repos and forking later).

---

## Step 2: Run the agent

```bash
uv run main.py read-issue https://github.com/psf/requests/issues/6730
```

You'll see the agent working in real time — each tool call it makes prints to the terminal. After a minute or two it produces a structured analysis.

Try it on any open issue in any public repo you're interested in contributing to.

---

## The core concept: The Agentic Loop

This is the most important idea in this entire tutorial. Every agent you'll ever build — whether it's a simple single-agent or a sophisticated multi-agent system — is built on this loop:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   1. Send message + tools to Claude             │
│                ↓                                │
│   2. Claude responds with:                      │
│      a) Text answer  →  DONE, return it         │
│      b) Tool call    →  run the tool            │
│                ↓                                │
│   3. Add tool result to conversation            │
│                ↓                                │
│   Go back to step 1                             │
│                                                 │
└─────────────────────────────────────────────────┘
```

In code, this is the `while` loop in `agents/issue_reader.py`. Claude decides what to do next on every iteration — we just faithfully execute whatever it asks for and hand back the results.

The key insight: **the LLM is the decision-maker, Python is the executor**. Claude decides which tools to call and in what order. Your code just provides the tools and runs them.

---

## The three parts of every agent

### 1. The system prompt

```python
SYSTEM_PROMPT = """You are the Issue Reader agent for NimbleDev..."""
```

This defines the agent's role, goals, and output format. It's the most important lever you have for controlling agent behavior. Change the system prompt and you change everything the agent does — without touching any other code.

A good system prompt tells the agent:
- Who it is and what its job is
- What steps to follow
- What format to produce output in
- What to avoid

### 2. The tools

```python
TOOL_SCHEMAS = [
    {
        "name": "get_issue",
        "description": "Fetch a GitHub issue...",
        "input_schema": { ... }
    },
    ...
]
```

Tools are the agent's interface with the world. Without tools, the agent can only reason — it can't read files, call APIs, or take any action. The `description` field is crucial: Claude reads it to decide when and how to use each tool. Write it clearly.

Each tool schema has three parts:
- `name` — what Claude calls it
- `description` — when and why to use it (Claude reads this)
- `input_schema` — what arguments it expects (JSON Schema format)

### 3. The loop

```python
while iteration < max_iterations:
    response = client.messages.create(...)          # Ask Claude
    
    if response.stop_reason == "end_turn":
        return the_text_answer                      # Done
    
    elif response.stop_reason == "tool_use":
        results = run_the_tools(response.content)   # Execute tools
        messages.append(results)                    # Feed back
        # loop continues
```

The `stop_reason` field tells you what Claude wants:
- `"end_turn"` — Claude has finished and is giving you a text answer
- `"tool_use"` — Claude wants to call one or more tools before continuing

The `messages` list is the full conversation history. Every turn (your message, Claude's response, tool results) gets appended. This is what lets Claude remember what it already discovered.

---

## What the conversation looks like

Here's a simplified view of the message history as it builds up during one run:

```
messages = [
  { role: "user",      content: "Analyze issue #6730 in psf/requests" },
  { role: "assistant", content: [ToolUse("get_issue", {...})] },
  { role: "user",      content: [ToolResult("ISSUE #6730: ...")] },
  { role: "assistant", content: [ToolUse("get_repo_structure", {...})] },
  { role: "user",      content: [ToolResult("📁 src\n📄 README.md\n...")] },
  { role: "assistant", content: [ToolUse("search_repo_code", {...})] },
  { role: "user",      content: [ToolResult("Found 3 results...")] },
  { role: "assistant", content: [ToolUse("get_file_content", {...})] },
  { role: "user",      content: [ToolResult("FILE: src/auth.py\n...")] },
  { role: "assistant", content: [Text("## Issue Summary\n...")] },  ← Final answer
]
```

Each tool result goes back as a `user` message — that's the API convention. Claude then reads the full history and decides what to do next.

---

## The tools we gave it

| Tool | What it does | When the agent uses it |
|---|---|---|
| `get_issue` | Fetches issue title, body, labels, comments | Always first — to understand the task |
| `get_repo_structure` | Lists files/folders in a path | To navigate the codebase |
| `get_file_content` | Reads a specific file | To understand relevant code |
| `search_repo_code` | GitHub code search within a repo | To find where a symbol or error is defined |

Notice that the agent decides the order and which tools to call — we don't script that. Claude reads the issue and figures out what to look at.

---

## Things to try

**Point it at a real issue you care about:**
```bash
uv run main.py read-issue https://github.com/pallets/flask/issues/5563
uv run main.py read-issue https://github.com/encode/httpx/issues/2932
```

**Change the system prompt and observe the difference.** Try making it more terse, or ask it to also estimate fix complexity on a 1-5 scale. The system prompt controls everything.

**Add a print statement inside the loop** to watch the full message history grow. Understanding the conversation structure is the key to debugging agents.

**Hit the rate limit intentionally** — search aggressively and see how the agent handles the error message from the tool. Notice that we return error strings rather than raising exceptions, so the agent can read what went wrong and adapt.

---

## Full curriculum

NimbleDev is structured as 9 modules. The first 5 build the core agent pipeline end-to-end. The final 4 add the enterprise-grade skills needed for production roles.

```
── Core pipeline ──────────────────────────────────────────────────────────
Module 1 ✅  Issue Reader    → understands the bug, maps the codebase
Module 2 🔜  Code Analyst    → finds exact lines to change, structured spec
Module 3     Fix Writer      → writes the code change
Module 4     Reviewer        → critiques fix, feedback loop back to writer
Module 5     PR Agent        → forks repo, commits, opens PR upstream

── Enterprise layer ───────────────────────────────────────────────────────
Module 6     Observability   → structured logging, trace IDs, run dashboard
Module 7     RAG + Memory    → vector DB (Chroma), embed past analyses,
                               retrieval-augmented context injection
Module 8     MCP             → rewrite tools as a Model Context Protocol
                               server — the emerging enterprise standard
Module 9     Cloud deploy    → AWS Lambda + Bedrock + CloudWatch,
                               triggered by GitHub webhook
```

### What each module teaches

| Module | Key concept |
|--------|-------------|
| 1 | The agentic loop — how LLMs become agents |
| 2 | Agent-to-agent handoffs, structured output schemas |
| 3 | Code generation, patch formatting, context limits |
| 4 | Feedback loops, critic agents, stopping conditions |
| 5 | Git operations, fork-based PR flow, human-in-the-loop |
| 6 | Observability — tracing, metrics, debugging agent runs |
| 7 | RAG — embeddings, vector search, long-term memory |
| 8 | MCP — building and connecting MCP tool servers |
| 9 | Cloud infra — serverless agents, webhooks, Bedrock |

### Job description coverage

After completing all 9 modules you will have hands-on experience with every core technical requirement in a typical AI orchestration engineer role: agent development, multi-agent coordination, tool routing, state management, failure handling, observability, RAG, MCP, API integration, and cloud deployment on AWS.
