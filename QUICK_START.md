# LEETBOT - Quick Start (Full Gemini Migration)

## ✅ What Changed
Your LEETBOT project now uses **Gemini API for EVERYTHING**:
- ✅ **Embeddings** - Gemini text-embedding-004
- ✅ **LLM Inference** - Gemini 1.5 Flash (chat, hints, complexity, recommendations)
- ❌ **Ollama** - Completely removed (no local hosting needed!)

## 🎯 Perfect for Deployment
Since everything runs through Gemini API, you can deploy anywhere without needing Ollama installed locally!

---

## 🚀 Quick Commands

### 1. Install Dependencies
```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. (Optional) Regenerate Embeddings
If you had an old Chroma database with OpenAI embeddings, delete it and re-run ingestion:
```bash
rmdir /s /q chroma_db
python -m ingestion.run
```

### 3. Start Backend
```bash
uvicorn backend.main:app --reload
```
Backend will be at: http://localhost:8000

### 4. Start Frontend (New Terminal)
```bash
cd frontend
npm run dev
```
Frontend will be at: http://localhost:5173

---

## 📋 Migration Summary

| Component | Before | After |
|-----------|--------|-------|
| **Embeddings** | OpenAI `text-embedding-3-small` | Gemini `models/text-embedding-004` |
| **Chat** | Ollama (local) | Gemini `gemini-1.5-flash` |
| **Hints** | Ollama (local) | Gemini `gemini-1.5-flash` |
| **Complexity** | Ollama (local) | Gemini `gemini-1.5-flash` |
| **Recommendations** | Ollama (local) | Gemini `gemini-1.5-flash` |
| **Deployment** | ❌ Needs Ollama server | ✅ Deploy anywhere! |

---

## 🔑 Environment Variables

Your `.env` file now uses:
```env
# Gemini API Key (used for everything)
GEMINI_API_KEY=your_gemini_api_key_here

# Embedding model for RAG
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
GEMINI_EMBED_BATCH_SIZE=100

# LLM model for chat/hints/complexity/recommendations
GEMINI_MODEL_NAME=gemini-1.5-flash
```

---

## 💰 Cost Considerations

Gemini API pricing (as of 2024):
- **gemini-1.5-flash**: Very affordable, fast responses
- **Embeddings**: Competitive pricing

All calls are made through Google's API, no local compute needed!

---

## 🛠️ Troubleshooting

### "Module not found" errors
Run: `pip install -r requirements.txt`

### Gemini API errors
- Verify your `GEMINI_API_KEY` is valid in `.env`
- Check API quota/limits in Google AI Studio
- Ensure billing is enabled if required

### Chroma dimension mismatch
This happens if you have old OpenAI embeddings. Solution:
```bash
rmdir /s /q chroma_db
python -m ingestion.run
```

### Frontend can't connect to backend
- Verify backend is running on http://localhost:8000
- Check CORS settings in `.env`: `CORS_ORIGINS=http://localhost:5173`

---

## 📦 File Changes Summary

**Modified files:**
1. `backend/config.py` - Gemini config for embeddings + LLM
2. `backend/db.py` - Uses Gemini embeddings
3. `backend/routers/chat.py` - Uses ChatGoogleGenerativeAI
4. `backend/routers/hints.py` - Uses ChatGoogleGenerativeAI
5. `backend/routers/complexity.py` - Uses ChatGoogleGenerativeAI
6. `backend/routers/recommend.py` - Uses ChatGoogleGenerativeAI
7. `ingestion/embedder.py` - Returns Gemini embeddings
8. `ingestion/indexer.py` - Type hints updated
9. `requirements.txt` - Removed `langchain-ollama`
10. `.env` - All Gemini config
11. `.env.example` - Updated template
12. `README.md` - Documentation updated

**No changes needed:**
- Frontend code - No changes needed
- Database schemas - No changes needed
- Authentication - No changes needed

---

## 🎯 Deployment Advantages

Since you no longer need Ollama:
- ✅ Deploy to **any cloud platform** (Vercel, Railway, Render, AWS, etc.)
- ✅ **No GPU/compute requirements** for local LLM
- ✅ **Scalable** - API handles the load
- ✅ **Reliable** - Google's infrastructure
- ✅ **Simple** - Just need environment variables

---

## 🎯 Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ⏭️ Start the backend server: `uvicorn backend.main:app --reload`
3. ⏭️ Start the frontend dev server: `cd frontend && npm run dev`
4. ⏭️ Register/login and test the application
5. ⏭️ Deploy to your favorite cloud platform!

---

Enjoy your fully cloud-powered LEETBOT! 🚀☁️
