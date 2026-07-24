import json
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

load_dotenv()

from backend.config import settings  # noqa: E402

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"

BATCH_SIZE = 100


def get_db():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB_NAME]


def setup_indexes(db) -> None:
    problems = db[settings.MONGO_PROBLEMS_COLLECTION]
    problems.create_index("slug", unique=True)
    problems.create_index("tags")
    problems.create_index("difficulty")
    problems.create_index([("tags", 1), ("difficulty", 1)])
    print("Indexes created/verified.")


def upload_problems(db) -> None:
    clean_files = sorted(CLEAN_DIR.glob("*.json"), key=lambda p: int(p.stem))
    total = len(clean_files)

    if total == 0:
        print("No clean files found in data/clean/. Run clean.py first.")
        return

    print(
        f"Uploading {total} problems to MongoDB "
        f"({settings.MONGO_DB_NAME}.{settings.MONGO_PROBLEMS_COLLECTION})...\n"
    )

    problems_col = db[settings.MONGO_PROBLEMS_COLLECTION]
    batch = []
    uploaded = 0

    for clean_path in clean_files:
        try:
            with open(clean_path, encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as e:
            print(f"  Could not read {clean_path.name}: {e}")
            continue

        batch.append(
            UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        )

        if len(batch) >= BATCH_SIZE:
            _flush_batch(problems_col, batch)
            uploaded += len(batch)
            print(f"  Uploaded {uploaded}/{total}...")
            batch = []

    if batch:
        _flush_batch(problems_col, batch)
        uploaded += len(batch)

    print(f"\nDone. {uploaded} problems upserted into MongoDB.")


def _flush_batch(collection, batch: list) -> None:
    try:
        collection.bulk_write(batch, ordered=False)
    except BulkWriteError as e:
        print(f"  Bulk write error (partial): {e.details.get('writeErrors', [])[:3]}")


def run():
    print("Connecting to MongoDB Atlas...")
    db = get_db()
    print(f"Connected to: {settings.MONGO_DB_NAME}\n")

    setup_indexes(db)
    upload_problems(db)

    count = db[settings.MONGO_PROBLEMS_COLLECTION].count_documents({})
    print(f"\nTotal documents in {settings.MONGO_PROBLEMS_COLLECTION} collection: {count}")


if __name__ == "__main__":
    run()
