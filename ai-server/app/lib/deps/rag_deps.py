from app.lib.deps.prompt import _build_message
from app.rag.retrieval import search
from sqlalchemy.ext.asyncio import AsyncSession
from app.rag.chunking import FIXED_STRATEGY_LABEL
import time
from openai import AsyncOpenAI
from app.rag.retrieval import RetrieveChunk
from dataclasses import dataclass
from app.config import settings
import re

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=5)

CHAT_MODEL = "gpt-4o-mini"

_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class AnswerResult:
    answer: str
    cited_chunks: list[RetrieveChunk]      # retrieved chunks the answer actually cites
    hallucinated_ids: list[int]            # cited ids that were never in the context
    retrieved: list[RetrieveChunk]         # everything we put in the prompt
    strategy: str
    k: int
    model: str
    embed_ms: int
    search_ms: int
    llm_ms: int


async def generate_res( db:AsyncSession, query:str, k:int = 5, strategy:str = FIXED_STRATEGY_LABEL, model:str =CHAT_MODEL,) -> AnswerResult:
    vectors = await search(db, query, k, strategy)
    messages = _build_message(query, vectors.chunks)

    t0 = time.perf_counter()

    resp = await _client.chat.completions.create(
        messages=messages,
        temperature=0,
        model=CHAT_MODEL
    )

    llm_ms = int((time.perf_counter() - t0) * 1000)

    answer = resp.choices[0].message.content or ""

    cited_ids = {int(i) for i in _CITATION_RE.findall(answer)}
    by_id = {c.chunk_id:c for c in vectors.chunks}

    valid_ids = cited_ids & by_id.keys()
    hallucinated = sorted(cited_ids - by_id.keys())

    cited_chunks = [c for c in vectors.chunks if c.chunk_id in valid_ids]


    return AnswerResult(
        answer=answer,
        cited_chunks=cited_chunks,
        hallucinated_ids=hallucinated,
        retrieved=vectors.chunks,
        strategy=strategy,
        k=k,
        model=model,
        embed_ms=vectors.embed_ms,
        search_ms=vectors.search_ms,
        llm_ms=llm_ms,
    )


if __name__ == "__main__":
    # python -m app.rag.answer "how do I keep code from blocking the event loop?"
    import asyncio
    import sys
 
    from app.lib.alchemy_db import SessionLocal, engine
 
    async def main() -> None:
        question = sys.argv[1] if len(sys.argv) > 1 else "what does async def do?"
        try:
            async with SessionLocal() as session:
                r = await generate_res(session, question)
            print(r.answer, "\n")
            print(f"cited: {[c.chunk_id for c in r.cited_chunks]}")
            print(f"hallucinated: {r.hallucinated_ids}")
            print(f"timings: embed {r.embed_ms}ms | search {r.search_ms}ms | llm {r.llm_ms}ms")
        finally:
            await engine.dispose()
 
    asyncio.run(main())
