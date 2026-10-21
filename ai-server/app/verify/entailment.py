from app.config import settings
from anthropic import AsyncAnthropic
import asyncio
from app.verify.evidence import Evidence
from dataclasses import dataclass

JUDGE_MODEL = "claude-sonnet-5-5"
LABELS = ('supported', 'contradicted', 'no_evidence')

_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=5)


_VERDICT_TOOL = {
    "name": "record_verdict",
    "description": "Record the verdict for one claim against the supplied evidence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": list(LABELS)},
            "evidence_index": {
                "type": "integer",
                "description": "1-based index of the single passage that decides the verdict; 0 when label is no_evidence.",
            },
            "rationale": {
                "type": "string",
                "description": "One sentence. Quote the deciding phrase from the evidence when there is one.",
            },
        },
        "required": ["label", "evidence_index", "rationale"],
    },
}
 
_SYSTEM = """You are a strict fact-checker. You receive one CLAIM and numbered EVIDENCE passages from a documentation corpus. Decide whether the evidence supports the claim, contradicts it, or does not settle it.
 
Rules:
1. JUDGE ONLY FROM THE EVIDENCE. Your own knowledge of the subject is irrelevant. A claim you know to be true is still no_evidence if the passages do not state or entail it.
2. supported: a passage states the claim or entails it without a leap. Paraphrase is fine; an extra inference step is not.
3. contradicted: a passage asserts something INCOMPATIBLE with the claim -- the opposite fact, a different value, a different owner, a scope the claim violates. Absence of a fact is never a contradiction.
4. no_evidence: the passages are about the topic but do not decide this specific claim, or are about something else entirely. Choose this whenever you would have to guess.
5. SCOPE MATTERS. "on the sync engine", "by default", "with def" are part of the claim. A passage about the async engine does not support a claim about the sync engine; it may contradict it if it states the engines differ.
6. Code blocks count as evidence: what the code demonstrably does supports a claim about it.
7. Cite exactly one passage index (the decisive one) and quote its deciding phrase in the rationale.
8. Always respond by calling the record_verdict tool. Never answer in prose.
9. If your rationale would need words like "implies", "presumably", "small inference", or "loose match", the label is no_evidence. Hedged support is not support."""

@dataclass(slots=True, frozen=True)
class Verdict:
    label:str
    evidence_index:int
    rationale:str
    model:str


def _format_evidence(evidence: list[Evidence]) -> str:
    if not evidence:
        return "(no passages retrieved)"
    return "\n\n".join(
        f"[{i}] source: {e.source} — {e.title}\n{e.content.strip()}"
        for i, e in enumerate(evidence, 1)
    )


async def judge_claim(claim:str, evidence:list[Evidence], model:str = JUDGE_MODEL)->Verdict:
    user = f"CLAIM:\n{claim}\n\nEVIDENCE:\n{_format_evidence(evidence)}"
    resp = await _client.messages.create(model=model, messages=[{"role": "user", "content": user}],system=_SYSTEM, tools=[_VERDICT_TOOL], tool_choice={"type": "auto"}, max_tokens=1024, )

    truncated = resp.stop_reason == "max_tokens"
    tag = "[truncated] " if truncated else ""

    # print(resp)
    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_verdict":
            data = block.input
            label = data.get('label','')
            if label not in LABELS:
                label = 'no_evidence'
            idx = int(data.get('evidence_index') or 0)

            if label == "no_evidence" or not 1 <= idx <=len(evidence):
                idx = 0

            return Verdict(label=label, evidence_index=idx, rationale=str(data.get("rationale", "")), model=model)

    return Verdict(label="no_evidence", evidence_index=0,
                   rationale="judge returned no verdict", model=model)



async def judge_many(pairs:list[tuple[str, list[Evidence]]], model:str = JUDGE_MODEL, concurreny:int = 4):
    sem = asyncio.Semaphore(concurreny)

    async def one(c:str, e:list[Evidence]):
        async with sem:
            return await judge_claim(c, e, model)

    return await asyncio.gather(*(one(c, e) for c,e in pairs))


async def main():
    ev = [Evidence(chunk_id=0, source="async.md", title="Async", content=(
        "FastAPI and Starlette are based on AnyIO, which makes it compatible "
        "with both Python's standard library asyncio and Trio."
    ), char_start=0, char_end=0, score=0.0)]

    for claim in [
    "FastAPI and Starlette are based on AnyIO.",                              # supported
    "FastAPI and Starlette are based on the ASGI standard as their async library.",  # contradicted
    "Traefik is written in Go.",                                              # no_evidence
        ]:

        v = await judge_claim(claim, ev, JUDGE_MODEL)
        print(f"{v.label:<13} [{v.evidence_index}] {claim}\n      {v.rationale}")


    



if __name__ == "__main__":
    asyncio.run(main())