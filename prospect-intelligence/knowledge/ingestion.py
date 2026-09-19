"""
Knowledge ingestion pipeline.
Extracts text from all PDFs in the knowledge_base_path, chunks them
(heading-aware), embeds them, and stores them in a ChromaDB collection
called 'coextend_knowledge'.

Run once at deploy time, or on-demand via POST /knowledge/ingest.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Generator

import chromadb

from config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "coextend_knowledge"
CHUNK_SIZE_TOKENS = 600          # approximate; we split on char count (1 token ≈ 4 chars)
CHUNK_OVERLAP_CHARS = 100
MAX_CHARS_PER_CHUNK = CHUNK_SIZE_TOKENS * 4   # ~2 400 chars
OVERLAP_CHARS = CHUNK_OVERLAP_CHARS


def _get_chroma_client() -> chromadb.ClientAPI:
    Path(settings.vector_store_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=settings.vector_store_path)


def _get_or_create_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Returns a list of {page: int, text: str} dicts.
    Falls back to empty list if the PDF cannot be parsed.
    """
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i + 1, "text": text})
        return pages
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", pdf_path.name, exc)
        return []


# ---------------------------------------------------------------------------
# Heading-aware chunking
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,4}\s+.+|^[A-Z][A-Z\s]{4,}$", re.MULTILINE)


def _split_into_chunks(text: str, source_doc: str, page: int) -> Generator[dict, None, None]:
    """
    Yields chunk dicts: {text, source_document, section, page, chunk_index}.
    Splits on heading boundaries first, then hard-splits oversized pieces.
    """
    # Find all heading positions
    heading_positions = [m.start() for m in _HEADING_RE.finditer(text)]
    heading_positions.append(len(text))  # sentinel

    current_section = "Introduction"
    chunk_index = 0

    segments: list[tuple[str, str]] = []
    prev = 0
    for pos in heading_positions:
        if pos == 0:
            continue
        segment_text = text[prev:pos].strip()
        if segment_text:
            segments.append((segment_text, current_section))
        # Update current_section to the heading at `pos`
        if pos < len(text):
            end = text.find("\n", pos)
            end = end if end != -1 else len(text)
            current_section = text[pos:end].strip().lstrip("#").strip()
        prev = pos

    # Hard-split large segments
    for seg_text, section in segments:
        start = 0
        while start < len(seg_text):
            end = min(start + MAX_CHARS_PER_CHUNK, len(seg_text))
            chunk_text = seg_text[start:end].strip()
            if chunk_text:
                yield {
                    "text": chunk_text,
                    "source_document": source_doc,
                    "section": section,
                    "page": page,
                    "chunk_index": chunk_index,
                }
                chunk_index += 1
            start = end - OVERLAP_CHARS if end < len(seg_text) else end


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using Gemini embedding model with rate pacing and exponential retry."""
    import asyncio
    import time
    from google import genai
    from google.genai.errors import ClientError

    client = genai.Client(api_key=settings.gemini_api_key)
    all_embeddings: list[list[float]] = []
    batch_size = 20  # Safe batch size for free tier

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        
        # Retry with exponential backoff on 429
        max_retries = 8
        backoff = 4.0
        success = False

        for attempt in range(max_retries):
            try:
                def _do(b=batch):
                    result = client.models.embed_content(
                        model=settings.gemini_embed_model,
                        contents=b,
                    )
                    return [list(e.values) for e in result.embeddings]

                batch_embs = await asyncio.get_event_loop().run_in_executor(None, _do)
                all_embeddings.extend(batch_embs)
                success = True
                break
            except Exception as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    logger.warning("Gemini embed rate limit hit (attempt %d/%d). Backing off %.1fs...", attempt + 1, max_retries, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.8, 45.0)
                else:
                    logger.error("Gemini embed error: %s", exc)
                    raise exc
        
        if not success:
            raise RuntimeError(f"Failed to embed batch {i}..{i+len(batch)} after {max_retries} retries due to quota limits.")
        
        # Small delay between batches to stay under rate caps
        await asyncio.sleep(1.0)

    return all_embeddings


# ---------------------------------------------------------------------------
# Main ingestion entry point
# ---------------------------------------------------------------------------

async def ingest_knowledge_base() -> int:
    """
    (Re)ingest all PDFs from knowledge_base_path.
    Clears and repopulates the ChromaDB collection so stale chunks are removed.
    Returns the total number of chunks indexed.
    """
    kb_path = Path(settings.knowledge_base_path)
    pdf_files = list(kb_path.glob("*.pdf")) + list(kb_path.glob("*.PDF"))

    if not pdf_files:
        logger.warning("No PDF files found in %s", kb_path)
        return 0

    logger.info("Ingesting %d PDFs from %s", len(pdf_files), kb_path)

    # Collect all chunks first so we can batch-embed them
    all_chunks: list[dict] = []
    for pdf_path in pdf_files:
        pages = extract_text_from_pdf(pdf_path)
        source_doc = pdf_path.stem  # e.g. "03 - Company Capabilities"
        for page_data in pages:
            for chunk in _split_into_chunks(
                page_data["text"], source_doc, page_data["page"]
            ):
                all_chunks.append(chunk)

    # Deduplicate chunks by text content
    unique_chunks = []
    seen_texts = set()
    for c in all_chunks:
        t = c["text"].strip()
        if t and t not in seen_texts:
            seen_texts.add(t)
            unique_chunks.append(c)
    all_chunks = unique_chunks

    if not all_chunks:
        logger.warning("No text extracted from any PDF.")
        return 0

    logger.info("Embedding %d unique chunks …", len(all_chunks))
    texts = [c["text"] for c in all_chunks]
    embeddings = await _embed_texts(texts)

    # Rebuild the collection (delete + recreate to avoid stale data)
    chroma = _get_chroma_client()
    try:
        chroma.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = _get_or_create_collection(chroma)

    ids = [f"chunk_{i}" for i in range(len(all_chunks))]
    metadatas = [
        {
            "source_document": c["source_document"],
            "section": c["section"],
            "page": c["page"],
            "chunk_index": c["chunk_index"],
        }
        for c in all_chunks
    ]

    # ChromaDB upsert in batches of 500
    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            documents=texts[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    logger.info("Knowledge base ingestion complete: %d chunks indexed.", len(all_chunks))
    return len(all_chunks)
