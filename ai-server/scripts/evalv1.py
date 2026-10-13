# structuring all the questions
# embed the question
# retrieve the relevant chunks
# building properties



import asyncio
from pydantic import BaseModel
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
import argparse
from app.lib.alchemy_db import SessionLocal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models.pdf_schema import Document, Chunk


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



    
    
    








async def evals(quesitions):
    return True


async def main(path:Path):
    qns = load_questions_v1(path)
    async with SessionLocal() as session:
        problems = await resolve_spans(session, qns)

        print(qns)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=Path)
    args = parser.parse_args()

    asyncio.run(main(args.path))


# ----------------------------


