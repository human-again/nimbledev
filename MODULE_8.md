# Module 8: MCP Server — Standardised Tool Protocol

## What We Built

Two files in `mcp_server/`:
- `github_mcp.py` — FastMCP server exposing all GitHub tools
- `__init__.py`

`main.py` gains a `serve-mcp` command:
```bash
uv run main.py serve-mcp
```

## How to Run It

Install the MCP SDK:
```bash
uv add mcp
```

Start the server:
```bash
uv run main.py serve-mcp
```

Inspect it with MCP Inspector:
```bash
npx @modelcontextprotocol/inspector uv run main.py serve-mcp
```

Connect from Claude Desktop (add to `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "nimbledev-github": {
      "command": "uv",
      "args": ["run", "main.py", "serve-mcp"],
      "cwd": "/path/to/nimbledev"
    }
  }
}
```

## Key New Concept: What MCP Is and Why It Matters

### The Problem MCP Solves

Before MCP, every agent framework had its own tool format:
- Anthropic: one JSON schema format
- OpenAI: a different format  
- LangChain: its own abstraction wrapping both

Tools written for one framework couldn't be used by another without rewriting them.

**MCP is USB for AI tools.** Define your tools once as an MCP server, and any MCP-compatible agent can use them.

### FastMCP: Tools from Functions

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nimbledev-github")

@mcp.tool()
def get_issue(owner: str, repo: str, issue_number: int) -> str:
    """Fetch a GitHub issue by number."""
    return _get_issue(owner, repo, issue_number)
```

FastMCP automatically:
1. Generates the JSON schema from the function signature and type hints
2. Registers the tool with the MCP protocol
3. Handles the server/client communication

Compare to the manual approach in earlier modules:
```python
# Before (Modules 1-5): manual schema + dispatcher
TOOL_SCHEMAS = [{"name": "get_issue", "input_schema": {...}}]
TOOL_FUNCTIONS = {"get_issue": get_issue}
def dispatch(name, args): return TOOL_FUNCTIONS[name](**args)
```

### Connecting Agents as MCP Clients

The existing agents use direct function calls:
```python
result = dispatch(block.name, block.input)  # direct call
```

An MCP client pattern looks like:
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="uv", args=["run", "main.py", "serve-mcp"])

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()           # discover tools
        result = await session.call_tool("get_issue", {...})  # call tool
```

The agentic loop logic (prompts, parsing, iteration) stays the same. Only the tool dispatch changes.

### Why Enterprise Systems Adopt MCP

- **Tool governance:** add auth/RBAC at the server level, not in every agent
- **Tool versioning:** v1 vs v2 of a tool, agents specify what they need
- **Tool discovery:** agents query "what tools exist?" dynamically
- **Observability:** all calls through one server → one place to log and rate-limit
- **Reuse:** the same GitHub tool server works for issue-fix agents, PR agents, and any future agent

## Things to Try

1. Run MCP Inspector and call `get_issue` directly from the UI
2. Add a new tool to the server (e.g. `list_issues`) and see it appear in Inspector
3. Connect Claude Desktop to the server and use Claude to explore a GitHub repo

## Congratulations!

You've built a complete multi-agent system:

| Module | Agent | Pattern |
|--------|-------|---------|
| 1 | Issue Reader | Agentic loop, tool calling |
| 2 | Code Analyst | Agent chaining, structured output |
| 3 | Fix Writer | Code generation, context management |
| 4 | Reviewer | Critic/generator, feedback loops |
| 5 | PR Agent | Deterministic sequences, human-in-the-loop |
| 6 | Observability | Tracing, token tracking, structured logging |
| 7 | Memory | RAG, vector databases, embeddings |
| 8 | MCP Server | Standardised tool protocol |
