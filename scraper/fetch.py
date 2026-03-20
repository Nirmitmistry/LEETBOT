import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR   = Path(__file__).resolve().parent.parent
RAW_DIR    = BASE_DIR / "data" / "raw"
FAILED_DIR = BASE_DIR / "data" / "failed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)

LEETCODE_GRAPHQL  = "https://leetcode.com/graphql"
SCRAPE_DELAY      = float(os.getenv("SCRAPE_DELAY", 1.5))
LEETCODE_SESSION  = os.getenv("LEETCODE_SESSION", "")

# Headers that make requests look like a normal browser session
HEADERS = {
    "Content-Type":  "application/json",
    "Referer":       "https://leetcode.com",
    "User-Agent":    "Mozilla/5.0 (compatible; leetbot-scraper/1.0)",
    "Cookie":        f"LEETCODE_SESSION={LEETCODE_SESSION}",
}

# ── GraphQL queries ────────────────────────────────────────────────────────────

# Query 1: Fetch the master list of all problems (paginated)
# Returns: id, title, slug, difficulty, tags, acceptance rate, is_premium
PROBLEM_LIST_QUERY = """
query problemList($skip: Int, $limit: Int) {
  problemsetQuestionList: questionList(
    categorySlug: ""
    limit: $limit
    skip: $skip
    filters: {}
  ) {
    total: totalNum
    questions: data {
      questionFrontendId
      title
      titleSlug
      difficulty
      acRate
      isPaidOnly
      topicTags {
        name
        slug
      }
    }
  }
}
"""

# Query 2: Fetch full detail for one problem by its slug
# Returns: statement, examples, constraints, hints, similar questions
PROBLEM_DETAIL_QUERY = """
query problemDetail($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    difficulty
    acRate
    isPaidOnly
    content
    hints
    similarQuestions
    topicTags {
      name
      slug
    }
    exampleTestcaseList
    metaData
  }
}
"""

# Query 3: Fetch top community solutions for one problem in one language
# Returns: code of top accepted solutions
SOLUTIONS_QUERY = """
query communitySolutions($questionSlug: String!, $languageName: String!, $skip: Int) {
  questionSolutions(
    filters: { questionSlug: $questionSlug, languageName: $languageName, orderBy: HOT }
    limit: 3
    skip: $skip
  ) {
    solutions {
      title
      lang
      langVerboseName
      content
      solutionTags { name }
      reactionSummary { count }
    }
  }
}
"""


# ── helpers ────────────────────────────────────────────────────────────────────

def graphql_post(query: str, variables: dict) -> dict | None:
    """
    Send one GraphQL request to LeetCode.
    Returns the parsed JSON response, or None if the request failed.
    """
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL,
            headers=HEADERS,
            json={"query": query, "variables": variables},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"  [network error] {e}")
        return None


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── step 1: fetch the problem list ────────────────────────────────────────────

def fetch_problem_list() -> list[dict]:
    """
    Fetches every free problem from LeetCode.
    Returns a flat list of problem metadata dicts.
    Filters out premium problems automatically.
    """
    print("Fetching problem list from LeetCode...")
    all_problems = []
    page_size    = 100
    skip         = 0

    while True:
        resp = graphql_post(PROBLEM_LIST_QUERY, {"skip": skip, "limit": page_size})
        if not resp:
            print(f"  Failed to fetch page at skip={skip}. Stopping list fetch.")
            break

        data      = resp.get("data", {}).get("problemsetQuestionList", {})
        questions = data.get("questions", [])
        total     = data.get("total", 0)

        # Filter out premium problems
        free = [q for q in questions if not q.get("isPaidOnly", False)]
        all_problems.extend(free)

        print(f"  Fetched {skip + len(questions)}/{total} problems "
              f"({len(all_problems)} free so far)...")

        skip += page_size
        if skip >= total:
            break

        time.sleep(SCRAPE_DELAY)

    print(f"Done. Found {len(all_problems)} free problems.")
    return all_problems


# ── step 2: fetch detail for one problem ──────────────────────────────────────

def fetch_problem_detail(slug: str) -> dict | None:
    """Fetch full problem detail (statement, hints, examples) for one slug."""
    resp = graphql_post(PROBLEM_DETAIL_QUERY, {"titleSlug": slug})
    if not resp:
        return None
    return resp.get("data", {}).get("question")


def fetch_solutions(slug: str, language: str) -> list[str]:
    """
    Fetch the top 3 community solutions for a problem in one language.
    Returns a list of code strings (may be empty if none found).
    """
    resp = graphql_post(SOLUTIONS_QUERY, {
        "questionSlug": slug,
        "languageName": language,
        "skip": 0,
    })
    if not resp:
        return []

    solutions = (
        resp.get("data", {})
            .get("questionSolutions", {})
            .get("solutions", [])
    )
    # Return just the code content of each solution
    return [s.get("content", "") for s in solutions if s.get("content")]


# ── step 3: scrape everything and save raw files ───────────────────────────────

def scrape_all(problem_list: list[dict]) -> None:
    """
    Main loop. For each problem:
      - Skip if raw file already exists
      - Fetch detail + solutions in 3 languages
      - Save full raw bundle to data/raw/{id}.json
      - On failure, save error to data/failed/{id}.json
    """
    languages = ["python3", "java", "cpp"]
    total     = len(problem_list)

    for i, problem in enumerate(problem_list, 1):
        problem_id = int(problem["questionFrontendId"])
        slug       = problem["titleSlug"]
        raw_path   = RAW_DIR / f"{problem_id}.json"
        fail_path  = FAILED_DIR / f"{problem_id}.json"

        # Skip if already scraped successfully
        if raw_path.exists():
            print(f"[{i}/{total}] #{problem_id} {slug} — already scraped, skipping.")
            continue

        print(f"[{i}/{total}] #{problem_id} {slug}...")

        # Fetch problem detail
        detail = fetch_problem_detail(slug)
        if not detail:
            print(f"  Failed to fetch detail.")
            save_json(fail_path, {
                "problem_id": problem_id,
                "slug": slug,
                "error": "detail fetch failed",
            })
            time.sleep(SCRAPE_DELAY)
            continue

        # Fetch solutions per language
        solutions_raw = {}
        for lang in languages:
            time.sleep(SCRAPE_DELAY)  # polite delay between each language request
            solutions_raw[lang] = fetch_solutions(slug, lang)
            print(f"  {lang}: {len(solutions_raw[lang])} solutions fetched")

        # Bundle everything into one raw object
        raw_bundle = {
            "problem_id":    problem_id,
            "list_data":     problem,   # from the problem list query
            "detail_data":   detail,    # from the detail query
            "solutions_raw": solutions_raw,
        }

        save_json(raw_path, raw_bundle)
        print(f"  Saved to data/raw/{problem_id}.json")
        time.sleep(SCRAPE_DELAY)

    print("\nScraping complete.")
    print(f"  Raw files:    {len(list(RAW_DIR.glob('*.json')))}")
    print(f"  Failed files: {len(list(FAILED_DIR.glob('*.json')))}")


# ── entry point ────────────────────────────────────────────────────────────────

def run():
    if not LEETCODE_SESSION:
        print("WARNING: LEETCODE_SESSION not set in .env.")
        print("Hints and some editorials may not be accessible.\n")
    problem_list = fetch_problem_list()
    scrape_all(problem_list)


if __name__ == "__main__":
    run()