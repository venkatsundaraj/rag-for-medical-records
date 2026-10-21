"""Measure the entailment judge against the claims golden dataset.

Two modes, run both -- the difference between them is the number that
tells you where errors come from:

  --mode retrieved   evidence = what task 3 actually retrieved. This is the
                     system as it will ship: judge error + retrieval error.
  --mode oracle      evidence = the gold quote(s) for supported/contradicted
                     claims (no_evidence claims still get retrieved
                     evidence -- there is no gold for "nothing"). This
                     isolates the JUDGE: if oracle is near-perfect and
                     retrieved is not, the gap is retrieval; if oracle
                     itself errs, the judge is at fault.

    python -m scripts.eval_entailment --mode retrieved \
        --evidence-run verification_runs/20261020_055424_evidence_hybrid_rerank.json
    python -m scripts.eval_entailment --mode oracle \
        --evidence-run verification_runs/20261020_055424_evidence_hybrid_rerank.json

Retrieved evidence is re-read FROM THE SAVED RUN by chunk id (no reranking
again): the judge is measured on a fixed retrieval, so two judge runs
differ only by the judge. --model lets you compare judges on identical input.

Headline metrics:
  false_supported_rate   gold contradicted -> judged supported   (the one that matters)
  ungrounded_supported   gold no_evidence  -> judged supported   (fooled by near-miss passages)
  accuracy, 3x3 confusion matrix, per-label precision/recall
"""

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from app.rag.chunking import FIXED_STRATEGY_LABEL
from pathlib import Path

from sqlalchemy import select

from app.lib.alchemy_db import SessionLocal, engine
from app.models.pdf_schema import Chunk, Document
from app.verify.entailment import JUDGE_MODEL, LABELS, judge_many
from app.verify.evidence import Evidence

CLAIMS_PATH = Path("data/golden/claims.jsonl")
OUT_DIR = Path("verification_runs")


def load_claims() -> list[dict]:
    rows = []
    for line in CLAIMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


async def fetch_chunks(session, ids: list[int], strategy:str = FIXED_STRATEGY_LABEL) -> dict[int, Evidence]:
    if not ids:
        return {}
    rows = (await session.execute(
        select(Chunk.id, Chunk.content, Chunk.char_start, Chunk.char_end,
               Document.source, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(ids))
    )).all()
    return {r.id: Evidence(chunk_id=r.id, source=r.source, title=r.title,
                           content=r.content, char_start=r.char_start,
                           char_end=r.char_end, score=0.0) for r in rows}


def gold_evidence(claim: dict) -> list[Evidence]:
    return [Evidence(chunk_id=-1, source=e["source"], title="(gold quote)",
                     content=e["quote"], char_start=-1, char_end=-1, score=0.0)
            for e in claim["evidence"]]


async def gold_chunk_ids(session, claims: list[dict], strategy: str) -> dict[str, list[int]]:
    """claim_id -> ids of chunks whose span covers a gold quote. The oracle
    is the passage the labeler read, in full -- not the bare locator quote."""
    sources = {e["source"] for c in claims for e in c["evidence"]}
    docs = (await session.execute(
        select(Document.id, Document.source, Document.content)
        .where(Document.source.in_(sources)))).all()
    doc_by_source = {d.source: d for d in docs}
    out: dict[str, list[int]] = {}
    for c in claims:
        ids: list[int] = []
        for e in c["evidence"]:
            d = doc_by_source.get(e["source"])
            if d is None:
                continue
            i = d.content.find(e["quote"])
            if i == -1:
                continue
            rows = (await session.execute(
                select(Chunk.id).where(
                    Chunk.document_id == d.id, Chunk.strategy == strategy,
                    Chunk.char_start < i + len(e["quote"]), Chunk.char_end > i)
                .order_by(Chunk.char_start))).all()
            ids.extend(r.id for r in rows if r.id not in ids)
        out[c["claim_id"]] = ids
    return out

def prf(cm: dict[str, Counter], label: str) -> tuple[float, float]:
    tp = cm[label][label]
    pred = sum(cm[g][label] for g in LABELS)
    gold = sum(cm[label].values())
    return (round(tp / pred, 4) if pred else 0.0, round(tp / gold, 4) if gold else 0.0)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["retrieved", "oracle"], default="retrieved")
    ap.add_argument("--evidence-run", type=Path, required=True)
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--strategy", default=FIXED_STRATEGY_LABEL)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    claims = load_claims()
    run = json.loads(args.evidence_run.read_text(encoding="utf-8"))
    retrieved_ids = {r["claim_id"]: r["retrieved_ids"][: args.k] for r in run["rows"]}
    missing = [c["claim_id"] for c in claims if c["claim_id"] not in retrieved_ids]
    if missing:
        print(f"WARNING: no retrieval row for {missing} -- rerun eval_evidence first")

    try:
        async with SessionLocal() as session:
            gold_ids: dict[str, list[int]] = {}
            if args.mode == "oracle":
                gold_ids = await gold_chunk_ids(session, claims, args.strategy)
                
            all_ids = sorted(
                {i for c in claims for i in retrieved_ids.get(c["claim_id"], [])}
                | {i for ids in gold_ids.values() for i in ids}
            )
            chunk_by_id = await fetch_chunks(session, all_ids)  
    finally:
        await engine.dispose()

    pairs, used = [], []
    for c in claims:
        ids = retrieved_ids.get(c["claim_id"], [])
        retrieved = [chunk_by_id[i] for i in ids if i in chunk_by_id]
        if args.mode == "oracle" and gold_ids.get(c["claim_id"]):
            ev = [chunk_by_id[i] for i in gold_ids[c["claim_id"]] if i in chunk_by_id]
        else:
            ev = retrieved
        pairs.append((c["claim"], ev))
        used.append(ev)

    print(f"{len(claims)} claims, mode={args.mode}, judge={args.model}")
    verdicts = await judge_many(pairs, model=args.model)

    # ---- score ---------------------------------------------------------
    cm: dict[str, Counter] = {g: Counter() for g in LABELS}   # cm[gold][pred]
    rows = []
    for c, ev, v in zip(claims, used, verdicts):
        cm[c["label"]][v.label] += 1
        cited = ev[v.evidence_index - 1] if v.evidence_index else None
        rows.append({
            "claim_id": c["claim_id"], "origin": c.get("origin"),
            "claim": c["claim"], "gold": c["label"], "pred": v.label,
            "correct": c["label"] == v.label,
            "cited_chunk_id": cited.chunk_id if cited else None,
            "cited_source": cited.source if cited else None,
            "rationale": v.rationale,
        })

    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    n_contra = sum(cm["contradicted"].values())
    n_noev = sum(cm["no_evidence"].values())
    agg = {
        "claims": n,
        "accuracy": round(correct / n, 4),
        "false_supported_rate": round(cm["contradicted"]["supported"] / n_contra, 4) if n_contra else None,
        "contradicted_missed_as_no_evidence": round(cm["contradicted"]["no_evidence"] / n_contra, 4) if n_contra else None,
        "ungrounded_supported_rate": round(cm["no_evidence"]["supported"] / n_noev, 4) if n_noev else None,
        "confusion": {g: dict(cm[g]) for g in LABELS},
    }
    for label in LABELS:
        p, r = prf(cm, label)
        agg[f"precision_{label}"], agg[f"recall_{label}"] = p, r

    print(f"\n== {args.mode} / {args.model} ==")
    print(f"accuracy {agg['accuracy']:.3f}   false_supported {agg['false_supported_rate']}   "
          f"contradicted->no_evidence {agg['contradicted_missed_as_no_evidence']}   "
          f"ungrounded_supported {agg['ungrounded_supported_rate']}")
    print("\nconfusion (rows=gold, cols=pred)")
    print(f"{'':14}" + "".join(f"{l:>14}" for l in LABELS))
    for g in LABELS:
        print(f"{g:14}" + "".join(f"{cm[g][p]:>14}" for p in LABELS))
    print()
    for label in LABELS:
        print(f"{label:13} precision {agg[f'precision_{label}']:.3f}  recall {agg[f'recall_{label}']:.3f}")

    wrong = [r for r in rows if not r["correct"]]
    severity = {("contradicted", "supported"): 0, ("no_evidence", "supported"): 1}
    wrong.sort(key=lambda r: severity.get((r["gold"], r["pred"]), 2))
    print(f"\nmisjudged ({len(wrong)}):")
    for r in wrong:
        flag = "!!" if (r["gold"], r["pred"]) == ("contradicted", "supported") else " ✗"
        print(f"  {flag} {r['claim_id']} gold={r['gold']} pred={r['pred']}  {r['claim'][:80]}")
        print(f"       {r['rationale'][:160]}")

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_model = args.model.replace("/", "_")
    out = OUT_DIR / f"{stamp}_entailment_{args.mode}_{safe_model}.json"
    out.write_text(json.dumps({
        "config": {"mode": args.mode, "judge_model": args.model, "k": args.k,
                   "evidence_run": str(args.evidence_run),
                   "claims_file": str(CLAIMS_PATH),
                   "timestamp": datetime.now(timezone.utc).isoformat()},
        "aggregates": agg,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())



# python -m app.verify.entailment        # smoke: expect supported / contradicted / no_evidence in that order
# python -m scripts.eval_entailment --mode oracle    --evidence-run verification_runs/20261020_055424_evidence_hybrid_rerank.json
# python -m scripts.eval_entailment --mode retrieved --evidence-run verification_runs/20261020_055424_evidence_hybrid_rerank.json