
from pathlib import Path
from app.rag.loader import load_corpus, LoadedDocument
from app.lib.alchemy_db import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Select, delete, update
from app.rag.embedding import embed_text
from app.models.pdf_schema import Document, Chunk
from app.rag.chunking import chunk_text, FIXED_STRATEGY_LABEL
from app.lib.alchemy_db import engine
from app.rag.chunking import CHUNKERS
import asyncio




EMBED_DB_BATCH = 100

async def _ingest_chunk(session:AsyncSession, doc_id:int, content:str, strategy:str):

    chunker = CHUNKERS[strategy] 

    txt = chunker(content)

    session.add_all(Chunk(content = c.content, document_id = doc_id, strategy = strategy,char_start=c.char_start, char_end=c.char_end, token_count=c.token_count, chunk_index = c.index, embedding = None ) for c in txt)

    return len(txt)



async def ingest_one(session:AsyncSession, loaded:LoadedDocument, strategy:str):

    doc = (await session.execute(Select(Document).where(Document.source == loaded.source))).scalar_one_or_none()

    if doc is None:

        doc = Document(title = loaded.title, meta=loaded.meta, source = loaded.source, content_hash=loaded.content_hash, content=loaded.content)

        session.add(doc)
        await session.flush()

        n = await _ingest_chunk(session, doc.id, loaded.content, strategy)

        return f"inserted ({n} chunks)"

    if doc.content_hash == loaded.content_hash:

        exists = (await session.execute(Select(Chunk).where(Chunk.document_id == doc.id, Chunk.strategy == strategy).limit(1))).scalar_one_or_none()

        if exists is not None:
            return "skipped"
        n = await _ingest_chunk(session, doc.id, loaded.content, strategy)
        return f"chunked new strategy ({n} chunks)"

    doc.title = loaded.title
    doc.meta = loaded.meta
    doc.content = loaded.content
    doc.content_hash = loaded.content_hash

    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    n = await _ingest_chunk(session, doc.id, loaded.content, strategy)

    return f"chunked new strategy ({n} chunks)"

async def _fill_embeddings(session:AsyncSession):

    filled = 0
    while True:
        rows = (await session.execute(Select(Chunk.id, Chunk.content).where(Chunk.embedding.is_(None)).order_by(Chunk.id).limit(EMBED_DB_BATCH))).all()

        if not rows:
            return filled

        vectors = await embed_text([content for _, content in rows])

        for (chunk_id, _), vec in zip(rows, vectors):
            await session.execute(update(Chunk).where(Chunk.id == chunk_id).values(embedding = vec))

        await session.commit()
        filled += len(rows)
        print(f"  embedded {filled} chunks...")

            
    


async def ingest_corpus(corpus_dir:Path, strategy:str=FIXED_STRATEGY_LABEL):
    docs = load_corpus(corpus_dir=corpus_dir)

    # print(docs)

    if docs is None:
        return []

    async with SessionLocal() as session:
        for d in docs:
            outcome = await ingest_one(session, d, strategy)
            await session.commit()
            print(f"  {d.source}: {outcome}")

        print("Phase B: filling embeddings")
        h = await _fill_embeddings(session)
           
    return "embedded is completed"



BASE_DIR = Path(__file__).resolve().parent.parent.parent
FILE_PATH = BASE_DIR / "data" / "corpus" 

async def main():
    import sys
    strategy = sys.argv[1] if len(sys.argv) > 1 else FIXED_STRATEGY_LABEL
    try:
        await ingest_corpus(FILE_PATH, strategy=strategy)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())