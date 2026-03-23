import os
from fastapi import APIRouter, HTTPException, Depends
from pymongo.database import Database
from bson import ObjectId
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.db import get_db
from backend.models.schemas import HintRequest, HintResponse
from backend.auth.dependecies import getcurrentuser
router = APIRouter()
MAX_STAGE = 6

_STAGE_FIELD = {
    1: "hints.stage_1",
    2: "hints.stage_2",
    3: "hints.stage_3",
    4: "hints.stage_4",
    5: "hints.stage_5",
    6: "solutions.python",
}

_STAGE_INSTRUCTION = {
    1: "Give a very subtle first hint — just nudge toward the right pattern. No code, no approach.",
    2: "Give a clearer hint about the algorithmic approach (e.g. sliding window, two pointers, DP). No code.",
    3: "Explain the algorithm step by step in plain English. Mention key data structures. No code.",
    4: "Give a detailed walkthrough including edge cases. Pseudocode is fine.",
    5: "Give a final detailed walkthrough of the approach with edge cases. No code.",
    6: "Provide a clean, well-commented C++ solution with time and space complexity analysis and a clear editorial explanation.",
}

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an expert LeetCode tutor. Be concise, educational, and follow the instruction exactly."),
    ("human", (
        "Problem: {title}\n\n"
        "Statement:\n{statement}\n\n"
        "Constraints:\n{constraints}\n\n"
        "Examples:\n{examples}\n\n"
        "---\n"
        "The student is at hint stage {stage} of 5.\n"
        "{instruction}\n"
        "Respond directly. No preamble."
    )),
])


def _extract_field(doc: dict, field_path: str) -> str | None:
    value = doc
    for key in field_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _call_ollama(problem: dict, stage: int) -> str:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL_NAME", "qwen2.5-coder:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.3,
    )
    chain = _PROMPT | llm | StrOutputParser()

    constraints = problem.get("constraints", [])
    if isinstance(constraints, str):
        constraints = [c.strip()
                       for c in constraints.splitlines() if c.strip()]
    constraints_text = "\n".join(
        f"- {c}" for c in constraints) or "None provided"

    examples = problem.get("examples", [])
    if isinstance(examples, list):
        examples_text = "\n".join(
            f"Input: {e.get('input', '')}  Output: {e.get('output', '')}"
            for e in examples[:2]
        )
    else:
        examples_text = str(examples) if examples else "None provided"

    return chain.invoke({
        "title":       problem.get("title", "Unknown"),
        "statement":   problem.get("problem_statement", ""),
        "constraints": constraints_text,
        "examples":    examples_text,
        "stage":       stage,
        "instruction": _STAGE_INSTRUCTION[stage],
    })


@router.post("/{slug}", response_model=HintResponse)
async def get_next_hint(
    slug: str,
    body: HintRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(getcurrentuser)
):
    try:
        oid = ObjectId(body.session_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid session_id format")

    session = db["hint_sessions"].find_one({
        "_id": oid,
        "slug": slug,
        "user_id": current_user["user_id"]
    })

    if not session:
        raise HTTPException(
            status_code=404, detail=f"Session '{body.session_id}' not found for '{slug}' or unauthorized access.")

    current_stage = session.get("current_stage", 0)
    if current_stage >= MAX_STAGE:
        raise HTTPException(
            status_code=400, detail="All hint stages already unlocked.")

    next_stage = current_stage + 1
    problem = db["problems"].find_one({"slug": slug})
    if not problem:
        raise HTTPException(
            status_code=404, detail=f"Problem '{slug}' not found")

    hint_text = _extract_field(problem, _STAGE_FIELD[next_stage])
    source = "db"

    if not hint_text:
        try:
            hint_text = _call_ollama(problem, next_stage)
            source = "llm"
            db["problems"].update_one(
                {"slug": slug},
                {"$set": {_STAGE_FIELD[next_stage]: hint_text}},
            )
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"LLM fallback failed: {e}")

    db["hint_sessions"].update_one(
        {"_id": oid}, {"$set": {"current_stage": next_stage}})

    return HintResponse(
        slug=slug,
        stage=next_stage,
        hint=hint_text,
        is_final=next_stage == MAX_STAGE,
        next_stage=next_stage + 1 if next_stage < MAX_STAGE else None,
        source=source,
    )
