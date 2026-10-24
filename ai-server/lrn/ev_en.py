


import asyncio
import argparse
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.alchemy_db import SessionLocal, engine
from app.models.pdf_schema import Chunk, Document
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.verify.entailment import JUDGE_MODEL, LABELS, judge_many
from app.verify.evidence import Evidence


FILE_PATH = 'data/golden/claims.jsonl'

def load_claims():
    raw = Path(FILE_PATH).read_text(encoding='utf-8').splitlines()

    rows = []
    for i, r in enumerate(raw):
        if r.strip() == "" or r.startswith('//'):
            continue
        item = json.loads(r)

        if i > 15:
            break

        rows.append(item)
    return rows

async def golden_chunk_list(session:AsyncSession, claims:list[dict], strategy:str = FIXED_STRATEGY_LABEL):
    rows:dict[tuple[str, str], tuple[str, str]] = {}

    soruced_by_ids = {e["source"] for s in claims for e in s['evidence']}

    rows = (await session.execute(select(Document.source, Document.content, Document.id).where(Document.source.in_(soruced_by_ids)))).all()

    ids_with_content = {r.source: r for r in rows}

    result:dict[str, list[int]] = {}
    for c in claims:
        chunk_ids = []
        for e in c['evidence']:
            d = ids_with_content.get(e['source'])
            if d is None:
                continue
            idx = d.content.find(e['quote'])
            if idx == -1:
                continue

            chunks = (await session.execute(select(Chunk.id).where(Chunk.document_id == d.id, Chunk.strategy == strategy, Chunk.char_start < idx + len(e['quote']), Chunk.char_end > idx))).all()
            chunk_ids.extend(r.id for r in chunks if r.id not in chunk_ids)
            # hello.extend(r.id for r in chunk if r.id no)
        result[c['claim_id']] = chunk_ids

    print(result)


async def main():
    ps = argparse.ArgumentParser()
    ps.add_argument('--evidence-run', type=Path)
    parser = ps.parse_args()

    claims = load_claims()
    golden_ids = {c["claim_id"] for c in claims}

    # r = Path(parser.evidence_run).read_text(encoding="utf-8")
    rows = json.loads(Path(parser.evidence_run).read_text(encoding="utf-8"))["rows"][:5]

    # this claimid and retrieved ids are generated via retrieval <- retrieved_chunks <- claims
    retrieved_ids = {r['claim_id']: r['retrieved_ids'] for r in rows if r['claim_id'] in golden_ids}

    async with SessionLocal() as session:
        gold_ids = await golden_chunk_list(session, claims)



if __name__ == "__main__":
    asyncio.run(main())