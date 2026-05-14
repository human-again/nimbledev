# Module 6: Observability — Logging, Tokens, and Trace IDs

## What We Built

Three files in `observability/`:
- `logger.py` — structured logging with structlog (falls back to stdlib)
- `tracker.py` — per-agent token usage, tool call counts, and timing
- `__init__.py` — clean imports

The tracker wraps the full `cmd_fix()` pipeline in `main.py`, printing a summary table and appending a JSON line to `observability/run_log.jsonl`.

## How to Run It

Observability is automatic when you run `fix`:

```bash
uv run main.py fix https://github.com/psf/requests/issues/6730
```

At the end of the run, you'll see:

```
 Run Summary  (trace: abc12345)
┌─────────────────────┬───────┬────────────┬───────────┬────────────┬──────────┬────────────┐
│ Agent               │ Turns │ Tool Calls │ Input Tok │ Output Tok │ Duration │ Cost (USD) │
├─────────────────────┼───────┼────────────┼───────────┼────────────┼──────────┼────────────┤
│ issue_reader        │     5 │          4 │    12,400 │      1,200 │    18.2s │    $0.0550 │
│ code_analyst        │     8 │          7 │    28,600 │      2,100 │    34.7s │    $0.1174 │
│ fix_writer_attempt_1│     6 │          5 │    18,900 │      3,800 │    26.3s │    $0.1139 │
│ reviewer_attempt_1  │     1 │          0 │     4,200 │        380 │     3.1s │    $0.0183 │
│ pr_agent            │     - │          - │         0 │          0 │     8.4s │    $0.0000 │
├─────────────────────┼───────┼────────────┼───────────┼────────────┼──────────┼────────────┤
│ TOTAL               │    20 │         16 │    64,100 │      7,480 │    90.7s │    $0.3046 │
└─────────────────────┴───────┴────────────┴───────────┴────────────┴──────────┴────────────┘
```

## Key New Concept: Observability for Non-Deterministic Systems

### Why Agents Are Hard to Debug

Traditional software: same input → same output every time. Add a print, run it, see what happened.

Agents: same input → different tool call sequences, different turns, different costs. A bug might only manifest 1 in 5 runs.

Without observability:
> "Something went wrong. Which agent? Which turn? Which tool call? No idea."

With observability:
> "Turn 3, fix_writer_attempt_2, get_file_content returned 404 for 'src/auth/middleware.py', duration 0.8s"

### Structured Logging vs Print Statements

```python
# Bad: unqueryable, no metadata
print(f"Calling {tool_name}")

# Good: JSON-queryable, has context
log.info("tool_call", tool=tool_name, duration_ms=340, result_len=4200, trace_id="abc123")
```

With JSON logs, you can query:
```bash
grep '"tool": "get_file_content"' run_log.jsonl | jq '.duration_ms' | sort -n
```

### Trace IDs for Multi-Agent Correlation

When 5 agents emit 50+ log lines each, you need a way to group them by run:

```python
trace_id = new_trace_id()  # "abc12345" — generated once per pipeline run
tracker = RunTracker(trace_id=trace_id, command="fix")
```

Every log line and every run_log.jsonl entry includes this trace_id. To find all logs for a failed run: `grep "abc12345" run_log.jsonl`.

### Token Tracking for Cost Management

```python
def record_turn(self, stats: AgentStats, response: object) -> None:
    usage = getattr(response, "usage", None)
    if usage:
        stats.input_tokens += usage.input_tokens
        stats.output_tokens += usage.output_tokens
```

This tells you which agent is expensive and where to optimise (e.g. truncate file reads, reduce system prompt length).

## Things to Try

1. Run the pipeline twice and compare token counts in `run_log.jsonl`
2. Add `tracker.record_tool_call(stats, block.name)` inside an agent's tool loop
3. Install structlog (`uv add structlog`) and see the prettier log output

## What's Next

Module 7: **RAG + Memory** — store past analyses in a vector database so future runs learn from past ones.
