import os
from openai import OpenAI

from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from bson import ObjectId

from backend.db import get_db
from backend.models.schemas import HintRequest, HintResponse

router = APIRouter()

MAX_STAGE = 5

_STAGE_FIELD = {
    1: "hints.stage_1",
    2: "hints.stage_2",
    3: "hints.stage_3",
    4: "hints.stage_4",
    5: "solutions.python",   
}

_STAGE_PROMPT = {
    1: "Give a very subtle first hint — just nudge the user toward the right problem-solving pattern. Do NOT reveal the approach or any code.",
    2: "Give a clearer hint about the algorithmic approach (e.g. sliding window, two pointers, DP). Still no code.",
    3: "Explain the core algorithm step by step in plain English. Mention key data structures. No code yet.",
    4: "Give a detailed walkthrough of the solution logic including edge cases. Pseudocode is fine.",
    5: "Provide a clean, well-commented Python solution with time and space complexity analysis.",
}


def _extract_field(doc: dict, field_path: str) -> str | None:
    value = doc
    for key in field_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _call_openai(problem: dict, stage: int) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    context_parts = [f"Problem: {problem.get('title', 'Unknown')}"]

    if stmt := problem.get("problem_statement"):
        context_parts.append(f"Statement:\n{stmt}")

    if constraints := problem.get("constraints"):
        context_parts.append("Constraints:\n" +
                             "\n".join(f"- {c}" for c in constraints))

    if examples := problem.get("examples"):
        ex_text = "\n".join(
            f"Input: {e.get('input', '')}  Output: {e.get('output', '')}"
            for e in examples[:2]
        )
        context_parts.append(f"Examples:\n{ex_text}")

    context = "\n\n".join(context_parts)
    instruction = _STAGE_PROMPT[stage]

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "You are a LeetCode tutor. Be concise and educational.",
            },
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"---\n"
                    f"The student is at hint stage {stage} of 5.\n"
                    f"{instruction}"
                ),
            },
        ],
    )

    return response.choices[0].message.content


@router.post("/{slug}", response_model=HintResponse)
async def get_next_hint(
    slug: str,
    body: HintRequest,
    db:   Database = Depends(get_db),
):
    # 1. Fetch and validate session
    try:
        oid = ObjectId(body.session_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({"_id": oid, "slug": slug})
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{body.session_id}' not found for problem '{slug}'",
        )

    current_stage = session.get("current_stage", 0)

    if current_stage >= MAX_STAGE:
        raise HTTPException(
            status_code=400,
            detail="All hint stages already unlocked. No further hints available.",
        )

    next_stage = current_stage + 1

    # 2. Fetch problem from MongoDB
    problem = db["problems"].find_one({"slug": slug})
    if not problem:
        raise HTTPException(
            status_code=404, detail=f"Problem '{slug}' not found")

    # 3. Try MongoDB first, fall back to Claude
    field_path = _STAGE_FIELD[next_stage]
    hint_text = _extract_field(problem, field_path)
    source = "db"

    if not hint_text:
        # MongoDB doesn't have this content — ask Claude
        try:
            hint_text = _call_openai(problem, next_stage)
            source = "llm"
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"MongoDB content missing and fallback failed: {e}",
            )

    # 4. Persist updated stage
    db["hint_sessions"].update_one(
        {"_id": oid},
        {"$set": {"current_stage": next_stage}},
    )

    return HintResponse(
        slug=slug,
        stage=next_stage,
        hint=hint_text,
        is_final=next_stage == MAX_STAGE,
        next_stage=next_stage + 1 if next_stage < MAX_STAGE else None,
        source=source,
    )
