import asyncio
from pymongo import MongoClient
from pymongo.database import Database

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import settings

_mongo_client: MongoClient | None = None
_db: Database | None = None
_chroma: Chroma | None = None


async def connect_db() -> None:
    global _mongo_client, _db, _chroma

    # ── MongoDB ───────────────────────────────────────────────────────────────
    _mongo_client = MongoClient(settings.MONGO_URI)
    _db = _mongo_client[settings.MONGO_DB_NAME]
    _mongo_client.admin.command("ping")
    print(f" MongoDB pinged and connected! (db: {settings.MONGO_DB_NAME})")

    # ── Chroma ────────────────────────────────────────────────────────────────
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )
    _chroma = Chroma(
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=settings.CHROMA_PATH,
    )
    print(f" Chroma connected — {settings.CHROMA_PATH} (collection: {settings.CHROMA_COLLECTION})")


async def close_db() -> None:
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        print("MongoDB connection closed")


def get_db() -> Database:
    if _db is None:
        raise RuntimeError(
            "Database not initialised — connect_db() was never called"
        )
    return _db


def get_chroma() -> Chroma:
    if _chroma is None:
        raise RuntimeError(
            "Chroma not initialised — connect_db() was never called"
        )
    return _chroma


if __name__ == "__main__":
    asyncio.run(connect_db())
