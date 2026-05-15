"""
GitHub API helpers and tool schemas for the PR review pipeline.
"""

import base64
import json

import requests

from config.settings import GITHUB_API_BASE, GITHUB_HEADERS


def get_pull_request(owner: str, repo: str, pr_number: int) -> str:
    """Fetch metadata and description for a GitHub pull request."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: PR #{pr_number} not found in {owner}/{repo}."
    if response.status_code != 200:
        return f"Error: {response.status_code} - {response.text}"

    pr = response.json()
    return (
        f"PR #{pr['number']}: {pr['title']}\n"
        f"State: {pr['state']} | Draft: {pr['draft']}\n"
        f"Author: {pr['user']['login']}\n"
        f"Base: {pr['base']['ref']} <- Head: {pr['head']['ref']}\n"
        f"Additions: +{pr['additions']} | Deletions: -{pr['deletions']} | Files: {pr['changed_files']}\n"
        f"URL: {pr['html_url']}\n\n"
        f"DESCRIPTION:\n{pr.get('body') or '(no description)'}"
    )


def get_pr_files(owner: str, repo: str, pr_number: int) -> str:
    """List all files changed in a PR with their change stats."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=GITHUB_HEADERS, params={"per_page": 50})

    if response.status_code != 200:
        return f"Error: {response.status_code} - {response.text}"

    files = response.json()
    lines = [f"Files changed ({len(files)}):"]
    for file_info in files:
        lines.append(
            f"  [{file_info['status']:8s}] "
            f"+{file_info['additions']:4d} "
            f"-{file_info['deletions']:4d}  "
            f"{file_info['filename']}"
        )
    return "\n".join(lines)


def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Fetch the unified diff for a pull request."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_headers = {**GITHUB_HEADERS, "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=diff_headers)

    if response.status_code != 200:
        return f"Error fetching diff: {response.status_code} - {response.text}"

    diff = response.text
    max_chars = 12000
    return json.dumps(
        {
            "content": diff[:max_chars],
            "truncated": len(diff) > max_chars,
            "total_chars": len(diff),
        },
        indent=2,
    )


def get_file_content(owner: str, repo: str, file_path: str) -> str:
    """Read the content of a specific file from a GitHub repo."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
    response = requests.get(url, headers=GITHUB_HEADERS)

    if response.status_code == 404:
        return f"Error: File '{file_path}' not found in {owner}/{repo}."
    if response.status_code != 200:
        return f"Error: {response.status_code} - {response.text}"

    data = response.json()
    if data.get("encoding") != "base64":
        return f"Error: Unexpected encoding: {data.get('encoding')}"

    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    max_chars = 8000
    return json.dumps(
        {
            "file_path": file_path,
            "content": content[:max_chars],
            "truncated": len(content) > max_chars,
            "total_chars": len(content),
        },
        indent=2,
    )


PR_REVIEW_TOOLS = [
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
        "name": "get_pr_diff",
        "description": "Fetch the unified diff for a pull request.",
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
        "name": "get_file_content",
        "description": "Read the content of a specific file in the repository.",
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
]

DIFF_PARSER_TOOLS = [
    tool for tool in PR_REVIEW_TOOLS
    if tool["name"] in {"get_pull_request", "get_pr_files", "get_pr_diff"}
]

CRITIC_TOOLS = [
    tool for tool in PR_REVIEW_TOOLS
    if tool["name"] in {"get_pr_diff", "get_file_content"}
]


TOOL_FUNCTIONS = {
    "get_pull_request": get_pull_request,
    "get_pr_files": get_pr_files,
    "get_pr_diff": get_pr_diff,
    "get_file_content": get_file_content,
}


def dispatch(tool_name: str, tool_input: dict) -> str:
    """Call the matching GitHub tool function."""
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return f"Error: Unknown tool '{tool_name}'"
    try:
        return fn(**tool_input)
    except TypeError as e:
        return f"Error calling {tool_name}: {e}"
