from dataclasses import dataclass
import json
from app.lib.deps.rag_deps import _client
from app.config import settings

_EXTRACTION_MODEL = settings.EXTRACTION_MODEL

_CLAIM_SCHEMA = {
    "name": "claim_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "One atomic, self-contained factual claim.",
                        },
                        "verifiable": {
                            "type": "boolean",
                            "description": "False for opinions, hedges, and meta-statements that no document could confirm or deny.",
                        },
                    },
                    "required": ["text", "verifiable"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
}


_SYSTEM = """You decompose an answer into atomic factual claims for verification.
 
Rules:
1. ATOMIC: one verifiable fact per claim. Split compound sentences. \
A claim containing "and" usually wants to be two claims.
2. SELF-CONTAINED: resolve every pronoun and implicit reference. \
"It runs in a threadpool" becomes "A path operation function declared \
with def runs in a threadpool". A reader who has not seen the answer \
must understand the claim.
3. PRESERVE SCOPE AND QUALIFIERS: "on the sync engine", "by default", \
"in FastAPI", "unless X" are part of the fact. Dropping them changes \
the claim's truth value. Never generalize beyond what the answer said.
4. FAITHFUL: extract what the answer ASSERTS, including its framing -- \
even if you believe the assertion is wrong. You are restating, not correcting.
5. SKIP the non-factual: citations markers like [123], hedges \
("I think"), refusals ("I don't know"), and pure code blocks. Mark \
opinions or unverifiable meta-statements verifiable=false instead of \
rephrasing them into facts.
6. COMPLETE: every factual assertion in the answer must appear in some \
claim. Do not summarize several facts into one claim.
7. QUESTION FRAME: when the question is provided and the answer responds \
to it, each claim must carry the question's frame. If the question asks \
"what async libraries is X based on" and the answer names Y, the claim is \
"X is based on Y as its async library" -- not the weaker "X is based on Y". \
The answer asserts Y as the ANSWER to the question; preserve that assertion.
"""


 
@dataclass(frozen=True, slots=True)
class Claim:
    text:str
    verifiable:bool


async def extract_claims(answer:str,question: str | None = None, model:str = _EXTRACTION_MODEL)->list[Claim]:

    user = f"Answer to decompose:\n\n{answer}"

    if question:
        user = f"Question that was asked:\n\n{question}\n\n{user}"


    messages = [{"role":"user", "content": user}, {"role":"system", "content":_SYSTEM}]

    res = await _client.chat.completions.create(messages=messages, temperature=0, model=model, response_format={"type":"json_schema","json_schema":_CLAIM_SCHEMA})

    raw = res.choices[0].message.content or {}

    data = json.loads(raw)

    if not isinstance(data, dict) or "claims" not in data:
        return [] 

    return [Claim(text=d['text'], verifiable=d['verifiable']) for d in data["claims"]]





if __name__ == "__main__":

    import asyncio

    OLD_Q004_ANSWER = (
    "FastAPI and Starlette are based on the ASGI (Asynchronous Server "
    "Gateway Interface) standard, which is being developed by members of "
    "the Django core team. ASGI improves interoperability among various "
    "tools in the Python ecosystem [6098]. Additionally, FastAPI uses "
    "Starlette as its foundation, which is a lightweight ASGI "
    "framework/toolkit designed for building high-performance asyncio "
    "services [6097][6072]."
)


    async def main()->None:
        claims = await extract_claims(OLD_Q004_ANSWER, "What async libraries are FastAPI and Starlette based on?")
        # print(claims, )
        print(f"{len(claims)} claims:")
        for c in claims:
            flag = "  " if c.verifiable else "~ "
            print(f"  {flag}{c.text}")


    asyncio.run(main())