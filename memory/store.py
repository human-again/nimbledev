"""
memory/store.py
---------------
Module 7: Chroma vector database wrapper for agent memory.

TEACHING NOTE — What RAG is and why agents need it:

  RAG = Retrieval-Augmented Generation

  The problem: LLMs have no persistent memory. Every time you run an agent,
  it starts from scratch. It doesn't remember that you fixed a similar
  authentication bug last week in a different repo.

  The solution: before each agent run, retrieve relevant past analyses from
  a vector database and inject them as context:

    "Similar past analyses:
      1. [repo: psf/requests, issue #6730] Root cause: missing timeout...
      2. [repo: django/django, issue #14823] Root cause: middleware order..."

  This lets agents learn from past runs without re-running all previous work.

TEACHING NOTE — Chroma as a local vector DB:

  Chroma is an open-source, embedded vector database — it runs in-process,
  stores data locally (like SQLite), and needs no server setup.

  Alternatives:
    - Pinecone: fully managed, great for production, costs money
    - Weaviate: powerful, complex to self-host
    - FAISS: fast, no persistence, pure in-memory
    - pgvector: Postgres extension, SQL-friendly

  For a local tutorial, Chroma is the right call: zero infrastructure,
  persistent across runs, simple Python API.

TEACHING NOTE — The retrieve-then-inject pattern:

  The pattern has two phases:

  STORE phase (after a successful run):
    1. Summarise the result as a short text
    2. Embed it (convert to vector)
    3. Store vector + metadata in Chroma

  RETRIEVE phase (before the next run):
    1. Embed the current task description
    2. Find the k closest stored vectors (semantic similarity)
    3. Return their metadata as context strings
    4. Prepend to the agent's user message: "Similar past analyses: ..."

TEACHING NOTE — When memory helps vs hurts (context pollution):

  Memory HELPS when:
    - The same type of bug appears in different repos (pattern recognition)
    - A past fix for repo A informs how to approach repo B
    - You want to avoid repeating the same mistakes

  Memory HURTS when:
    - Retrieved entries are only superficially similar but semantically different
    - Retrieved context is too long and crowds out the actual task
    - Stale memories conflict with current code structure

  Mitigation:
    - Limit to top-3 results (we do this)
    - Truncate retrieved entries to a few sentences each
    - Let the agent decide how much weight to give past context
"""

import os
from typing import Optional

from config.settings import MEMORY_DIR

try:
    import chromadb
    _HAS_CHROMADB = True
except ImportError:
    _HAS_CHROMADB = False

from memory.embedder import embed


class MemoryStore:
    """
    A semantic memory store backed by Chroma.

    Each MemoryStore instance is a named collection within the same Chroma DB.
    Use separate collection_names for different types of memories:
      - "code_analyses"  for CodeAnalysis results
      - "pr_reviews"     for PRReview results

    Usage:
        store = MemoryStore("code_analyses")
        store.store(
            id="psf/requests#6730",
            text="authentication bug: missing timeout in session...",
            metadata={"repo": "psf/requests", "issue_number": 6730}
        )
        results = store.retrieve("JWT token expiry not handled", n_results=3)
    """

    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self._client = None
        self._collection = None

        if not _HAS_CHROMADB:
            import warnings
            warnings.warn(
                "chromadb not installed — memory will not persist. "
                "Install with: uv add chromadb",
                stacklevel=2,
            )

    def _ensure_collection(self):
        """Lazy-initialise Chroma client and collection."""
        if self._collection is not None:
            return

        if not _HAS_CHROMADB:
            return

        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._client = chromadb.PersistentClient(path=MEMORY_DIR)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity for text
        )

    def store(self, id: str, text: str, metadata: dict) -> None:
        """
        Embed and store a memory entry.

        Args:
            id:       Unique identifier (e.g. "psf/requests#6730")
            text:     The text to embed (what the semantic search will match)
            metadata: Any JSON-serialisable dict to store alongside the vector
        """
        self._ensure_collection()
        if self._collection is None:
            return  # chromadb not available

        vector = embed(text)

        # Chroma upserts — if id already exists, update it
        self._collection.upsert(
            ids=[id],
            embeddings=[vector],
            documents=[text],
            metadatas=[metadata],
        )

    def retrieve(self, query: str, n_results: int = 3) -> list[dict]:
        """
        Find the most semantically similar stored entries.

        Args:
            query:     The text to search for similar entries
            n_results: How many results to return (default 3)

        Returns:
            List of dicts, each with keys:
              - id:       the stored ID
              - text:     the stored document text
              - metadata: the stored metadata dict
              - distance: cosine distance (0 = identical, 2 = opposite)
        """
        self._ensure_collection()
        if self._collection is None:
            return []

        count = self._collection.count()
        if count == 0:
            return []

        # Can't request more results than exist
        n = min(n_results, count)
        vector = embed(query)

        results = self._collection.query(
            query_embeddings=[vector],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return output

    def format_for_prompt(self, results: list[dict], header: str = "Similar past analyses") -> str:
        """
        Format retrieved entries for injection into an agent's prompt.

        Args:
            results: Output of retrieve()
            header:  Section header text

        Returns:
            A formatted string to prepend to the agent's user message
        """
        if not results:
            return ""

        lines = [f"## {header} (from memory)\n"]
        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            similarity = 1.0 - r["distance"]  # convert distance to similarity
            lines.append(f"{i}. [{r['id']}] (similarity: {similarity:.0%})")
            lines.append(f"   {r['text'][:200]}")
            if meta:
                # Show a few key metadata fields
                key_fields = {k: v for k, v in meta.items() if k in (
                    "repo", "issue_number", "pr_number", "root_cause",
                    "fix_approach", "verdict",
                )}
                if key_fields:
                    lines.append(f"   Metadata: {key_fields}")
            lines.append("")

        return "\n".join(lines)
