import os
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from bson import ObjectId
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_chroma import Chroma
from backend.db import get_db, get_chroma
from backend.auth.dependecies import getcurrentuser
from backend.models.schemas import RecommendRequest, RecommendResponse, ProblemSummary

router = APIRouter()

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a LeetCode expert. Give a concise 1-2 sentence explanation."),
    ("human", (
        "User profile:\n"
        "- Solved problems: {solved}\n"
        "- Attempted problems: {attempted}\n"
        "- Preferred difficulty: {difficulty}\n\n"
        "Source problem: {source_title}\n"
        "Tags: {source_tags}\n\n"
        "Recommended problems:\n{recommended_list}\n\n"
        "In 1-2 sentences, explain why these problems are good next steps for this user "
        "based on their history and the source problem."
    )),
])


def _to_summary(doc: dict) -> ProblemSummary:
    tags = doc.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.splitlines() if t.strip()]
    return ProblemSummary(
        slug=doc["slug"],
        title=doc["title"],
        difficulty=doc["difficulty"],
        acceptance_rate=doc.get("acceptance_rate", 0.0),
        tags=tags,
        is_premium=doc.get("is_premium", False),
    )


def _call_ollama(
    source: dict,
    recommended: list[dict],
    user: dict,
) -> str:
    if not recommended:
        return "No similar problems found."

    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL_NAME", "qwen2.5-coder:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.4,
    )
    chain = _PROMPT | llm | StrOutputParser()

    recommended_list = "\n".join(
        f"- {p.get('title', p.get('slug', '?'))} "
        f"({p.get('difficulty', '?')}, "
        f"tags: {', '.join(p.get('tags', [])[:3])})"
        for p in recommended
    )

    source_tags = source.get("tags", [])
    if isinstance(source_tags, str):
        source_tags = [t.strip()
                       for t in source_tags.splitlines() if t.strip()]

    return chain.invoke({
        "solved":           ", ".join(user.get("solved_problems", [])[-10:]) or "none",
        "attempted":        ", ".join(user.get("attempted_problems", [])[-10:]) or "none",
        "difficulty":       user.get("preferred_difficulty") or "any",
        "source_title":     source.get("title", source.get("slug", "?")),
        "source_tags":      ", ".join(source_tags[:5]),
        "recommended_list": recommended_list,
    })


@router.post("", response_model=RecommendResponse)
async def recommend_problems(
    body:         RecommendRequest,
    current_user: dict = Depends(getcurrentuser),
    db:           Database = Depends(get_db),
    chroma:       Chroma = Depends(get_chroma),
):
    source = db["problems"].find_one({"slug": body.slug})
    if not source:
        raise HTTPException(
            status_code=404, detail=f"Problem '{body.slug}' not found")

    solved_set = set(current_user.get("solved_problems", []))
    attempted_set = set(current_user.get("attempted_problems", []))

    # 1. Get similar_problem_ids from MongoDB
    similar_ids = source.get("similar_problem_ids", [])
    if isinstance(similar_ids, str):
        similar_ids = [s.strip()
                       for s in similar_ids.splitlines() if s.strip()]

    # 2. Semantic search via Chroma for additional candidates
    chroma_docs = chroma.similarity_search(
        query=source.get("problem_statement", body.slug),
        k=10,
        filter={"hint_stage": 0},
    )
    chroma_slugs = [
        d.metadata.get("slug") for d in chroma_docs
        if d.metadata.get("slug") and d.metadata.get("slug") != body.slug
    ]

    # 3. Merge both candidate lists, deduplicate
    all_candidates = list(dict.fromkeys(similar_ids + chroma_slugs))

    # 4. Filter out already solved problems
    all_candidates = [s for s in all_candidates if s not in solved_set]

    # 5. Build MongoDB query — prefer not attempted either, fall back if needed
    not_attempted = [s for s in all_candidates if s not in attempted_set]
    final_candidates = not_attempted if len(
        not_attempted) >= body.top_k else all_candidates

    query: dict = {"slug": {"$in": final_candidates}}
    if body.difficulty:
        query["difficulty"] = body.difficulty
    elif current_user.get("preferred_difficulty"):
        query["difficulty"] = current_user["preferred_difficulty"]

    cursor = db["problems"].find(query, {"_id": 0}).limit(body.top_k)
    results = [_to_summary(p) for p in cursor]

    reason = _call_ollama(
        source=source,
        recommended=[r.model_dump() for r in results],
        user=current_user,
    )

    return RecommendResponse(
        based_on=body.slug,
        recommended=results,
        reason=reason,
    )
