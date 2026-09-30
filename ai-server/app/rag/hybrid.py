
from app.lib.alchemy_db import SessionLocal, engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.rag.chunking import chunk_text, FIXED_STRATEGY_LABEL
from app.rag.embedding import embed_text
from sqlalchemy import select, func
from app.rag.retrieval import RetrieveChunk, RetrieveResult
from app.models.pdf_schema import Document, Chunk
import time


CANDIDATES = 20
RRF_K = 60 

def _row_to_chunk(row, similarity: float) -> RetrieveChunk:
    return RetrieveChunk(
        chunk_id=row.id,
        source=row.source,
        title=row.title,
        char_start=row.char_start,
        char_end=row.char_end,
        content=row.content,
        distance=1.0 - similarity,
        similarity=similarity,
    )




 
async def _vector_candidates(
    session: AsyncSession, query_vector: list[float], n: int, strategy: str
):
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(Chunk.id, Chunk.content, Chunk.char_start, Chunk.char_end,
               Document.source, Document.title, distance)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.strategy == strategy, Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(n)
    )
    return (await session.execute(stmt)).all()
 
 
async def _keyword_candidates(
    session: AsyncSession, query: str, n: int, strategy: str
):
    
    tsq = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank(Chunk.tsv, tsq).label("rank")
    stmt = (
        select(Chunk.id, Chunk.content, Chunk.char_start, Chunk.char_end,
               Document.source, Document.title, rank)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.strategy == strategy, Chunk.tsv.op("@@")(tsq))
        .order_by(rank.desc())
        .limit(n)
    )
    return (await session.execute(stmt)).all()
 
 

async def search_hybrid(session:AsyncSession, query:str, k:int = 5, strategy:str = FIXED_STRATEGY_LABEL)->RetrieveResult:
    t0 = time.perf_counter()
    query_vector = (await embed_text([query]))[0]
    embed_ms = int((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    vec_rows = await _vector_candidates(session, query_vector, CANDIDATES, strategy)
    kw_rows = await _keyword_candidates(session, query, CANDIDATES, strategy)


    scores: dict[int, float] = {}
    row_by_id: dict[int, tuple] = {}
 
    for rank, row in enumerate(vec_rows, start=1):
        scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (RRF_K + rank)
        row_by_id[row.id] = row
    for rank, row in enumerate(kw_rows, start=1):
        scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (RRF_K + rank)
        row_by_id.setdefault(row.id, row)
 
    top_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:k]
    search_ms = int((time.perf_counter() - t1) * 1000)
 
    max_score = scores[top_ids[0]] if top_ids else 1.0
    chunks = [
        # similarity here is the normalized RRF score (0..1, top hit = 1),
        # NOT cosine similarity — comparable within one response only.
        _row_to_chunk(row_by_id[cid], similarity=round(scores[cid] / max_score, 4))
        for cid in top_ids
    ]
    return RetrieveResult(chunks=chunks, embed_ms=embed_ms, search_ms=search_ms)

if __name__ == "__main__":
    import sys
    import asyncio
    from app.rag.retrieval import search as vector_search

    query = sys.argv[1] if len(sys.argv[0]) > 0 else "What is the async value?"

    async def main():
        query = sys.argv[1] if len(sys.argv) > 1 else "what does async def do?"
        try:
            async with SessionLocal() as session:
                hyb = await search_hybrid(session, query)
                vec = await vector_search(session, query)
            print(f"query: {query!r}\n")
            print("hybrid:")
            for c in hyb.chunks:
                print(f"  [{c.chunk_id}] rrf={c.similarity:.3f}  {c.source}")
            print("vector-only:")
            for c in vec.chunks:
                print(f"  [{c.chunk_id}] sim={c.similarity:.3f}  {c.source}")
        finally:
            await engine.dispose()

            

            
            


    asyncio.run(main())