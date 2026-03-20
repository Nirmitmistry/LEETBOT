"""
run.py
------
Master script. Runs the full Phase 3 pipeline in order:

  Step 1 — fetch.py   : scrape LeetCode → data/raw/
  Step 2 — clean.py   : transform raw → data/clean/
  Step 3 — upload.py  : push clean data → MongoDB Atlas

Run this file to do everything in one go:
  python scraper/run.py

Or run individual steps if one fails:
  python scraper/fetch.py
  python scraper/clean.py
  python scraper/upload.py
"""

from scraper.upload import run as run_upload
from scraper.clean import run as run_clean
from scraper.fetch import run as run_fetch
import sys
from pathlib import Path

# Make sure imports resolve from the project root
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
