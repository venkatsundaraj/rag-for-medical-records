import argparse
import asyncio
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
 
from app.lib.alchemy_db import SessionLocal, engine
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.verify.entailment import JUDGE_MODEL
from app.verify.verdict import STATUSES, verify_answer, to_dict
from scripts.eval import SEARCHERS


OUT_DIR = Path("verification_runs")
P1_KEYS = ("faithfulness", "answer_relevance", "citation_precision",
           "hallucinated_ids", "cited_ids", "refused")
 

def _mean(xs):
    return round(statistics.mean(xs), 1) if xs else 0.0
 
 
def _median(xs):
    return round(statistics.median(xs), 1) if xs else 0.0


 
async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--search", choices=sorted(SEARCHERS), default="hybrid_rerank")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--strategy", default=FIXED_STRATEGY_LABEL)
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--qid", nargs="*", help="only these qids")

    args = ap.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))

    questions = [q for q in run["questions"] if q["answer"]]

    if args.qid:
        questions = [q for q in run['questions'] if q['qid'] in set(args.qid)]

    print(f"{len(questions)} answers from {args.run.name}; "
          f"search={args.search} k={args.k} judge={args.model}\n")

    search = SEARCHERS[args.search]

    rows = []
    try:
        async with SessionLocal() as session:
            for i, q in enumerate(questions, 1):
                av = await verify_answer(session, q['answer'], q['question'], search, args.model, args.k, args.strategy, )

                d = to_dict(av)

                d.update({
                    "qid": q["qid"], "question": q["question"], "answer": q["answer"],
                    "p1": {k: q[k] for k in P1_KEYS if k in q},
                })

                rows.append(d)
                flag = {"contradicted": "!!", "unverified": " ?", "verified": "ok",
                            "no_claims": "--"}[av.status]
                print(f"  {flag} {q['qid']:5} {av.status:12} "
                        f"{av.counts['supported']}/{av.counts['contradicted']}/"
                        f"{av.counts['no_evidence']}  {av.timing_ms['total']/1000:.1f}s")
                for cv in av.claims:
                    if cv.label != "supported":
                        print(f"        [{cv.label}] {cv.text[:90]}")
    finally:
        await engine.dispose()

        # ---- aggregates ----------------------------------------------------
    status_counts = Counter(r["status"] for r in rows)
    n = len(rows)
    totals = [r["timing_ms"]["total"] for r in rows]
    n_claims = [len(r["claims"]) for r in rows]
    agg = {
        "answers": n,
        **{f"status_{s}": status_counts.get(s, 0) for s in STATUSES},
        "contradicted_rate": round(status_counts.get("contradicted", 0) / n, 4) if n else 0,
        "unverified_rate": round(status_counts.get("unverified", 0) / n, 4) if n else 0,
        "verified_rate": round(status_counts.get("verified", 0) / n, 4) if n else 0,
        "mean_grounded_rate": round(statistics.mean(r["grounded_rate"] for r in rows), 4) if n else 0,
        "claims_per_answer": _mean(n_claims),
        "judge_calls": sum(n_claims),
        "latency_ms_mean": _mean(totals), "latency_ms_median": _median(totals),
        "latency_ms_by_stage_mean": {
            s: _mean([r["timing_ms"][s] for r in rows]) for s in ("extract", "retrieve", "judge")
        },
    }
    # Agreement with Project 1's judge where it recorded faithfulness.
    p1 = [(r["p1"].get("faithfulness"), r["status"]) for r in rows if "faithfulness" in r["p1"]]
    if p1:
        flagged_p1 = [s for f, s in p1 if f is not None and f < 1.0]
        agg["p1_flagged_answers"] = len(flagged_p1)
        agg["p1_flagged_also_flagged_here"] = sum(s in ("contradicted", "unverified") for s in flagged_p1)
        agg["p1_clean_but_flagged_here"] = sum(
            s in ("contradicted", "unverified") for f, s in p1 if f == 1.0
        )
 
    print(f"\n== {args.run.name} / {args.search} / {args.model} ==")
    print(f"verified {agg['verified_rate']:.0%}  unverified {agg['unverified_rate']:.0%}  "
          f"contradicted {agg['contradicted_rate']:.0%}  "
          f"(grounded_rate mean {agg['mean_grounded_rate']:.3f})")
    print(f"{agg['claims_per_answer']} claims/answer, {agg['judge_calls']} judge calls, "
          f"median {agg['latency_ms_median']/1000:.1f}s/answer "
          f"(extract {agg['latency_ms_by_stage_mean']['extract']/1000:.1f}s, "
          f"retrieve {agg['latency_ms_by_stage_mean']['retrieve']/1000:.1f}s, "
          f"judge {agg['latency_ms_by_stage_mean']['judge']/1000:.1f}s)")
    if p1:
        print(f"Project 1 judge flagged {agg['p1_flagged_answers']}; of those this layer flags "
              f"{agg['p1_flagged_also_flagged_here']}. Clean in P1 but flagged here: "
              f"{agg['p1_clean_but_flagged_here']}")
 
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"{stamp}_verify_{args.run.stem}.json"
    out.write_text(json.dumps({
        "config": {"run_file": str(args.run), "search": args.search, "k": args.k,
                   "strategy": args.strategy, "judge_model": args.model,
                   "qids": args.qid, "timestamp": datetime.now(timezone.utc).isoformat()},
        "aggregates": agg,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved: {out}")
 
    status_by_qid = {r["qid"]: r["status"] for r in rows}
    failed = [q for q in args.expect_contradicted if status_by_qid.get(q) != "contradicted"]
    if failed:
        print(f"\nACCEPTANCE FAILED: expected contradicted, got "
              + ", ".join(f"{q}={status_by_qid.get(q)}" for q in failed))
        return 1
    if args.expect_contradicted:
        print(f"acceptance ok: {', '.join(args.expect_contradicted)} flagged")
    return 0
 









if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


# python -m scripts.eval_verify eval_runs/20261002_055656_fixed_c1000_o150_hybrid_rerank_k5.json --qid q004