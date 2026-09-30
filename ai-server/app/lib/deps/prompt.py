

from app.rag.retrieval import RetrieveChunk

SYSTEM_PROMPT = """\
You are a technical assistant answering questions about the FastAPI documentation.
 
Rules:
1. Answer ONLY from the numbered sources provided. Do not use outside knowledge.
2. If the sources do not contain the answer, reply exactly: "I don't know based on the provided sources." Do not guess.
3. After each claim, cite the source id in square brackets, like [12]. \
Multiple ids are allowed, like [12][45]. Only cite ids that appear in the sources.
"""
 

def format_context(chunks:list[RetrieveChunk])->str:
    parts = []
    for c in chunks:
        parts.append(f"[{c.chunk_id}] {c.source} — \"{c.title}\"\n{c.content}")

    return "\n\n--\n\n".join(parts)

def _build_message(query:str, chunks:list[RetrieveChunk])->list[dict]:
    user_message = (
        f"sources:\n\n{format_context(chunks)}\n\n"
        f"Question:\n\n{query}\n\n"
        f"Answer with inline [id] citations."
                    )

    
    return [{"role": "system", "content": SYSTEM_PROMPT},{"role":"user", "content": user_message}]
