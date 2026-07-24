import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

from backend.config import settings  # noqa: E402
from ingestion.chunker import chunk_problem
from ingestion.embedder import get_embedder
from ingestion.indexer import get_vectorstore, upsert_documents, collection_stats


def run():
    print("\nConnecting to MongoDB...")
    client = MongoClient(settings.MONGO_URI)
    collection = client[settings.MONGO_DB_NAME][settings.MONGO_PROBLEMS_COLLECTION]
    total = collection.count_documents({})
    print(f"      Found {total:,} problems in MongoDB ({settings.MONGO_DB_NAME}.{settings.MONGO_PROBLEMS_COLLECTION})")

    print("\n Setting up embedder + Chroma vectorstore...")
    embedder = get_embedder()
    vectorstore = get_vectorstore(embedder)
    collection_stats(vectorstore)
    print(f"\n Starting ingestion in batches of {settings.INGESTION_BATCH_SIZE} problems...")

    processed = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    existing_ids = set()
    try:
        existing = vectorstore._collection.get(include=[])
        existing_ids = set(existing["ids"])
        if existing_ids:
            print(
                f"      Found {len(existing_ids):,} existing vectors — will skip already-indexed problems\n"
            )
    except Exception:
        pass

    cursor = collection.find({})
    batch_docs = []
    batch_slugs = []

    for problem in cursor:
        slug = problem.get("slug", str(problem["_id"]))
        statement_id = f"{problem['_id']}_statement"
        if statement_id in existing_ids:
            skipped += 1
            continue

        batch_docs.append(problem)
        batch_slugs.append(slug)

        if len(batch_docs) >= settings.INGESTION_BATCH_SIZE:
            _process_batch(batch_docs, batch_slugs, vectorstore, processed, total)
            processed += len(batch_docs)
            batch_docs = []
            batch_slugs = []

    if batch_docs:
        _process_batch(batch_docs, batch_slugs, vectorstore, processed, total)
        processed += len(batch_docs)

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
        print(
            f"  Indexed problems {processed + 1}–{end}/{total} "
            f"({len(all_chunks)} chunks upserted)"
        )
    except Exception as e:
        print(f"  [upsert error] batch starting at {processed + 1}: {e}")


if __name__ == "__main__":
    run()
