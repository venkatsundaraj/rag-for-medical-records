


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

    for c in claims:
        for e in c['evidence']:
            rows[(c["claim_id"], c["source_qid"])] = (e['source'], e["quote"])

    print(rows)
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
        await golden_chunk_list(session, claims)



if __name__ == "__main__":
    asyncio.run(main())