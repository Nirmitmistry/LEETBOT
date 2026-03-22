from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import httpx
import os

from auth.dependecies import getcurrentuser

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
async def chat(req: ChatRequest, currentuser=Depends(getcurrentuser)):
    system_prompt = "You are a helpful coding assistant specializing in DSA and LeetCode problems."

    if req.problem_slug and req.problem_title:
        system_prompt += f"""The user is currently working on the problem: '{req.problem_title}'."""
    if req.problem_description:
        system_prompt += f"""Problem description:{req.problem_description}Help the user understand and solve this problem. Give hints, explain concepts, and review code — but don't give away the full solution directly unless explicitly asked."""

    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in req.messages:
        ollama_messages.append({"role": msg.role, "content": msg.content})

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL_NAME,
                "messages": ollama_messages,
                "stream": False,
            }
        )
        data = response.json()
        reply = data["message"]["content"]

    return {"reply": reply}
