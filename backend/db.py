"""
Database connection helpers — MongoDB + ChromaDB.

DEPLOYMENT NOTE (Render free tier):
    Render's free-tier filesystem is *ephemeral*.  Any ChromaDB data written at
    runtime disappears on the next deploy / restart.  For a demo deployment,
    commit a small ``chroma_db/`` snapshot into the repo (``git add -f chroma_db``)
    so it ships with the slug.  For production persistence, migrate to a hosted
    vector store or a persistent-disk plan.
"""

import logging
import os

from pymongo import MongoClient
from pymongo.database import Database

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import settings

logger = logging.getLogger(__name__)

_mongo_client: MongoClient | None = None
_db: Database | None = None
_chroma: Chroma | None = None


async def connect_db() -> None:
    global _mongo_client, _db, _chroma

    # ── MongoDB ───────────────────────────────────────────────────────────────
    try:
        _mongo_client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _mongo_client[settings.MONGO_DB_NAME]
        _mongo_client.admin.command("ping")
        logger.info("MongoDB connected (db: %s)", settings.MONGO_DB_NAME)
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        raise

    # ── Chroma ────────────────────────────────────────────────────────────────
    try:
        chroma_path = settings.CHROMA_PATH
        os.makedirs(chroma_path, exist_ok=True)

        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
        _chroma = Chroma(
            collection_name=settings.CHROMA_COLLECTION,
            embedding_function=embeddings,
            persist_directory=chroma_path,
        )

        try:
            count = _chroma._collection.count()
        except Exception:
            count = 0

        logger.info(
            "Chroma ready — path=%s  collection=%s  vectors=%d",
            chroma_path,
            settings.CHROMA_COLLECTION,
            count,
        )

        # ── BM25 sparse index (built from the same Chroma corpus) ─────────────
        if settings.HYBRID_RETRIEVAL:
            try:
                from backend.rag.bm25_index import warm_bm25_index
                n_indexed = warm_bm25_index(_chroma)
                logger.info("BM25 sparse index ready — %d chunks", n_indexed)
            except RuntimeError as exc:
                # rank_bm25 not installed — hybrid will degrade gracefully
                logger.warning("BM25 warm-up skipped (rank_bm25 not installed?): %s", exc)
            except Exception as exc:
                logger.warning("BM25 warm-up failed (non-fatal): %s", exc)

    except Exception as exc:
        logger.warning("Chroma initialisation failed (non-fatal): %s", exc)
        _chroma = None


async def close_db() -> None:
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB connection closed")


def get_db() -> Database:
    if _db is None:
        raise RuntimeError(
            "Database not initialised — connect_db() was never called"
        )
    return _db


def get_chroma() -> Chroma:
    if _chroma is None:
        raise RuntimeError(
            "Chroma vector store is not available. "
            "The chroma_db directory may be empty or initialisation failed."
        )
    return _chroma
