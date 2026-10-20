from dataclasses import dataclass
from typing import Awaitable, Any, Protocol, Callable
import time
from sqlalchemy.ext.asyncio import AsyncSession

Searcher = Callable[..., Awaitable[Any]]


class _ChunkLike(Protocol):
    chunk_id:str
    source:str
    title:str
    content:str
    char_start:int
    char_end:int
    similarity: float

@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id:str
    source:str
    title:str
    content:str
    score:float
    char_start:int
    char_end:int



@dataclass(frozen=True, slots=True)
class EvidenceSet:
    claim:str
    evidence:list[Evidence]
    retrieval_ms:int

async def retrieve_evidence( searcher:Searcher,session:AsyncSession, claim:str, k:int = 5, strategy:str | None = None)->EvidenceSet:
    key_args:dict[str, Any] = {}
    if strategy is not None:
        key_args["strategy"] = {"k":k}

    t0 = time.perf_counter()

    results = await searcher(session, claim, **key_args)

    t1= int((time.perf_counter() - t0) * 1000)

    return EvidenceSet(claim=claim, evidence=[_to_evidence(i) for i in results.chunks], retrieval_ms=t1)


def _to_evidence(c:_ChunkLike):
    return Evidence(
        chunk_id=c.chunk_id,
        char_start=c.char_start,
        char_end=c.char_end,
        content=c.content,
        source=c.source,
        title=c.title,
        score=float(c.similarity)
    )




if __name__ == "__main__":
    # Eyeball test with the champion searcher on the project's favorite
    # false claim (c002). Expect ASGI/Django passage in the top 3.
    #   python -m app.verify.evidence "ASGI is being developed by members of the Django core team."
    import asyncio
    import sys
 
    from app.lib.alchemy_db import SessionLocal, engine
    from app.rag.rerank import search_reranked
 
    async def main() -> None:
        claim = sys.argv[1] if len(sys.argv) > 1 else (
            "ASGI is being developed by members of the Django core team."
        )
        try:
            async with SessionLocal() as session:
                es = await retrieve_evidence(search_reranked, session, claim, k=5)
            print(f"claim: {claim!r}\nretrieval: {es.retrieval_ms}ms\n")
            for e in es.evidence:
                print(f"[{e.chunk_id}] score={e.score:+.3f}  {e.source} — {e.title}")
                print("   " + e.content[:160].replace("\n", " "))
        finally:
            await engine.dispose()
 
    asyncio.run(main())
