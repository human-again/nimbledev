# Module 7: RAG + Memory — Teaching Agents to Learn

## What We Built

Three files in `memory/`:
- `embedder.py` — text → vector using sentence-transformers (all-MiniLM-L6-v2)
- `store.py` — `MemoryStore` class wrapping Chroma vector DB
- `__init__.py` — clean imports

`config/settings.py` gains `MEMORY_DIR` pointing to `.nimbledev_memory/`.

`main.py`'s `cmd_fix()` uses memory in two ways:
- **Retrieve** top-3 similar past analyses before Issue Reader runs
- **Store** each new CodeAnalysis after it completes

## How to Run It

Install the dependencies:
```bash
uv add chromadb sentence-transformers
```

Memory is automatic when you run `fix`:
```bash
uv run main.py fix https://github.com/psf/requests/issues/6730
```

After the first run, `.nimbledev_memory/` will contain the Chroma database. On subsequent runs targeting similar issues, the agents will receive context like:

```
## Similar past analyses (from memory)

1. [psf/requests#6730] (similarity: 87%)
   repo: psf/requests, issue: #6730, root_cause: missing timeout in session...
   Metadata: {'repo': 'psf/requests', 'confidence': 'high'}
```

## Key New Concept: Embeddings and RAG

### Embeddings Explained Simply

An embedding is a list of numbers that captures the *meaning* of text:

```python
embed("authentication bug in JWT token")    → [0.12, -0.34, 0.88, ...]
embed("login fails with expired credentials") → [0.11, -0.31, 0.85, ...]
embed("database connection timeout")          → [-0.42, 0.67, -0.11, ...]
```

The first two vectors are close (both about auth). The third is far away (different topic). This lets us find semantically similar text **without keyword matching**.

### The Store → Retrieve → Inject Pattern

```python
# STORE: after a successful CodeAnalysis
store = MemoryStore("code_analyses")
store.store(
    id="psf/requests#6730",
    text=f"root_cause: {analysis.root_cause}, fix_approach: {analysis.fix_approach}",
    metadata={"repo": "psf/requests", "issue_number": 6730}
)

# RETRIEVE: before the next run
results = store.retrieve("JWT expiry not handled in session", n_results=3)
context = store.format_for_prompt(results)
# → "Similar past analyses:\n1. [psf/requests#6730] ..."

# INJECT: prepend to agent's user message
user_message = f"{context}\n\n{issue_analysis}"
```

### Chroma: A Local Vector Database

Chroma stores vectors persistently on disk (like SQLite for vectors). No server needed:

```python
client = chromadb.PersistentClient(path=".nimbledev_memory")
collection = client.get_or_create_collection("code_analyses")
collection.upsert(ids=[id], embeddings=[vector], documents=[text])
results = collection.query(query_embeddings=[vector], n_results=3)
```

### When Memory Helps vs Hurts

**Memory helps when:**
- The same type of bug appears in different repos (pattern recognition)
- A past fix informs how to approach a similar new issue

**Memory hurts when:**
- Retrieved entries are only superficially similar but semantically different
- Retrieved context is too long and crowds out the actual task

**Mitigation:** limit to top-3 results, truncate to a few sentences each, let the agent decide how much weight to give past context.

## Things to Try

1. Run `fix` on two similar issues and check if memory helps the second run
2. Query the store directly: `store.retrieve("authentication timeout", n_results=5)`
3. Add PR reviews to memory (store `PRReview.summary` in a `"pr_reviews"` collection)

## What's Next

Module 8: **MCP Server** — expose NimbleDev's GitHub tools as a proper MCP server so they can be used by any MCP-compatible agent or client.
