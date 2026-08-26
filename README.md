# PubMed Semantic Search

Hybrid semantic search over PubMed RCT abstracts: a fine-tuned bi-encoder for
dense retrieval fused with BM25 for lexical matching, served by FastAPI with
JWT auth, chat history, and an optional live NHS scraper.

- **Corpus:** 17,500 PubMed RCT abstracts
- **Model:** `models/biomed-miniLM` — MiniLM-L6-v2 fine-tuned with
  `MultipleNegativesRankingLoss` on 78k query/abstract pairs
- **Index:** FAISS `IndexFlatIP` over 384-d normalised embeddings (cosine)
- **Warm query latency:** ~20 ms dense, ~32 ms hybrid (p50, CPU)

---

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows
# python3 -m venv .venv && source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
python -c "import secrets;print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET

uvicorn src.app.main:app --reload --port 8000
```

Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the
OpenAPI console.

> The index and model are **not** in this repo (114 MB of build artifacts).
> See [Building the index](#building-the-index) to regenerate them, or copy an
> existing `data/cache/` and `models/` into place.

### Docker

```bash
docker compose up --build
```

`data/` and `models/` are bind-mounted rather than baked into the image, so
they must exist on the host first.

---

## How retrieval works

A query is scored by two independent retrievers and the results are fused:

```
final_score = α · dense_score + (1 − α) · bm25_score        (α = HYBRID_ALPHA)
```

Both sides are min-max normalised over the candidate pool first, because raw
cosine similarity and BM25 scores are not on comparable scales. Both retrievers
propose `HYBRID_CANDIDATES` documents and the union is re-ranked, so a document
either one finds can still surface — that union is what lifts recall.

Optionally a cross-encoder (`RERANK_ENABLED=true`) re-scores the top
`RERANK_CANDIDATES` hits. It reads query and document jointly, so it is much
more accurate than the bi-encoder but too slow to run over the whole corpus.
If the reranker fails to load, retrieval degrades to the fused ranking rather
than erroring.

### Index/model safety check

Querying a FAISS index with a *different* model than it was built with returns
confident nonsense rather than an error. On startup the service compares
`EMBEDDING_MODEL` against the `model_path` recorded in
`data/cache/index_meta.json` and refuses to serve on a mismatch. It also
verifies that the embedding dimension and the document count line up.

---

## Evaluation

```bash
python -m eval.eval_runner --n 300
python -m eval.eval_runner --n 300 --configs dense bm25 hybrid:0.3 hybrid:0.5
```

Measured on 200 held-out queries against all 17,500 documents:

| config       |   R@1 |   R@5 |  R@10 | MRR@10 | p50 ms |
|--------------|------:|------:|------:|-------:|-------:|
| dense only   | 0.640 | 0.820 | 0.865 |  0.720 |   17.4 |
| BM25 only    | 0.945 | 0.980 | 0.995 |  0.961 |   33.5 |
| hybrid α=0.3 | 0.950 | 0.985 | 0.995 |  0.967 |   31.6 |
| hybrid α=0.5 | 0.890 | 0.980 | 0.985 |  0.928 |   30.9 |
| hybrid α=0.7 | 0.810 | 0.905 | 0.930 |  0.853 |   30.9 |

### ⚠️ What these numbers do and do not show

`scripts/make_pairs_pubmed.py` builds the train/val pairs by sampling sentences
**out of** an abstract and using that same abstract as the positive. Every
validation query is therefore a verbatim substring of its own gold document.

So this table measures *"can you find the document this sentence was copied
from"* — near-duplicate detection, not semantic search. It structurally favours
lexical matching, which is why BM25 scores near-perfectly. **That is expected,
not evidence that BM25 is the better retriever for real queries.**

Treat these as a **regression signal**: a change that drops recall here has
probably broken something. To measure genuine search quality you need queries
written independently of the documents — human-written questions with judged
relevant documents, or an established benchmark such as BEIR, NFCorpus, or
TREC-COVID.

The same caveat applies to the fine-tune itself: the model was trained on
sentence→abstract pairs from the same distribution, so its validation score
overstates how well it generalises to real user phrasing.

`HYBRID_ALPHA` defaults to **0.5** rather than the 0.3 that maximises the table
above, precisely so the default is not overfitted to a lexically-biased
benchmark.

---

## Configuration

All settings load from `.env` (see `.env.example`). Notable ones:

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `dev` | `prod` makes `JWT_SECRET` mandatory |
| `JWT_SECRET` | *(random in dev)* | Token signing key. **Required in prod.** |
| `EMBEDDING_MODEL` | `models/biomed-miniLM` | Must match the index build model |
| `INDEX_PATH` | `data/cache/faiss.index` | FAISS index |
| `CORPUS_JSONL_PATH` | `data/cache/corpus.jsonl` | Document texts, aligned to the index |
| `HYBRID_ENABLED` | `true` | Fuse BM25 with dense retrieval |
| `HYBRID_ALPHA` | `0.5` | Dense weight; `0.0` = pure BM25, `1.0` = pure dense |
| `RERANK_ENABLED` | `false` | Cross-encoder reranking (slower, more accurate) |
| `CORS_ORIGINS` | *(empty)* | Comma-separated. Empty ⇒ `*` **without** credentials |
| `RATE_LIMIT_TIMES` / `_SECONDS` | `30` / `60` | Per-client limit on expensive routes |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limiting; optional |

In dev, an unset `JWT_SECRET` generates a random per-process key, so tokens
simply stop working across restarts. In `ENV=prod` the app refuses to boot
without one — there is no shared fallback constant anywhere in the source.

If Redis is unreachable, rate limiting is disabled with a warning rather than
failing every protected request.

---

## API

| Method | Path | Auth | Notes |
|---|---|:--:|---|
| `GET`  | `/health` | — | Liveness; never touches the index |
| `GET`  | `/v1/ready` | — | Reports whether the index is loaded |
| `POST` | `/v1/auth/register` | — | |
| `POST` | `/v1/auth/login` | — | Form-encoded, returns a bearer token |
| `GET`  | `/v1/auth/me` | ✔ | |
| `GET`  | `/v1/search?q=…&k=10` | — | Rate limited |
| `POST` | `/v1/search` | — | Per-request `hybrid` / `rerank` overrides |
| `GET`  | `/v1/search/stats` | — | Index provenance — which model is actually serving |
| `GET`  | `/v1/chat/conversations` | ✔ | Scoped to the calling user |
| `POST` | `/v1/chat/messages` | ✔ | |
| `POST` | `/v1/ingest/web` | ✔ | Stages documents to `data/scraped/` |
| `POST` | `/v1/rewrite` | — | Grammar correction (LanguageTool) |
| `GET`  | `/v1/nhs/search?query=…` | — | Live NHS scrape; network-bound |

```bash
curl "http://localhost:8000/v1/search?q=insulin%20resistance%20treatment&k=5"
```

---

## Building the index

```bash
# 1. CSV -> train/val pairs
python scripts/make_pairs_pubmed.py data/raw/pubmed_rct20k.csv

# 2. Fine-tune the bi-encoder (optional; a trained model is expected at models/)
python -m src.app.train.finetune_retriever \
    data/processed/train_pairs.jsonl data/processed/val_pairs.jsonl models/biomed-miniLM

# 3. Flatten pairs into a corpus, then embed + index it
python -m src.app.index.make_corpus_from_pairs \
    --inputs data/processed/train_pairs.jsonl --out data/raw/corpus.txt
python -m src.app.index.build_index \
    --model-path models/biomed-miniLM --input data/raw/corpus.txt --normalize
```

Step 3 writes `faiss.index`, `embeddings.npy`, `corpus.jsonl` and
`index_meta.json` into `data/cache/`. `index_meta.json` records the model used,
which is what the startup safety check reads.

Convenience wrappers live in `scripts/` and `make`:

```bash
make run      # dev server
make test     # pytest
make eval     # retrieval metrics
make reindex  # rebuild the FAISS index
```

---

## Tests

```bash
pytest              # 68 tests, ~5s
pytest --cov=src    # with coverage
```

The suite deliberately never loads the real index or transformer — a stub
corpus is injected instead, keeping the whole run at a few seconds. Retrieval
maths (BM25 ranking, score normalisation, fusion) is tested directly against
that fixture.

---

## Project layout

```
src/app/
  core/        config, logging, security (JWT), rate limiting
  db/          SQLAlchemy engine, session, table bootstrap
  models/      ORM models: User, Conversation, Message
  schemas/     Pydantic request/response models
  routers/     auth, chat, search, ingest, rewrite, nhs_live
  services/    retriever.py (dense+hybrid), lexical.py (BM25)
  index/       corpus preparation and FAISS index building
  scraper/     NHS conditions scraper
  train/       bi-encoder fine-tuning
eval/          retrieval metrics harness
tests/         pytest suite
```

## Known limitations

- **The evaluation set cannot measure real semantic quality** (see above). This
  is the single biggest gap in the project.
- `data/raw/pubmed_rct20K/validaition.txt` is misspelled upstream and unused.
- Schema changes rely on `create_all`, which creates missing tables but never
  alters existing ones. Alembic is **not** set up (the `alembic/` directory was
  empty and has been removed), so adding a column to a live database currently
  requires a manual migration.
- The NHS scraper parses live HTML and will break when nhs.uk changes markup.
- `/v1/rewrite` calls the public LanguageTool API, which is rate limited and
  sends text to a third party.
