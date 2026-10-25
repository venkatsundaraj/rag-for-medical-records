"""Pydantic schemas for verification -- add to app/schemas/rag.py (or a
new app/schemas/verify.py and import from there).

Wire-format mirror of app.verify.verdict.to_dict(): the dashboard and
the eval runs see the same shape as API callers.
"""

from pydantic import BaseModel, Field


class ClaimEvidence(BaseModel):
    chunk_id: int
    source: str
    title: str
    excerpt: str


class ClaimVerdictOut(BaseModel):
    text: str
    label: str                              # supported | contradicted | no_evidence
    rationale: str
    evidence: ClaimEvidence | None = None
    candidate_ids: list[int] = []


class VerificationOut(BaseModel):
    status: str                             # verified | unverified | contradicted | no_claims
    grounded_rate: float
    counts: dict[str, int]
    claims: list[ClaimVerdictOut]
    skipped: list[str]
    timing_ms: dict[str, int]
    judge_model: str


# ---- POST /api/verify : verify any (question, answer) pair --------------
class VerifyRequest(BaseModel):
    question: str | None = None
    answer: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=10)


# ---- additions to the existing rag schemas ------------------------------
# RagQueryRequest gains:
#     verify: bool = False
# RagQueryResponse gains:
#     verification: VerificationOut | None = None
# RagDebug gains:
#     verify_ms: int | None = None