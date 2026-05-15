#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3.10 >/dev/null 2>&1; then
  cat <<'EOF'
python3.10 was not found on your machine.

Install Python 3.10, then run this again:
  ./setup.sh

Common options:
  macOS with Homebrew: brew install python@3.10
  python.org installer: https://www.python.org/downloads/release/python-31011/
EOF
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment with python3.10..."
  python3.10 -m venv .venv
else
  echo "Using existing .venv..."
fi

echo "Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip

echo "Installing NimbleDev dependencies..."
.venv/bin/pip install -e .

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your API keys before running commands."
fi

cat <<'EOF'

Setup complete.

Next steps:
  1. Open .env and fill in ANTHROPIC_API_KEY and GITHUB_TOKEN
     Optional: adjust LLM_PROVIDER and MODEL
  2. Run one of these commands:

     .venv/bin/python main.py --help
     .venv/bin/python main.py review-pr https://github.com/psf/requests/pull/6745
EOF
