from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import httpx
import os

from backend.auth.dependecies import getcurrentuser

from pymongo.database import Database
from langchain_chroma import Chroma
from backend.db import get_db, get_chroma

router = APIRouter(prefix="/chat", tags=["chat"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "qwen2.5-coder:7b")


class ChatMessage(BaseModel):
    role: str 
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    problem_slug: Optional[str] = None
    problem_title: Optional[str] = None
    problem_description: Optional[str] = None


@router.post("")
async def chat(
    req: ChatRequest,
    currentuser=Depends(getcurrentuser),
    db: Database = Depends(get_db),
    chroma: Chroma = Depends(get_chroma)
):
    system_prompt = "You are a helpful coding assistant specializing in DSA and LeetCode problems."

    if req.problem_slug and req.problem_title:
        problem = db["problems"].find_one({"slug": req.problem_slug})
        hint_1 = problem.get("hints", {}).get("stage_1") if problem else None
        
        system_prompt += f"\nThe user is currently working on the problem: '{req.problem_title}'."
        if req.problem_description:
            system_prompt += f"\nProblem description: {req.problem_description}\nHelp the user understand and solve this problem. Give hints, explain concepts, and review code — but don't give away the full solution directly unless explicitly asked."
        if hint_1:
            system_prompt += f"\nIf the user asks for a hint, you can provide them with Hint 1: {hint_1}"
    else:
        last_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), None)
        if last_msg:
            docs = chroma.similarity_search(query=last_msg, k=1)
            if docs:
                detected_slug = docs[0].metadata.get("slug")
                problem = db["problems"].find_one({"slug": detected_slug})
                if problem:
                    hint_1 = problem.get("hints", {}).get("stage_1")
                    if hint_1:
                        system_prompt += f"\nBased on the user's message, they might be referring to the problem '{problem.get('title')}'. Ask them if they are working on it, and if so, you can provide them with Hint 1: {hint_1} if they need a hint."

    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in req.messages:
        ollama_messages.append({"role": msg.role, "content": msg.content})

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL_NAME,
                "messages": ollama_messages,
                "stream": False,
            }
        )
        data = response.json()
        if "message" not in data:
            error_msg = data.get("error", f"Unexpected Ollama response: {str(data)[:200]}")
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail=f"Ollama error: {error_msg}")
        reply = data["message"]["content"]

    return {"reply": reply}
