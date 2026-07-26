
from langchain_openai import OpenAIEmbeddings
from backend.config import settings


def get_embedder():
    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
    )
