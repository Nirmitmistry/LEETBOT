"""
run.py — Batch ingestion runner for LEETBOT.

Usage
-----
Normal run (skip already-indexed problems):
    python -m ingestion.run

Re-ingest / re-chunk everything (upserts in place, no duplicates):
    python -m ingestion.run --reingest

Re-ingest only specific problems by their integer ID:
    python -m ingestion.run --reingest --ids 1 2 42

How --reingest works
--------------------
- Skips the "already indexed?" check so every problem goes through the
  chunker again.
- upsert_documents() deletes old vectors by doc_id before inserting new
  ones, so there are zero duplicate vectors in Chroma after re-ingestion.
- Safe to interrupt and restart: already-updated problems just get
  upserted again (idempotent).
"""

import argparse
import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

from backend.config import settings  # noqa: E402
from ingestion.chunker import chunk_problem
from ingestion.embedder import get_embedder
from ingestion.indexer import get_vectorstore, upsert_documents, collection_stats

# Sanity-check: ensure the embedding model name is clean (no trailing spaces)
_embed_model = settings.GEMINI_EMBEDDING_MODEL.strip()
if _embed_model != settings.GEMINI_EMBEDDING_MODEL:
    import os
    os.environ["GEMINI_EMBEDDING_MODEL"] = _embed_model
    print(f"  [warning] GEMINI_EMBEDDING_MODEL had leading/trailing spaces — stripped to '{_embed_model}'")

# ---------------------------------------------------------------------------
# Gemini free-tier rate limit: 100 requests/minute per model per user.
# Each batch of 50 problems produces ~300 chunks, which langchain sends as
# multiple embed_documents() calls in batches of GEMINI_EMBED_BATCH_SIZE.
# We pause between problem-batches to stay under the per-minute cap.
# ---------------------------------------------------------------------------
_BATCH_DELAY_S: float = float(
    __import__("os").getenv("INGESTION_BATCH_DELAY_S", "65")
)  # seconds to sleep between Chroma upsert batches; 65s safely under 100 req/min


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LEETBOT ingestion pipeline")
    parser.add_argument(
        "--reingest",
        action="store_true",
        default=False,
        help=(
            "Re-chunk and re-index all problems (or only --ids if specified). "
            "Old vectors are deleted and replaced; no duplicates are created."
        ),
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        type=int,
        metavar="ID",
        default=None,
        help="Only process problems with these integer _id values (implies --reingest).",
    )
    return parser.parse_args()


def run(reingest: bool = False, problem_ids: list[int] | None = None) -> None:
    """
    Main ingestion entry point.

    Parameters
    ----------
    reingest     : If True, skip the already-indexed check and upsert everything.
    problem_ids  : Optional list of specific problem _id values to process.
                   When provided, only those problems are fetched from Mongo.
                   Implies reingest=True.
    """
    if problem_ids:
        reingest = True  # specific-ID runs always re-ingest

    mode_label = "RE-INGEST" if reingest else "normal"
    if problem_ids:
        mode_label += f" (ids={problem_ids})"

    print(f"\nConnecting to MongoDB…  [mode: {mode_label}]")
    client = MongoClient(settings.MONGO_URI)
    mongo_collection = client[settings.MONGO_DB_NAME][settings.MONGO_PROBLEMS_COLLECTION]

    # Build Mongo query
    mongo_query: dict = {}
    if problem_ids:
        mongo_query = {"_id": {"$in": problem_ids}}

    total = mongo_collection.count_documents(mongo_query)
    print(f"      Found {total:,} problems in MongoDB "
          f"({settings.MONGO_DB_NAME}.{settings.MONGO_PROBLEMS_COLLECTION})")

    print("\n Setting up embedder + Chroma vectorstore…")
    embedder = get_embedder()
    vectorstore = get_vectorstore(embedder)
    collection_stats(vectorstore)

    # Build the set of already-indexed problem_ids (only needed in normal mode)
    existing_problem_ids: set[str] = set()
    if not reingest:
        try:
            result = vectorstore._collection.get(include=["metadatas"])
            existing_problem_ids = {
                m["problem_id"]
                for m in result.get("metadatas", [])
                if m and "problem_id" in m
            }
            if existing_problem_ids:
                print(
                    f"      Found {len(existing_problem_ids):,} already-indexed problem IDs "
                    "— will skip them\n"
                )
        except Exception:
            pass

    print(f"\n Starting ingestion in batches of {settings.INGESTION_BATCH_SIZE} problems…")

    processed = 0
    skipped = 0
    start_time = time.time()

    cursor = mongo_collection.find(mongo_query)
    batch_docs: list[dict] = []
    batch_slugs: list[str] = []

    for problem in cursor:
        pid = str(problem["_id"])
        slug = problem.get("slug", pid)

        if not reingest and pid in existing_problem_ids:
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
    print(f"\n Ingestion complete in {elapsed:.1f}s")
    print(f"      Processed : {processed:,} problems")
    print(f"      Skipped   : {skipped:,} (already indexed, skipped in normal mode)")
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
        # Rate-limit guard: pause so we don't exceed Gemini free-tier quota
        # (100 embedContent requests/min). Skip delay after the final batch.
        if end < total and _BATCH_DELAY_S > 0:
            print(f"  [rate limit] sleeping {_BATCH_DELAY_S:.0f}s …")
            time.sleep(_BATCH_DELAY_S)
    except Exception as e:
        print(f"  [upsert error] batch starting at {processed + 1}: {e}")


if __name__ == "__main__":
    args = _parse_args()
    run(reingest=args.reingest, problem_ids=args.ids)
