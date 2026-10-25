
 
import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


from app.verify.entailment import JUDGE_MODEL, judge_many
from app.verify.evidence import Evidence

import re
_CITE = re.compile(r"\s*\[\d+\]")
 
OUT_DIR = Path("verification_runs")


ENTAILMENT_SYSTEM = """You check whether a TEXT asserts a CLAIM. The TEXT is an answer written by \
a system; the CLAIM was extracted from it by another system. You are checking the extraction, \
not the truth of either.

Rules:
1. supported: the TEXT states the claim, or entails it without a leap, WITH the same scope and \
conditions. A claim that drops a qualifier the text had ("for validators", "with invoke_group", \
"when X") is NOT supported.
2. contradicted: the TEXT asserts the opposite of the claim (the claim inverted a condition or a \
negation).
3. no_evidence: the TEXT does not assert the claim -- it is added, broadened, or about something \
the text only illustrates (e.g. names from the text's own example code).
4. Judge only from the TEXT. Ignore whether the claim is true in the world.
5. Always respond by calling the record_verdict tool, citing passage index 1."""


def answer_as_evidence(answer: str) -> list[Evidence]:
    text = _CITE.sub("", answer)
    return [Evidence(chunk_id=1, source="text", title="TEXT",
                     content=text, char_start=0, char_end=len(text), score=0.0)]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("verify_run", type=Path)
    ap.add_argument("--model", default=JUDGE_MODEL)
    args = ap.parse_args()

    run = json.loads(args.verify_run.read_text(encoding="utf-8"))

    pairs, index = [], []
    for r in run["rows"]:
        ev = answer_as_evidence(r["answer"])
        for c in r["claims"]:
            pairs.append((c["text"], ev))
            index.append((r["qid"], c["text"], c["label"]))
    print(f"{len(pairs)} claims from {len(run['rows'])} answers; judge={args.model}")

    verdicts = await judge_many(pairs, model=args.model, system=ENTAILMENT_SYSTEM)

    rows, by_qid = [], Counter()
    for (qid, text, e2e_label), v in zip(index, verdicts):
        faithful = v.label == "supported"
        rows.append({"qid": qid, "claim": text, "faithful": faithful,
                     "answer_entailment": v.label, "e2e_label": e2e_label,
                     "rationale": v.rationale})
        if not faithful:
            by_qid[qid] += 1
 
    n = len(rows)
    unfaithful = [r for r in rows if not r["faithful"]]
    # The ones that matter most: unfaithful claims that went on to be
    # judged contradicted/no_evidence against the corpus -- i.e. the
    # extractor manufactured a flag.
    manufactured = [r for r in unfaithful if r["e2e_label"] != "supported"]
    agg = {
        "claims": n,
        "extraction_precision": round((n - len(unfaithful)) / n, 4) if n else 0.0,
        "unfaithful": len(unfaithful),
        "unfaithful_and_flagged_e2e": len(manufactured),
        "answers_with_unfaithful_claims": len(by_qid),
        "answers_with_manufactured_flags": len({r["qid"] for r in manufactured}),
    }
 
    print(f"\nextraction_precision {agg['extraction_precision']:.3f}  "
          f"({agg['unfaithful']} unfaithful claims across {agg['answers_with_unfaithful_claims']} answers; "
          f"{agg['unfaithful_and_flagged_e2e']} of them became flags in "
          f"{agg['answers_with_manufactured_flags']} answers)")
    print("\nunfaithful claims (* = also flagged end-to-end):")
    for r in sorted(unfaithful, key=lambda r: (r["e2e_label"] == "supported", r["qid"])):
        star = "*" if r["e2e_label"] != "supported" else " "
        print(f" {star} {r['qid']} [{r['answer_entailment']}] {r['claim'][:95]}")
        print(f"       {r['rationale'][:150]}")
 
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"{stamp}_extraction_precision.json"
    out.write_text(json.dumps({
        "config": {"verify_run": str(args.verify_run), "judge_model": args.model,
                   "timestamp": datetime.now(timezone.utc).isoformat()},
        "aggregates": agg, "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved: {out}")


        




if __name__ == "__main__":
    asyncio.run(main())


# python -m scripts.eval_extraction_precision verification_runs/20261023_163037_verify_20261002_055656_fixed_c1000_o150_hybrid_rerank_k5.json