from openai import AsyncOpenAI
from app.config import settings
from app.models.pdf_schema import EMBEDDING_DIM
from pathlib import Path
import asyncio


_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    max_retries=5
)

EMBEDDING = "text-embedding-3-small"
BATCH = 100

async def embed_text(text:list[str])->list[list[float]]:

    if not text:
        return []

    vectors:list[list[float]] = []
    for i in range(0, len(text), BATCH):
        text_item = text[i : i+BATCH]

        res = await _client.embeddings.create(
            input=text_item,
            model=EMBEDDING
        )

        vectors.extend(d.embedding for d in sorted(res.data, key=lambda d:d.index))

    assert len(text) == len(vectors), (f"embedding count mismatch: sent {len(text)}, got {len(vectors)}")
    return vectors



BASE_PATH = Path(__file__).resolve().parent.parent.parent
FILE_PATH = BASE_PATH / "data" / "corpus" / "async.md"

async def main():
    text = FILE_PATH.read_text(encoding="utf-8")
    chunk = [*text.splitlines()[0:10]]
    

    items = await embed_text(chunk)
    print(items)
    # return items


if __name__ == "__main__":
    asyncio.run(main())