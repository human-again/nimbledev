"""
observability/tracker.py
------------------------
Module 6: Per-run token, tool-call, and timing tracker.

Tracks every agent's resource consumption for a pipeline run, then renders
a summary table using rich and appends a JSON line to run_log.jsonl.

TEACHING NOTE — Token tracking for cost management:

  Every message.create() call returns response.usage with:
    - input_tokens:  tokens in the prompt + tool results
    - output_tokens: tokens in the assistant's response

  Cost = (input_tokens * price_in) + (output_tokens * price_out)

  For claude-sonnet-4-6 (as of 2025):
    input:  $3.00 / 1M tokens
    output: $15.00 / 1M tokens

  Without tracking, you have no idea which agent is expensive. With tracking:
    Fix Writer: 12,400 input + 3,200 output = ~$0.085 per run
    Reviewer:    2,100 input +   400 output = ~$0.012 per run

  This tells you where to optimise (e.g. truncate file reads in Fix Writer).
"""

import json
import time
import os
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

console = Console()

# Approximate costs for claude-sonnet-4-6 (per million tokens)
_COST_INPUT_PER_M = 3.00
_COST_OUTPUT_PER_M = 15.00


@dataclass
class AgentStats:
    """Stats for a single agent's execution within a run."""
    name: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None

    @property
    def duration_s(self) -> float:
        end = self.end_time if self.end_time else time.monotonic()
        return end - self.start_time

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * _COST_INPUT_PER_M
            + self.output_tokens / 1_000_000 * _COST_OUTPUT_PER_M
        )


class RunTracker:
    """
    Tracks a complete pipeline run across multiple agents.

    Usage:
        tracker = RunTracker(trace_id="abc123", command="fix")
        with tracker.agent("issue_reader") as stats:
            # inside the agent loop:
            tracker.record_turn(stats, response)
            tracker.record_tool_call(stats, "get_issue", ...)
        tracker.print_summary()
        tracker.save_log()
    """

    def __init__(self, trace_id: str, command: str):
        self.trace_id = trace_id
        self.command = command
        self.start_time = time.monotonic()
        self.agents: list[AgentStats] = []
        self._current: Optional[AgentStats] = None

    def start_agent(self, name: str) -> AgentStats:
        """Begin tracking a new agent."""
        stats = AgentStats(name=name)
        self.agents.append(stats)
        self._current = stats
        return stats

    def finish_agent(self, stats: AgentStats) -> None:
        """Mark an agent as done."""
        stats.end_time = time.monotonic()

    def record_turn(self, stats: AgentStats, response: object) -> None:
        """
        Record token usage from an API response.

        Call this after each client.messages.create() call.
        """
        stats.iterations += 1
        usage = getattr(response, "usage", None)
        if usage:
            stats.input_tokens += getattr(usage, "input_tokens", 0)
            stats.output_tokens += getattr(usage, "output_tokens", 0)

    def record_tool_call(self, stats: AgentStats, tool_name: str) -> None:
        """Increment tool call count for an agent."""
        stats.tool_calls += 1

    def total_tokens(self) -> int:
        return sum(a.total_tokens for a in self.agents)

    def total_cost_usd(self) -> float:
        return sum(a.estimated_cost_usd for a in self.agents)

    def total_duration_s(self) -> float:
        return time.monotonic() - self.start_time

    def print_summary(self) -> None:
        """Print a rich summary table of the run."""
        table = Table(
            title=f"Run Summary  [dim](trace: {self.trace_id})[/dim]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Agent", style="bold")
        table.add_column("Turns", justify="right")
        table.add_column("Tool Calls", justify="right")
        table.add_column("Input Tok", justify="right")
        table.add_column("Output Tok", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Cost (USD)", justify="right")

        for a in self.agents:
            table.add_row(
                a.name,
                str(a.iterations),
                str(a.tool_calls),
                f"{a.input_tokens:,}",
                f"{a.output_tokens:,}",
                f"{a.duration_s:.1f}s",
                f"${a.estimated_cost_usd:.4f}",
            )

        # Totals row
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            str(sum(a.iterations for a in self.agents)),
            str(sum(a.tool_calls for a in self.agents)),
            f"{sum(a.input_tokens for a in self.agents):,}",
            f"{sum(a.output_tokens for a in self.agents):,}",
            f"{self.total_duration_s():.1f}s",
            f"[bold]${self.total_cost_usd():.4f}[/bold]",
        )

        console.print()
        console.print(table)

    def save_log(self, log_path: Optional[str] = None) -> None:
        """Append a JSON line to run_log.jsonl."""
        if log_path is None:
            # Default: nimbledev root directory
            here = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(here, "..", "observability", "run_log.jsonl")
            log_path = os.path.normpath(log_path)

        record = {
            "trace_id": self.trace_id,
            "command": self.command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tokens": self.total_tokens(),
            "total_duration_s": round(self.total_duration_s(), 2),
            "estimated_cost_usd": round(self.total_cost_usd(), 6),
            "agents_run": [
                {
                    "name": a.name,
                    "iterations": a.iterations,
                    "tool_calls": a.tool_calls,
                    "input_tokens": a.input_tokens,
                    "output_tokens": a.output_tokens,
                    "duration_s": round(a.duration_s, 2),
                }
                for a in self.agents
            ],
        }

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        console.print(f"[dim]Run logged → {log_path}[/dim]")
