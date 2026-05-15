# Contributing to NimbleDev

Thanks for your interest in contributing.

## Development Setup

1. Clone the repo and run:

```bash
./setup.sh
```

2. Configure `.env` with required values:

```bash
LLM_PROVIDER=anthropic
MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=...
GITHUB_TOKEN=...
```

## Run Tests

Use the local virtual environment for all checks:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Pull Request Guidelines

1. Keep PRs focused on one concern.
2. Add or update tests for behavior changes.
3. Update docs when user-facing behavior or setup changes.
4. Prefer small, reviewable commits.
5. Include a clear PR description:
   - Problem
   - Approach
   - Validation performed

## Review Expectations

- Changes should preserve schema contracts (`DiffSummary`, `PRReview`).
- Retries and structured-output validation should remain covered by tests.
- New provider support should go through the `LLMClient` adapter boundary.

## Good First Contributions

- Add fixture-based eval cases for PR review quality.
- Improve context-file retrieval strategy.
- Improve traces and cost telemetry.
- Expand docs for contributor workflows.
