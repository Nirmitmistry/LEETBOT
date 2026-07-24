import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from backend.config import settings  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
FAILED_DIR = BASE_DIR / "data" / "failed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Referer":      "https://leetcode.com",
    "User-Agent":   "Mozilla/5.0 (compatible; leetbot-scraper/1.0)",
    "Cookie":       f"LEETCODE_SESSION={settings.LEETCODE_SESSION}",
}

# ── GraphQL queries ────────────────────────────────────────────────────────────

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


# ── helpers ────────────────────────────────────────────────────────────────────

def graphql_post(query: str, variables: dict) -> dict | None:
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
    print("Fetching problem list from LeetCode...")
    all_problems = []
    page_size = 100
    skip = 0

    while True:
        resp = graphql_post(PROBLEM_LIST_QUERY, {"skip": skip, "limit": page_size})
        if not resp:
            print(f"  Failed to fetch page at skip={skip}. Stopping list fetch.")
            break

        data = resp.get("data", {}).get("problemsetQuestionList", {})
        questions = data.get("questions", [])
        total = data.get("total", 0)

        free = [q for q in questions if not q.get("isPaidOnly", False)]
        all_problems.extend(free)

        print(
            f"  Fetched {skip + len(questions)}/{total} problems "
            f"({len(all_problems)} free so far)..."
        )

        skip += page_size
        if skip >= total:
            break

        time.sleep(settings.SCRAPE_DELAY)

    print(f"Done. Found {len(all_problems)} free problems.")
    return all_problems


# ── step 2: fetch detail for one problem ──────────────────────────────────────

def fetch_problem_detail(slug: str) -> dict | None:
    resp = graphql_post(PROBLEM_DETAIL_QUERY, {"titleSlug": slug})
    if not resp:
        return None
    return resp.get("data", {}).get("question")


# ── step 3: scrape everything and save raw files ───────────────────────────────

def scrape_all(problem_list: list[dict]) -> None:
    total = len(problem_list)

    for i, problem in enumerate(problem_list, 1):
        problem_id = int(problem["questionFrontendId"])
        slug = problem["titleSlug"]
        raw_path = RAW_DIR / f"{problem_id}.json"
        fail_path = FAILED_DIR / f"{problem_id}.json"

        if raw_path.exists():
            print(f"[{i}/{total}] #{problem_id} {slug} — already scraped, skipping.")
            continue

        print(f"[{i}/{total}] #{problem_id} {slug}...")

        detail = fetch_problem_detail(slug)
        if not detail:
            print(f"  Failed to fetch detail.")
            save_json(fail_path, {
                "problem_id": problem_id,
                "slug": slug,
                "error": "detail fetch failed",
            })
            time.sleep(settings.SCRAPE_DELAY)
            continue

        raw_bundle = {
            "problem_id":    problem_id,
            "list_data":     problem,
            "detail_data":   detail,
            "solutions_raw": {"python3": [], "java": [], "cpp": []},
        }

        save_json(raw_path, raw_bundle)
        print(f"  Saved → data/raw/{problem_id}.json")
        time.sleep(settings.SCRAPE_DELAY)

    print("\nScraping complete.")
    print(f"  Raw files:    {len(list(RAW_DIR.glob('*.json')))}")
    print(f"  Failed files: {len(list(FAILED_DIR.glob('*.json')))}")


# ── entry point ────────────────────────────────────────────────────────────────

def run():
    if not settings.LEETCODE_SESSION:
        print("WARNING: LEETCODE_SESSION not set in .env.")
        print("Hints and some content may not be accessible.\n")
    problem_list = fetch_problem_list()
    scrape_all(problem_list)


if __name__ == "__main__":
    run()
