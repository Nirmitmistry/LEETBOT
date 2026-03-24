# LeetBot 🤖

LeetBot is a full-stack, Retrieval-Augmented Generation (RAG) based LeetCode assistant. It is designed to provide intelligent hints, complexity analysis, and tailored problem recommendations to help users improve their algorithmic problem-solving skills.

## 🌟 Features

* **Intelligent Hints:** Get context-aware hints for LeetCode problems without seeing the direct solution, powered by RAG.
* **Complexity Analysis:** Analyze time and space complexity for your solutions.
* **Smart Recommendations:** Discover new problems tailored to your skill level and past sessions.
* **User Authentication & Sessions:** Track your progress, chat history, and active problem-solving sessions.
* **Custom Data Pipeline:** Built-in web scrapers and ingestion scripts to maintain an up-to-date vector database of LeetCode problems.

## 🛠️ Tech Stack

**Frontend**
* **Framework:** React 19 + Vite
* **Styling:** Tailwind CSS (v4)
* **Routing & Networking:** React Router DOM, Axios
* **State & UI:** React Hot Toast for notifications

**Backend**
* **Framework:** FastAPI (Python)
* **Database:** MongoDB Atlas (Document storage) & Chroma (Vector database)
* **AI / Embeddings:** OpenAI Embeddings (RAG pipeline)
* **Authentication:** JWT-based auth

## 📁 Project Structure

The repository is organized into four main functional areas:

```text
LEETBOT/
├── backend/            # FastAPI server serving the core application
│   ├── main.py         # Entry point, CORS config, and router aggregation
│   ├── db.py           # MongoDB and Vector DB connection management
│   ├── auth/           # JWT hashing and dependencies
│   ├── models/         # Pydantic schemas and MongoDB models
│   └── routers/        # API endpoints (problems, hints, recommend, auth, etc.)
│
├── frontend/           # React SPA
│   ├── src/            # React components, pages, and API utility functions
│   ├── package.json    # Dependencies (React, Tailwind, Vite)
│   └── vite.config.js  # Vite bundler configuration
│
├── scraper/            # Data acquisition pipeline (Phase 3)
│   ├── fetch.py        # Scrapes raw problem data from LeetCode
│   ├── clean.py        # Cleans and formats the raw HTML/markdown
│   ├── upload.py       # Pushes the cleaned data to MongoDB Atlas
│   └── run.py          # Orchestrates the 3-step pipeline
│
└── ingestion/          # RAG Embeddings pipeline (Phase 4)
    ├── chunker.py      # Splits problem statements into semantic chunks
    ├── embedder.py     # Generates OpenAI embeddings for chunks
    ├── indexer.py      # Upserts embeddings into Chroma vector store
    └── run.py          # Orchestrates batch ingestion (50 problems/batch)
