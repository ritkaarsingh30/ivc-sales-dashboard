"""
GET /api/insights — AI-powered insights via Groq
POST /api/insights/refresh — force regenerate
"""
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()
_insights_lock = asyncio.Lock()


async def _fetch_source_data() -> tuple[dict, dict, dict]:
    """Fetch pre-computed overview, delegates, and expenses data (from cache or recompute)."""
    from routers.overview import get_overview
    from routers.delegates import get_delegates
    from routers.expenses import get_expenses

    overview = await get_api_cache("overview") or await get_overview()
    delegates = await get_api_cache("delegates") or await get_delegates()
    expenses = await get_api_cache("expenses") or await get_expenses()
    return overview, delegates, expenses


@router.get("/insights")
async def get_insights(request: Request):
    """Return cached insights. If not yet generated, generate now."""
    cached = await get_api_cache("insights")
    if cached:
        return cached

    from main import app_state
    if app_state.get("insights_cache") is None:
        from insights_builder import generate_insights
        overview, delegates, expenses = await _fetch_source_data()
        app_state["insights_cache"] = await generate_insights(overview, delegates, expenses)

    result = {"insights": app_state["insights_cache"], "cached": True}
    await set_api_cache("insights", result)
    return result


@router.post("/insights/refresh")
async def refresh_insights(request: Request):
    """Force regenerate insights from Groq."""
    if _insights_lock.locked():
        return JSONResponse(
            status_code=409,
            content={"status": "busy", "reason": "Insights generation already in progress. Please wait."},
        )

    async with _insights_lock:
        from main import app_state
        from insights_builder import generate_insights
        overview, delegates, expenses = await _fetch_source_data()
        app_state["insights_cache"] = await generate_insights(overview, delegates, expenses)
        result = {"insights": app_state["insights_cache"], "cached": False}
        await set_api_cache("insights", result)
        return result
