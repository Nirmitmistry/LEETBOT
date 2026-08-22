"""
scripts/rebuild_chroma.py — Safe Chroma rebuild for LEETBOT.

This script:
  1. Backs up the existing chroma_db directory (renames to chroma_db_backup_<timestamp>)
  2. Runs the current ingestion pipeline (chunker → Gemini embedder → Chroma)
  3. Validates the resulting corpus

Usage
-----
    python scripts/rebuild_chroma.py            # backup + rebuild + validate
    python scripts/rebuild_chroma.py --no-backup  # skip backup (CI / clean env)
    python scripts/rebuild_chroma.py --validate-only  # only run validation, no rebuild

Why rebuild?
------------
The previous ingestion run used OpenAI text-embedding-3-small (1536 dims).
The backend uses GoogleGenerativeAIEmbeddings (GEMINI_EMBEDDING_MODEL, 3072 dims).
Querying 1536-dim vectors with a 3072-dim query model produces incorrect results.

The previous run also used an older chunker that only produced 'statement' and
'hint' chunks.  The current chunker also produces 'constraints', 'example_N',
'editorial_approach_N', and 'solutions' chunks — all missing from the old collection.

This script rebuilds everything using the current pipeline so Chroma + BM25 are
consistent with the backend's embedding model and chunk schema.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from backend.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backup_chroma(chroma_path: Path) -> Path | None:
    """Rename chroma_db → chroma_db_backup_<timestamp>. Returns backup path."""
    if not chroma_path.exists():
        print(f"  [backup] {chroma_path} does not exist — nothing to back up")
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = chroma_path.parent / f"{chroma_path.name}_backup_{ts}"
    chroma_path.rename(backup)
    print(f"  [backup] {chroma_path.name} → {backup.name}")
    return backup


def _validate(chroma_path: Path) -> bool:
    """
    Validate the rebuilt Chroma collection and BM25 readiness.
    Returns True if all checks pass.
    """
    import chromadb
    from backend.rag.bm25_index import warm_bm25_index, is_ready
    from langchain_chroma import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    print("\n=== Validation ===")
    ok = True

    # ── Chroma ────────────────────────────────────────────────────────────────
    try:
        raw_client = chromadb.PersistentClient(path=str(chroma_path))
        col = raw_client.get_collection(settings.CHROMA_COLLECTION)
        total = col.count()
        print(f"  ✓ Chroma collection '{settings.CHROMA_COLLECTION}': {total:,} vectors")
        if total == 0:
            print("  ✗ ERROR: Chroma collection is empty!")
            ok = False
    except Exception as exc:
        print(f"  ✗ ERROR opening Chroma: {exc}")
        return False

    # ── Chunk type distribution ───────────────────────────────────────────────
    try:
        all_data = col.get(include=["metadatas"])
        chunk_types: dict[str, int] = {}
        problem_ids: set[str] = set()
        doc_ids: set[str] = set()

        for meta, id_ in zip(all_data["metadatas"], all_data["ids"]):
            if meta:
                chunk_types[meta.get("chunk_type", "unknown")] = \
                    chunk_types.get(meta.get("chunk_type", "unknown"), 0) + 1
                if "problem_id" in meta:
                    problem_ids.add(meta["problem_id"])
            doc_ids.add(id_)

        print(f"  ✓ Unique problems in Chroma: {len(problem_ids):,}")
        print(f"  ✓ Chunk type distribution:")
        for ct, n in sorted(chunk_types.items()):
            print(f"      {ct:<28} {n:>6,}")

        expected_types = {"statement", "constraints", "example", "editorial_approach", "hint", "solutions"}
        present_types = set(chunk_types.keys())
        missing = expected_types - present_types
        if missing:
            print(f"  ⚠ WARNING: expected chunk types not found: {missing}")
            print("    (this may be normal if some problems lack editorials/solutions)")
        else:
            print(f"  ✓ All expected chunk types present")

    except Exception as exc:
        print(f"  ✗ ERROR reading metadata: {exc}")
        ok = False

    # ── Embedding dimensions ──────────────────────────────────────────────────
    try:
        ids = all_data["ids"]
        if ids:
            sample = col.get(ids=[ids[0]], include=["embeddings"])
            dim = len(sample["embeddings"][0])
            print(f"  ✓ Embedding dimensions: {dim}")
            # Warn if dimensions don't match expected Gemini output
            # text-embedding-004 = 768, gemini-embedding-2 = 3072, text-embedding-3-small = 1536
            if dim == 1536:
                print("  ✗ ERROR: 1536-dim vectors detected — this is OpenAI text-embedding-3-small.")
                print("    The backend uses Gemini embeddings. Re-ingestion with the Gemini embedder is required.")
                ok = False
    except Exception as exc:
        print(f"  ⚠ Could not check embedding dimensions: {exc}")

    # ── doc_id → Chroma ID mapping ────────────────────────────────────────────
    try:
        chroma_ids = set(all_data["ids"])
        meta_doc_ids = {
            m["doc_id"] for m in all_data["metadatas"]
            if m and "doc_id" in m
        }
        mismatch = chroma_ids - meta_doc_ids
        if mismatch:
            print(f"  ⚠ {len(mismatch):,} Chroma IDs missing 'doc_id' in metadata")
        else:
            print(f"  ✓ All {len(chroma_ids):,} Chroma IDs have matching doc_id metadata")
    except Exception as exc:
        print(f"  ⚠ doc_id check error: {exc}")

    # ── BM25 ──────────────────────────────────────────────────────────────────
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
        chroma_lc = Chroma(
            collection_name=settings.CHROMA_COLLECTION,
            embedding_function=embeddings,
            persist_directory=str(chroma_path),
        )
        n_bm25 = warm_bm25_index(chroma_lc)
        if n_bm25 == 0:
            print("  ✗ ERROR: BM25 index empty — Chroma collection may be empty")
            ok = False
        else:
            print(f"  ✓ BM25 index: {n_bm25:,} chunks indexed")
            # Verify BM25 count matches Chroma count
            if n_bm25 != total:
                print(f"  ⚠ BM25 count ({n_bm25:,}) ≠ Chroma count ({total:,})")
            else:
                print(f"  ✓ BM25 count matches Chroma count ({total:,})")
    except Exception as exc:
        print(f"  ✗ BM25 warm-up error: {exc}")
        ok = False

    print()
    if ok:
        print("  ✓ All validation checks passed")
    else:
        print("  ✗ One or more validation checks FAILED")

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe Chroma rebuild — backup, re-ingest, validate"
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip backing up the existing chroma_db (use in CI or clean environments)"
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Skip ingestion; only run the validation checks on the existing collection"
    )
    parser.add_argument(
        "--ids", nargs="+", type=int, metavar="ID",
        help="Only re-ingest these problem IDs (useful for incremental updates)"
    )
    args = parser.parse_args()

    chroma_path = Path(settings.CHROMA_PATH).resolve()

    if args.validate_only:
        ok = _validate(chroma_path)
        sys.exit(0 if ok else 1)

    print("=== LEETBOT Chroma Rebuild ===")
    print(f"  Chroma path    : {chroma_path}")
    print(f"  Collection     : {settings.CHROMA_COLLECTION}")
    print(f"  Embed model    : {settings.GEMINI_EMBEDDING_MODEL}")
    print(f"  MongoDB db     : {settings.MONGO_DB_NAME}")
    print()

    # Step 1: Backup
    if not args.no_backup and not args.ids:
        _backup_chroma(chroma_path)
    elif args.ids:
        print("  [backup] Skipping backup for targeted --ids run (upsert is safe)")

    # Step 2: Re-ingest
    print("\n=== Running ingestion pipeline ===")
    t0 = time.time()

    from ingestion.run import run as run_ingestion
    run_ingestion(reingest=True, problem_ids=args.ids)

    elapsed = time.time() - t0
    print(f"\n  Ingestion completed in {elapsed:.1f}s")

    # Step 3: Validate
    ok = _validate(chroma_path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
