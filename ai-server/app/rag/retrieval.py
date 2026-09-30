from app.lib.alchemy_db import SessionLocal, engine
import sys
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
import time
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.rag.embedding import embed_text
from sqlalchemy import select, update, delete
from app.models.pdf_schema import Document, Chunk

@dataclass(frozen=True, slots=True)
class RetrieveChunk:
    chunk_id:int
    title:str
    content:str
    char_start:int
    char_end:int
    source:str
    distance:float
    similarity:float


@dataclass(frozen=True, slots=True)
class RetrieveResult:
    chunks:list[RetrieveChunk]
    embed_ms:int
    search_ms:int


async def search(session:AsyncSession, query:str, k:int = 5, strategy:str = FIXED_STRATEGY_LABEL)->RetrieveResult:

    t0 = time.perf_counter()

    query_vector = (await embed_text([query]))[0]

    embed_ms = int((time.perf_counter() - t0) * 1000)

    distance = Chunk.embedding.cosine_distance(query_vector).label('distance')

    smt = select(Chunk.id, Document.title, Chunk.content, Chunk.char_start, Chunk.char_end, Document.source, distance).where(Chunk.strategy == strategy, Chunk.embedding.is_not(None)).join(Document).order_by(distance).limit(k)

    t1 = time.perf_counter()

    rows = (await session.execute(smt)).all()

    search_ms = int((time.perf_counter() - t1) * 1000)

    chunks = [
        RetrieveChunk(
            chunk_id=row.id,
            source=row.source,
            title=row.title,
            char_start=row.char_start,
            char_end=row.char_end,
            content=row.content,
            distance=row.distance,
            similarity=1.0 - row.distance,
        )
        for row in rows
    ]

    print(i.title for i in chunks)

    return RetrieveResult(chunks=chunks, embed_ms=embed_ms, search_ms=search_ms)




if __name__ == "__main__":
    query = "what is path operation and when to use one?"

    async def main():
        try:
            async with SessionLocal() as session:
                results = await search(session, query)
                for c in results.chunks:
                    print(f"[{c.chunk_id}] sim={c.similarity:.3f}  {c.source} — {c.title}")
                    print(c.content[:200].replace("\n", " "))
                    print()

        finally:
            await engine.dispose()

    asyncio.run(main())