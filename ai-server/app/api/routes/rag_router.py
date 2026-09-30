from fastapi import APIRouter, Depends
from dataclasses import dataclass
from app.schemas.rag import RagRequest, RagResponse, Citation, RagDebug
from sqlalchemy.ext.asyncio import AsyncSession
from app.lib.alchemy_db import get_db
from typing import Annotated
from app.lib.deps.rag_deps import generate_res





rag_router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]

SNIPPET_LEN = 300

# response_class=RagResponse 
@rag_router.post('/query', response_model=RagResponse)
async def get_answer(body:RagRequest, db:DB ):

    result = await generate_res(db, body.question, body.k, body.strategy)


    return RagResponse(
        answer=result.answer,
        citations=[
            Citation(
                chunk_id=c.chunk_id,
                source=c.source,
                title=c.title,
                char_start=c.char_start,
                char_end=c.char_end,
                snippet=c.content[:SNIPPET_LEN],
                similarity=round(c.similarity, 4),
            )
            for c in result.cited_chunks
        ],
        debug=RagDebug(
            strategy=result.strategy,
            k=result.k,
            model=result.model,
            embed_ms=result.embed_ms,
            search_ms=result.search_ms,
            llm_ms=result.llm_ms,
            hallucinated_citations=result.hallucinated_ids,
        ),
    )



