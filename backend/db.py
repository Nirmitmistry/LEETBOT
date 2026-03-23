import os
import asyncio
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

_mongo_client: MongoClient | None = None
_db: Database | None = None
_chroma: Chroma | None = None


async def connect_db() -> None:
    global _mongo_client, _db, _chroma
    # MongoDB
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in .env")
    _mongo_client = MongoClient(mongo_uri)
    _db = _mongo_client["LEETBOT"]
    _mongo_client.admin.command('ping')
    print(" MongoDB pinged and connected!")

    # Chroma
    chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_key,
    )
    _chroma = Chroma(
        collection_name="leetcode_chunks",
        embedding_function=embeddings,
        persist_directory=chroma_path,
    )
    print(f" Chroma connected — {chroma_path}")


async def close_db() -> None:
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        print("MongoDB connection closed")


def get_db() -> Database:
    if _db is None:
        raise RuntimeError(
            "Database not initialised — connect_db() was never called")
    return _db


def get_chroma() -> Chroma:
    if _chroma is None:
        raise RuntimeError(
            "Chroma not initialised — connect_db() was never called")
    return _chroma


if __name__ == "__main__":
    asyncio.run(connect_db())
