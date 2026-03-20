import re
import json
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
FAILED_DIR = BASE_DIR / "data" / "failed"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


# ── HTML stripping ─────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """
    Remove HTML tags from LeetCode's problem content.
    LeetCode returns the problem statement as HTML — we want plain text.
    """
    if not text:
        return ""
    # Replace common HTML elements with readable equivalents
    text = re.sub(r"<br\s*/?>",        "\n",  text)
    text = re.sub(r"<p>",              "\n",  text)
    text = re.sub(r"</p>",             "\n",  text)
    text = re.sub(r"<li>",             "- ",  text)
    text = re.sub(r"<strong>(.*?)</strong>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>",         r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<code>(.*?)</code>",     r"`\1`", text, flags=re.DOTALL)
    text = re.sub(r"<pre>(.*?)</pre>",       r"\1",   text, flags=re.DOTALL)
    # Strip any remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&lt;",  "<")
    text = text.replace("&gt;",  ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#39;", "'")
    text = text.replace("&quot;", '"')
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── example parsing ────────────────────────────────────────────────────────────

def parse_examples(content_html: str) -> list[dict]:
    """
    Extract input/output/explanation blocks from the HTML problem content.
    LeetCode embeds examples inside <pre> blocks in the content field.
    """
    examples = []
    # Find all <pre> blocks — each one is usually one example
    pre_blocks = re.findall(r"<pre>(.*?)</pre>", content_html or "", re.DOTALL)

    for block in pre_blocks:
        text = strip_html(block).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        example = {}

        for line in lines:
            if line.lower().startswith("input:"):
                example["input"] = line[6:].strip()
            elif line.lower().startswith("output:"):
                example["output"] = line[7:].strip()
            elif line.lower().startswith("explanation:"):
                example["explanation"] = line[12:].strip()

        if example.get("input") and example.get("output"):
            examples.append(example)

    return examples


# ── constraints parsing ────────────────────────────────────────────────────────

def parse_constraints(content_html: str) -> str:
    """
    Extract the constraints section from the HTML content.
    LeetCode puts constraints inside an <ul> after a 'Constraints:' heading.
    """
    if not content_html:
        return ""
    # Find everything after "Constraints:" heading
    match = re.search(
        r"<strong[^>]*>Constraints:?</strong>(.*?)(?=<strong|$)",
        content_html,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return ""
    return strip_html(match.group(1)).strip()


# ── solution cleaning ──────────────────────────────────────────────────────────

def best_solution(solutions: list[str]) -> str:
    """
    From the list of raw community solutions, return the cleanest one.
    Strategy: pick the shortest one (usually the most elegant approach).
    Falls back to empty string if no solutions were fetched.
    """
    if not solutions:
        return ""
    # Filter out empty strings, pick the shortest non-empty one
    valid = [s for s in solutions if s and len(s.strip()) > 10]
    if not valid:
        return ""
    return min(valid, key=len).strip()


# ── complexity inference ───────────────────────────────────────────────────────

def infer_complexity(editorial: str) -> tuple[str, str]:
    """
    Try to extract time/space complexity from the editorial text.
    This is a best-effort heuristic — it won't be perfect.
    Returns ("unknown", "unknown") if nothing is found.
    """
    if not editorial:
        return "unknown", "unknown"

    time_match = re.search(
        r"[Tt]ime\s+[Cc]omplexity[:\s]+O\(([^)]+)\)", editorial)
    space_match = re.search(
        r"[Ss]pace\s+[Cc]omplexity[:\s]+O\(([^)]+)\)", editorial)

    time_c = f"O({time_match.group(1)})" if time_match else "unknown"
    space_c = f"O({space_match.group(1)})" if space_match else "unknown"
    return time_c, space_c


# ── hint staging ───────────────────────────────────────────────────────────────

def build_hints(official_hints: list[str], editorial: str) -> dict:
    """
    Map raw hint data into our 4-stage hint structure.

    Stage 1: first official hint (conceptual nudge)
    Stage 2: second official hint (pattern name)
    Stage 3: editorial intro / approach overview
    Stage 4: editorial code walkthrough (first code block)

    Stage 5 is not stored here — it's the full solution, stored in solutions{}.
    """
    hints = {}

    # Stage 1 — first official hint
    hints["stage_1"] = official_hints[0] if len(official_hints) > 0 else ""

    # Stage 2 — second official hint (or a gentle fallback)
    hints["stage_2"] = official_hints[1] if len(official_hints) > 1 else ""

    # Stage 3 — editorial approach overview (first 500 chars of editorial)
    if editorial:
        # Take just the approach section, not the full thing
        approach_match = re.search(
            r"(Approach|Intuition|Overview)(.*?)(?=Approach \d|Complexity|$)",
            editorial,
            re.DOTALL | re.IGNORECASE,
        )
        hints["stage_3"] = approach_match.group(
            0)[:600].strip() if approach_match else editorial[:500].strip()
    else:
        hints["stage_3"] = ""

    # Stage 4 — first code block from editorial (the key logic)
    code_match = re.search(r"```[a-z]*\n(.*?)```", editorial or "", re.DOTALL)
    hints["stage_4"] = code_match.group(1).strip() if code_match else ""

    return hints


# ── main cleaning function ─────────────────────────────────────────────────────

def clean_problem(raw: dict) -> dict | None:
    """
    Convert one raw bundle into a clean problem document matching our schema.
    Returns None if the raw data is too broken to clean.
    """
    detail = raw.get("detail_data", {})
    sol_raw = raw.get("solutions_raw", {})

    # These fields are required — if missing the problem is broken
    problem_id = raw.get("problem_id")
    slug = detail.get("titleSlug") or raw.get("list_data", {}).get("titleSlug")
    title = detail.get("title")
    if not all([problem_id, slug, title]):
        return None

    content_html = detail.get("content", "")
    editorial = strip_html(detail.get("solution", {}).get(
        "content", "")) if detail.get("solution") else ""

    time_c, space_c = infer_complexity(editorial)

    return {
        # ── identity ──────────────────────────────────────
        "_id":             problem_id,
        "slug":            slug,
        "title":           title,
        "difficulty":      detail.get("difficulty", "").lower(),
        "acceptance_rate": round(float(detail.get("acRate", 0)), 1),
        "is_premium":      detail.get("isPaidOnly", False),

        # ── classification ────────────────────────────────
        "tags": [
            t["slug"] for t in detail.get("topicTags", [])
        ],

        # EDITED: Added `and q["titleSlug"].split("-")[0].isdigit()` to the if-condition
        # to prevent ValueError when encountering slugs that don't start with numbers (like "3sum").
        "similar_problem_ids": [
            int(q["titleSlug"].split("-")[0])
            for q in json.loads(detail.get("similarQuestions", "[]") or "[]")
            if q.get("titleSlug") and q["titleSlug"].split("-")[0].isdigit()
        ][:5],  # cap at 5

        # ── content ───────────────────────────────────────
        "problem_statement": strip_html(content_html),
        "constraints":       parse_constraints(content_html),
        "examples":          parse_examples(content_html),

        # ── hints ─────────────────────────────────────────
        "hints": build_hints(
            official_hints=detail.get("hints", []),
            editorial=editorial,
        ),

        # ── editorial ─────────────────────────────────────
        "editorial": {
            "source":  "official" if editorial else "none",
            "content": editorial,
        },

        # ── solutions ─────────────────────────────────────
        # We pick the best (shortest clean) community solution per language
        "solutions": {
            "python": best_solution(sol_raw.get("python3", [])),
            "java":   best_solution(sol_raw.get("java", [])),
            "cpp":    best_solution(sol_raw.get("cpp", [])),
        },

        # ── complexity ────────────────────────────────────
        "complexity": {
            "time":        time_c,
            "space":       space_c,
            "explanation": "",
        },

        # ── metadata ──────────────────────────────────────
        "scraped_at":               raw.get("scraped_at", ""),
        "editorial_source_verified": bool(editorial),
    }


# ── batch runner ───────────────────────────────────────────────────────────────

def run():
    raw_files = sorted(RAW_DIR.glob("*.json"), key=lambda p: int(p.stem))
    total = len(raw_files)
    success = 0
    skipped = 0
    failed = 0

    print(f"Cleaning {total} raw files...\n")

    for raw_path in raw_files:
        problem_id = int(raw_path.stem)
        clean_path = CLEAN_DIR / f"{problem_id}.json"

        raw = None
        try:
            with open(raw_path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"  #{problem_id} — could not read raw file: {e}")
            failed += 1
            continue

        clean = clean_problem(raw)

        if clean is None:
            print(f"  #{problem_id} — skipped (missing required fields)")
            skipped += 1
            continue

        with open(clean_path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)

        success += 1
        if success % 100 == 0:
            print(f"  Cleaned {success}/{total}...")

    print(f"\nDone.")
    print(f"  Cleaned:  {success}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {failed}")


if __name__ == "__main__":
    run()
