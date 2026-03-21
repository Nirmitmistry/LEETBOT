import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = "leetcode_chunks"


def get_vectorstore(embedder: OpenAIEmbeddings) -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedder,
        persist_directory=CHROMA_PATH,
        collection_metadata={"hnsw:space": "cosine"},
    )


def upsert_documents(vectorstore: Chroma, documents: list[Document]) -> None:
    ids = [doc.metadata["doc_id"] for doc in documents]
    vectorstore.add_documents(documents=documents, ids=ids)


def collection_stats(vectorstore: Chroma) -> None:
    count = vectorstore._collection.count()
    print(f"Chroma '{COLLECTION_NAME}': {count:,} vectors stored")
