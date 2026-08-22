# LeetBot

LeetBot is a full-stack, RAG-based LeetCode assistant. It gives you context-aware hints, complexity analysis, and tailored problem recommendations — without just handing you the answer.

The backend runs a **production-grade RAG pipeline** on top of a 3,000+ problem dataset: hybrid BM25 + dense retrieval, query transformation (HyDE / multi-query), cross-encoder reranking, and a Redis semantic cache.

---

## Features

- **Intelligent Hints** — progressive, Socratic hints grounded in retrieved problem context
- **Complexity Analysis** — time and space complexity breakdown for submitted code
- **Smart Recommendations** — problems matched to your skill level and session history
- **Chat** — free-form conversation about any LeetCode problem
- **User Auth & Sessions** — JWT-based auth, persistent chat history and problem sessions
- **Production RAG Pipeline** — hybrid retrieval → query transform → reranker → semantic cache
- **RAG Eval Harness** — offline faithfulness scoring with a golden dataset (`backend/rag/eval/`)

---

## Tech Stack

**Frontend**
- React 19 + Vite
- Tailwind CSS v4
- React Router DOM, Axios
- React Hot Toast

**Backend**
- FastAPI (Python), async throughout
- MongoDB Atlas — problems, users, sessions
- Chroma — local persistent vector store
- Google Gemini (`gemini-embedding-001` for embeddings, `gemini-2.0-flash` for inference)
- LangChain (`langchain-google-genai`, `langchain-chroma`)
- Redis + RedisVL — semantic response cache
- `rank-bm25` — BM25 sparse retrieval leg
- JWT (`python-jose`) + `passlib[bcrypt]` auth

**Data Pipelines**
- `scraper/` — fetch → clean → upload to MongoDB
- `ingestion/` — chunk → embed → index into Chroma (batched, Gemini free-tier safe)

---

## Project Structure

```text
LEETBOT/
├── backend/
│   ├── main.py               # App entry point, CORS, router registration
│   ├── config.py             # All settings via env vars (_Settings class)
│   ├── db.py                 # MongoDB + Chroma connection management
│   ├── auth/                 # JWT creation/validation, bcrypt hashing, dependencies
│   ├── models/               # Pydantic schemas and MongoDB document models
│   ├── routers/              # API endpoints
│   │   ├── auth.py           # /auth  — register, login
│   │   ├── users.py          # /users — profile
│   │   ├── problems.py       # /problems — list, search, detail
│   │   ├── hints.py          # /hints — progressive RAG hints
│   │   ├── chat.py           # /chat  — streaming conversation
│   │   ├── complexity.py     # /complexity — code analysis
│   │   ├── recommend.py      # /recommend — personalised suggestions
│   │   └── sessions.py       # /sessions — session CRUD
│   └── rag/                  # Production RAG modules
│       ├── retriever.py      # Dense Chroma retrieval
│       ├── bm25_index.py     # BM25 sparse index (rank-bm25)
│       ├── hybrid_retriever.py  # RRF fusion of dense + sparse legs
│       ├── query_transform.py   # HyDE (vague) + multi-query (specific)
│       ├── cache.py          # Redis semantic cache (RedisVL)
│       └── eval/             # Offline RAG evaluation harness
│           ├── pipeline.py   # End-to-end eval pipeline
│           ├── scorer.py     # Faithfulness / relevance metrics (ragas)
│           ├── schema.py     # Eval data types
│           ├── golden_dataset.json
│           └── run.py        # CLI runner (exit 0/1/2)
│
├── scraper/
│   ├── fetch.py              # Scrapes raw problem data from LeetCode
│   ├── clean.py              # Cleans and normalises HTML/markdown
│   ├── upload.py             # Pushes cleaned data to MongoDB Atlas
│   └── run.py                # Orchestrates the 3-step pipeline
│
├── ingestion/
│   ├── chunker.py            # Splits problem text into semantic chunks
│   ├── embedder.py           # Generates Gemini embeddings
│   ├── indexer.py            # Upserts embeddings into Chroma
│   └── run.py                # Batched pipeline (default 10 problems/batch)
│
├── data/
│   ├── clean/                # 3,226 cleaned problem JSON files
│   └── raw/                  # 3,226 raw scraped problem JSON files
│
├── frontend/                 # React SPA
│   ├── src/                  # Components, pages, API utilities
│   ├── package.json
│   └── vite.config.js
│
├── Dockerfile
├── docker-compose.yml        # Runs backend with a persisted Chroma volume
├── render.yaml               # One-click Render.com deployment config
├── Procfile                  # Heroku / Railway start command
├── requirements.txt
└── .env.example
```

---

## RAG Pipeline

```
User query
    │
    ▼
Query Transform (optional, QUERY_TRANSFORM=true)
  ├── Vague query  → HyDE (generate hypothetical answer, embed that)
  └── Specific     → 2–3 reformulations, all fused with RRF
    │
    ▼
Hybrid Retrieval (optional, HYBRID_RETRIEVAL=true)
  ├── Dense leg  — Chroma cosine similarity (RERANKER_CANDIDATE_K candidates)
  └── Sparse leg — BM25 keyword search
  └── RRF fusion → top HYBRID_CANDIDATE_K docs
    │
    ▼
Reranker
  ├── local  — BAAI/bge-reranker-large (CrossEncoder, sentence-transformers)
  └── cohere — Cohere Rerank API
  └── keep top RERANKER_TOP_N docs above RERANKER_THRESHOLD
    │
    ▼
Semantic Cache check (Redis + RedisVL, cosine ≥ SEMANTIC_CACHE_THRESHOLD)
  ├── Hit  → return cached response immediately
  └── Miss → continue
    │
    ▼
LLM (Gemini) — generate hint / answer grounded in retrieved chunks
    │
    ▼
Write to semantic cache (TTL = SEMANTIC_CACHE_TTL_S)
```

All flags (`HYBRID_RETRIEVAL`, `QUERY_TRANSFORM`, `RERANKER_BACKEND`) are togglable via `.env` for A/B testing.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas cluster
- Google Gemini API key
- Redis (local or cloud) — required for semantic cache

### 1. Clone and install

```bash
git clone <repo-url>
cd LEETBOT

pip install -r requirements.txt

cd frontend
npm install
cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in MONGO_URI, GEMINI_API_KEY, JWT_SECRET, REDIS_URL
```

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Run ingestion (first time only)

```bash
python -m ingestion.run
```

This embeds and indexes all problems into Chroma. On the Gemini free tier this takes a while — lower `INGESTION_BATCH_SIZE` to 10 and set `INGESTION_BATCH_DELAY_S=65` to stay under rate limits.

### 4. Start the backend

```bash
uvicorn backend.main:app --reload
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 5. Start the frontend

```bash
cd frontend
npm run dev
# UI: http://localhost:5173
```

---

## Environment Variables

See `.env.example` for the full annotated list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | — | MongoDB Atlas connection string (required) |
| `GEMINI_API_KEY` | — | Google Gemini API key (required) |
| `GEMINI_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Embedding model |
| `GEMINI_MODEL_NAME` | `gemini-2.0-flash` | LLM for inference |
| `JWT_SECRET` | — | Random hex string (required) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for semantic cache |
| `HYBRID_RETRIEVAL` | `true` | BM25 + dense fusion |
| `QUERY_TRANSFORM` | `true` | HyDE / multi-query expansion |
| `RERANKER_BACKEND` | `local` | `local` or `cohere` |
| `RERANKER_TOP_N` | `4` | Chunks passed to LLM |
| `SEMANTIC_CACHE_THRESHOLD` | `0.92` | Min cosine similarity for cache hit |

---

## Running the RAG Eval

```bash
python -m backend.rag.eval.run
```

Exit codes: `0` = passed, `1` = faithfulness below `EVAL_FAITHFULNESS_THRESHOLD`, `2` = hard error.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (MongoDB + Chroma status) |
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login, returns JWT |
| `GET` | `/problems` | List / search problems |
| `GET` | `/problems/{slug}` | Problem detail |
| `POST` | `/hints` | Get RAG-powered hint |
| `POST` | `/chat` | Chat about a problem |
| `POST` | `/complexity` | Analyse code complexity |
| `POST` | `/recommend` | Get personalised recommendations |
| `GET/POST` | `/sessions` | Session management |
| `GET` | `/users/me` | Current user profile |

Full interactive docs at `/docs` (Swagger UI) when running locally.

---

## Docker

```bash
docker-compose up --build
```

Runs the backend on port 8000 with a named volume persisting Chroma data across restarts.

---

## Deployment

**Backend (Render / Railway)**

A `render.yaml` is included for one-click Render deploys. Set `MONGO_URI`, `GEMINI_API_KEY`, `JWT_SECRET`, and `CORS_ORIGINS` as secrets in the dashboard.

```bash
# Start command
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend (Vercel)**

Set root directory to `frontend` and add:

```env
VITE_API_URL=https://your-backend.onrender.com
```

See `DEPLOYMENT.md` for a full walkthrough.

---

## Data Pipeline (Scraper)

To refresh the problem dataset:

```bash
python -m scraper.run          # fetch → clean → upload to MongoDB
python -m ingestion.run        # re-embed and index into Chroma
```

Requires `LEETCODE_SESSION` cookie in `.env` for the scraper.
