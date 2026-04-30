"""
GET /api/insights — AI-powered insights via Groq
POST /api/insights/refresh — force regenerate
"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/insights")
async def get_insights(request: Request):
    """Return cached insights. If not yet generated, generate now."""
    from main import app_state
    if app_state.get("insights_cache") is None:
        from insights_builder import generate_insights
        app_state["insights_cache"] = await generate_insights(app_state["data"])
    return {"insights": app_state["insights_cache"], "cached": True}


@router.post("/insights/refresh")
async def refresh_insights(request: Request):
    """Force regenerate insights from Groq."""
    from main import app_state
    from insights_builder import generate_insights
    app_state["insights_cache"] = await generate_insights(app_state["data"])
    return {"insights": app_state["insights_cache"], "cached": False}
