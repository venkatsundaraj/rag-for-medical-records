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

---

## Tasks (in order)

- [ ] **1. Build the claims golden dataset.**
  - Unit under test is now a _claim_, not a question. Create `data/golden/claims.jsonl`: `{claim_id, source_qid, claim, label, evidence}` where `label ∈ {supported, contradicted, no_evidence}` and `evidence` is `(source file, verbatim quote)` — same strategy-independent labeling trick as Project 1.
  - Seed it for free: your `--full` run files already contain every answer plus the judge's `unsupported_claims`. q004's old answers alone yield 3–4 labeled _contradicted_ claims. Harvest, then hand-label to ~80–100 claims with all three classes represented (aim ≥20 per class; write a few deliberately tricky _no_evidence_ ones — true facts your corpus simply doesn't contain).
  - _You'll learn:_ the difference between "false" and "unsupported" — the central distinction of the whole project. A claim can be true in the world and still `no_evidence` in your corpus.
  - **Done when:** the file loads, class counts printed, and 10 random labels survive your own re-review a day later.
- [ ] **2. Claim extraction (`app/verify/claims.py`).**
  - Pure-ish function: `extract_claims(answer: str) -> list[Claim]`. LLM call with a **structured output** (JSON schema / tool call — not regex over prose). Atomic = one verifiable fact per claim, pronouns resolved, no citations markers carried over.
  - Measure before iterating: run it over the 51 answers in your best `--full` run; score _coverage_ (did it find the claims your labels came from?) and _atomicity_ (manually sample 20 — compound claims count as misses). Record numbers, then iterate the prompt.
  - _You'll learn:_ schema-constrained generation, and that extraction quality caps everything downstream — a claim never extracted is never verified.
  - **Done when:** coverage ≥90% on labeled answers and the output validates against the schema on all 51 without a retry loop crutch.
- [ ] **3. Evidence retrieval per claim (`app/verify/evidence.py`).**
  - Thin wrapper over the existing `SEARCHERS` dispatch: `gather_evidence(session, claim, k, search_mode) -> list[RetrieveChunk]`. The claim text is the query. Start with `hybrid` (rerank's latency × N claims per answer will hurt; measure before paying it).
  - Measure: _evidence recall_ — for labeled claims, is the gold evidence span in the top-k? This is Project 1's recall@k reborn at claim granularity; reuse `spans_overlap`.
  - _You'll learn:_ claims are better queries than questions (declarative, entity-dense) — verify that hypothesis with numbers, don't assume it.
  - **Done when:** evidence recall measured for k ∈ {3, 5} under hybrid vs hybrid_rerank, and a chosen default written down with its reason.
- [ ] **4. Entailment judge (`app/verify/entailment.py`).**
  - `judge_entailment(claim, passages) -> {verdict, rationale}` — structured output, temperature 0, and **Claude or Gemini, never the GPT family that generated the answer**. This is the cross-family judge Project 1's case study promised.
  - Measure on the claims dataset: per-class precision/recall, confusion matrix, and the headline metric — **false-supported rate** (contradicted/no-evidence claims waved through). A verifier that rubber-stamps hallucinations is worse than none.
  - Optional but high-value experiment: also run a small local NLI model (e.g. a DeBERTa-NLI cross-encoder — same mechanics as your reranker) as a cheap baseline. "LLM judge beats/loses to a 400MB local model by X points at Y× the cost" is a result worth a post either way.
  - _You'll learn:_ entailment ≠ truth; judge calibration; why rationales make failures debuggable.
  - **Done when:** confusion matrix saved to a run file, false-supported rate < 10%, and the q048 disputed claim adjudicated — your new judge settles Project 1's open question.
- [ ] **5. Verdict aggregation (`app/verify/verdict.py`) + end-to-end eval.**
  - Combine per-claim verdicts into an answer-level result: confidence score, list of unsupported/contradicted claims with character offsets into the answer (your offset discipline, third application).
  - The acceptance test: run verification over all 51 answers from the best and the worst `--full` runs. **It must flag q004's old ASGI answer and pass the final AnyIO answer.** Compare answer-level flags against the old judge's faithfulness scores — where they disagree, read the rows and decide who's right; that analysis _is_ the write-up's core table.
  - **Done when:** a `verification_runs/` JSON exists with per-answer, per-claim results, and the q004 before/after screenshot-able.
- [ ] **6. Pipeline + API integration.**
  - `verify: bool = false` on `POST /api/rag/query`; when true, response gains `verification: {confidence, claims: [...]}`. One stage after `generate_res` — keyword arguments throughout; you know why.
  - Record per-stage cost and latency in the debug block (extraction call + N entailment calls adds up; measure ₹/query and ms/query honestly).
  - **Done when:** curl shows a verified answer end-to-end, and the latency/cost numbers are written down next to the quality gain.
- [ ] **7. Dashboard: verification view.**
  - Extend the Next.js dashboard: a claims table per answer (claim · verdict · evidence snippet), red highlighting for unsupported spans, and false-supported rate on the summary. Reuse the runs-listing pattern against `verification_runs/`.
  - **Done when:** the q004 autopsy is visible in a browser — the demo artifact for the launch post.
- [ ] **8. Deploy and write it up.**
  - Merge `verification` → main, push, let the webhook deploy; set the new env var (ANTHROPIC/GEMINI key) in Coolify; re-run the task-5 eval against the deployed instance (the 0.8438 ritual, new numbers).
  - README section + case study: pipeline diagram, judge confusion matrix, false-supported rate, cost/latency table, the q004 catch, and whatever negative result shows up — one always does, and it's the proof the methodology was real, again.
