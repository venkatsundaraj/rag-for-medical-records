"""Verification endpoints.

  POST /api/verify                 verify any (question, answer) pair
  GET  /api/verify/runs            list verification_runs/*.json (dashboard)
  GET  /api/verify/runs/{name}     one run, full rows

Plus the `verify: bool` flag on POST /api/rag/query -- see the patch at
the bottom of this file, which goes into app/api/routes/rag_router.py.

The searcher is fixed to hybrid_rerank: task 3 measured it at 100%
contradicted-evidence hit@5 vs 89% for hybrid. The cost of that choice
is the retrieve_ms you will see in every response.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.alchemy_db import get_db
from app.rag.rerank import search_reranked
from app.schemas.verify_schema import VerificationOut, VerifyRequest
from app.verify.verdict import to_dict, verify_answer

router = APIRouter(tags=["verify"])

RUNS_DIR = Path("verification_runs")
VERIFY_SEARCHER = search_reranked


@router.post("", response_model=VerificationOut)
async def verify(body: VerifyRequest, db: AsyncSession = Depends(get_db)) -> VerificationOut:
    av = await verify_answer(body.answer, body.question, VERIFY_SEARCHER, db, k=body.k)
    return VerificationOut(**to_dict(av))


@router.get("/runs")
def list_runs() -> list[dict]:
    """config + aggregates of every saved verification run, newest first.
    Same contract as /api/eval/runs so the dashboard can reuse its loader."""
    out = []
    for p in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or "aggregates" not in data:
            continue
        kind = p.stem.split("_", 2)[-1]          # e.g. verify_20261002_..., entailment_retrieved_...
        out.append({"name": p.stem, "kind": kind,
                    "config": data.get("config", {}), "aggregates": data["aggregates"]})
    return out


@router.get("/runs/{name}")
def get_run(name: str) -> dict:
    if "/" in name or ".." in name:
        raise HTTPException(400, "bad name")
    p = RUNS_DIR / f"{name}.json"
    if not p.is_file():
        raise HTTPException(404, "no such run")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# PATCH for app/api/routes/rag_router.py -- the `verify` flag.
#
#   from app.rag.rerank import search_reranked
#   from app.schemas.verify import VerificationOut
#   from app.verify.verdict import to_dict, verify_answer
#
#   @router.post("/query", response_model=RagQueryResponse)
#   async def query_rag(body: RagQueryRequest, db: AsyncSession = Depends(get_db)):
#       result = await answer_question(db, question=body.question, k=body.k,
#                                      strategy=body.strategy)      # unchanged
#
#       verification, verify_ms = None, None
#       if body.verify:
#           av = await verify_answer(result.answer, body.question, search_reranked, db,
#                                    k=5, strategy=body.strategy)
#           verification = VerificationOut(**to_dict(av))
#           verify_ms = av.timing_ms["total"]
#
#       return RagQueryResponse(
#           answer=result.answer,
#           citations=[...unchanged...],
#           verification=verification,
#           debug=RagDebug(..., verify_ms=verify_ms),
#       )
#
# Register in main.py next to the others:
#   from app.api.routes.verify_router import router as verify_router
#   app.include_router(verify_router)
# ---------------------------------------------------------------------------