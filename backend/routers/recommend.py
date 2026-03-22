import os
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.db import get_db
from backend.models.schemas import RecommendRequest, RecommendResponse, ProblemSummary

router = APIRouter()

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a LeetCode expert. Explain problem similarities concisely in 1-2 sentences."),
    ("human", (
        "Source problem: {source_title}\n"
        "Tags: {source_tags}\n\n"
        "Recommended problems:\n{recommended_list}\n\n"
        "In 1-2 sentences, explain what these problems have in common algorithmically."
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


def _call_ollama(source: dict, recommended: list[dict]) -> str:
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

    tags = source.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.splitlines() if t.strip()]

    return chain.invoke({
        "source_title":     source.get("title", source.get("slug", "?")),
        "source_tags":      ", ".join(tags[:5]),
        "recommended_list": recommended_list,
    })


@router.post("", response_model=RecommendResponse)
async def recommend_problems(body: RecommendRequest, db: Database = Depends(get_db)):
    source = db["problems"].find_one({"slug": body.slug})
    if not source:
        raise HTTPException(
            status_code=404, detail=f"Problem '{body.slug}' not found")

    similar_ids = source.get("similar_problem_ids", [])
    if isinstance(similar_ids, str):
        similar_ids = [s.strip()
                       for s in similar_ids.splitlines() if s.strip()]

    query: dict = {"slug": {"$in": similar_ids}}
    if body.difficulty:
        query["difficulty"] = body.difficulty

    cursor = db["problems"].find(query, {"_id": 0}).limit(body.top_k)
    results = [_to_summary(p) for p in cursor]

    reason = _call_ollama(
        source=source,
        recommended=[r.model_dump() for r in results],
    )

    return RecommendResponse(
        based_on=body.slug,
        recommended=results,
        reason=reason,
    )
