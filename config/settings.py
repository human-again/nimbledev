"""
config/settings.py
------------------
Central place for all configuration.
Loads from .env so secrets never live in code.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    """Get an env var or raise a clear error if it's missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Check your .env file (copy .env.example to get started)."
        )
    return value


ANTHROPIC_API_KEY = require("ANTHROPIC_API_KEY")
GITHUB_TOKEN = require("GITHUB_TOKEN")

MODEL = os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-6"

GITHUB_API_BASE = "https://api.github.com"
GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
