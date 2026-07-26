"""Create the MongoDB indexes used by LEETBOT.

Run once from the repository root:
    python scripts/create_indexes.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError


def main() -> int:
    load_dotenv()

    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "leetbot_db")

    if not mongo_uri:
        print("ERROR: MONGO_URI is missing from the environment.", file=sys.stderr)
        return 1

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000)

    try:
        client.admin.command("ping")
        db = client[db_name]

        db["users"].create_index(
            [("email", ASCENDING)],
            unique=True,
            name="users_email_unique",
        )
        db["users"].create_index(
            [("username", ASCENDING)],
            unique=True,
            name="users_username_unique",
        )
        db["problems"].create_index(
            [("slug", ASCENDING)],
            unique=True,
            name="problems_slug_unique",
        )
        db["hint_sessions"].create_index(
            [("user_id", ASCENDING), ("slug", ASCENDING)],
            unique=True,
            name="hint_sessions_user_slug_unique",
        )
        db["hint_sessions"].create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="hint_sessions_user_created_at",
        )

        problem_count = db["problems"].count_documents({})
        print(f"Indexes created successfully in database: {db_name}")
        print(f"Problems available for Chroma ingestion: {problem_count}")

        if problem_count == 0:
            print(
                "WARNING: The problems collection is empty. "
                "Populate it before the Render build runs ingestion."
            )

        return 0
    except PyMongoError as exc:
        print(f"MongoDB error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
