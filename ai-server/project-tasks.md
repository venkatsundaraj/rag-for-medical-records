# Production RAG: task checklist

## ContextThe goal is to build a production-grade RAG from scratch inside `ai-server/` to deepen AI-engineering skill. The focus is on measurable improvement, so the end result can be stated as "hybrid search raised retrieval precision from X to Y".

Current state of `ai-server/`:- FastAPI, async SQLAlchemy, Alembic and Postgres are wired up (`app/lib/alchemy_db.py`, `migrations/`).- The only model is `todos`. There is no pgvector, no RAG tables, no Docker and no tests yet.- `app/models/todo.py` and `app/api/routes/todo_router.py` are the patterns to copy for new models and routers.
Rule for the whole project: **measure first, then improve.** Build the eval harness right after the naive baseline. Every later task ends with an eval run you can compare.

## Tasks (in order)

- [ ] **1. Set up the data layer.** - Pick a document corpus of about 20–50 docs. - Enable the `pgvector` extension through an Alembic migration. - Add `documents` and `chunks` tables. A chunk has its text, an embedding (a `vector` column), a `tsvector` column, a position in its source doc, and a chunking-strategy label. - _You'll learn:_ a vector DB is just a column type plus an index (HNSW).
- [ ] **2. Build naive ingestion.** - Pipeline: load docs, split them into fixed-size chunks, embed each chunk, store it. - Expose an ingest endpoint or script. - _You'll learn:_ the embedding model's input limits, batching, and why chunk size matters.
- [ ] **3. Build the naive RAG: vector search, answer, citations.** - Embed the query and run a cosine top-k search in SQL. - Put the chunks into the prompt, each tagged with its chunk ID. - Have the LLM answer with inline `[chunk_id]` citations. The API returns the answer plus the cited chunks (doc, position, text). - _This is your baseline._
- [ ] **4. Build the eval harness and record baseline numbers.** - Hand-write a golden dataset of 30–50 questions, each with its expected answer and the IDs of the chunk(s) or source it should come from. - Measure: - retrieval precision@k, recall@k and MRR (plain Python) - faithfulness and answer relevance (RAGAS or your own LLM-as-judge) - citation correctness - Save each run's results (config, metrics, timestamp) to a table or JSON file.
- [ ] **5. Improve chunking and compare.** - Add recursive chunking (split on paragraph, then sentence, then words, with overlap) and semantic chunking (split where embedding similarity drops). - Re-ingest the corpus under each strategy label and run the eval on each. - Keep the winner.
- [ ] **6. Add hybrid search.** - Add BM25-style keyword search using Postgres full-text search (`tsvector`, `ts_rank`, a GIN index). - Merge it with the vector results using Reciprocal Rank Fusion. - Run the eval and compare against vector-only.
- [ ] **7. Add re-ranking.** - Take the top ~20 hybrid results and re-score them with a cross-encoder: `bge-reranker` locally or Cohere Rerank. - Keep the top ~5. - Run the eval and note the latency cost alongside the quality gain.
- [ ] **8. Build an eval dashboard.** - Build a simple page, either in `client/` (Next.js) or with Streamlit. - Show each config (naive, better chunking, hybrid, hybrid plus rerank) side by side for every metric. - This is your interview artifact.
- [ ] **9. Dockerize.** - Write a `Dockerfile` for the API. - Write a `docker-compose.yml` with the `pgvector/pgvector` Postgres image. - Run Alembic migrations on startup and handle env-based config and secrets. - Done when `docker compose up` runs the whole stack locally.
- [ ] **10. Deploy and write it up.** - Deploy to a cheap VM (Hetzner, DigitalOcean or Lightsail) with Postgres and pgvector. - Run the eval against the deployed instance. - Write a README covering the architecture, the before/after metrics table and the trade-offs you found.

## Decisions to make as we go (not needed up front)- Corpus choice (task 1).- Embedding model: an API model or a local sentence-transformers model. This sets the vector dimension (task 1).- LLM provider for answers and judging (task 3).- RAGAS or a hand-rolled judge (task 4).

## VerificationEach task is done when:- it works end-to-end through the API or script, and- from task 4 onward, it has an eval run saved with numbers you can compare against the previous task.
