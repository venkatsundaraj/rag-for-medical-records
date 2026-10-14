# structuring all the questions
# embed the question
# retrieve the relevant chunks
# building properties



import asyncio
from pydantic import BaseModel
from app.rag.eval.golden import chunk_is_relevant
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
import argparse
from app.lib.alchemy_db import SessionLocal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models.pdf_schema import Document, Chunk
from app.rag.chunking import FIXED_STRATEGY_LABEL
from typing import List
from app.rag.retrieval import search, RetrieveChunk



class GoldenEvidence(BaseModel):
    source:str
    quote:str
    char_start:int =-1
    char_end:int = -1

class GoldenQuestion(BaseModel):
    qid:str
    expected_answer:str
    question:str
    answerable:bool = True
    evidence:list[GoldenEvidence]

def load_questions_v1(path:Path)->list[GoldenQuestion]:
    data = path.read_text(encoding="utf-8")

    questions = []

    for line in data.splitlines():
        # line = line.strip()
        if not line:
            continue
        raw = json.loads(line)

        questions.append( GoldenQuestion(qid=raw["qid"], question=raw["question"],answerable=raw.get("answerable", True), expected_answer=raw["expected_answer"], evidence= [GoldenEvidence(**e) for e in raw.get('evidence',{})]))

    return questions

async def resolve_spans(session:AsyncSession, qns:list[GoldenQuestion]):
    sources = (e.source for q in qns for e in q.evidence)

    documents = (await session.scalars(select(Document).where(Document.source.in_(sources)))).all()

    source_by_ids = {i.source:i.content for i in documents}

    for q in qns:
        for e in q.evidence:
            problems = []
            content = source_by_ids.get(e.source)

            if not content:
                problems.append(f"{q.qid}: source not in DB: {e.source}")
                continue
            idx = content.find(e.quote)
            if idx == -1:
                problems.append(f"{q.qid}: quote not found in {e.source}: {e.quote[:60]!r}")
                continue
            e.char_start = idx
            e.char_end = idx + len(e.quote)

            return problems


# helper functions
def span_overlap(a_start:int, a_end:int, b_start:int, b_end:int):
    return a_start < b_end and a_end > b_start

def is_chunk_relevant(chunk:RetrieveChunk, evidence:list[GoldenEvidence]):
    return any(e.source == chunk.source and e.char_start > 0 and span_overlap(chunk.char_start, chunk.char_end, e.char_start, e.char_end)  for e in evidence)

def precision_at_k(items:list[bool], k:int=5)->int:
    rel = items[:k]
    if not rel:
        return 0.0
    return sum(rel)/len(rel)

def recall_at_k(evidence_found:list[bool])->float:
    if not evidence_found:
        return 0.0
    return sum(evidence_found) / len(evidence_found)

def relevance(chunks:list[RetrieveChunk], e:GoldenEvidence):
    return any(
            c.source == e.source
            and e.char_start >= 0
            and span_overlap(c.char_start, c.char_end, e.char_start, e.char_end)
            for c in chunks
        )

def mrr(items:list[bool])->int:
    for i, rel in enumerate(items):
        if rel:
            return 1.0 / (i+1)
        return 0.0
async def evals(session, questions:list[GoldenQuestion], strategy:str = FIXED_STRATEGY_LABEL, k:int = 5):
    rows = []
    for q in questions:
        row:dict = {"qid":q.qid, "question":q.question, "answerable":q.answerable}
        result = await search(session, q.question, k=k, strategy=strategy)

        row["retrieved_ids"] = [i.chunk_id for i in result.chunks]

        if q.answerable:
            flags = [is_chunk_relevant(i, q.evidence) for i in result.chunks]

            row["precision_k"] = precision_at_k(flags, k)
            row["recall_k"] = recall_at_k([relevance(result.chunks, i) for i in q.evidence])

            row["mrr"] = mrr(flags)

            rows.append(row)

    print(rows)           
    return True


async def main(path:Path):
    qns = load_questions_v1(path)
    async with SessionLocal() as session:
        problems = await resolve_spans(session, qns)

        hello = await evals(session, qns)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=Path)
    args = parser.parse_args()

    asyncio.run(main(args.path))


# ----------------------------


