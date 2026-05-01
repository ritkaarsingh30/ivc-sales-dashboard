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

# Add backend dir to path so imports work
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


async def eager_recompute(endpoints: list[str]):
    """Call router functions directly to eagerly populate cache."""
    from routers.overview import get_overview
    from routers.months import get_month
    from routers.products import get_products
    from routers.delegates import get_delegates
    from routers.expenses import get_expenses
    from routers.insights import get_insights
    from fastapi import Request
    
    scope = {"type": "http", "method": "GET"}
    dummy_req = Request(scope)

    if "overview" in endpoints: await get_overview()
    if "months:jan" in endpoints: await get_month("jan")
    if "months:feb" in endpoints: await get_month("feb")
    if "months:mar" in endpoints: await get_month("mar")
    if "products" in endpoints: await get_products()
    if "delegates" in endpoints: await get_delegates()
    if "expenses" in endpoints: await get_expenses()
    if "insights" in endpoints: await get_insights(dummy_req)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load all data once
    storage = get_storage()
    backend = os.getenv("STORAGE_BACKEND", "local")

    if backend == "sheets":
        from sheets_loader import load_all_from_sheets
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        if folder_id:
            print(f"[startup] Auto-discovering spreadsheets in Drive folder {folder_id!r}…")
            storage.discover(folder_id)
        else:
            print("[startup] GOOGLE_DRIVE_FOLDER_ID not set — sheet IDs must be in .env")
            
        from cache.redis_client import health_check, get_api_cache
        redis_ok = await health_check()
        
        all_present = False
        if redis_ok:
            all_present = True
            for k in ["overview", "months:jan", "months:feb", "months:mar", "products", "delegates", "expenses", "insights"]:
                if not await get_api_cache(k):
                    all_present = False
                    break
                    
        if all_present:
            print("[startup] All data loaded from Redis cache")
            data = {
                "jan": {"sales": {}, "projection": {}, "expense": {}, "monthly": {}, "copy": {}, "tour": {}, "visits": {}},
                "feb": {"sales": {}, "projection": {}, "expense": {}, "monthly": {}, "copy": {}, "tour": {}, "visits": {}},
                "mar": {"sales": {}, "projection": {}, "expense": {}, "monthly": {}, "copy": {}, "tour": {}, "visits": {}},
            }
        else:
            from loaders import load_all_data
            from storage.local import LocalStorage
            print("Loading baseline IVC data from local files to save Google API quotas…")
            data = load_all_data(LocalStorage())
            app_state["data"] = data
            _build_doctor_index_from_data(data)
            
            # Eagerly populate cache
            if redis_ok:
                await eager_recompute(["overview", "months:jan", "months:feb", "months:mar", "products", "delegates", "expenses", "insights"])
                
                # Sync Google Drive metadata into Redis so refresh_changed_from_sheets works seamlessly
                import asyncio
                from datetime import datetime
                from sheets_loader import MONTHS
                from cache.redis_client import set_sheet_metadata
                
                print("Syncing Google Drive metadata to Redis to establish baseline…")
                keys = ["SHEET_SALES", "SHEET_COPY_REPORT"]
                for m in MONTHS:
                    keys.extend([m["projection_key"], m["expense_key"], m["monthly_key"], m["tour_key"], m["visits_key"]])
                
                for k in keys:
                    sheet_id = storage.sheet_id(k)
                    if sheet_id:
                        try:
                            drive_mod = await asyncio.get_event_loop().run_in_executor(None, storage.get_modified_time, sheet_id)
                            if drive_mod:
                                await set_sheet_metadata(sheet_id, datetime.utcnow().isoformat(), drive_mod)
                        except Exception as exc:
                            print(f"[startup] Could not sync metadata for {k}: {exc}")
    else:
        from loaders import load_all_data
        from cache.redis_client import health_check
        
        print("Loading all IVC data files locally…")
        data = load_all_data(storage)
        app_state["data"] = data
        _build_doctor_index_from_data(data)
        
        redis_ok = await health_check()
        if redis_ok:
            await eager_recompute(["overview", "months:jan", "months:feb", "months:mar", "products", "delegates", "expenses", "insights"])

    print(f"Loaded months: {list(data.keys())}")
    app_state["data"] = data
    app_state["storage"] = storage
    app_state["insights_cache"] = None  # populated on first /api/insights call
    print("Backend ready.")
    yield
    app_state.clear()


app = FastAPI(title="IVC Dashboard API", lifespan=lifespan, default_response_class=NaNSafeJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
from routers import overview, months, products, delegates, expenses, insights

app.include_router(overview.router, prefix="/api")
app.include_router(months.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(delegates.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(insights.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "months_loaded": list(app_state.get("data", {}).keys())}


@app.post("/api/data/refresh")
async def refresh_data():
    """Re-pull all data from Google Sheets and invalidate the insights cache."""
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
    from cache.redis_client import SHEET_DEPENDENCIES, invalidate_api_keys
    
    existing_data = app_state.get("data", {})
    updated_data, changed_keys = await refresh_changed_from_sheets(storage, existing_data)
    app_state["data"] = updated_data
    _build_doctor_index_from_data(updated_data)

    if changed_keys:
        endpoints_to_invalidate = set()
        for ck in changed_keys:
            if ck in SHEET_DEPENDENCIES:
                endpoints_to_invalidate.update(SHEET_DEPENDENCIES[ck])
        
        endpoints_to_invalidate.add("insights")
        app_state["insights_cache"] = None
        
        endpoints_list = list(endpoints_to_invalidate)
        await invalidate_api_keys(endpoints_list)
        
        await eager_recompute(endpoints_list)

    return {"status": "ok", "months_refreshed": ["jan", "feb", "mar"], "changed_sheets": changed_keys}


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
        "keys": keys
    }
