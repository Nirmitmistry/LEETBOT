
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Read a required env var; raise a clear error if it is missing."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file or deployment environment."
        )
    return value


class _Settings:
    # ── MongoDB ───────────────────────────────────────────────────────────────
    @property
    def MONGO_URI(self) -> str:
        return _require("MONGO_URI")

    @property
    def MONGO_DB_NAME(self) -> str:
        return os.getenv("MONGO_DB_NAME", "leetbot_db")

    @property
    def MONGO_PROBLEMS_COLLECTION(self) -> str:
        return os.getenv("MONGO_PROBLEMS_COLLECTION", "problems")

    # ── Chroma / Vector store ────────────────────────────────────────────────
    @property
    def CHROMA_PATH(self) -> str:
        return os.getenv("CHROMA_PATH", "./chroma_db")

    @property
    def CHROMA_COLLECTION(self) -> str:
        return os.getenv("CHROMA_COLLECTION", "leetcode_chunks")

    # ── Gemini ────────────────────────────────────────────────────────────────
    @property
    def GEMINI_API_KEY(self) -> str:
        return _require("GEMINI_API_KEY")

    @property
    def GEMINI_EMBEDDING_MODEL(self) -> str:
        return os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")

    @property
    def GEMINI_EMBED_BATCH_SIZE(self) -> int:
        return int(os.getenv("GEMINI_EMBED_BATCH_SIZE", "100"))

    # ── Gemini LLM ────────────────────────────────────────────────────────────
    @property
    def GEMINI_MODEL_NAME(self) -> str:
        return os.getenv("GEMINI_MODEL_NAME", "gemini-3.6-flash")

    # ── OpenAI (Ingestion Embeddings) ─────────────────────────────────────────
    @property
    def OPENAI_API_KEY(self) -> str:
        return _require("OPENAI_API_KEY")

    @property
    def OPENAI_EMBEDDING_MODEL(self) -> str:
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # ── JWT ───────────────────────────────────────────────────────────────────
    @property
    def JWT_SECRET(self) -> str:
        return _require("JWT_SECRET")

    @property
    def JWT_ALGORITHM(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def JWT_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # ── CORS ──────────────────────────────────────────────────────────────────
    @property
    def CORS_ORIGINS(self) -> list[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [o.strip() for o in raw.split(",") if o.strip()]

    # ── Scraper ───────────────────────────────────────────────────────────────
    @property
    def LEETCODE_SESSION(self) -> str:
        return os.getenv("LEETCODE_SESSION", "")

    @property
    def SCRAPE_DELAY(self) -> float:
        return float(os.getenv("SCRAPE_DELAY", "1.5"))

    # ── Ingestion ─────────────────────────────────────────────────────────────
    @property
    def INGESTION_BATCH_SIZE(self) -> int:
        return int(os.getenv("INGESTION_BATCH_SIZE", "50"))

    # ── Reranker ──────────────────────────────────────────────────────────────
    @property
    def RERANKER_BACKEND(self) -> str:
        """'local' (sentence-transformers CrossEncoder) or 'cohere' (Cohere Rerank API)."""
        value = os.getenv("RERANKER_BACKEND", "local").lower()
        if value not in ("local", "cohere"):
            raise RuntimeError(
                f"RERANKER_BACKEND must be 'local' or 'cohere', got '{value}'"
            )
        return value

    @property
    def RERANKER_CANDIDATE_K(self) -> int:
        """Number of candidates pulled from Chroma before reranking."""
        return int(os.getenv("RERANKER_CANDIDATE_K", "25"))

    @property
    def RERANKER_TOP_N(self) -> int:
        """Maximum documents to keep after reranking."""
        return int(os.getenv("RERANKER_TOP_N", "4"))

    @property
    def RERANKER_THRESHOLD(self) -> float:
        """
        Minimum rerank score to keep a chunk.
        - Local CrossEncoder (BAAI/bge-reranker-large) outputs raw logits,
          typically in the range [-10, 10].  A threshold of -5.0 drops clearly
          irrelevant chunks while keeping anything marginally useful.
        - Cohere Rerank returns scores in [0, 1]; a threshold of 0.05 is
          similarly conservative.
        Set per-backend in your .env file.
        """
        return float(os.getenv("RERANKER_THRESHOLD", "-5.0"))

    @property
    def RERANKER_LOCAL_MODEL(self) -> str:
        """sentence-transformers model used when RERANKER_BACKEND=local."""
        return os.getenv("RERANKER_LOCAL_MODEL", "BAAI/bge-reranker-large")

    @property
    def COHERE_API_KEY(self) -> str:
        """Required when RERANKER_BACKEND=cohere."""
        return os.getenv("COHERE_API_KEY", "")


# Single shared instance imported everywhere
settings = _Settings()
