from dataclasses import dataclass, field
from openai import AsyncOpenAI
from app.config import settings
import json
from app.rag.embedding import EMBEDDING

_JUDGE_SYSTEM = """\
You are a strict evaluator of RAG answers. You will get a question, source
passages, the system's answer, and a reference answer.
 
Score two things from 0.0 to 1.0:
- faithfulness: is every factual claim in the answer supported by the source
  passages? Deduct for any claim that contradicts the sources or adds outside
  knowledge, even if the claim is true in the real world.
- relevance: does the answer actually address the question, and is it
  consistent with the reference answer?
 
If the answer is a refusal ("I don't know..."), set faithfulness to 1.0
(refusing adds no unsupported claims) and score relevance on whether refusing
was the right call given the sources.
 
Respond with ONLY a JSON object, no markdown fences:
{"faithfulness": 0.0, "relevance": 0.0, "unsupported_claims": ["..."], "notes": "..."}
"""

JUDGE_MODEL = "gpt-4o-mini" 

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=5)

@dataclass(frozen=True, slots=True)
class JudgeClaim:
    faithfulness:float
    relevance:float
    unsupported_claims:list[str]
    notes:str


async def judge_response(question:str, answer:str, context_texts:list[str], ref_answer:str, model:str = EMBEDDING)->JudgeClaim:
    user_message = (
        f"Question:\n{question}\n\n"
        f"Source Object:\n{context_texts}\n\n"
        f"System answer:\n{answer}\n\n"
        f"Reference answer:\n{ref_answer}"

    )

    resp = await _client.chat.completions.create(
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        model=JUDGE_MODEL
    )

    raw = (resp.choices[0].message.content or "").strip()
    raw = raw.removeprefix("```json").removesuffix('```').removeprefix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        JudgeClaim(0.0, 0.0, [],f"judge returned unparseable output: {raw[:200]}")

    return JudgeClaim(
        faithfulness=float(data.get("faithfulness",0.0)),
        relevance=float(data.get("relevance",0.0)),
        unsupported_claims=list(data.get("unsupported_claims",0.0)),
        notes=str(data.get("notes",0.0))
    )

