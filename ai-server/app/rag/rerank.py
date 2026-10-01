

import asyncio
import time
 
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.rag.hybrid import search_hybrid
from app.rag.retrieval import RetrieveChunk, RetrieveResult
 
RERANK_CANDIDATES = 20   # how many hybrid results the cross-encoder scores
RERANK_MODEL = "BAAI/bge-reranker-base"

_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(RERANK_MODEL, max_length=512)

    return _model

def _score_pairs(query:str, texts:list[str])->list[float]:
    model = _get_model()
    return model.predict([(query, t) for t in texts]).tolist()


async def search_reranked(session, query, k =RERANK_CANDIDATES, strategy:str=FIXED_STRATEGY_LABEL)->RetrieveResult:
    nominated = await search_hybrid(session, query, k, strategy)

    t0 = time.perf_counter 

    scores = await asyncio.to_thread(_score_pairs, query, nominated.chunks)

    rerank_ms = int((time.perf_counter() - t0) * 1000)

    ranked = sorted(zip(nominated.chunks, scores, key = lambda p: p[1], reverse=True))[:k]

    chunks = [RetrieveChunk(            
            chunk_id=c.chunk_id,
            source=c.source,
            title=c.title,
            char_start=c.char_start,
            char_end=c.char_end,
            content=c.content,
            distance=c.distance,
            # cross-encoder raw score (unbounded logit); higher = better.
            # Comparable within one response only, like the RRF score.
            similarity=round(float(s), 4)) for c, s in ranked]

    return RetrieveResult(
                chunks=chunks,
                embed_ms=nominated.embed_ms,
                search_ms=nominated.search_ms,
                rerank_ms=rerank_ms,

    )


if __name__ == "__main__":
    import sys
 
    from app.lib.alchemy_db import SessionLocal, engine
 
    async def main() -> None:
        query = sys.argv[1] if len(sys.argv) > 1 else "what does async def do?"
        print(query)
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
