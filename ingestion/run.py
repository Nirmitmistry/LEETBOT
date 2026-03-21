import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from ingestion.chunker import chunk_problem
from ingestion.embedder import get_embedder, estimate_cost
from ingestion.indexer import get_vectorstore, upsert_documents, collection_stats, test_query

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = "LEETBOT"
COLLECTION = "problems"
BATCH_SIZE = 50   # problems per batch (= 350 chunks per OpenAI call)


def run():
    print("=" * 60)
    print("  LeetBot Ingestion Pipeline — Phase 5")
    print("=" * 60)

    # ── 0. Pre-flight checks ──────────────────────────────────────────────────
    if not MONGO_URI:
        raise ValueError("MONGO_URI not set in .env")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    # ── 1. Connect to MongoDB ─────────────────────────────────────────────────
    print("\n[1/5] Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION]
    total = collection.count_documents({})
    print(f"      Found {total:,} problems in MongoDB")

    # ── 2. Set up embedder + vectorstore ──────────────────────────────────────
    print("\n[2/5] Setting up embedder + Chroma vectorstore...")
    estimate_cost(total)
    embedder = get_embedder()
    vectorstore = get_vectorstore(embedder)
    collection_stats(vectorstore)

    # ── 3. Main ingestion loop ────────────────────────────────────────────────
    print(f"\n[3/5] Starting ingestion in batches of {BATCH_SIZE} problems...")
    print("-" * 60)

    processed = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    # Get all existing doc IDs from Chroma to skip already-indexed problems
    existing_ids = set()
    try:
        existing = vectorstore._collection.get(include=[])
        existing_ids = set(existing["ids"])
        if existing_ids:
            print(
                f"      Found {len(existing_ids):,} existing vectors — will skip already-indexed problems\n")
    except Exception:
        pass

    # Paginate through MongoDB in batches
    cursor = collection.find({})
    batch_docs = []
    batch_slugs = []

    for problem in cursor:
        slug = problem.get("slug", str(problem["_id"]))

        # Check if this problem is already fully indexed (all 7 chunks present)
        statement_id = f"{problem['_id']}_statement"
        if statement_id in existing_ids:
            skipped += 1
            continue

        batch_docs.append(problem)
        batch_slugs.append(slug)

        # Process when batch is full
        if len(batch_docs) >= BATCH_SIZE:
            _process_batch(batch_docs, batch_slugs,
                           vectorstore, processed, total)
            processed += len(batch_docs)
            batch_docs = []
            batch_slugs = []

    # Process any remaining problems
    if batch_docs:
        _process_batch(batch_docs, batch_slugs, vectorstore, processed, total)
        processed += len(batch_docs)

    # ── 4. Final stats ────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"[4/5] Ingestion complete in {elapsed:.1f}s")
    print(f"      Processed : {processed:,} problems")
    print(f"      Skipped   : {skipped:,} (already indexed)")
    print(f"      Failed    : {failed:,}")
    collection_stats(vectorstore)

    # ── 5. Test query to verify retrieval works ───────────────────────────────
    print("\n[5/5] Running test queries...")
    test_query(vectorstore, "two sum array hash table easy")
    test_query(vectorstore, "binary tree level order traversal")
    test_query(vectorstore, "dynamic programming longest subsequence")

    print("Pipeline finished. Chroma DB is ready at:",
          os.getenv("CHROMA_PATH", "./chroma_db"))
    client.close()


def _process_batch(
    batch_docs:  list[dict],
    batch_slugs: list[str],
    vectorstore,
    processed:   int,
    total:       int,
) -> None:
    """
    Chunks + upserts one batch of problems into Chroma.
    Handles errors per-problem so one failure doesn't stop the whole run.
    """
    all_chunks = []

    for problem, slug in zip(batch_docs, batch_slugs):
        try:
            chunks = chunk_problem(problem)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  [chunk error] #{problem.get('_id')} {slug}: {e}")
            continue

    if not all_chunks:
        return

    try:
        upsert_documents(vectorstore, all_chunks)
        end = min(processed + len(batch_docs), total)
        print(f"  Indexed problems {processed + 1}–{end}/{total} "
              f"({len(all_chunks)} chunks upserted)")
    except Exception as e:
        print(f"  [upsert error] batch starting at {processed + 1}: {e}")


if __name__ == "__main__":
    run()
