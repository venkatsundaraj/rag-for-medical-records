from pathlib import Path
import statistics
from app.rag.eval.golden import resolve_spans, load_question, chunk_is_relevant, evidence_covered
from app.rag.eval.judge import judge_response
import asyncio
from app.lib.alchemy_db import SessionLocal, engine
from app.rag.retrieval import search
from app.rag.eval.metrics import precision_at_k, recall_at_k, mrr
from app.lib.deps.rag_deps import generate_res
from app.rag.eval.judge import judge_response
import time
import json
import argparse
from datetime import datetime, timezone
from app.rag.rerank import search_hybrid
from app.rag.chunking import FIXED_STRATEGY_LABEL
from app.rag.rerank import search_reranked


SEARCHERS = {"vector": search, "hybrid": search_hybrid, "hybrid_rerank": search_reranked}
REFUSAL_MARKER = "i don't know"

 
def _mean(xs: list[float]) -> float:
    return round(statistics.mean(xs), 4) if xs else 0.0


async def run_eval(path:Path, strategy:str, k:int, full:bool, search_mode:str = "vector"):
    
    questions = load_question(path)
    async with SessionLocal() as session:
        problems = await resolve_spans(session, questions)
        
        
        if problems:
            print("Unresolved gold labels (fix these before trusting numbers):")
            for p in problems:
                print(f"  - {p}")
       
        rows =[]
        for q in questions:
            row:dict = {"qid":q.qid, "question":q.question, "answerable":q.answerable}

            search_fn = SEARCHERS[search_mode]


            result = await search_fn(session, q.question, k=k, strategy=strategy)
            row["retrieved_ids"] = [i.chunk_id for i in result.chunks]

            if q.answerable:
                
                flags = [chunk_is_relevant(c, q.evidence) for c in result.chunks]
                
                row["precision_at_k"] = precision_at_k(flags, k)
                row["recall_at_k"] = recall_at_k(
                    [evidence_covered(e, result.chunks) for e in q.evidence]
                )
                row["mrr"] = mrr(flags)

            

            if full:
                ans = await generate_res(session, q.question, k, strategy, search_mode)
                refused = REFUSAL_MARKER in ans.answer.lower()
                row["answer"] = ans.answer
                row["cited_ids"] = [i.chunk_id for i in ans.cited_chunks]
                row["hallucinated_ids"] = ans.hallucinated_ids
                row["refused"] = refused

                if q.answerable:
                    # citation correctness: cited chunks should be relevant ones
                    row["citation_precision"] = (
                        precision_at_k(
                            [chunk_is_relevant(c, q.evidence) for c in ans.cited_chunks],
                            len(ans.cited_chunks) or 1,
                        )
                        if ans.cited_chunks
                        else 0.0
                    )
                else:
                    row["correct_refusal"] = refused
                j = await judge_response(
                    q.question,
                    ans.answer,
                    [c.content for c in ans.retrieved],
                    q.expected_answer,
                )
                row["faithfulness"] = j.faithfulness
                row["relevance"] = j.relevance
                row["unsupported_claims"] = j.unsupported_claims


            rows.append(row)   
            print(f"  {q.qid}: done")

    answerable = [r for r in rows if r["answerable"]]
    agg = {
        "precision_at_k": _mean([r["precision_at_k"] for r in answerable if "precision_at_k" in r]),
        "recall_at_k": _mean([r["recall_at_k"] for r in answerable if "recall_at_k" in r]),
        "mrr": _mean([r["mrr"] for r in answerable if "mrr" in r]),
    }
    if full:
        agg["faithfulness"] = _mean([r["faithfulness"] for r in rows if "faithfulness" in r])
        agg["relevance"] = _mean([r["relevance"] for r in rows if "relevance" in r])
        agg["citation_precision"] = _mean(
            [r["citation_precision"] for r in rows if "citation_precision" in r]
        )
        agg["hallucinated_citation_rate"] = _mean(
            [1.0 if r.get("hallucinated_ids") else 0.0 for r in rows if "hallucinated_ids" in r]
        )
        refusal_rows = [r for r in rows if not r["answerable"]]
        if refusal_rows:
            agg["correct_refusal_rate"] = _mean(
                [1.0 if r.get("correct_refusal") else 0.0 for r in refusal_rows]
            )
 
    return {
        "config": {
            "strategy": strategy,
            "k": k,
            "mode": "full" if full else "retrieval_only",
            "golden_file": str(path),
            "n_questions": len(questions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "aggregates": agg,
        "questions": rows,
    }
 




BASE_PATH = Path(__file__).resolve().parent.parent.parent.parent
FILE_PATH = BASE_PATH / "data" / "golden" / "golden.jsonl"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path)
    parser.add_argument("--strategy", default=FIXED_STRATEGY_LABEL)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--search", default="vector", choices=SEARCHERS.keys())
    parser.add_argument("--full", action="store_true", help="also run generation + judge")
    args = parser.parse_args()
 
    t0 = time.perf_counter()
    try:
        report = await run_eval(args.golden, args.strategy, args.k, args.full, args.search)
    finally:
        await engine.dispose()
 
    out_dir = Path("eval_runs")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{stamp}_{args.strategy}_k{args.k}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
 
    print(f"\n== {report['config']['mode']} | strategy={args.strategy} k={args.k} "
          f"| {int(time.perf_counter() - t0)}s ==")
    for name, value in report["aggregates"].items():
        print(f"  {name:28s} {value}")
    print(f"saved: {out_path}")
 
 
if __name__ == "__main__":
    asyncio.run(main())


# python -m scripts.eval data/golden/golden.jsonl --full