from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()

# Import settings after load_dotenv so the env file is read first
from backend.config import settings  # noqa: E402


def get_embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        chunk_size=settings.OPENAI_EMBED_BATCH_SIZE,
    )
