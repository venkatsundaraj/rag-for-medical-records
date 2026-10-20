"""Measure claim-extraction quality against the claims golden dataset. v2.

    python -m scripts.eval_extraction eval_runs/RUN_A.json eval_runs/RUN_B.json ...

Pass EVERY --full run the claims were harvested from. v2 fixes the two
measurement defects v1 exposed:

  1. STALE ANSWER KEYS: a claim harvested from run A's answer cannot be
     extracted from run B's different answer. v2 extracts claims from
     every provided run and scores each labeled claim against its best
     run -- the claim is covered if ANY source answer yields it.
  2. SPLIT CREDIT: the extractor is told to split compound facts
     (rule 1: atomic), but pairwise best-match punishes the split.
     v2 adds token_recall: the fraction of the gold claim's content
     words found in the UNION of that answer's extracted claims.

covered  :=  best_score >= MATCH  or  token_recall >= RECALL_MATCH
"""

import asyncio
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.verify.claims import extract_claims

CLAIMS_PATH = Path("data/golden/claims.jsonl")
OUT_DIR = Path("verification_runs")

MATCH = 0.60         # pairwise best-match threshold
RECALL_MATCH = 0.80  # union token-recall threshold
BORDERLINE = 0.40    # below MATCH but above this: print for review

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "be", "been", "being", "it",
    "its", "in", "on", "of", "to", "for", "with", "and", "or", "as",
    "that", "this", "by", "you", "your", "can", "will", "when", "not",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def token_recall(gold: str, candidates: list[str]) -> float:
    gold_tokens = content_tokens(gold)
    if not gold_tokens:
        return 0.0
    union = content_tokens(" ".join(candidates))
    return len(gold_tokens & union) / len(gold_tokens)


def load_labeled_claims() -> list[dict]:
    rows = []
    for line in CLAIMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        if row.get("origin") == "harvested" and row.get("source_qid"):
            rows.append(row)
    return rows


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run_paths = [Path(p) for p in sys.argv[1:]]

    # (run_name, qid) -> (question, answer)
    answers: dict[tuple[str, str], tuple[str, str]] = {}
    for rp in run_paths:
        run = json.loads(rp.read_text(encoding="utf-8"))
        for q in run["questions"]:
            if q.get("answer") and not q.get("refused"):
                answers[(rp.name, q["qid"])] = (q["question"], q["answer"])
    labeled = load_labeled_claims()
    print(f"{len(run_paths)} runs, {len(answers)} answers, "
          f"{len(labeled)} harvested labeled claims\n")

    keys = sorted(answers)
    extractions = await asyncio.gather(
        *(extract_claims(answers[k][1], question=answers[k][0]) for k in keys)
    )
    extracted: dict[tuple[str, str], list[str]] = {
        k: [c.text for c in claims if c.verifiable]
        for k, claims in zip(keys, extractions)
    }

    

    covered, borderline, missed, no_answer = [], [], [], []
    rows = []
    for lab in labeled:
        qid, gold = lab["source_qid"], lab["claim"]
        run_keys = [k for k in keys if k[1] == qid]
        if not run_keys:
            no_answer.append(lab)
            continue
        # Best across runs: the claim only had to come from ONE answer.
        best = {"score": 0.0, "text": "", "recall": 0.0, "run": ""}
        for k in run_keys:
            cands = extracted[k]
            rec = token_recall(gold, cands)
            for cand in cands:
                s = similarity(gold, cand)
                if s > best["score"]:
                    best.update(score=s, text=cand, run=k[0])
            if rec > best["recall"]:
                best["recall"] = rec
                if not best["run"]:
                    best["run"] = k[0]
        rows.append({"claim_id": lab["claim_id"], "qid": qid,
                     "gold": gold, "best_match": best["text"],
                     "score": round(best["score"], 3),
                     "token_recall": round(best["recall"], 3),
                     "best_run": best["run"]})
        if best["score"] >= MATCH or best["recall"] >= RECALL_MATCH:
            covered.append(lab)
        elif best["score"] >= BORDERLINE:
            borderline.append((lab, best))
        else:
            missed.append((lab, best))

    scored = len(covered) + len(borderline) + len(missed)
    print(f"coverage: {len(covered)}/{scored} auto-matched "
          f"({len(covered) / max(scored, 1):.0%})")
    print(f"borderline ({len(borderline)}):")
    for lab, b in borderline:
        print(f"  ? {lab['claim_id']} [sim {b['score']:.2f} / recall {b['recall']:.2f}]"
              f"\n      gold: {lab['claim']}\n      best: {b['text']}")
    print(f"missed ({len(missed)}):")
    for lab, b in missed:
        print(f"  ✗ {lab['claim_id']} [sim {b['score']:.2f} / recall {b['recall']:.2f}]"
              f"\n      gold: {lab['claim']}\n      best: {b['text'] or '(nothing close)'}")
    if no_answer:
        print(f"\nnot scored ({len(no_answer)}): "
              + ", ".join(l["claim_id"] for l in no_answer))

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"{stamp}_extraction_coverage.json"
    out.write_text(json.dumps({
        "config": {"run_files": [str(p) for p in run_paths],
                   "match_threshold": MATCH, "recall_threshold": RECALL_MATCH,
                   "timestamp": datetime.now(timezone.utc).isoformat()},
        "aggregates": {"auto_coverage": round(len(covered) / max(scored, 1), 4),
                       "borderline": len(borderline), "missed": len(missed)},
        "matches": rows,
        "extractions": {f"{k[0]}::{k[1]}": v for k, v in extracted.items()},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())



# python -m scripts.eval_extraction \
# eval_runs/20261002_055656_fixed_c1000_o150_hybrid_rerank_k5.json \
# eval_runs/20261002_044015_fixed_c1000_o150_k5.json \
# eval_runs/20260930_114006_recursive_c1000_o150_k5.json \
# eval_runs/20260930_153706_recursive_c1000_o150_k5.json \
# eval_runs/20260930_113450_fixed_c1000_o150_k5.json