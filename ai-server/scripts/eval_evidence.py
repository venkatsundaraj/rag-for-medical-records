

import argparse
import asyncio
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.lib.alchemy_db import SessionLocal, engine
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.rag.eval.golden import GoldEvidence, spans_overlap
from app.verify.evidence import Evidence, retrieve_evidence
from scripts.eval import SEARCHERS

CLAIMS_PATH = Path("data/golden/claims.jsonl")
OUT_DIR = Path("verification_runs")


def load_claims() -> list[dict]:
    rows = []
    for line in CLAIMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


async def resolve_evidence_spans(session, claims: list[dict]) -> list[str]:
    from sqlalchemy import select
    from app.models.pdf_schema import Document

    sources = {e["source"] for c in claims for e in c["evidence"]}
    rows = (await session.execute(
        select(Document.source, Document.content).where(Document.source.in_(sources))
    )).all()
    content_by_source = {r.source: r.content for r in rows}

    problems = []
    for c in claims:
        gold: list[GoldEvidence] = []
        for e in c["evidence"]:
            content = content_by_source.get(e["source"])
            if content is None:
                problems.append(f"{c['claim_id']}: source not in DB: {e['source']}")
                continue
            idx = content.find(e["quote"])
            if idx == -1:
                problems.append(f"{c['claim_id']}: quote not found in {e['source']}")
                continue
            g = GoldEvidence(source=e["source"], quote=e["quote"])
            g.char_start, g.char_end = idx, idx + len(e["quote"])
            gold.append(g)
        c["_gold"] = gold
    return problems


def covered(e: GoldEvidence, evidence: list[Evidence]) -> bool:
    return any(
        ev.source == e.source
        and spans_overlap(ev.char_start, ev.char_end, e.char_start, e.char_end)
        for ev in evidence
    )


def _mean(xs: list[float]) -> float:
    return round(statistics.mean(xs), 4) if xs else 0.0


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", choices=sorted(SEARCHERS), default="hybrid")
    parser.add_argument("--ks", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--strategy", default=FIXED_STRATEGY_LABEL)
    args = parser.parse_args()
    searcher = SEARCHERS[args.search]
    k_max = max(args.ks)

    claims = load_claims()
    with_evidence = [c for c in claims if c["evidence"]]
    print(f"{len(claims)} claims, {len(with_evidence)} with evidence; "
          f"searcher={args.search} ks={args.ks}")

    rows = []
    try:
        async with SessionLocal() as session:
            problems = await resolve_evidence_spans(session, with_evidence)
            for p in problems:
                print("  !", p)

            for i, c in enumerate(claims, 1):
                es = await retrieve_evidence(
                    searcher, session, c["claim"], k=k_max, strategy=args.strategy
                )
                row = {
                    "claim_id": c["claim_id"], "label": c["label"],
                    "origin": c.get("origin"), "claim": c["claim"],
                    "retrieved_ids": [e.chunk_id for e in es.evidence],
                    "retrieved_sources": [e.source for e in es.evidence],
                    "retrieval_ms": es.retrieval_ms,
                }
                for k in args.ks:
                    top = es.evidence[:k]
                    if c["evidence"]:
                        flags = [covered(g, top) for g in c["_gold"]]
                        row[f"recall_at_{k}"] = round(sum(flags) / len(flags), 4)
                        row[f"hit_at_{k}"] = any(flags)
                rows.append(row)
                if i % 10 == 0 or i == len(claims):
                    print(f"  {i}/{len(claims)}  ({es.retrieval_ms}ms last)")
            print(rows, "rows")
    finally:
        await engine.dispose()

    # ---- aggregates --------------------------------------------------
    scored = [r for r in rows if "recall_at_%d" % args.ks[0] in r]
    agg: dict = {"claims_scored": len(scored),
                 "mean_retrieval_ms": _mean([r["retrieval_ms"] for r in rows])}
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_label[r["label"]].append(r)
    for k in args.ks:
        agg[f"evidence_recall_at_{k}"] = _mean([r[f"recall_at_{k}"] for r in scored])
        agg[f"hit_at_{k}"] = _mean([float(r[f"hit_at_{k}"]) for r in scored])
        for label, rs in sorted(by_label.items()):
            agg[f"hit_at_{k}_{label}"] = _mean([float(r[f"hit_at_{k}"]) for r in rs])

    print(f"\n== {args.search} ==")
    for k in args.ks:
        print(f"k={k}: evidence_recall {agg[f'evidence_recall_at_{k}']:.3f}  "
              f"hit {agg[f'hit_at_{k}']:.3f}  "
              + "  ".join(f"{l} {agg[f'hit_at_{k}_{l}']:.3f}" for l in sorted(by_label)))
    print(f"mean retrieval: {agg['mean_retrieval_ms']:.0f}ms/claim")

    misses = [r for r in scored if not r[f"hit_at_{k_max}"]]
    if misses:
        print(f"\nmissed at k={k_max} ({len(misses)}):")
        for r in misses:
            print(f"  ✗ {r['claim_id']} [{r['label']}] {r['claim'][:80]}")
            print(f"      got: {', '.join(dict.fromkeys(r['retrieved_sources']))}")

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"{stamp}_evidence_{args.search}.json"
    out.write_text(json.dumps({
        "config": {"search": args.search, "ks": args.ks, "strategy": args.strategy,
                   "claims_file": str(CLAIMS_PATH),
                   "timestamp": datetime.now(timezone.utc).isoformat()},
        "aggregates": agg,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())