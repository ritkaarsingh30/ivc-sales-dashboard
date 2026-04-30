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
        print("Loading all IVC data from Google Sheets…")
        data = load_all_from_sheets(storage)
    else:
        from loaders import load_all_data
        print("Loading all IVC data files…")
        data = load_all_data(storage)

    print(f"Loaded months: {list(data.keys())}")
    _build_doctor_index_from_data(data)

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

    # Clear gspread in-memory cache so next fetch is fresh from Google
    storage.clear_cache()

    # Re-scan the Drive folder in case new files were uploaded since startup
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if folder_id:
        storage.discover(folder_id)

    from sheets_loader import load_all_from_sheets
    data = load_all_from_sheets(storage)
    _build_doctor_index_from_data(data)

    app_state["data"] = data
    app_state["insights_cache"] = None  # force AI insight regeneration

    return {"status": "ok", "months_refreshed": list(data.keys())}
