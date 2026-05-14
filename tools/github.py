"""
tools/github.py
---------------
GitHub API helpers and tool schemas used by the agents.
"""

import requests
from config.settings import GITHUB_API_BASE, GITHUB_HEADERS


# ── Tool functions ─────────────────────────────────────────────────────────────

def get_issue(owner: str, repo: str, issue_number: int) -> str:
    """Fetch a single GitHub issue including its body and comments."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: Issue #{issue_number} not found in {owner}/{repo}. Check the repo name and issue number."
    if response.status_code != 200:
        return f"Error: GitHub API returned {response.status_code} — {response.text}"

    data = response.json()

    # Fetch comments too — they often contain crucial reproduction steps
    comments_url = f"{url}/comments"
    comments_resp = requests.get(comments_url, headers=GITHUB_HEADERS)
    comments = comments_resp.json() if comments_resp.status_code == 200 else []

    result = f"""
ISSUE #{data['number']}: {data['title']}
State: {data['state']}
Labels: {', '.join(l['name'] for l in data.get('labels', [])) or 'none'}
Author: {data['user']['login']}
Created: {data['created_at']}
URL: {data['html_url']}

BODY:
{data.get('body') or '(no body)'}
"""
    if comments:
        result += f"\n\nCOMMENTS ({len(comments)}):\n"
        for c in comments[:5]:  # cap at 5 to avoid token overflow
            result += f"\n--- {c['user']['login']} ---\n{c['body']}\n"

    return result.strip()


def get_repo_structure(owner: str, repo: str, path: str = "") -> str:
    """List files and directories in a repo path (top-level by default)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code != 200:
        return f"Error fetching repo structure: {response.status_code} — {response.text}"

    items = response.json()
    if not isinstance(items, list):
        return f"Error: expected directory listing but got a file. Use get_file_content for files."

    lines = []
    for item in sorted(items, key=lambda x: (x["type"] == "file", x["name"])):
        icon = "📁" if item["type"] == "dir" else "📄"
        lines.append(f"{icon} {item['path']}")

    return "\n".join(lines) if lines else "(empty directory)"


def get_file_content(owner: str, repo: str, file_path: str) -> str:
    """Read the content of a specific file from a GitHub repo."""
    import base64

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: File '{file_path}' not found in {owner}/{repo}."
    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    data = response.json()

    if data.get("encoding") != "base64":
        return f"Error: Unexpected encoding: {data.get('encoding')}"

    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    # Guard against enormous files swamping the context window
    max_chars = 8000
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... (truncated — file is {len(content)} chars total)"

    return f"FILE: {file_path}\n{'─' * 40}\n{content}"


def search_repo_code(owner: str, repo: str, query: str) -> str:
    """Search for code within a specific repo matching a query string."""
    url = f"{GITHUB_API_BASE}/search/code"
    params = {"q": f"{query} repo:{owner}/{repo}", "per_page": 10}
    response = requests.get(url, headers=GITHUB_HEADERS, params=params)

    if response.status_code == 403:
        return "Error: GitHub search rate limit hit. Wait 60 seconds and try again."
    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    data = response.json()
    items = data.get("items", [])

    if not items:
        return f"No results found for '{query}' in {owner}/{repo}."

    lines = [f"Found {data['total_count']} results (showing top {len(items)}):"]
    for item in items:
        lines.append(f"  • {item['path']}")

    return "\n".join(lines)


def get_file_at_lines(owner: str, repo: str, file_path: str, start_line: int, end_line: int) -> str:
    """Read a specific line range from a file in a GitHub repo."""
    import base64

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: File '{file_path}' not found in {owner}/{repo}."
    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    data = response.json()
    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    all_lines = content.splitlines()
    total = len(all_lines)

    # Clamp to actual file bounds
    start = max(1, start_line)
    end = min(total, end_line)

    selected = all_lines[start - 1:end]
    numbered = "\n".join(f"{start + i:4d} │ {line}" for i, line in enumerate(selected))

    return f"FILE: {file_path} (lines {start}–{end} of {total})\n{'─' * 40}\n{numbered}"


def get_recent_commits(owner: str, repo: str, file_path: str, limit: int = 5) -> str:
    """Get recent commits to a specific file."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {"path": file_path, "per_page": limit}
    response = requests.get(url, headers=GITHUB_HEADERS, params=params)

    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    commits = response.json()
    if not commits:
        return f"No commits found for '{file_path}' in {owner}/{repo}."

    lines = [f"Recent commits to {file_path}:"]
    for c in commits:
        sha = c["sha"][:7]
        msg = c["commit"]["message"].splitlines()[0][:80]
        author = c["commit"]["author"]["name"]
        date = c["commit"]["author"]["date"][:10]
        lines.append(f"  {sha} [{date}] {author}: {msg}")

    return "\n".join(lines)


def get_pull_request(owner: str, repo: str, pr_number: int) -> str:
    """Fetch metadata and description for a GitHub pull request."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: PR #{pr_number} not found in {owner}/{repo}."
    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    pr = response.json()
    return (
        f"PR #{pr['number']}: {pr['title']}\n"
        f"State: {pr['state']} | Draft: {pr['draft']}\n"
        f"Author: {pr['user']['login']}\n"
        f"Base: {pr['base']['ref']} ← Head: {pr['head']['ref']}\n"
        f"Additions: +{pr['additions']} | Deletions: -{pr['deletions']} | Files: {pr['changed_files']}\n"
        f"URL: {pr['html_url']}\n\n"
        f"DESCRIPTION:\n{pr.get('body') or '(no description)'}"
    )


def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Fetch the unified diff for a pull request."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_headers = {**GITHUB_HEADERS, "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=diff_headers)

    if response.status_code != 200:
        return f"Error fetching diff: {response.status_code} — {response.text}"

    diff = response.text
    max_chars = 12000
    if len(diff) > max_chars:
        diff = diff[:max_chars] + f"\n\n... (diff truncated — {len(diff)} chars total)"
    return diff


def get_pr_files(owner: str, repo: str, pr_number: int) -> str:
    """List all files changed in a PR with their change stats."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=GITHUB_HEADERS, params={"per_page": 50})

    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    files = response.json()
    lines = [f"Files changed ({len(files)}):"]
    for f in files:
        lines.append(
            f"  [{f['status']:8s}] +{f['additions']:4d} -{f['deletions']:4d}  {f['filename']}"
        )
    return "\n".join(lines)


def get_contributing_guide(owner: str, repo: str) -> str:
    """
    Fetch CONTRIBUTING.md or a similar contributor guide from a repo.
    """
    import base64

    candidates = [
        "CONTRIBUTING.md",
        "CONTRIBUTING.rst",
        ".github/CONTRIBUTING.md",
        "docs/contributing.rst",
        "docs/contributing.md",
    ]

    for path in candidates:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url, headers=GITHUB_HEADERS)
        if response.status_code == 200:
            data = response.json()
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                max_chars = 6000
                if len(content) > max_chars:
                    content = content[:max_chars] + f"\n\n... (truncated — {len(content)} chars total)"
                return f"CONTRIBUTING GUIDE ({path}):\n{'─' * 40}\n{content}"

    return f"No CONTRIBUTING guide found in {owner}/{repo} (checked: {', '.join(candidates)})."


def fork_repo(owner: str, repo: str) -> str:
    """
    Fork a repo to GITHUB_USERNAME's account.

    Returns the forked repo's full name and clone URL.
    """
    from config.settings import GITHUB_USERNAME
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/forks"
    response = requests.post(url, headers=GITHUB_HEADERS)

    if response.status_code in (202, 200):
        data = response.json()
        return (
            f"Forked {owner}/{repo} → {data['full_name']}\n"
            f"Clone URL: {data['clone_url']}\n"
            f"Fork owner: {data['owner']['login']}"
        )
    if response.status_code == 422:
        # Already forked — look up the existing fork
        existing_url = f"{GITHUB_API_BASE}/repos/{GITHUB_USERNAME}/{repo}"
        existing = requests.get(existing_url, headers=GITHUB_HEADERS)
        if existing.status_code == 200:
            data = existing.json()
            return (
                f"Fork already exists: {data['full_name']}\n"
                f"Clone URL: {data['clone_url']}"
            )
    return f"Error forking repo: {response.status_code} — {response.text}"


def create_branch(owner: str, repo: str, branch_name: str, base_sha: str) -> str:
    """
    Create a new branch in owner/repo pointing at base_sha.

    Typically called on the forked repo (owner = GITHUB_USERNAME).
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
    payload = {
        "ref": f"refs/heads/{branch_name}",
        "sha": base_sha,
    }
    response = requests.post(url, headers=GITHUB_HEADERS, json=payload)

    if response.status_code == 201:
        data = response.json()
        return f"Branch '{branch_name}' created at {data['object']['sha'][:7]}"
    if response.status_code == 422:
        return f"Branch '{branch_name}' already exists in {owner}/{repo}."
    return f"Error creating branch: {response.status_code} — {response.text}"


def get_file_sha(owner: str, repo: str, path: str, branch: str = "main") -> str:
    """
    Get the blob SHA of a file — needed by GitHub's update-file API.

    Returns the SHA string, or an error message prefixed with 'Error:'.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, headers=GITHUB_HEADERS, params={"ref": branch})

    if response.status_code == 404:
        return "NOT_FOUND"  # file doesn't exist yet — this is fine for new files
    if response.status_code != 200:
        return f"Error: {response.status_code} — {response.text}"

    data = response.json()
    return data.get("sha", "Error: no sha in response")


def push_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str,
    sha: str,
) -> str:
    """
    Create or update a file in owner/repo on branch.

    sha should be the current blob SHA (from get_file_sha), or empty string
    for new files.
    """
    import base64

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha and sha != "NOT_FOUND":
        payload["sha"] = sha

    response = requests.put(url, headers=GITHUB_HEADERS, json=payload)

    if response.status_code in (200, 201):
        data = response.json()
        return (
            f"Pushed {path} → {owner}/{repo}@{branch}\n"
            f"Commit: {data['commit']['sha'][:7]} — {data['commit']['message'][:60]}"
        )
    return f"Error pushing {path}: {response.status_code} — {response.text}"


def open_pull_request(
    owner: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
) -> str:
    """
    Open a pull request on owner/repo.

    head: the branch with changes (e.g. 'myuser:fix/issue-42-auth-bug')
    base: the target branch to merge into (usually 'main')
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }
    response = requests.post(url, headers=GITHUB_HEADERS, json=payload)

    if response.status_code == 201:
        data = response.json()
        return (
            f"Pull request opened!\n"
            f"PR #{data['number']}: {data['title']}\n"
            f"URL: {data['html_url']}"
        )
    return f"Error opening PR: {response.status_code} — {response.text}"


def get_default_branch_sha(owner: str, repo: str) -> str:
    """Get the HEAD SHA of the default branch. Used as base for new branches."""
    # First get default branch name
    repo_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    repo_resp = requests.get(repo_url, headers=GITHUB_HEADERS)
    if repo_resp.status_code != 200:
        return f"Error: {repo_resp.status_code} — {repo_resp.text}"

    default_branch = repo_resp.json().get("default_branch", "main")

    # Then get its SHA
    ref_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{default_branch}"
    ref_resp = requests.get(ref_url, headers=GITHUB_HEADERS)
    if ref_resp.status_code != 200:
        return f"Error: {ref_resp.status_code} — {ref_resp.text}"

    sha = ref_resp.json()["object"]["sha"]
    return f"{sha} (branch: {default_branch})"


# ── Tool schemas (what the LLM sees) ──────────────────────────────────────────
# This is the "menu" of tools we hand to the Anthropic API.
# Each entry matches one function above.

TOOL_SCHEMAS = [
    {
        "name": "get_issue",
        "description": (
            "Fetch a GitHub issue by number, including its title, body, labels, "
            "and up to 5 comments. Use this first to understand what needs to be fixed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "GitHub repo owner or org, e.g. 'psf'"},
                "repo": {"type": "string", "description": "Repository name, e.g. 'requests'"},
                "issue_number": {"type": "integer", "description": "Issue number, e.g. 1234"},
            },
            "required": ["owner", "repo", "issue_number"],
        },
    },
    {
        "name": "get_repo_structure",
        "description": (
            "List the files and folders in a repo directory. "
            "Start with path='' for the root. Then drill into relevant folders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Use '' for repo root.",
                    "default": "",
                },
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "get_file_content",
        "description": "Read the full content of a specific file in the repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "file_path": {"type": "string", "description": "Full path to the file, e.g. 'src/utils.py'"},
            },
            "required": ["owner", "repo", "file_path"],
        },
    },
    {
        "name": "search_repo_code",
        "description": (
            "Search for a keyword or symbol within a repo's code. "
            "Useful for finding where a bug lives or which files define a function."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "query": {"type": "string", "description": "Search term, e.g. a function name or error message"},
            },
            "required": ["owner", "repo", "query"],
        },
    },
    {
        "name": "get_file_at_lines",
        "description": (
            "Read a specific line range from a file. Use this when you already know "
            "which file is relevant and want to focus on a particular function or section "
            "without loading the whole file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "file_path": {"type": "string"},
                "start_line": {"type": "integer", "description": "First line to return (1-indexed)"},
                "end_line": {"type": "integer", "description": "Last line to return (inclusive)"},
            },
            "required": ["owner", "repo", "file_path", "start_line", "end_line"],
        },
    },
    {
        "name": "get_recent_commits",
        "description": (
            "Get the most recent commits to a file. Useful for understanding recent changes "
            "that may have introduced the bug, or for understanding coding conventions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "file_path": {"type": "string", "description": "Path to the file to inspect"},
                "limit": {"type": "integer", "description": "Number of commits to return (default 5)", "default": 5},
            },
            "required": ["owner", "repo", "file_path"],
        },
    },
    {
        "name": "get_pull_request",
        "description": "Fetch metadata and description for a GitHub pull request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pr_number": {"type": "integer", "description": "PR number"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_diff",
        "description": (
            "Fetch the unified diff for a pull request — the raw +/- lines. "
            "Use this to see exactly what code changed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pr_number": {"type": "integer"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_files",
        "description": "List all files changed in a PR with their addition/deletion counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pr_number": {"type": "integer"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    },
    {
        "name": "get_contributing_guide",
        "description": (
            "Fetch the project's CONTRIBUTING.md or contributor guide. "
            "Use this before writing code to understand the project's style conventions, "
            "test requirements, and contribution workflow."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
    },
]

# Subsets for each pipeline — agents only see the tools relevant to their job
ISSUE_FIX_TOOLS = [
    s for s in TOOL_SCHEMAS
    if s["name"] not in ("get_pull_request", "get_pr_diff", "get_pr_files")
]
PR_REVIEW_TOOLS = [s for s in TOOL_SCHEMAS if s["name"] not in ("get_issue",)]

# Fix Writer gets the full issue-fix set
FIX_WRITER_TOOLS = ISSUE_FIX_TOOLS  # same set, aliased for clarity


# ── Tool dispatcher ────────────────────────────────────────────────────────────
# When the agent says "call get_issue with these args", this routes it here.

TOOL_FUNCTIONS = {
    "get_issue": get_issue,
    "get_repo_structure": get_repo_structure,
    "get_file_content": get_file_content,
    "search_repo_code": search_repo_code,
    "get_file_at_lines": get_file_at_lines,
    "get_recent_commits": get_recent_commits,
    "get_pull_request": get_pull_request,
    "get_pr_diff": get_pr_diff,
    "get_pr_files": get_pr_files,
    "get_contributing_guide": get_contributing_guide,
    # PR Agent tools (called directly, not via agent loop)
    "fork_repo": fork_repo,
    "create_branch": create_branch,
    "get_file_sha": get_file_sha,
    "push_file": push_file,
    "open_pull_request": open_pull_request,
    "get_default_branch_sha": get_default_branch_sha,
}


def dispatch(tool_name: str, tool_input: dict) -> str:
    """Call the right tool function given a name and input dict."""
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return f"Error: Unknown tool '{tool_name}'"
    try:
        return fn(**tool_input)
    except TypeError as e:
        return f"Error calling {tool_name}: {e}"
