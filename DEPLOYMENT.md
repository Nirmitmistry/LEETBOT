# LEETBOT - Deployment Guide

## ✅ Ready for Cloud Deployment!

Since LEETBOT now uses **100% Gemini API** (no Ollama required), you can deploy it anywhere!

---

## 🚀 Deployment Options

### Option 1: Backend on Railway/Render + Frontend on Vercel

#### Backend (Railway or Render)
1. **Create a new project** on [Railway.app](https://railway.app) or [Render.com](https://render.com)
2. **Connect your GitHub repository**
3. **Set environment variables:**
   ```env
   MONGO_URI=mongodb+srv://...
   MONGO_DB_NAME=leetbot_db
   MONGO_PROBLEMS_COLLECTION=problems
   
   GEMINI_API_KEY=your_key_here
   GEMINI_EMBEDDING_MODEL=models/text-embedding-004
   GEMINI_EMBED_BATCH_SIZE=100
   GEMINI_MODEL_NAME=gemini-1.5-flash
   
   CHROMA_PATH=./chroma_db
   CHROMA_COLLECTION=leetcode_chunks
   
   JWT_SECRET=your_secret_here
   JWT_EXPIRE_MINUTES=1440
   JWT_ALGORITHM=HS256
   
   CORS_ORIGINS=https://your-frontend-domain.vercel.app
   ```

4. **Set build command:** (none needed for Python)
5. **Set start command:**
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```

6. **Deploy!**

#### Frontend (Vercel)
1. **Create a new project** on [Vercel.com](https://vercel.com)
2. **Connect your GitHub repository**
3. **Set root directory:** `frontend`
4. **Set environment variables:**
   ```env
   VITE_API_URL=https://your-backend-url.railway.app
   ```
5. **Update `frontend/.env` or `vite.config.js`:**
   ```javascript
   // In vite.config.js
   export default defineConfig({
     server: {
       proxy: {
         '/api': {
           target: process.env.VITE_API_URL || 'http://localhost:8000',
           changeOrigin: true,
         },
       },
     },
   })
   ```

6. **Deploy!**

---

### Option 2: All-in-One on Railway/Render

1. **Deploy backend** as described above
2. **Build frontend** locally:
   ```bash
   cd frontend
   npm run build
   ```
3. **Serve frontend** from FastAPI using StaticFiles:
   ```python
   # In backend/main.py
   from fastapi.staticfiles import StaticFiles
   
   app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
   ```

---

### Option 3: Docker Deployment

#### Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/
COPY .env .env

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGO_URI=${MONGO_URI}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_EMBEDDING_MODEL=models/text-embedding-004
      - GEMINI_MODEL_NAME=gemini-1.5-flash
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ./chroma_db:/app/chroma_db

  frontend:
    image: node:18-alpine
    working_dir: /app
    volumes:
      - ./frontend:/app
    ports:
      - "5173:5173"
    command: sh -c "npm install && npm run dev"
```

---

## 🔧 Pre-Deployment Checklist

### 1. Update CORS Settings
In `.env`:
```env
CORS_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com
```

### 2. Secure JWT Secret
Generate a strong secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Run Ingestion (if needed)
Before deploying, ensure Chroma has data:
```bash
python -m ingestion.run
```

Upload `chroma_db` folder to your deployment or run ingestion on first deployment.

### 4. Environment Variables Security
- ✅ Never commit `.env` to Git
- ✅ Use deployment platform's secret management
- ✅ Rotate API keys regularly

### 5. Database Setup
- ✅ Ensure MongoDB Atlas is accessible from deployment IP
- ✅ Whitelist deployment platform IPs or use 0.0.0.0/0 (not recommended for production)

---

## 📊 Monitoring & Scaling

### Rate Limits
Gemini API has rate limits. Monitor usage in Google AI Studio.

### Caching
Consider caching LLM responses for common queries:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_gemini_call(prompt: str):
    # Your Gemini API call
    pass
```

### Database Indexes
Ensure MongoDB indexes for common queries:
```python
db.problems.create_index("slug")
db.hint_sessions.create_index([("user_id", 1), ("slug", 1)])
```

---

## 🔒 Security Best Practices

1. **HTTPS Only** - Use SSL/TLS in production
2. **Rate Limiting** - Add rate limiting middleware:
   ```python
   from slowapi import Limiter
   
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   ```

3. **Input Validation** - Already using Pydantic ✅
4. **CORS** - Restrict to your frontend domain only
5. **Secrets Management** - Use environment variables, never hardcode

---

## 🧪 Testing Before Deployment

### Local Production Simulation
```bash
# Build frontend
cd frontend
npm run build

# Test production build
cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### API Health Check
Create a health endpoint:
```python
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "gemini": "connected",
        "mongo": "connected",
        "chroma": "connected"
    }
```

---

## 📈 Cost Estimation (Monthly)

Based on moderate usage (1000 requests/day):

- **Gemini API**: ~$10-20/month
- **MongoDB Atlas**: $0 (free tier) or $9+/month
- **Railway/Render**: $5-20/month
- **Vercel**: $0 (hobby tier)

**Total**: ~$15-50/month

---

## 🎯 Post-Deployment

1. **Monitor logs** for errors
2. **Test all endpoints** (chat, hints, complexity, recommendations)
3. **Check Gemini API usage** in Google AI Studio
4. **Set up alerts** for errors/downtime
5. **Backup MongoDB** regularly

---

## 🆘 Common Deployment Issues

### Issue: "Module not found"
**Solution**: Ensure `requirements.txt` is installed correctly
```bash
pip freeze > requirements.txt
```

### Issue: CORS errors
**Solution**: Update `CORS_ORIGINS` in `.env` with your frontend URL

### Issue: Gemini API rate limit
**Solution**: Implement caching or upgrade API tier

### Issue: Chroma not persisting
**Solution**: Ensure `CHROMA_PATH` directory has write permissions

---

Congratulations! Your LEETBOT is ready for the cloud! 🎉☁️
