import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from ingestion.chunker import chunk_problem
from ingestion.embedder import get_embedder
from ingestion.indexer import get_vectorstore, upsert_documents, collection_stats

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = "LEETBOT"
COLLECTION = "problems"
BATCH_SIZE = 50   # problems per batch


def run():
    if not MONGO_URI:
        raise ValueError("MONGO_URI not set in .env")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env")

    print("\nConnecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION]
    total = collection.count_documents({})
    print(f"      Found {total:,} problems in MongoDB")

    print("\n Setting up embedder + Chroma vectorstore...")
    embedder = get_embedder()
    vectorstore = get_vectorstore(embedder)
    collection_stats(vectorstore)
    print(f"\n Starting ingestion in batches of {BATCH_SIZE} problems...")

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
    print(f" Ingestion complete in {elapsed:.1f}s")
    print(f"      Processed : {processed:,} problems")
    print(f"      Skipped   : {skipped:,} (already indexed)")
    print(f"      Failed    : {failed:,}")
    collection_stats(vectorstore)


def _process_batch(
    batch_docs:  list[dict],
    batch_slugs: list[str],
    vectorstore,
    processed:   int,
    total:       int,
) -> None:
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
