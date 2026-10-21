
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

Searcher = Callable[..., Awaitable[Any]]


class _ChunkLike(Protocol):
    chunk_id: int
    source: str
    title: str
    content: str
    char_start: int
    char_end: int
    similarity: float


@dataclass(frozen=True, slots=True)
class Evidence:
    """One candidate passage for one claim. Mirrors the retrieved chunk
    but owns its fields, so a judge (task 4) never needs app.rag types."""
    chunk_id: int
    source: str
    title: str
    content: str
    char_start: int
    char_end: int
    score: float        # searcher-specific: cosine sim, RRF, or CE logit


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    claim: str
    evidence: list[Evidence]
    retrieval_ms: int


async def retrieve_evidence(
    searcher: Searcher,
    session: Any,
    claim: str,
    k: int = 5,
    strategy: str | None = None,
) -> EvidenceSet:
    """Run one searcher with the claim as the query."""
    kwargs: dict[str, Any] = {"k": k}
    if strategy is not None:
        kwargs["strategy"] = strategy
    t0 = time.perf_counter()
    result = await searcher(session, claim, **kwargs)
    ms = int((time.perf_counter() - t0) * 1000)
    return EvidenceSet(
        claim=claim,
        evidence=[_to_evidence(c) for c in result.chunks],
        retrieval_ms=ms,
    )


async def retrieve_evidence_many(
    searcher: Searcher,
    session: Any,
    claims: list[str],
    k: int = 5,
    strategy: str | None = None,
) -> list[EvidenceSet]:
    """Sequential on purpose: one AsyncSession cannot run concurrent
    queries, and the reranker is CPU-bound anyway. Parallelism, if ever
    needed, belongs at the session level (one session per task), not here."""
    return [
        await retrieve_evidence(searcher, session, c, k=k, strategy=strategy)
        for c in claims
    ]


def _to_evidence(c: _ChunkLike) -> Evidence:
    return Evidence(
        chunk_id=c.chunk_id,
        source=c.source,
        title=c.title,
        content=c.content,
        char_start=c.char_start,
        char_end=c.char_end,
        score=float(c.similarity),
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