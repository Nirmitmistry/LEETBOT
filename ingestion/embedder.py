
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import settings


def get_embedder():
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )
