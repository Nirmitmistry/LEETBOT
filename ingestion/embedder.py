import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
load_dotenv()
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 100


def get_embedder() -> OpenAIEmbeddings:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        chunk_size=EMBED_BATCH_SIZE,
    )
