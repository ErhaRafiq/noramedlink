from fastapi import APIRouter

from schemas import SummarizeRequest, SummaryResponse
from services.nlp_service import summarize_with_optional_llm


router = APIRouter(prefix="/nlp", tags=["nlp"])


@router.post("/summarize", response_model=SummaryResponse)
async def summarize(payload: SummarizeRequest):
    summary, method, warning = await summarize_with_optional_llm(payload.text, payload.category)
    return SummaryResponse(summary=summary, method=method, warning=warning)
