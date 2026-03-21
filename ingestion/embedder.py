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

def estimate_cost(num_problems: int = 2000) -> None:
    chunks = num_problems * 7
    total_tokens = chunks * 300          # ~300 tokens per chunk
    cost = (total_tokens / 1_000_000) * 0.02   # $0.02 per 1M tokens

    print(f"Embedding cost estimate for {num_problems} problems:")
    print(f"  Total chunks  : {chunks:,}")
    print(f"  Est. tokens   : {total_tokens:,}")
    print(f"  Est. cost     : ${cost:.4f}   (text-embedding-3-small)")


if __name__ == "__main__":
    estimate_cost()

    print("\nTesting embedder with 2 sample texts...")
    embedder = get_embedder()
    from langchain_core.documents import Document
    test_docs = [
        Document(page_content="Given an array find two numbers that sum to target."),
        Document(
            page_content="Use a hash map to store complement values as you iterate."),
    ]

    vectors = embedder.embed_documents([d.page_content for d in test_docs])

    print(f"  Texts embedded : {len(vectors)}")
    print(f"  Vector dims    : {len(vectors[0])}")   # should be 1536
    print(f"  First 5 values : {[round(v, 4) for v in vectors[0][:5]]}")
    print("\nEmbedder working correctly.")
