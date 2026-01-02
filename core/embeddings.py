"""
Embedding utilities for vector search.

Provides efficient batched embedding generation using OpenRouter.
"""

import logging
import numpy as np
from typing import List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Singleton embedding client
_embedding_cache: dict = {}


def get_embeddings(texts: List[str], model: str = None) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Uses OpenRouter's embedding API with batching for efficiency.
    Results are cached in-memory to avoid redundant API calls.

    Args:
        texts: List of texts to embed
        model: Embedding model (defaults to config)

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    from core.config import config
    from core.llm_client import get_openai_client

    model = model or config.embedding_model
    client = get_openai_client()

    # Check cache for already embedded texts
    results = []
    texts_to_embed = []
    cache_indices = []

    for i, text in enumerate(texts):
        cache_key = f"{model}:{hash(text)}"
        if cache_key in _embedding_cache:
            results.append((i, _embedding_cache[cache_key]))
        else:
            texts_to_embed.append(text)
            cache_indices.append(i)

    # Embed uncached texts
    if texts_to_embed:
        try:
            response = client.embeddings.create(
                model=model,
                input=texts_to_embed
            )

            for j, embedding_data in enumerate(response.data):
                emb = np.array(embedding_data.embedding, dtype=np.float32)
                original_idx = cache_indices[j]
                results.append((original_idx, emb))

                # Cache result
                cache_key = f"{model}:{hash(texts_to_embed[j])}"
                _embedding_cache[cache_key] = emb

        except Exception as e:
            logger.error(f"Embedding API error: {e}")
            # Return zero vectors on error
            dim = 1536  # Default for text-embedding-3-small
            for idx in cache_indices:
                results.append((idx, np.zeros(dim, dtype=np.float32)))

    # Sort by original index and extract embeddings
    results.sort(key=lambda x: x[0])
    embeddings = np.array([r[1] for r in results])

    return embeddings


def get_embedding(text: str, model: str = None) -> np.ndarray:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed
        model: Embedding model (defaults to config)

    Returns:
        numpy array of shape (embedding_dim,)
    """
    return get_embeddings([text], model)[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity score (-1 to 1)
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def batch_cosine_similarity(query: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between query and multiple vectors.

    Optimized for batch operations.

    Args:
        query: Query vector of shape (dim,)
        vectors: Matrix of vectors of shape (n, dim)

    Returns:
        Array of similarities of shape (n,)
    """
    if len(vectors) == 0:
        return np.array([])

    # Normalize query
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return np.zeros(len(vectors))
    query_normalized = query / query_norm

    # Normalize vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    vectors_normalized = vectors / norms

    # Batch dot product
    return np.dot(vectors_normalized, query_normalized)


def clear_embedding_cache():
    """Clear the embedding cache."""
    global _embedding_cache
    _embedding_cache = {}
    logger.info("Embedding cache cleared")
