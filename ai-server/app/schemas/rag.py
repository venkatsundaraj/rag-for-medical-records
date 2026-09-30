
from app.rag.chunking import FIXED_STRATEGY_LABEL
from pydantic import BaseModel, Field


class RagRequest(BaseModel):
    question:str = Field(min_length=3)
    k:int = Field(gt=1, lt=20, default=5)
    strategy:str = FIXED_STRATEGY_LABEL


class Citation(BaseModel):
    chunk_id: int
    source: str
    title: str
    char_start: int
    char_end: int
    snippet: str
    similarity: float
 
 
class RagDebug(BaseModel):
    strategy: str
    k: int
    model: str
    embed_ms: int
    search_ms: int
    llm_ms: int
    hallucinated_citations: list[int]
 
 
class RagResponse(BaseModel):
    answer: str
    citations: list[Citation]
    debug: RagDebug
 





