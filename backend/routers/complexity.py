import os
import json
import re
from fastapi import APIRouter
from backend.models.schemas import ComplexityRequest, ComplexityResponse
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

router = APIRouter()
SUPPORTED_LANGUAGES = {"python", "java", "cpp"}

prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an algorithm expert. Analyze the time and space complexity of the given code.\n"
        "You MUST respond with valid JSON only — no explanation outside the JSON.\n"
        'Format: {{"time": "O(...)", "space": "O(...)", "explanation": "brief explanation here"}}'
    )),
    ("human", (
        "Language: {language}\n\n"
        "Code:\n```{language}\n{code}\n```\n\n"
        "Respond with JSON only."
    )),
])


@router.post("", response_model=ComplexityResponse)
async def analyze_complexity(body: ComplexityRequest):
    lang = body.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "C++"
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL_NAME"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0)
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({"code": body.code, "language": lang})

    cleaned = re.sub(r"```json\s*|```\s*", "", raw,
                     flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(cleaned)
        return ComplexityResponse(
            time_complexity=parsed.get("time", "Unknown"),
            space_complexity=parsed.get("space", "Unknown"),
            explanation=parsed.get("explanation", raw),
            language=lang,
        )
    except json.JSONDecodeError:
        return ComplexityResponse(
            time_complexity="Unknown",
            space_complexity="Unknown",
            explanation=raw,
            language=lang,
        )
