from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# Import settings after load_dotenv so the env file is read first
from backend.config import settings  # noqa: E402


def get_embedder() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )
