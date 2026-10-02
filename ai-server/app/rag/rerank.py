"""Re-ranking: cross-encoder over the hybrid top-N.

Funnel: hybrid search nominates CANDIDATES chunks cheaply; the
cross-encoder reads (query, chunk) PAIRS jointly and re-scores them;
keep the top k. The bi-encoder asks "do these vectors point the same
way?"; the cross-encoder asks "does this passage answer this query?" —
a strictly harder question it can only afford on a shortlist.

Model: BAAI/bge-reranker-base, run locally via sentence-transformers.
    pip install sentence-transformers --break-system-packages? no — plain:
    pip install sentence-transformers torch
First call downloads ~1.1GB and is slow; afterwards ~0.5-2s per query
on CPU for 20 candidates. That latency is the cost you're measuring.
"""

import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.rag.hybrid import search_hybrid
from app.rag.retrieval import RetrieveChunk, RetrieveResult

RERANK_CANDIDATES = 20   # how many hybrid results the cross-encoder scores
RERANK_MODEL = "BAAI/bge-reranker-base"

_model = None  # loaded lazily: importing this module must stay cheap


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(RERANK_MODEL, max_length=512)
    return _model


def _score_pairs(query: str, texts: list[str]) -> list[float]:
    """Blocking model inference. Called via asyncio.to_thread."""
    model = _get_model()
    return model.predict([(query, t) for t in texts]).tolist()


async def search_reranked(
    session: AsyncSession,
    query: str,
    k: int = 5,
    strategy: str = FIXED_STRATEGY_LABEL,
) -> RetrieveResult:
    # Stage 1: cheap nomination — hybrid top-N.
    nominated = await search_hybrid(session, query, k=RERANK_CANDIDATES, strategy=strategy)

    # Stage 2: careful re-scoring. The model call is CPU-bound and
    # blocking, so it runs in a thread to keep the event loop free.
    t0 = time.perf_counter()
    scores = await asyncio.to_thread(
        _score_pairs, query, [c.content for c in nominated.chunks]
    )
    rerank_ms = int((time.perf_counter() - t0) * 1000)

    ranked = sorted(zip(nominated.chunks, scores), key=lambda p: p[1], reverse=True)[:k]

    chunks = [
        RetrieveChunk(
            chunk_id=c.chunk_id,
            source=c.source,
            title=c.title,
            char_start=c.char_start,
            char_end=c.char_end,
            content=c.content,
            distance=c.distance,
            # cross-encoder raw score (unbounded logit); higher = better.
            # Comparable within one response only, like the RRF score.
            similarity=round(float(s), 4),
        )
        for c, s in ranked
    ]
    return RetrieveResult(
        chunks=chunks,
        embed_ms=nominated.embed_ms,
        search_ms=nominated.search_ms,
        rerank_ms=rerank_ms,
    )


if __name__ == "__main__":
    # python -m app.rag.rerank "What is the difference between send() and raise_() on a StateChart?"
    import sys

    from app.lib.alchemy_db import SessionLocal, engine

    async def main() -> None:
        query = sys.argv[1] if len(sys.argv) > 1 else "what does async def do?"
        try:
            async with SessionLocal() as session:
                hyb = await search_hybrid(session, query)
                rr = await search_reranked(session, query)
            print(f"query: {query!r}")
            print(f"rerank cost: {rr.rerank_ms}ms over {RERANK_CANDIDATES} candidates\n")
            print("hybrid top-5:")
            for c in hyb.chunks:
                print(f"  [{c.chunk_id}] {c.source}")
            print("reranked top-5:")
            for c in rr.chunks:
                print(f"  [{c.chunk_id}] score={c.similarity:+.3f}  {c.source}")
        finally:
            await engine.dispose()

    asyncio.run(main())