"""
mcp_server/github_mcp.py
-------------------------
Module 8: NimbleDev's GitHub tools exposed as a proper MCP server.

TEACHING NOTE — What MCP is and why it matters:

  MCP (Model Context Protocol) is an open standard by Anthropic for how AI
  agents communicate with external tools. Think of it as "USB for AI tools":

    Before MCP: every agent framework defined its own tool format.
      - Anthropic used one JSON schema format
      - OpenAI used a different format
      - LangChain wrapped both with its own abstraction
      → Tools were not reusable across frameworks

    After MCP: tools are defined once as MCP servers.
      - Any MCP-compatible agent (Claude, OpenAI, custom) can use them
      - Tools are discoverable: the agent can ask "what tools exist?"
      - Tools are versioned and governed centrally
      → Same GitHub tools, used by any agent anywhere

  Real-world analogy: REST APIs vs SOAP. MCP is REST — simple, standard,
  widely adopted. The ad-hoc tool JSON schemas we used in Modules 1-5 are
  like SOAP — it works, but it's bespoke and not interoperable.

TEACHING NOTE — FastMCP vs raw MCP SDK:

  The official MCP SDK (mcp package) gives you full control but requires
  boilerplate: server setup, tool registration, message handling.

  FastMCP is the high-level wrapper (included in the mcp package):
    @mcp.tool()
    def get_issue(owner: str, repo: str, issue_number: int) -> str:
        ...

  FastMCP handles:
    - Automatically generating the JSON schema from the function signature
    - Running the server (stdio or HTTP transport)
    - Registering tools with the MCP protocol

  Use FastMCP for new servers. Use raw SDK only if you need features
  FastMCP doesn't expose.

TEACHING NOTE — How agents connect as MCP clients:

  In Modules 1-5, agents called tools directly:
    result = dispatch(block.name, block.input)  # direct function call

  In Module 8+, agents call tools via MCP:
    # Tools are defined on a remote MCP server
    # The agent's tool schemas come from server discovery
    # Tool calls are forwarded over the MCP protocol (stdio or HTTP)

  The agent code barely changes — you swap out the tool schemas and the
  dispatch mechanism. The tool implementations stay on the server.

  This is powerful because:
    1. Tools can be shared across multiple agents without code duplication
    2. Tools can be deployed, versioned, and monitored independently
    3. Any MCP-compatible framework can use the same tools

TEACHING NOTE — Why enterprise systems adopt MCP:

  Tool governance: who can call what tool? With MCP, you add auth/RBAC
  at the server level without changing agent code.

  Tool versioning: v1 of get_file_content returns raw text, v2 returns
  structured metadata. Agents specify which version they need.

  Tool discovery: agents can query "what tools are available?" instead of
  having schemas hardcoded. This enables dynamic agent capability.

  Observability: all tool calls go through one server → one place to log,
  rate-limit, and monitor.

HOW TO RUN THE MCP SERVER:
  uv run main.py serve-mcp
  → Starts stdio MCP server (for use with Claude Desktop, MCP Inspector, etc.)

  To connect from MCP Inspector:
    npx @modelcontextprotocol/inspector uv run main.py serve-mcp

  To use with Claude Desktop, add to claude_desktop_config.json:
    {
      "mcpServers": {
        "nimbledev-github": {
          "command": "uv",
          "args": ["run", "main.py", "serve-mcp"],
          "cwd": "/path/to/nimbledev"
        }
      }
    }
"""

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False
    # Provide a stub so the rest of the codebase can import without crashing
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self.name = name
        def tool(self):
            def decorator(fn):
                return fn
            return decorator
        def run(self):
            raise ImportError(
                "MCP is not installed. Install with: uv add mcp\n"
                "Then run: uv run main.py serve-mcp"
            )

from tools.github import (
    get_issue as _get_issue,
    get_repo_structure as _get_repo_structure,
    get_file_content as _get_file_content,
    search_repo_code as _search_repo_code,
    get_file_at_lines as _get_file_at_lines,
    get_recent_commits as _get_recent_commits,
    get_pull_request as _get_pull_request,
    get_pr_diff as _get_pr_diff,
    get_pr_files as _get_pr_files,
    get_contributing_guide as _get_contributing_guide,
)

mcp = FastMCP("nimbledev-github")


# ── Issue Fix tools ────────────────────────────────────────────────────────────

@mcp.tool()
def get_issue(owner: str, repo: str, issue_number: int) -> str:
    """
    Fetch a GitHub issue by number, including its title, body, labels,
    and up to 5 comments.
    """
    return _get_issue(owner, repo, issue_number)


@mcp.tool()
def get_repo_structure(owner: str, repo: str, path: str = "") -> str:
    """
    List the files and folders in a GitHub repo directory.
    Use path='' for the root. Drill into relevant folders.
    """
    return _get_repo_structure(owner, repo, path)


@mcp.tool()
def get_file_content(owner: str, repo: str, file_path: str) -> str:
    """
    Read the full content of a specific file in a GitHub repo.
    Returns the file content with a path header.
    """
    return _get_file_content(owner, repo, file_path)


@mcp.tool()
def search_repo_code(owner: str, repo: str, query: str) -> str:
    """
    Search for a keyword or symbol within a repo's code.
    Useful for finding where a bug lives or which files define a function.
    """
    return _search_repo_code(owner, repo, query)


@mcp.tool()
def get_file_at_lines(
    owner: str,
    repo: str,
    file_path: str,
    start_line: int,
    end_line: int,
) -> str:
    """
    Read a specific line range from a file in a GitHub repo.
    More efficient than get_file_content when you only need a section.
    """
    return _get_file_at_lines(owner, repo, file_path, start_line, end_line)


@mcp.tool()
def get_recent_commits(owner: str, repo: str, file_path: str, limit: int = 5) -> str:
    """
    Get the most recent commits to a specific file.
    Useful for understanding recent changes that may have introduced a bug.
    """
    return _get_recent_commits(owner, repo, file_path, limit)


@mcp.tool()
def get_contributing_guide(owner: str, repo: str) -> str:
    """
    Fetch the project's CONTRIBUTING.md or contributor guide.
    Use before writing code to understand style conventions and test requirements.
    """
    return _get_contributing_guide(owner, repo)


# ── PR Review tools ────────────────────────────────────────────────────────────

@mcp.tool()
def get_pull_request(owner: str, repo: str, pr_number: int) -> str:
    """
    Fetch metadata and description for a GitHub pull request.
    Returns PR title, state, author, branch info, and description.
    """
    return _get_pull_request(owner, repo, pr_number)


@mcp.tool()
def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """
    Fetch the unified diff for a pull request.
    Returns the raw +/- lines showing exactly what code changed.
    """
    return _get_pr_diff(owner, repo, pr_number)


@mcp.tool()
def get_pr_files(owner: str, repo: str, pr_number: int) -> str:
    """
    List all files changed in a PR with their addition/deletion counts.
    """
    return _get_pr_files(owner, repo, pr_number)


# ── MCP client pattern (for reference) ────────────────────────────────────────
#
# To connect agents to this MCP server instead of direct tool calls,
# you would use the MCP client pattern. Here is a sketch of how that works:
#
#   from mcp import ClientSession, StdioServerParameters
#   from mcp.client.stdio import stdio_client
#
#   server_params = StdioServerParameters(
#       command="uv",
#       args=["run", "main.py", "serve-mcp"],
#   )
#
#   async with stdio_client(server_params) as (read, write):
#       async with ClientSession(read, write) as session:
#           await session.initialize()
#
#           # Discover available tools
#           tools = await session.list_tools()
#
#           # Call a tool
#           result = await session.call_tool("get_issue", {
#               "owner": "psf",
#               "repo": "requests",
#               "issue_number": 6730,
#           })
#
# The existing agents use direct dispatch() calls. Switching to MCP means:
#   1. Replacing dispatch(name, args) with session.call_tool(name, args)
#   2. Getting tool schemas from session.list_tools() instead of TOOL_SCHEMAS
#   3. Running the MCP server as a subprocess
#
# The agent logic (the agentic loop, prompts, parsing) stays the same.
