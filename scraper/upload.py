"""
upload.py
---------
Reads all clean JSON files from data/clean/ and uploads them to MongoDB Atlas.

Run this AFTER clean.py has finished.
Uses upsert so it's safe to re-run — existing documents are updated, not duplicated.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

load_dotenv()

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"

# ── mongo connection ───────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "leetbot_db")

BATCH_SIZE = 100  # upload this many documents at once


def get_db():
    """Connect to MongoDB and return the database object."""
    if not MONGO_URI:
        raise ValueError(
            "MONGO_URI not set in .env — cannot connect to MongoDB.")
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]


def setup_indexes(db) -> None:
    """
    Create the indexes we planned in Phase 2.
    This is idempotent — calling it twice doesn't break anything.
    """
    problems = db["problems"]
    problems.create_index("slug",       unique=True)
    problems.create_index("tags")
    problems.create_index("difficulty")
    problems.create_index([("tags", 1), ("difficulty", 1)])  # compound
    print("Indexes created/verified.")


def upload_problems(db) -> None:
    """
    Load all clean JSON files and upsert them into the problems collection.
    Uses bulk_write with upserts for efficiency — one round trip per 100 docs.
    """
    clean_files = sorted(CLEAN_DIR.glob("*.json"), key=lambda p: int(p.stem))
    total = len(clean_files)

    if total == 0:
        print("No clean files found in data/clean/. Run clean.py first.")
        return

    print(
        f"Uploading {total} problems to MongoDB ({MONGO_DB_NAME}.problems)...\n")

    problems_col = db["problems"]
    batch = []
    uploaded = 0

    for clean_path in clean_files:
        try:
            with open(clean_path, encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as e:
            print(f"  Could not read {clean_path.name}: {e}")
            continue

        # Build an upsert operation
        # filter: match by _id (problem_id)
        # update: replace the whole document
        batch.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": doc},
                upsert=True,
            )
        )

        # Flush batch when full
        if len(batch) >= BATCH_SIZE:
            _flush_batch(problems_col, batch)
            uploaded += len(batch)
            print(f"  Uploaded {uploaded}/{total}...")
            batch = []

    # Flush remaining
    if batch:
        _flush_batch(problems_col, batch)
        uploaded += len(batch)

    print(f"\nDone. {uploaded} problems upserted into MongoDB.")


def _flush_batch(collection, batch: list) -> None:
    """Execute a batch of write operations, with error reporting."""
    try:
        collection.bulk_write(batch, ordered=False)
    except BulkWriteError as e:
        # Some docs may have failed — report but keep going
        print(
            f"  Bulk write error (partial): {e.details.get('writeErrors', [])[:3]}")


def run():
    print("Connecting to MongoDB Atlas...")
    db = get_db()
    print(f"Connected to: {MONGO_DB_NAME}\n")

    setup_indexes(db)
    upload_problems(db)

    # Print a quick count to confirm
    count = db["problems"].count_documents({})
    print(f"\nTotal documents in problems collection: {count}")


if __name__ == "__main__":
    run()
