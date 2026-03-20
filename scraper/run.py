from scraper.upload import run as run_upload
from scraper.clean import run as run_clean
from scraper.fetch import run as run_fetch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    print("=" * 60)
    print("LEETBOT — Phase 3: Data Pipeline")
    print("=" * 60)

    print("\n[ STEP 1 / 3 ] Scraping LeetCode...")
    print("-" * 40)
    run_fetch()

    print("\n[ STEP 2 / 3 ] Cleaning raw data...")
    print("-" * 40)
    run_clean()

    print("\n[ STEP 3 / 3 ] Uploading to MongoDB Atlas...")
    print("-" * 40)
    run_upload()

    print("\n" + "=" * 60)
    print("Phase 3 complete. Your data is in MongoDB.")
    print("Next: Phase 4 — build the ingestion pipeline (embeddings + Chroma).")
    print("=" * 60)


if __name__ == "__main__":
    main()
