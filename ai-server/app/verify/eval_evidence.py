import argparse
import asyncio
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


from scripts.eval import SEARCHERS
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.lib.alchemy_db import SessionLocal
from app.rag.eval.golden import GoldEvidence, spans_overlap
from app.verify.evidence import Evidence, retrieve_evidence




CLAIMS_PATH = Path("data/golden/claims.jsonl")
OUT_DIR = Path("verification_runs")


def covered(e: GoldEvidence, evidence: list[Evidence]) -> bool:
    return any(
        ev.source == e.source
        and spans_overlap(ev.char_start, ev.char_end, e.char_start, e.char_end)
        for ev in evidence
    )

 
def load_claims() -> list[dict]:
    rows = []
    for line in CLAIMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows
 
async def evidence_span():
    return []


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--search', default="hybrid", choices=sorted(SEARCHERS))
    parser.add_argument('--ks', nargs='+', type=int, default=[3, 5])
    parser.add_argument("--strategy", default=FIXED_STRATEGY_LABEL)

    args = parser.parse_args()
    search = SEARCHERS[args.search]

    k_max = max(args.ks)

    claims = load_claims()

    with_evidence = [i for i in claims if i["evidence"] ]

    print(f"{len(claims)} claims, {len(with_evidence)} with evidence; "
          f"searcher={args.search} ks={args.ks}")
 
    rows = []

    try:
        async with SessionLocal as session:
            problems = []
            for p in problems:
                print("  !", p)

            for i, c in enumerate(with_evidence, 1):
                es = await retrieve_evidence(search, session, c["claim"], k_max, strategy=args.strategy)

                row = {"claim_id":c["claim_id"], "origin":c.get('origin'), "label":c["label"], "retrieved_ids":[i["retrieved_ids"] for i in es.evidence],"retrieved_sources":[i["retrieved_sources"] for i in es.evidence], "retrieval_ms":es.retrieval_ms}

                for k in args.ks:
                    top = es.evidence[:k]
                    if c['Evidence']:
                        flags = [covered(i, top) for i in c["_gold"]]
                        row[f"recall_at_{k}"] = round(sum(flags) / len(flags), 4)
                        row[f"hit_at_{k}"] = any(flags)

                rows.append(row)


    finally:
        return






if __name__ == "__main__":
    asyncio.run(main())