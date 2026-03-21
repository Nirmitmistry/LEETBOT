import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = "leetcode_chunks"


def get_vectorstore(embedder: OpenAIEmbeddings) -> Chroma:
    """
    Returns a LangChain Chroma vectorstore instance.
    Creates the chroma_db/ folder automatically on first run.
    Safe to call multiple times — connects to existing DB if it exists.

    Args:
        embedder : OpenAIEmbeddings instance from embedder.get_embedder()

    Returns:
        LangChain Chroma vectorstore — same object used in Phase 7 RAG chain
    """
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedder,
        persist_directory=CHROMA_PATH,
        collection_metadata={"hnsw:space": "cosine"},
    )


def upsert_documents(vectorstore: Chroma, documents: list[Document]) -> None:
    """
    Upserts LangChain Documents into Chroma.
    Uses doc_id from metadata as the Chroma document ID so re-runs don't duplicate.

    Args:
        vectorstore : Chroma instance from get_vectorstore()
        documents   : list of LangChain Documents from chunker.chunk_problem()
    """
    ids = [doc.metadata["doc_id"] for doc in documents]
    vectorstore.add_documents(documents=documents, ids=ids)


def collection_stats(vectorstore: Chroma) -> None:
    """Prints how many vectors are currently stored."""
    count = vectorstore._collection.count()
    print(f"Chroma '{COLLECTION_NAME}': {count:,} vectors stored")
    print(f"Expected after full ingestion: ~14,000 (7 chunks × 2,000 problems)")


def test_query(vectorstore: Chroma, query: str, n_results: int = 5) -> None:
    """
    Runs a similarity search and pretty-prints results.
    Use this after ingestion to verify retrieval is working.

    Args:
        vectorstore : Chroma instance from get_vectorstore()
        query       : plain English query string
        n_results   : how many results to return
    """
    print(f"\nTest query: '{query}'")
    print("-" * 50)

    results = vectorstore.similarity_search_with_score(query, k=n_results)

    for i, (doc, score) in enumerate(results, 1):
        print(f"  [{i}] {doc.metadata.get('doc_id')}")
        print(
            f"       Score      : {score:.4f}  (lower = more similar in cosine)")
        print(f"       Difficulty : {doc.metadata.get('difficulty')}")
        print(f"       Tags       : {doc.metadata.get('tags')}")
        print(f"       Chunk type : {doc.metadata.get('chunk_type')}")
        print(f"       Preview    : {doc.page_content[:100]}...")
        print()


if __name__ == "__main__":
    from ingestion.embedder import get_embedder

    embedder = get_embedder()
    vectorstore = get_vectorstore(embedder)
    collection_stats(vectorstore)
