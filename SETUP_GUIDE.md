# LEETBOT Setup & Run Guide

## Prerequisites
✅ Python 3.13.5 (Installed)
✅ Node.js v24.14.0 (Installed)
- MongoDB Atlas account (you already have this configured)
- Gemini API Key (you already have this in .env)

---

## Step 1: Install Python Dependencies

Open a terminal in the project root and run:

```bash
pip install -r requirements.txt
```

**Note:** This will install all Python packages including:
- FastAPI (backend framework)
- langchain-google-genai (for Gemini embeddings + LLM)
- chromadb (vector database)
- pymongo (MongoDB client)
- And all other dependencies

---

## Step 2: Install Frontend Dependencies

Navigate to the frontend folder and install Node.js packages:

```bash
cd frontend
npm install
cd ..
```

---

## Step 3: Set Up the Database

### Option A: Fresh Start (Recommended)
If your Chroma database has old OpenAI embeddings, delete it:

```bash
rmdir /s /q chroma_db
```

### Option B: Re-run Ingestion
Run the ingestion pipeline to populate Chroma with Gemini embeddings:

```bash
python -m ingestion.run
```

**What this does:**
- Connects to your MongoDB Atlas database
- Chunks all problems into semantic pieces
- Generates Gemini embeddings for each chunk
- Stores them in the local Chroma vector database

**Note:** This may take some time depending on how many problems are in your MongoDB.

---

## Step 4: Run the Backend

Start the FastAPI server:

```bash
uvicorn backend.main:app --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     MongoDB pinged and connected! (db: leetbot_db)
INFO:     Chroma connected — ./chroma_db (collection: leetcode_chunks)
```

The backend API will be available at: **http://localhost:8000**

API docs (Swagger): **http://localhost:8000/docs**

Health check: **http://localhost:8000/health**

---

## Step 5: Run the Frontend

Open a **NEW terminal** (keep the backend running in the first terminal):

```bash
cd frontend
npm run dev
```

**Expected output:**
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
```

The frontend will be available at: **http://localhost:5173**

---

## Running Everything (Quick Commands)

### Terminal 1 - Backend:
```bash
uvicorn backend.main:app --reload
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

---

## Troubleshooting

### 1. "ModuleNotFoundError: No module named 'fastapi'"
**Solution:** Run `pip install -r requirements.txt`

### 2. Gemini API errors
**Solution:**
- Make sure your `.env` file has `GEMINI_API_KEY` set (it already does)
- Verify API limits in Google AI Studio
- Ensure billing is enabled if required

### 3. MongoDB connection error
**Solution:** Verify your `MONGO_URI` in `.env` is correct and your IP is whitelisted in MongoDB Atlas

### 4. Chroma dimension mismatch error
**Solution:** Delete the old Chroma database and re-run ingestion:
```bash
rmdir /s /q chroma_db
python -m ingestion.run
```

### 5. Frontend shows connection errors
**Solution:** 
- Verify backend is running on http://localhost:8000
- Check CORS settings in backend allow http://localhost:5173

---

## Optional: Scraper Setup

If you want to scrape fresh LeetCode data:

1. Get your LeetCode session cookie
2. Add it to `.env`: `LEETCODE_SESSION=your_session_cookie`
3. Run the scraper:
   ```bash
   python -m scraper.run
   ```

---

## Project Status Check

Run these commands to verify everything is set up:

```bash
# Check Python packages
pip list | findstr "fastapi langchain chromadb"

# Check if backend can start (stop with Ctrl+C after verification)
python -c "from backend.config import settings; print('Config loaded successfully')"

# Check if MongoDB connection works
python -c "from pymongo import MongoClient; from backend.config import settings; MongoClient(settings.MONGO_URI).admin.command('ping'); print('MongoDB connected')"
```

---

## Next Steps After Setup

1. **Register a user** at http://localhost:5173
2. **Login** with your credentials
3. **Browse problems** from the dashboard
4. **Start a session** and get AI-powered hints
5. **Analyze complexity** of your solutions
6. **Get recommendations** based on your progress

---

## Architecture Overview

```
┌─────────────┐
│   Browser   │  (http://localhost:5173)
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐
│  React SPA  │  (Vite dev server)
└──────┬──────┘
       │ Axios
       ▼
┌─────────────┐
│   FastAPI   │  (http://localhost:8000)
└──┬───┬───┬──┘
   │   │   │
   │   │   └─────► Chroma (./chroma_db)
   │   │              ▲
   │   │              │ Gemini Embeddings
   │   │              │ (text-embedding-004)
   │   │              │
   │   └──────────► MongoDB Atlas
   │
   └──────────────► Gemini API (gemini-1.5-flash)
                       (Chat, Hints, Complexity, Recommendations)
```

---

## Environment Variables Reference

Your current `.env` is configured with:
- ✅ `MONGO_URI` - MongoDB connection
- ✅ `GEMINI_API_KEY` - Gemini API (embeddings + LLM)
- ✅ `GEMINI_EMBEDDING_MODEL` - Embedding model (text-embedding-004)
- ✅ `GEMINI_MODEL_NAME` - LLM model (gemini-1.5-flash)
- ✅ `JWT_SECRET` - Authentication
- ✅ `CORS_ORIGINS` - Frontend URL

---

Enjoy using LEETBOT! 🚀
