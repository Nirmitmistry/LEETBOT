"""
indexer.py — Chroma vector-store helpers for LEETBOT ingestion.

upsert_documents() is a true upsert: it deletes any existing vectors whose
doc_id matches before inserting the new ones.  This allows re-ingestion
(re-chunking) to update stale vectors without creating duplicates.
"""

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

load_dotenv()

from backend.config import settings  # noqa: E402


def get_vectorstore(embedder: OpenAIEmbeddings) -> Chroma:
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=embedder,
        persist_directory=settings.CHROMA_PATH,
        collection_metadata={"hnsw:space": "cosine"},
    )


def upsert_documents(vectorstore: Chroma, documents: list[Document]) -> None:
    """
    Upsert documents by doc_id.

    Strategy: delete any existing vectors with the same IDs first, then add.
    This guarantees that re-ingestion updates chunk text/metadata without
    leaving stale or duplicate vectors behind.
    """
    ids = [doc.metadata["doc_id"] for doc in documents]

    # Delete existing vectors for these IDs (no-op if they don't exist)
    try:
        vectorstore._collection.delete(ids=ids)
    except Exception:
        # Collection may be empty or IDs may not exist — safe to ignore
        pass

    vectorstore.add_documents(documents=documents, ids=ids)


def get_existing_problem_ids(vectorstore: Chroma) -> set[str]:
    """
    Return the set of problem_ids already indexed in Chroma.
    Used by run.py to decide which problems to skip or re-process.
    """
    try:
        result = vectorstore._collection.get(include=["metadatas"])
        return {
            m["problem_id"]
            for m in result.get("metadatas", [])
            if m and "problem_id" in m
        }
    except Exception:
        return set()


def get_existing_doc_ids(vectorstore: Chroma) -> set[str]:
    """Return the raw set of doc_ids (vector IDs) stored in Chroma."""
    try:
        result = vectorstore._collection.get(include=[])
        return set(result.get("ids", []))
    except Exception:
        return set()


def collection_stats(vectorstore: Chroma) -> None:
    count = vectorstore._collection.count()
    print(f"Chroma '{settings.CHROMA_COLLECTION}': {count:,} vectors stored")
