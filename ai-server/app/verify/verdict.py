import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
 
from app.verify.claims import Claim, extract_claims
from app.verify.entailment import JUDGE_MODEL, Verdict, judge_many
from app.verify.evidence import Evidence, Searcher, retrieve_evidence
from sqlalchemy.ext.asyncio import AsyncSession


STATUSES = ("verified", "unverified", "contradicted", "no_claims")

@dataclass(slots=True, frozen=True)
class ClaimVerdict:
    text:str
    label:str
    rationale:str
    evidence:Evidence
    candidates:list[Evidence] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AnswerVerdict:
    status:str
    claims:list[ClaimVerdict]
    skipped:list[Claim]
    grounded_rate:float
    counts:dict[str, int]
    timing_ms:dict[str, int]
    judge_model:str


def aggregate(labels: list[str]) -> str:
    if not labels:
        return "no_claims"
    if "contradicted" in labels:
        return "contradicted"
    if "no_evidence" in labels:
        return "unverified"
    return "verified"




async def verify_answer(session:AsyncSession, answer:str, question:str, searcher:Searcher, judge_model:str=JUDGE_MODEL,k: int = 5,
    strategy: str | None = None,judge_concurrency:int = 4
):
    t0 = time.perf_counter()

    claims = await extract_claims(answer, question)
    
    t_extract = time.perf_counter()

    verifiable = [c for c in claims if c.verifiable]
    missed = [c for c in claims if not c.verifiable]

    evidences = [await retrieve_evidence(searcher, session, v.text, k=k, strategy=strategy) for v in verifiable]

    t_retrieve = time.perf_counter()

    for c, ev in zip(verifiable, evidences):
        print(c.text, ev)
        print('\n\n')

    verdicts = await judge_many([(v.text, ev.evidence) for v, ev in zip(verifiable, evidences)], model=judge_model, concurreny=judge_concurrency,)

    t_judge = time.perf_counter()

    verdict_claims = [ClaimVerdict(text=c.text, label=v.label, rationale=v.rationale, evidence=ev.evidence[v.evidence_index - 1] if v.evidence_index else None, candidates=ev.evidence) for c, ev, v in zip(verifiable, evidences, verdicts)]

    labels = [i.label for i in verdict_claims]

    counted = {lab:labels.count(lab) for lab in ('supported', 'contradicted', 'no_evidence')}

    return AnswerVerdict(
        claims=verdict_claims,
        counts=counted, 
        grounded_rate=round(counted["supported"]/len(labels) , 4) if labels else 0.0,
        judge_model=judge_model, 
        skipped=missed,
        timing_ms={
            "extract": int((t_extract - t0) * 1000),
            "retrieve": int((t_retrieve - t_extract) * 1000),
            "judge": int((t_judge - t_retrieve) * 1000),
            "total": int((t_judge - t0) * 1000),
        },

        status=aggregate(labels)
    )



def to_dict(av: AnswerVerdict) -> dict:
    """JSON-ready view: what the API (task 6) returns and the runs save."""
    return {
        "status": av.status,
        "grounded_rate": av.grounded_rate,
        "counts": av.counts,
        "claims": [
            {
                "text": cv.text, "label": cv.label, "rationale": cv.rationale,
                "evidence": None if cv.evidence is None else {
                    "chunk_id": cv.evidence.chunk_id, "source": cv.evidence.source,
                    "title": cv.evidence.title,
                    "excerpt": cv.evidence.content[:300],
                },
                "candidate_ids": [e.chunk_id for e in cv.candidates],
            }
            for cv in av.claims
        ],
        "skipped": [c.text for c in av.skipped],
        "timing_ms": av.timing_ms,
        "judge_model": av.judge_model,
    }



if __name__ == "__main__":
    import json
    import asyncio
 
    from app.lib.alchemy_db import SessionLocal, engine
    from app.rag.rerank import search_reranked

    OLD_Q004_ANSWER = (
        "FastAPI and Starlette are based on the ASGI (Asynchronous Server "
        "Gateway Interface) standard, which is being developed by members of "
        "the Django core team. ASGI improves interoperability among various "
        "tools in the Python ecosystem [6098]. Additionally, FastAPI uses "
        "Starlette as its foundation, which is a lightweight ASGI "
        "framework/toolkit designed for building high-performance asyncio "
        "services [6097][6072]."
    )

    Q004 = "What async libraries are FastAPI and Starlette based on?"

    async def main() -> None:
        try:
            async with SessionLocal() as session:
                res = await verify_answer(session, OLD_Q004_ANSWER, Q004, search_reranked)
                # print(res)

        finally:
            await engine.dispose()



    asyncio.run(main())
