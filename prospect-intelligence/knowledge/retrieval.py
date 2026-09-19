"""
Retrieval functions - scoped exclusively to the coextend_knowledge collection.
Uses Gemini embeddings (free tier) with in-memory caching, batching, and hard timeouts.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Sequence

import chromadb
from google import genai

from config import settings
from knowledge.ingestion import COLLECTION_NAME, _get_chroma_client

logger = logging.getLogger(__name__)

# In-memory cache for query embeddings to avoid duplicate API calls
_EMBED_CACHE: dict[str, list[float]] = {}
_GENAI_CLIENT: genai.Client | None = None
_EMBED_TIMEOUT = 12.0  # seconds per batch embedding call


def _get_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        _GENAI_CLIENT = genai.Client(api_key=settings.gemini_api_key)
    return _GENAI_CLIENT


@dataclass
class KnowledgeChunk:
    text: str
    source_document: str
    section: str
    page: int
    score: float


async def _get_embeddings_batch(queries: Sequence[str]) -> list[list[float]]:
    """Embed multiple query strings in a single batch API call with caching and hard timeout."""
    needed = [q for q in queries if q not in _EMBED_CACHE]
    if needed:
        client = _get_client()

        def _embed():
            result = client.models.embed_content(
                model=settings.gemini_embed_model,
                contents=needed,
            )
            return [list(e.values) for e in result.embeddings]

        loop = asyncio.get_running_loop()
        try:
            new_embeddings = await asyncio.wait_for(
                loop.run_in_executor(None, _embed),
                timeout=_EMBED_TIMEOUT,
            )
            for q, emb in zip(needed, new_embeddings):
                _EMBED_CACHE[q] = emb
        except asyncio.TimeoutError:
            logger.warning("Batch embedding timed out after %ds for %d queries", _EMBED_TIMEOUT, len(needed))
            raise RuntimeError(f"embedding_timeout: Gemini embed call timed out after {_EMBED_TIMEOUT}s")
        except Exception as exc:
            exc_str = str(exc)
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                logger.error("Gemini embedding rate limit hit: %s", exc)
                raise RuntimeError(f"failed:rate_limited (Gemini embedding API: {exc})") from exc
            raise

    return [_EMBED_CACHE[q] for q in queries if q in _EMBED_CACHE]


async def warm_embed_cache() -> None:
    """Pre-warm embeddings for canonical queries at startup so RAG retrieval is instant."""
    canonical = [
        "Coextend services facade cladding estimating BIM shop drawings",
        "Coextend ideal customer profile ICP criteria",
        "recommended sales outreach positioning strategy",
        "Coextend capabilities positioning outsourcing value proposition",
    ]
    try:
        await _get_embeddings_batch(canonical)
        logger.info("Pre-warmed embedding cache with %d canonical knowledge queries", len(canonical))
    except Exception as exc:
        logger.warning("Could not pre-warm embedding cache: %s", exc)


async def retrieve(query: str, top_k: int = 5) -> list[KnowledgeChunk]:
    """
    Retrieve top-k internal-knowledge chunks for a single query.
    Returns empty list (never raises) if collection unavailable.
    """
    results = await retrieve_batch([query], top_k=top_k)
    return results


async def retrieve_batch(queries: Sequence[str], top_k: int = 5) -> list[KnowledgeChunk]:
    """
    Retrieve top-k internal-knowledge chunks for multiple queries in a single batched operation.
    Deduplicates results across all queries.
    """
    if not queries:
        return []

    try:
        query_embeddings = await _get_embeddings_batch(queries)
        if not query_embeddings or len(query_embeddings) != len(queries):
            return []

        chroma = _get_chroma_client()
        try:
            collection = chroma.get_collection(COLLECTION_NAME)
        except Exception:
            logger.warning(
                "Knowledge collection '%s' not found - run /knowledge/ingest first.",
                COLLECTION_NAME,
            )
            return []

        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[KnowledgeChunk] = []
        seen_texts: set[str] = set()

        all_docs = results.get("documents", [])
        all_metas = results.get("metadatas", [])
        all_dists = results.get("distances", [])

        for q_idx in range(len(queries)):
            docs = all_docs[q_idx] if q_idx < len(all_docs) else []
            metas = all_metas[q_idx] if q_idx < len(all_metas) else []
            dists = all_dists[q_idx] if q_idx < len(all_dists) else []

            for doc, meta, dist in zip(docs, metas, dists):
                if doc in seen_texts:
                    continue
                seen_texts.add(doc)
                similarity = max(0.0, 1.0 - dist)
                chunks.append(
                    KnowledgeChunk(
                        text=doc,
                        source_document=meta.get("source_document", "unknown"),
                        section=meta.get("section", ""),
                        page=meta.get("page", 0),
                        score=similarity,
                    )
                )

        logger.debug("Retrieved %d unique chunks for %d queries", len(chunks), len(queries))
        return chunks

    except Exception as exc:
        logger.error("Batch retrieval failed: %s", exc)
        return []


def format_chunks_for_prompt(chunks: list[KnowledgeChunk]) -> str:
    if not chunks:
        return "(No internal knowledge retrieved for this query.)"
    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[{i}] Source: {chunk.source_document!r} | Section: {chunk.section!r} | Page: {chunk.page}\n"
            f"{chunk.text}"
        )
    return "\n\n---\n\n".join(lines)