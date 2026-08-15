"""
chunker.py — Schema-aware chunking for LeetCode problems.

Chunk types produced per problem
---------------------------------
statement          : problem title + clean statement text (no examples, no constraints)
constraints        : the constraints block as a standalone chunk
example_{n}        : one chunk per example — input + output + explanation kept together
editorial_approach : one chunk per editorial approach paragraph (if editorial exists)
hint_{1-4}         : individual hint stages (unchanged from previous version)
solutions          : combined solution code chunk (if any solution exists)

Metadata stored on every chunk
--------------------------------
doc_id         : stable upsert key  →  {problem_id}_{chunk_type}[_{index}]
problem_id     : str(doc["_id"])
slug           : problem slug
difficulty     : easy / medium / hard
tags           : comma-separated tag string
chunk_type     : one of the types above
hint_stage     : int (used by retriever for hint-gating; 0 = no gate)
example_index  : int  (only on example chunks)
approach_name  : str  (only on editorial_approach chunks)

Parent-document retrieval
--------------------------
Child chunks are what Chroma embeds and searches.  The retriever in
backend/retriever.py hydrates each hit with the full parent document from
MongoDB (keyed on problem_id) before passing content to the LLM.
"""

from __future__ import annotations

import re
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_statement(raw: str) -> str:
    """
    Strip the trailing Constraints / Example blocks that are often duplicated
    inside problem_statement so the statement chunk is clean prose only.
    """
    # Cut at the first occurrence of a standalone "Constraints:" heading
    raw = re.split(r"\n\s*Constraints\s*:", raw, maxsplit=1)[0]
    # Cut at the first "Example N:" heading (sometimes embedded in statement)
    raw = re.split(r"\n\s*Example\s+\d+\s*:", raw, maxsplit=1)[0]
    return raw.strip()


def _split_editorial_approaches(editorial_text: str) -> list[str]:
    """
    Split a multi-paragraph editorial into individual approach chunks.
    Splits on common heading patterns like "Approach 1:", "## Two Pointers", etc.
    Falls back to returning the whole text as a single chunk.
    """
    # Try to split on numbered or headed approach sections
    parts = re.split(
        r"\n(?=(?:Approach\s+\d+|##\s+|###\s+|\*\*Approach))",
        editorial_text,
        flags=re.IGNORECASE,
    )
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [editorial_text.strip()]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def chunk_problem(doc: dict) -> list[Document]:
    """
    Produce schema-aware child chunks for a single LeetCode problem document.

    Parameters
    ----------
    doc : raw MongoDB problem dict (the clean JSON shape)

    Returns
    -------
    List of Document objects ready to embed and upsert into Chroma.
    Each document's metadata["doc_id"] is the stable upsert key.
    """
    pid = str(doc["_id"])
    slug = doc.get("slug", "")

    base_meta: dict = {
        "problem_id": pid,
        "slug":       slug,
        "difficulty": doc.get("difficulty", ""),
        "tags":       ",".join(doc.get("tags", [])) if isinstance(doc.get("tags"), list)
                      else str(doc.get("tags", "")),
    }

    chunks: list[Document] = []

    # ── 1. Statement chunk ────────────────────────────────────────────────────
    raw_statement = doc.get("problem_statement", "")
    clean_stmt = _clean_statement(raw_statement)
    title = doc.get("title", slug)

    chunks.append(Document(
        page_content=f"{title}\n\n{clean_stmt}" if clean_stmt else title,
        metadata={
            **base_meta,
            "chunk_type": "statement",
            "hint_stage":  0,
            "doc_id":      f"{pid}_statement",
        },
    ))

    # ── 2. Constraints chunk ──────────────────────────────────────────────────
    constraints_raw = doc.get("constraints", "")
    if isinstance(constraints_raw, list):
        constraints_raw = "\n".join(constraints_raw)
    constraints_raw = constraints_raw.strip()

    if constraints_raw:
        chunks.append(Document(
            page_content=f"Constraints for {title}:\n{constraints_raw}",
            metadata={
                **base_meta,
                "chunk_type": "constraints",
                "hint_stage":  0,
                "doc_id":      f"{pid}_constraints",
            },
        ))

    # ── 3. Per-example chunks (input + output + explanation together) ─────────
    examples = doc.get("examples", [])
    if isinstance(examples, str):
        # Some docs store examples as a raw string — treat as a single example
        examples = [{"input": examples, "output": "", "explanation": ""}]

    for idx, ex in enumerate(examples):
        parts = []
        inp = str(ex.get("input", "")).strip()
        out = str(ex.get("output", "")).strip()
        exp = str(ex.get("explanation", "")).strip()

        if inp:
            parts.append(f"Input:  {inp}")
        if out:
            parts.append(f"Output: {out}")
        if exp:
            parts.append(f"Explanation: {exp}")

        if not parts:
            continue  # skip empty examples

        chunks.append(Document(
            page_content=f"Example {idx + 1} for {title}:\n" + "\n".join(parts),
            metadata={
                **base_meta,
                "chunk_type":    "example",
                "hint_stage":    0,
                "example_index": idx,
                "doc_id":        f"{pid}_example_{idx}",
            },
        ))

    # ── 4. Editorial approach chunks ──────────────────────────────────────────
    editorial = doc.get("editorial", {})
    if isinstance(editorial, dict):
        editorial_text = editorial.get("content", "") or ""
    elif isinstance(editorial, str):
        editorial_text = editorial
    else:
        editorial_text = ""

    editorial_text = editorial_text.strip()

    if editorial_text:
        approaches = _split_editorial_approaches(editorial_text)
        for a_idx, approach_text in enumerate(approaches):
            # Derive a short name from the first line (heading or first sentence)
            first_line = approach_text.splitlines()[0].strip()
            approach_name = re.sub(r"[#*`]", "", first_line).strip()[:80] or f"approach_{a_idx}"

            chunks.append(Document(
                page_content=approach_text,
                metadata={
                    **base_meta,
                    "chunk_type":    "editorial_approach",
                    "hint_stage":    3,
                    "approach_name": approach_name,
                    "doc_id":        f"{pid}_editorial_approach_{a_idx}",
                },
            ))

    # ── 5. Hint chunks (stage 1–4) ────────────────────────────────────────────
    hints = doc.get("hints", {})
    for stage_num in range(1, 5):
        hint_text = ""
        if isinstance(hints, dict):
            hint_text = (hints.get(f"stage_{stage_num}") or "").strip()

        if hint_text:
            chunks.append(Document(
                page_content=f"Hint stage {stage_num} for {title}:\n{hint_text}",
                metadata={
                    **base_meta,
                    "chunk_type": "hint",
                    "hint_stage":  stage_num,
                    "doc_id":      f"{pid}_hint_{stage_num}",
                },
            ))

    # ── 6. Solutions chunk ────────────────────────────────────────────────────
    solutions = doc.get("solutions", {})
    solution_parts = []
    if isinstance(solutions, dict):
        for lang in ("python", "java", "cpp"):
            code = (solutions.get(lang) or "").strip()
            if code:
                solution_parts.append(f"### {lang.upper()} solution:\n{code}")

    if solution_parts:
        chunks.append(Document(
            page_content="\n\n".join(solution_parts),
            metadata={
                **base_meta,
                "chunk_type": "solutions",
                "hint_stage":  5,
                "doc_id":      f"{pid}_solutions",
            },
        ))

    return chunks
