import logging
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional

from backend.auth.dependencies import get_current_user
from backend.config import settings

from pymongo.database import Database
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.db import get_db, get_chroma

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ── Maximum characters per user message ──────────────────────────────────────
_MAX_MSG_LENGTH = 2000
_MAX_HISTORY_TURNS = 20  # keep last N user+assistant pairs to avoid token bloat

# ── Regex guard: block clearly off-topic requests ────────────────────────────
_OFF_TOPIC_PATTERNS = re.compile(
    r"\b("
    r"weather|forecast|stock(s| market)|bitcoin|crypto|recipe|cook(ing)?|"
    r"movie|netflix|sport(s)?|football|soccer|basketball|nba|nfl|"
    r"relationship|dating|love advice|horoscope|zodiac|astrology|"
    r"politics|election|president|government|news headline|"
    r"homework help(?! .*leetcode)|essay writing|write my essay"
    r")\b",
    re.IGNORECASE,
)

_ALLOWED_TOPICS_HINT = (
    "I'm focused on DSA and LeetCode topics. "
    "Please ask about algorithms, data structures, coding problems, "
    "time/space complexity, or your current problem."
)


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=_MAX_MSG_LENGTH)

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v.strip()


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    problem_slug: Optional[str] = Field(None, max_length=120)
    problem_title: Optional[str] = Field(None, max_length=200)
    problem_description: Optional[str] = Field(None, max_length=8000)

    @field_validator("messages")
    @classmethod
    def must_end_with_user(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v or v[-1].role != "user":
            raise ValueError("The last message must be from the user.")
        return v


class ChatResponse(BaseModel):
    reply: str


def _is_off_topic(text: str) -> bool:
    """Return True if the text is clearly unrelated to coding / DSA."""
    return bool(_OFF_TOPIC_PATTERNS.search(text))


def _build_system_prompt(
    req: ChatRequest,
    db: Database,
    chroma: Chroma | None,
) -> str:
    """Construct the system prompt, optionally enriched with problem context."""

    base = (
        "You are LeetBot, an expert coding assistant specialising in Data Structures, "
        "Algorithms, and LeetCode problems.\n\n"
        "## Rules you must follow\n"
        "1. Only answer questions related to programming, algorithms, data structures, "
        "   time/space complexity, code reviews, and LeetCode problems.\n"
        "2. If a question is unrelated to these topics, politely decline and redirect "
        "   the user back to coding.\n"
        "3. Format your answers using Markdown:\n"
        "   - Use ``` code blocks ``` for all code snippets.\n"
        "   - Use **bold** for key terms.\n"
        "   - Use numbered or bulleted lists where appropriate.\n"
        "   - Keep explanations concise but complete.\n"
        "4. Do NOT reveal the full solution unless the user has explicitly asked "
        "   for the solution after exhausting hints.\n"
        "5. Never fabricate problem statements or constraints.\n"
    )

    # ── Problem-specific context ─────────────────────────────────────────────
    if req.problem_slug and req.problem_title:
        problem = db["problems"].find_one({"slug": req.problem_slug})
        hint_1 = problem.get("hints", {}).get("stage_1") if problem else None

        base += (
            f"\n## Current Problem\n"
            f"The user is working on **{req.problem_title}** (slug: `{req.problem_slug}`).\n"
        )
        if req.problem_description:
            base += (
                f"\n### Problem Statement\n{req.problem_description}\n\n"
                "Help the user understand and solve this problem. Give hints and explain "
                "concepts — but do **not** give away the full solution directly "
                "unless explicitly asked.\n"
            )
        if hint_1:
            base += f"\n### Hint 1 (reveal only if the user asks for a hint)\n{hint_1}\n"

    # ── RAG fallback: try to detect which problem the user is asking about ───
    else:
        last_user_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), None
        )
        if last_user_msg and chroma is not None:
            try:
                docs = chroma.similarity_search(query=last_user_msg, k=1)
            except Exception as exc:
                logger.warning("Chroma similarity search failed: %s", exc)
                docs = []

            if docs:
                detected_slug = docs[0].metadata.get("slug")
                problem = db["problems"].find_one({"slug": detected_slug})
                if problem:
                    hint_1 = problem.get("hints", {}).get("stage_1")
                    base += (
                        f"\n## Detected Problem Context\n"
                        f"Based on the user's message, they may be referring to "
                        f"**{problem.get('title')}**. "
                        f"If relevant, you can confirm this with the user.\n"
                    )
                    if hint_1:
                        base += (
                            f"\n### Hint 1 (reveal only if the user asks for a hint)\n"
                            f"{hint_1}\n"
                        )

    return base


@router.post("", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    chroma: Chroma = Depends(get_chroma),
):
    # ── Off-topic guard ───────────────────────────────────────────────────────
    last_user_msg = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    if _is_off_topic(last_user_msg):
        logger.info(
            "Off-topic query from user %s rejected", current_user.get("user_id")
        )
        return ChatResponse(reply=_ALLOWED_TOPICS_HINT)

    # ── Build system prompt ───────────────────────────────────────────────────
    # chroma dependency raises RuntimeError if unavailable; catch and degrade
    try:
        system_prompt = _build_system_prompt(req, db, chroma)
    except RuntimeError:
        system_prompt = _build_system_prompt(req, db, None)

    # ── Trim history to avoid token bloat ────────────────────────────────────
    # Keep only the tail of the conversation (most recent turns)
    trimmed = req.messages[-(_MAX_HISTORY_TURNS * 2):]

    # ── Build LangChain message list ──────────────────────────────────────────
    lc_messages: list = [SystemMessage(content=system_prompt)]
    for msg in trimmed:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))

    # ── Invoke Gemini ─────────────────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.4,
    )

    try:
        response = llm.invoke(lc_messages)
        reply = response.content
        if not reply or not reply.strip():
            raise ValueError("Empty response from Gemini")
    except ValueError as exc:
        logger.error("Empty Gemini response: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The AI returned an empty response. Please try rephrasing your question.",
        )
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The AI service is temporarily unavailable. Please try again shortly.",
        )

    return ChatResponse(reply=reply)
