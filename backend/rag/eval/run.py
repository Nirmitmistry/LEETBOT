"""
backend/rag/eval/run.py — CLI entrypoint for the LEETBOT RAG evaluation harness.

Usage
-----
# Run with defaults (golden dataset bundled in this package):
    python -m backend.rag.eval.run

# Custom golden dataset and output directory:
    python -m backend.rag.eval.run \\
        --dataset path/to/golden.json \\
        --output  eval_reports/

# Adjust faithfulness gate threshold:
    python -m backend.rag.eval.run --threshold 0.80

# Dense-only mode (disable hybrid retrieval for this run):
    python -m backend.rag.eval.run --no-hybrid

# Increase concurrency (careful with Gemini rate limits):
    python -m backend.rag.eval.run --concurrency 5

# Dry-run: retrieval only, skip generation and Ragas scoring:
    python -m backend.rag.eval.run --retrieval-only

Exit codes
----------
0   All checks passed (faithfulness >= threshold, or faithfulness unavailable).
1   Faithfulness gate failed (aggregate faithfulness < threshold).
2   Hard error (missing env vars, connection failure, etc.).

Output
------
A timestamped JSON report is written to the output directory:
    <output>/eval_<YYYYMMDD_HHMMSS>.json

This makes it easy to diff runs:
    python -m backend.rag.eval.run   # produces eval_20260816_120000.json
    git stash
    python -m backend.rag.eval.run   # produces eval_20260816_120100.json
    diff eval_20260816_120000.json eval_20260816_120100.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap logging before any project imports so startup messages are visible
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths
_HERE = Path(__file__).parent
_DEFAULT_DATASET = _HERE / "golden_dataset.json"
_DEFAULT_OUTPUT  = _HERE / "reports"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.rag.eval.run",
        description="Run the LEETBOT RAG evaluation harness and write a JSON report.",
    )
    p.add_argument(
        "--dataset", "-d",
        type=Path,
        default=_DEFAULT_DATASET,
        help=f"Path to the golden dataset JSON file (default: {_DEFAULT_DATASET})",
    )
    p.add_argument(
        "--output", "-o",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Directory to write the timestamped report (default: {_DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--threshold", "-t",
        type=float,
        default=None,
        help=(
            "Faithfulness gate threshold [0.0–1.0]. "
            "Exits non-zero if aggregate faithfulness drops below this. "
            "Defaults to EVAL_FAITHFULNESS_THRESHOLD env var or 0.85."
        ),
    )
    p.add_argument(
        "--concurrency", "-c",
        type=int,
        default=3,
        help="Max concurrent pipeline runs (default: 3, keep low for API rate limits)",
    )
    p.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Disable hybrid retrieval for this run (uses dense-only Chroma search)",
    )
    p.add_argument(
        "--no-query-transform",
        action="store_true",
        help="Disable HyDE / multi-query transformation for this run",
    )
    p.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip LLM generation and Ragas scoring (useful for fast retrieval smoke-tests)",
    )
    p.add_argument(
        "--filter-id",
        type=str,
        default=None,
        help="Run only the entry with this sample ID (useful for debugging one entry)",
    )
    p.add_argument(
        "--filter-slug",
        type=str,
        default=None,
        help="Run only entries for this problem slug",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return p


# ---------------------------------------------------------------------------
# Config snapshot (for the report)
# ---------------------------------------------------------------------------

def _config_snapshot(args: argparse.Namespace) -> dict:
    """
    Capture key config values at eval time so the report is self-contained.
    Avoids reading secrets — only logs non-sensitive setting names.
    """
    from backend.config import settings
    return {
        "gemini_model": settings.GEMINI_MODEL_NAME,
        "reranker_backend": settings.RERANKER_BACKEND,
        "reranker_top_n": settings.RERANKER_TOP_N,
        "reranker_threshold": settings.RERANKER_THRESHOLD,
        "hybrid_retrieval": settings.HYBRID_RETRIEVAL and not args.no_hybrid,
        "query_transform": settings.QUERY_TRANSFORM and not args.no_query_transform,
        "hybrid_candidate_k": settings.HYBRID_CANDIDATE_K,
        "reranker_candidate_k": settings.RERANKER_CANDIDATE_K,
        "retrieval_only": args.retrieval_only,
    }


# ---------------------------------------------------------------------------
# Env-var overrides (allow CI to inject flags via env instead of CLI args)
# ---------------------------------------------------------------------------

def _resolve_threshold(args_threshold: float | None) -> float:
    """
    Threshold resolution order:
    1. Explicit --threshold CLI arg
    2. EVAL_FAITHFULNESS_THRESHOLD env var
    3. Hardcoded default 0.85
    """
    if args_threshold is not None:
        return args_threshold
    env_val = os.getenv("EVAL_FAITHFULNESS_THRESHOLD")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            logger.warning(
                "EVAL_FAITHFULNESS_THRESHOLD='%s' is not a valid float — using default 0.85",
                env_val,
            )
    return 0.85


# ---------------------------------------------------------------------------
# Main async runner
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    """
    Async main — returns the process exit code.
    """
    from backend.rag.eval.schema import GoldenDataset, EvalReport
    from backend.rag.eval.pipeline import run_pipeline, _open_connections
    from backend.rag.eval.scorer import score_results, compute_aggregates

    threshold = _resolve_threshold(args.threshold)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # ── Load golden dataset ───────────────────────────────────────────────────
    if not args.dataset.exists():
        logger.error("Golden dataset not found: %s", args.dataset)
        return 2

    try:
        raw = json.loads(args.dataset.read_text(encoding="utf-8"))
        dataset = GoldenDataset.model_validate(raw)
    except Exception as exc:
        logger.error("Failed to parse golden dataset: %s", exc)
        return 2

    entries = dataset.entries

    # Optional filters
    if args.filter_id:
        entries = [e for e in entries if e.id == args.filter_id]
        if not entries:
            logger.error("No entry with id='%s' found in the dataset", args.filter_id)
            return 2

    if args.filter_slug:
        entries = [e for e in entries if e.slug == args.filter_slug]
        if not entries:
            logger.error("No entries for slug='%s' found in the dataset", args.filter_slug)
            return 2

    logger.info("Loaded %d golden entries from %s", len(entries), args.dataset)

    # ── Apply CLI flag overrides to settings ──────────────────────────────────
    # We override the module-level settings via env vars before importing
    # pipeline code so that retrieve_and_rerank picks up the flags.
    # This is intentionally done here (not at import time) so the overrides
    # only apply for this eval run.
    if args.no_hybrid:
        os.environ["HYBRID_RETRIEVAL"] = "false"
        logger.info("Hybrid retrieval disabled for this run")
    if args.no_query_transform:
        os.environ["QUERY_TRANSFORM"] = "false"
        logger.info("Query transform disabled for this run")

    # ── Open connections ──────────────────────────────────────────────────────
    try:
        mongo_client, db, chroma = _open_connections()
    except Exception as exc:
        logger.error("Failed to open database connections: %s", exc)
        return 2

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        logger.info(
            "Running pipeline on %d entries (concurrency=%d)…",
            len(entries), args.concurrency,
        )
        results = await run_pipeline(
            entries=entries,
            db=db,
            chroma=chroma,
            concurrency=args.concurrency,
        )
    except Exception as exc:
        logger.error("Pipeline run failed: %s", exc)
        mongo_client.close()
        return 2
    finally:
        mongo_client.close()

    # ── Ragas scoring ─────────────────────────────────────────────────────────
    if not args.retrieval_only:
        results = score_results(results)
    else:
        logger.info("--retrieval-only: skipping Ragas scoring")

    # ── Aggregates ────────────────────────────────────────────────────────────
    aggregate = compute_aggregates(results)
    errored   = sum(1 for r in results if r.error)
    passed    = (
        aggregate.faithfulness is None   # can't fail a gate with no data
        or aggregate.faithfulness >= threshold
    )

    # ── Build report ──────────────────────────────────────────────────────────
    report = EvalReport(
        run_id=run_id,
        pipeline_config=_config_snapshot(args),
        query_results=results,
        aggregate=aggregate,
        faithfulness_threshold=threshold,
        passed_faithfulness_gate=passed,
        total_samples=len(results),
        errored_samples=errored,
    )

    # ── Write report ──────────────────────────────────────────────────────────
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / f"eval_{run_id}.json"
    report_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("Report written to %s", report_path)

    # ── Summary to stdout ─────────────────────────────────────────────────────
    _print_summary(report, threshold)

    return 0 if passed else 1


def _print_summary(report: "EvalReport", threshold: float) -> None:  # noqa: F821
    """Print a human-readable summary table to stdout."""
    agg = report.aggregate

    def _fmt(v: float | None) -> str:
        return f"{v:.4f}" if v is not None else "  N/A  "

    sep = "─" * 52
    print(f"\n{'═' * 52}")
    print(f"  LEETBOT RAG Eval — {report.run_id}")
    print(f"{'═' * 52}")
    print(f"  Samples total  : {report.total_samples}")
    print(f"  Samples errored: {report.errored_samples}")
    print(sep)
    print(f"  {'Metric':<26}  {'Score':>7}")
    print(sep)
    print(f"  {'faithfulness':<26}  {_fmt(agg.faithfulness):>7}  ← gate threshold {threshold:.2f}")
    print(f"  {'context_precision':<26}  {_fmt(agg.context_precision):>7}")
    print(f"  {'context_recall':<26}  {_fmt(agg.context_recall):>7}")
    print(f"  {'answer_relevancy':<26}  {_fmt(agg.answer_relevancy):>7}")
    print(sep)
    print(f"  {'vague faithfulness':<26}  {_fmt(agg.vague_faithfulness):>7}")
    print(f"  {'precise faithfulness':<26}  {_fmt(agg.precise_faithfulness):>7}")
    print(f"{'═' * 52}")
    gate_str = "✓ PASSED" if report.passed_faithfulness_gate else "✗ FAILED"
    print(f"  Faithfulness gate : {gate_str}")
    print(f"{'═' * 52}\n")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        exit_code = asyncio.run(_run(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        exit_code = 2
    except Exception as exc:
        logger.exception("Unhandled error in eval harness: %s", exc)
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
