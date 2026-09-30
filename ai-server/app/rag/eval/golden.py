from dataclasses import dataclass, field
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.lib.alchemy_db import SessionLocal
from pathlib import Path
from sqlalchemy import Select
from app.models.pdf_schema import Document
from app.rag.retrieval import RetrieveChunk
from app.rag.eval.metrics import spans_overlap
from app.rag.retrieval import search
import asyncio
from app.rag.chunking import FIXED_STRATEGY_LABEL



@dataclass(slots=True)
class GoldEvidence:
    source:str
    quote:str
    char_start:int = -1
    char_end:int = -1


@dataclass(slots=True, frozen=True)
class GoldQuestion:
    qid:int
    question:str
    expected_answer:str
    answerable:bool =True
    evidence:list[GoldEvidence] = field(default_factory=list)


def load_question(path: Path) -> list[GoldQuestion]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        raw = json.loads(line)
        questions.append(
            GoldQuestion(
                qid=raw["qid"],
                question=raw["question"],
                expected_answer=raw["expected_answer"],
                answerable=raw.get("answerable", True),
                evidence=[GoldEvidence(**e) for e in raw.get("evidence", [])],
            )
        )
    return questions





async def resolve_spans(session:AsyncSession, questions:list[GoldQuestion])->list[str]:
    sources = (e.source for q in questions for e in q.evidence)
   
    rows = (await session.execute(Select(Document.source, Document.content).where(Document.source.in_(sources)))).all()
    print(list(rows))
    sources_by_ids = {i.source:i.content for i in rows}
    problems = []

    for q in questions:
        for e in q.evidence:
            content = sources_by_ids.get(e.source)
            if content is None:
                problems.append(f"{q.qid}: source not in DB: {e.source}")
                continue
            idx = content.find(e.quote)
            if idx == -1:
                problems.append(f"{q.qid}: quote not found in {e.source}: {e.quote[:60]!r}")
                continue
            e.char_start = idx
            e.char_end =  idx + len(e.quote)


    
    return problems


def chunk_is_relevant(chunk:RetrieveChunk, evidence:list[GoldEvidence]):
    return any(chunk.source == e.source and e.char_start>= 0 and spans_overlap(chunk.char_start, chunk.char_end, e.char_start, e.char_end) for e in evidence)


def evidence_covered(e: GoldEvidence, chunks: list[RetrieveChunk]) -> bool:
    return any(
        c.source == e.source
        and e.char_start >= 0
        and spans_overlap(c.char_start, c.char_end, e.char_start, e.char_end)
        for c in chunks
    )

BASE_PATH = Path(__file__).resolve().parent.parent.parent.parent
FILE_PATH = BASE_PATH / "data" / "golden" / "golden.jsonl"

async def main():
    questions = load_question(FILE_PATH)
    # print(questions[:5])
    async with SessionLocal() as session:
        res = await resolve_spans(session, questions)
        print(res, "res")

        for q in questions[:10]:
            # result = await search(session, q.question, k=5, strategy=FIXED_STRATEGY_LABEL)
            print(len(q.evidence))


if __name__ == "__main__":
    asyncio.run(main())
