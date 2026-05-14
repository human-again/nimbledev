"""
observability/logger.py
-----------------------
Module 6: Structured logging setup for NimbleDev.

TEACHING NOTE — Why observability matters for agents:

  Traditional software is deterministic: given the same input, you always
  get the same output. Debugging is straightforward — add a print, run it,
  see what happened.

  Agents are NON-DETERMINISTIC. The same issue might trigger different tool
  calls on different runs. The LLM might take a different path through the
  problem. A fix that worked yesterday might not work today.

  This makes debugging MUCH harder without proper observability:
    - Without logs: "something went wrong, which turn? which tool? no idea"
    - With logs: "turn 3, get_file_content failed, 1.2s, result=404"

  Three things you need for good agent observability:
    1. STRUCTURED LOGS: JSON lines that can be queried and filtered
       (not plain print statements)
    2. TRACE IDs: A unique ID per pipeline run that ties all logs together
       across multiple agents
    3. TOKEN TRACKING: LLM calls cost money. Knowing which agent and turn
       consumed how many tokens lets you optimise and budget.

TEACHING NOTE — Structured logging vs print statements:

  print(f"Calling {tool_name}") → hard to query, no metadata, no timestamps

  structlog with JSON output:
    {"event": "tool_call", "tool": "get_file_content", "duration_ms": 340,
     "result_len": 4200, "trace_id": "abc123", "timestamp": "..."}

  You can then grep, jq-filter, or pipe into any log aggregation system
  (Datadog, CloudWatch, Grafana) without changing your code.

TEACHING NOTE — Trace IDs for multi-agent correlation:

  When four agents run in sequence, each emitting dozens of log lines,
  you need a way to answer: "show me all logs from the run that failed."

  The answer is a trace_id — a UUID generated once per pipeline run and
  passed to every agent. Every log line includes it. Then:

    grep '"trace_id": "abc123"' run_log.jsonl  # all logs for this run

  This is standard practice in microservices (OpenTelemetry) applied to
  multi-agent AI systems.
"""

import uuid
import logging
import sys
from typing import Any

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


def new_trace_id() -> str:
    """Generate a short UUID trace ID for a pipeline run."""
    return str(uuid.uuid4())[:8]


def get_logger(name: str = "nimbledev") -> Any:
    """
    Get a structured logger.

    Returns a structlog logger if structlog is installed,
    falls back to stdlib logging with a structured format.
    """
    if _HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.dev.ConsoleRenderer()
                if sys.stderr.isatty()
                else structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
        return structlog.get_logger(name)
    else:
        # Fallback: stdlib logger with structured-ish format
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    fmt='{"time": "%(asctime)s", "level": "%(levelname)s", '
                        '"logger": "%(name)s", "event": "%(message)s"}',
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
