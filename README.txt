LEETBOT free-deployment configuration bundle

Files:
- frontend/vercel.json: SPA fallback for React Router on Vercel.
- render.yaml: Render Blueprint for the FastAPI backend and build-time Chroma ingestion.
- scripts/create_indexes.py: one-time MongoDB index setup.

Important:
- Never put secret values into render.yaml or commit a production .env file.
- Copy GEMINI_MODEL_NAME and GEMINI_EMBEDDING_MODEL from the local environment that already works.
- Set CORS_ORIGINS to the final Vercel production URL.
