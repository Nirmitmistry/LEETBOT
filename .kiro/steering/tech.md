# LEETBOT Tech Context
- Backend: FastAPI (Python), routers in backend/routers/
- Stores: MongoDB Atlas (source of truth: problems, users, sessions) + Chroma (vectors)
- LLM/embeddings currently: Google Gemini via google-generativeai SDK
- Ingestion pipeline: scraper/ (fetch->clean->upload to Mongo) then ingestion/ (chunker->embedder->indexer, batched, writes to Chroma)
- Auth: JWT, backend/auth/
- We are upgrading this from naive RAG to production RAG. Do NOT introduce new
top-level services or infra unless a task explicitly calls for it — prefer extending backend/rag/ as a new module over restructuring existing routers.
- All new RAG components go under backend/rag/ (create if it doesn't exist):
backend/rag/chunker.py, retriever.py, reranker.py, cache.py, eval/
- Always add type hints and async/await consistent with existing FastAPI style.
- Never break existing router contracts in backend/routers/ — extend, don't rewrite.
