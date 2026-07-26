from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from backend.auth.dependencies import get_current_user
from backend.config import settings

from pymongo.database import Database
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.db import get_db, get_chroma

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    problem_slug: Optional[str] = None
    problem_title: Optional[str] = None
    problem_description: Optional[str] = None


@router.post("")
def chat(
    req: ChatRequest,
    currentuser=Depends(get_current_user),
    db: Database = Depends(get_db),
    chroma: Chroma = Depends(get_chroma),
):
    system_prompt = "You are a helpful coding assistant specializing in DSA and LeetCode problems."

    if req.problem_slug and req.problem_title:
        problem = db["problems"].find_one({"slug": req.problem_slug})
        hint_1 = problem.get("hints", {}).get("stage_1") if problem else None

        system_prompt += f"\nThe user is currently working on the problem: '{req.problem_title}'."
        if req.problem_description:
            system_prompt += (
                f"\nProblem description: {req.problem_description}"
                "\nHelp the user understand and solve this problem. Give hints, explain concepts, "
                "and review code — but don't give away the full solution directly unless explicitly asked."
            )
        if hint_1:
            system_prompt += f"\nIf the user asks for a hint, you can provide them with Hint 1: {hint_1}"
    else:
        last_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), None
        )
        if last_msg:
            try:
                docs = chroma.similarity_search(query=last_msg, k=1)
            except Exception:
                docs = []
            if docs:
                detected_slug = docs[0].metadata.get("slug")
                problem = db["problems"].find_one({"slug": detected_slug})
                if problem:
                    hint_1 = problem.get("hints", {}).get("stage_1")
                    if hint_1:
                        system_prompt += (
                            f"\nBased on the user's message, they might be referring to the problem "
                            f"'{problem.get('title')}'. Ask them if they are working on it, and if so, "
                            f"you can provide them with Hint 1: {hint_1} if they need a hint."
                        )

    # Gemini LLM for chat inference
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.7,
    )
    
    # Convert messages to LangChain format
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in req.messages:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    
    try:
        response = llm.invoke(messages)
        reply = response.content
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Gemini API error: {str(e)}"
        )

    return {"reply": reply}
