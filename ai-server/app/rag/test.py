from dataclasses import dataclass
from app.lib.alchemy_db import engine
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import hashlib 
import tiktoken
from openai import AsyncOpenAI
from app.config import settings
import asyncio
from app.lib.alchemy_db import SessionLocal
from app.models.pdf_schema import Document, Chunk
from sqlalchemy import Select, update, delete


@dataclass
class TextContent:
    title:str
    content:str
    content_hash:str
    source:str
    meta:dict

@dataclass
class TextChunk:
    index:int
    char_start:int
    char_end:int
    content:str
    token_count:int


_ENCODING = tiktoken.get_encoding('cl100k_base')
EMBEDDING_VECTOR = 1536
MODAL_NAME = "text-embedding-3-small"

_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    max_retries=5
)

# loading - str (dir path) -> list[TextContent]

def load_text(file_dir:Path, corpus_dir:Path)->list[TextContent]:

    content = file_dir.read_text(encoding="utf-8")

    relative_path = file_dir.relative_to(corpus_dir)

    source = relative_path.as_posix()

    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    title = next((d[2:].strip() for d in content.splitlines() if d.startswith('# ')), file_dir.stem)

    meta = {
            "source":source,
             "url": f"https://fastapi.tiangolo.com/{source.removesuffix('.md')}/",
        }

    return TextContent(title=title, content=content, content_hash=content_hash, meta=meta, source=source)

BASE_PATH = Path(__file__).resolve().parent.parent.parent
FILE_PATH = BASE_PATH / "data" / "corpus-1" 


def main_loader(corpus_path:Path):
    items = []
    for c in corpus_path.rglob('*.md'):
        item = load_text(c, corpus_path)
        items.append(item)
    # print(items)
    return items


# chunking str -> list[list[float]]
CHUNK_LENGTH = 1000
OVERLAP = 150
FIXED_STRATEGY_LABEL = f"fixed_c{CHUNK_LENGTH}_o{OVERLAP}"

def chunk_text(text:str, chunk_lenth:int = CHUNK_LENGTH, overlap:int = OVERLAP)->list[TextChunk]:

    if not text:
        return []

    if overlap > chunk_lenth:
        ValueError('it need to higher')

    index = 0
    start = 0

    items:list[TextChunk] = []

    while start < len(text):
        end = min(start + chunk_lenth, len(text))
        window = text[start:end]

        if window.strip():
            items.append(TextChunk(index = index, char_start = start, char_end = end, content = window, token_count = len(_ENCODING.encode(window))))

            index +=1

        if end == len(text):
            break

        start = end - overlap

    for chunk in items:
            assert text[chunk.char_start : chunk.char_end] == chunk.content, (
                f"offset rule violated at chunk {chunk.index} "
                f"({chunk.char_start}:{chunk.char_end})"
            )   
    return items

CONTENT_PATH = FILE_PATH / "async.md"


# embedding list[str] -> list[list[float]]
BATCH = 10
async def embed_text(texts:list[str]) -> list[list[float]]:

    items:list[list[float]] = []

    for i in range(0, len(texts), BATCH):
        txt = texts[i:i+BATCH]

        res = await _client.embeddings.create(
            model=MODAL_NAME,
            input=txt
        )

        items.extend(d.embedding for d in sorted(res.data, key=lambda d:d.index))
    assert len(texts) == len(items), (f"embedding count mismatch: sent {len(texts)}, got {len(items)}")
    
    return items


# ingestion - multiple operation

async def _ingest_chunks(session:AsyncSession, doc_id:str, content:str, strategy:str):
    texts = chunk_text(content)

    session.add_all(Chunk(
        document_id = doc_id, 
        content = c.content, 
        char_start = c.char_start, 
        char_end = c.char_end, 
        strategy = strategy, 
        embedding = None, 
        chunk_index = c.index, 
        token_count = c.token_count
        ) for c in texts)
    
    return f"chunk updated without embeddings - {len(texts)}"

async def ingest_document(session:AsyncSession, loaded:TextContent, strategy:str):
    # no document
    doc = (await session.execute(Select(Document).where(Document.source == loaded.source))).scalar_one_or_none()

    if doc is None:
        doc =  Document(
            title = loaded.title,
            source = loaded.source,
            content = loaded.content,
            content_hash = loaded.content_hash,
            meta = loaded.meta
        )
        session.add(doc)
        await session.flush()

        n = await _ingest_chunks(session, doc.id, loaded.content, strategy)

        return n
        
    # adding chunks when hash presents while strategy differs
    if doc.content_hash == loaded.content_hash:
        exists = await session.execute(Select(Chunk).where(Chunk.document_id == doc.id,Chunk.strategy == strategy))
        if exists is not None:
            return "skipped"

        await _ingest_chunks(session, doc.id, loaded.content, strategy)
        return f"inserted ({n} chunks)"
    
    # updating all
    doc.meta = loaded.meta
    doc.title = loaded.title
    doc.content = loaded.content
    doc.content_hash = loaded.content_hash
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    n = await _ingest_chunks(session, doc.id, loaded.content, strategy)

    return f"chunked new strategy ({n} chunks) "

async def _fill_embeddings(session:AsyncSession):

    filled = 0

    while True:
        rows = (await session.execute(Select(Chunk.id, Chunk.content).where(Chunk.embedding.is_(None)).order_by(Chunk.id).limit(BATCH))).all()

        if not rows:
            return filled
        
        vectors = await embed_text([content for _, content in rows])

        for (chunk_id,_),vec in zip(rows, vectors):
            await session.execute(update(Chunk).where(Chunk.id == chunk_id).values(embedding = vec))

        await session.commit()
        filled += len(rows)
        print(f"  embedded {filled} chunks...")

async def start_ingetion(file_path:Path):
    async with SessionLocal() as session:
        for d in main_loader(file_path):
            
            await ingest_document(session, d, strategy=FIXED_STRATEGY_LABEL)
            await session.commit()

            print("Phase B: filling embeddings")
            h = await _fill_embeddings(session)
            return "embedded is completed"
            



async def main_ingest():
    try:
        await start_ingetion(FILE_PATH)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print(True)
    # main_loader(FILE_PATH)

    content = CONTENT_PATH.read_text(encoding="utf-8")
    # chunk_text(content[0:70])
    # asyncio.run(embed_text([i.content for i in chunk_text(content[0:320])]))
    asyncio.run(main_ingest())
    