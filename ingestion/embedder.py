
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import settings


def get_embedder() -> GoogleGenerativeAIEmbeddings:
    """
    Return the embedding model used for ingestion.

    IMPORTANT: This MUST match the embedding model configured in
    backend/db.py (GoogleGenerativeAIEmbeddings with GEMINI_EMBEDDING_MODEL).
    Using a different model here than in the backend causes a dimension
    mismatch and breaks all similarity searches at query time.
    """
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )
