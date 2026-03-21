

from fastapi import APIRouter
from backend.models.schemas import ComplexityRequest, ComplexityResponse

router = APIRouter()

SUPPORTED_LANGUAGES = {"python", "java", "cpp"}


@router.post("", response_model=ComplexityResponse)
async def analyze_complexity(body: ComplexityRequest):
    lang = body.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "C++"
    return ComplexityResponse(
        time_complexity="O(?)",
        space_complexity="O(?)",
        explanation=(
            "[Phase 6 stub] Claude integration coming in Phase 7. "
            f"Received {len(body.code)} chars of {lang} code."
        ),
        language=lang,
    )
