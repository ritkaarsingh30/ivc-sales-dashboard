from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
import os
import json
import math


class NaNSafeJSONResponse(JSONResponse):
    """Global JSON response that converts NaN/Inf floats → null recursively."""
    def render(self, content) -> bytes:
        def _fix(obj):
            if isinstance(obj, dict):
                return {k: _fix(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_fix(v) for v in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj
        return json.dumps(_fix(content), ensure_ascii=False).encode("utf-8")

sys.path.insert(0, os.path.dirname(__file__))

from storage import get_storage
from name_map import build_doctor_index

app_state = {}


def _build_doctor_index_from_data(data: dict):
    all_doctors = []
    for month_data in data.values():
        visits = month_data.get("visits")
        if visits is not None and hasattr(visits, "empty") and not visits.empty:
            all_doctors.extend(visits["Doctor"].dropna().tolist())
    build_doctor_index(all_doctors)


def _empty_month_shell(month_keys: list[str]) -> dict:
    """Minimal data dict used when everything is served from Redis cache."""
    return {k: {"sales": {}, "projection": {}, "expense": {}, "monthly": {}, "copy": {}, "tour": {}, "visits": {}} for k in month_keys}


def _has_shell_data(data: dict) -> bool:
    """Return True if app_state data has no real loaded content.

    Detects both the explicit empty-shell case (sales={}) and the zeroed-data case
    that the old startup code produced when load_all_from_sheets got all cache HITs
    (sales={"current": empty_df, "prev": empty_df}).
    """
    for month_data in data.values():
        if not isinstance(month_data, dict):
            continue
        sales = month_data.get("sales")
        if not isinstance(sales, dict):
            continue
        if not sales:
            return True  # empty dict — explicit shell
        current = sales.get("current")
        if hasattr(current, "empty") and current.empty:
            return True  # empty DataFrame — zeroed from cache-hit startup
    return False


async def eager_recompute(endpoints: list[str]):
    """Call router functions to eagerly populate the Redis API cache."""
    from routers.overview import get_overview
    from routers.months import get_month
    from routers.products import get_products
    from routers.delegates import get_delegates
    from routers.expenses import get_expenses
    from routers.insights import get_insights
    from routers.activities import get_activities
    from fastapi import Request

    scope = {"type": "http", "method": "GET"}
    dummy_req = Request(scope)

    for ep in endpoints:
        if ep == "overview":      await get_overview()
        elif ep == "products":    await get_products()
        elif ep == "delegates":   await get_delegates()
        elif ep == "expenses":    await get_expenses()
        elif ep == "activities":  await get_activities()
        elif ep == "insights":    await get_insights(dummy_req)
        elif ep.startswith("months:"):
            month_key = ep.split(":", 1)[1]
            await get_month(month_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = get_storage()
    backend = os.getenv("STORAGE_BACKEND", "local")

    if backend == "sheets":
        from sheets_loader import init_months_config, load_all_from_sheets, MONTHS
        from cache.redis_client import health_check, get_api_cache, build_sheet_dependencies

        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        if folder_id:
            print(f"[startup] Discovering spreadsheets in Drive folder {folder_id!r}…")
            storage.discover(folder_id)
        else:
            print("[startup] GOOGLE_DRIVE_FOLDER_ID not set — sheet IDs must be in .env")

        # Determine active months (cached in Redis to avoid extra API calls on restarts)
        await init_months_config(storage)

        # Re-import MONTHS after it was populated by init_months_config
        import sheets_loader as _sl
        month_keys = [m["key"] for m in _sl.MONTHS]
        all_endpoints = (
            ["overview", "products", "delegates", "expenses", "activities", "insights"]
            + [f"months:{k}" for k in month_keys]
        )

        redis_ok = await health_check()

        if redis_ok:
            import asyncio as _asyncio
            cache_results = await _asyncio.gather(*[get_api_cache(k) for k in all_endpoints])
            all_cached = all(bool(r) for r in cache_results)
        else:
            all_cached = False
            cache_results = [None] * len(all_endpoints)

        print("[startup] Loading data from Google Drive…")
        existing = app_state.get("data", {})
        data = await load_all_from_sheets(storage, existing_data=existing)
        app_state["data"] = data
        _build_doctor_index_from_data(data)

        if redis_ok:
            # Only recompute endpoints that are missing from the API cache.
            stale_endpoints = [ep for ep, cached in zip(all_endpoints, cache_results) if not cached]
            if stale_endpoints:
                await eager_recompute(stale_endpoints)
            else:
                print("[startup] All API endpoints already cached — skipping recompute.")

        # Store dynamic dependency map for the refresh endpoint
        app_state["sheet_dependencies"] = build_sheet_dependencies(month_keys)

    else:
        # Local mode
        from loaders import load_all_data
        from cache.redis_client import health_check, build_sheet_dependencies

        print("Loading all IVC data files locally…")
        data = load_all_data(storage)
        app_state["data"] = data
        _build_doctor_index_from_data(data)

        # For local mode, derive month keys from what was loaded
        month_keys = list(data.keys())
        app_state["sheet_dependencies"] = build_sheet_dependencies(month_keys)

        redis_ok = await health_check()
        all_endpoints = (
            ["overview", "products", "delegates", "expenses", "activities", "insights"]
            + [f"months:{k}" for k in month_keys]
        )
        if redis_ok:
            await eager_recompute(all_endpoints)

    app_state["data"] = data
    app_state["storage"] = storage
    app_state["insights_cache"] = None
    print(f"Backend ready. Loaded months: {list(data.keys())}")
    yield
    app_state.clear()


app = FastAPI(
    title="IVC Dashboard API",
    lifespan=lifespan,
    default_response_class=NaNSafeJSONResponse,
)

_extra_origins = [
    u.strip() for u in os.getenv("FRONTEND_URL", "").split(",") if u.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://ivc-sales-dashboard-production.up.railway.app",
        *_extra_origins,
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import overview, months, products, delegates, expenses, insights, activities

app.include_router(overview.router, prefix="/api")
app.include_router(months.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(delegates.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(activities.router, prefix="/api")


@app.get("/api/health")
def health():
    data = app_state.get("data", {})
    return {"status": "ok", "months_loaded": list(data.keys())}


@app.get("/api/months")
def available_months():
    """Return the list of month keys currently loaded (e.g. ['jan', 'feb', 'mar', 'apr'])."""
    return {"months": list(app_state.get("data", {}).keys())}


@app.post("/api/data/refresh")
async def refresh_data():
    """Re-check Google Drive for changes and refresh only what changed."""
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend != "sheets":
        return {"status": "skipped", "reason": "Not using Google Sheets backend"}

    storage = app_state.get("storage")
    if storage is None:
        return {"status": "error", "reason": "Storage not initialised"}

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if folder_id:
        storage.discover(folder_id)

    from sheets_loader import refresh_changed_from_sheets
    from cache.redis_client import invalidate_api_keys, build_sheet_dependencies, flush_all_api_cache

    existing_data = app_state.get("data", {})

    # If server started from Redis cache, app_state["data"] is an empty shell.
    # Eager-recomputing endpoints against shell data would overwrite good Redis caches
    # with half-empty results. Force a full fresh load from Drive instead.
    if _has_shell_data(existing_data):
        from sheets_loader import load_all_from_sheets
        from cache.redis_client import redis_client as _rc

        print("[refresh] Detected empty shell — performing full reload from Drive")

        # Clear drive_modified metadata so load_all_from_sheets re-fetches everything
        drive_keys = await _rc.keys("sheets:*:drive_modified")
        if drive_keys:
            await _rc.delete(*drive_keys)

        await flush_all_api_cache()

        existing_data = await load_all_from_sheets(storage, existing_data={})
        app_state["data"] = existing_data
        app_state["insights_cache"] = None
        _build_doctor_index_from_data(existing_data)

        import sheets_loader as _sl
        month_keys = [m["key"] for m in _sl.MONTHS]
        sheet_deps = build_sheet_dependencies(month_keys)
        app_state["sheet_dependencies"] = sheet_deps

        all_endpoints = (
            ["overview", "products", "delegates", "expenses", "activities", "insights"]
            + [f"months:{k}" for k in month_keys]
        )
        await eager_recompute(all_endpoints)

        return {"status": "ok", "months_loaded": month_keys, "changed_sheets": ["full_reload"]}

    updated_data, changed_keys = await refresh_changed_from_sheets(storage, existing_data)
    app_state["data"] = updated_data
    _build_doctor_index_from_data(updated_data)

    # Rebuild dependency map with potentially new months
    import sheets_loader as _sl
    month_keys = [m["key"] for m in _sl.MONTHS]
    sheet_deps = build_sheet_dependencies(month_keys)
    app_state["sheet_dependencies"] = sheet_deps

    if changed_keys:
        endpoints_to_invalidate = set()
        for ck in changed_keys:
            endpoints_to_invalidate.update(sheet_deps.get(ck, []))
        endpoints_to_invalidate.add("insights")
        app_state["insights_cache"] = None

        endpoints_list = list(endpoints_to_invalidate)
        await invalidate_api_keys(endpoints_list)
        await eager_recompute(endpoints_list)

    return {
        "status": "ok",
        "months_loaded": month_keys,
        "changed_sheets": changed_keys,
    }


@app.get("/api/cache/redisStatus")
async def get_redis_status():
    from cache.redis_client import health_check, redis_client
    is_ok = await health_check()
    if not is_ok:
        return {"redis_available": False}

    keys = await redis_client.keys("api:*")
    return {
        "redis_available": True,
        "cached_endpoints": len(keys),
        "keys": keys,
    }
