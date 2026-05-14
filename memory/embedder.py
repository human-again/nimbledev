"""
memory/embedder.py
------------------
Module 7: Text embedding for semantic memory retrieval.

TEACHING NOTE — Embeddings explained simply:

  An embedding is a list of numbers (a vector) that captures the *meaning*
  of a piece of text in high-dimensional space.

  Similar meanings → similar vectors → small distance between them
  Different meanings → different vectors → large distance

  Example:
    embed("authentication bug in JWT token") → [0.12, -0.34, 0.88, ...]
    embed("login fails with expired credentials") → [0.11, -0.31, 0.85, ...]
    embed("database connection timeout") → [-0.42, 0.67, -0.11, ...]

  The first two are semantically similar (both about auth) so their vectors
  are close. The third is different (database, not auth) so it's far away.

  This lets us answer: "what past analyses are similar to this new issue?"
  by computing distances — without any keyword matching.

TEACHING NOTE — Why sentence-transformers over Anthropic embeddings API:

  We use sentence-transformers (all-MiniLM-L6-v2) because:
    - It's LOCAL: no API call, no cost, no rate limit
    - It's FAST: small model, runs on CPU in milliseconds
    - It's GOOD ENOUGH: 384-dim embeddings, strong semantic similarity
    - It's SIMPLE: one pip install, one function call

  Anthropic's embedding API (voyage-*) is better quality but:
    - Costs tokens per call
    - Adds network latency
    - Needs API key management

  For a local tutorial system, sentence-transformers is the right choice.
  For production systems handling millions of queries, use the best available
  embedding model.
"""

from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    _model: Optional[SentenceTransformer] = None

    def _get_model() -> SentenceTransformer:
        global _model
        if _model is None:
            # all-MiniLM-L6-v2: fast, small, strong semantic quality
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        return _model

    def embed(text: str) -> list[float]:
        """
        Embed text into a 384-dimensional vector.

        Args:
            text: The text to embed (a few sentences is ideal)

        Returns:
            List of 384 floats representing the text's meaning
        """
        model = _get_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    HAS_SENTENCE_TRANSFORMERS = True

except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

    def embed(text: str) -> list[float]:  # type: ignore[misc]
        """
        Fallback embedder when sentence-transformers is not installed.
        Returns a zero vector — memory retrieval will not work but won't crash.
        """
        # 384 zeros — same dimension as all-MiniLM-L6-v2
        return [0.0] * 384
