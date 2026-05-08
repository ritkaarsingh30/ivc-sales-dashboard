import os
import json
import logging
from datetime import datetime
from uuid import UUID
import redis.asyncio as redis
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

class NaNEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle NaN, Infinity, dates, and numpy types."""
    def default(self, obj):
        if isinstance(obj, float):
            if pd.isna(obj) or np.isnan(obj) or np.isinf(obj):
                return None
        elif pd.isna(obj):  # Catches pd.NaT and others
            return None
        elif isinstance(obj, (np.integer, np.floating)):
            if pd.isna(obj):
                return None
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

def build_sheet_dependencies(month_keys: list[str]) -> dict[str, list[str]]:
    """
    Build the sheet→API-endpoint dependency map for a given set of active months.
    Call this after discovering which months are loaded, then store the result in
    app_state["sheet_dependencies"] so the refresh endpoint can use it.
    """
    month_endpoints = [f"months:{k}" for k in month_keys]
    deps: dict[str, list[str]] = {
        "SHEET_SALES": ["overview", "products", "delegates", "expenses", "insights"] + month_endpoints,
    }
    for mon in month_keys:
        mon_up = mon.upper()
        deps[f"SHEET_{mon_up}_EXPENSE"]    = ["overview", f"months:{mon}", "expenses", "insights"]
        deps[f"SHEET_{mon_up}_MONTHLY"]    = [f"months:{mon}", "delegates", "insights"]
        deps[f"SHEET_{mon_up}_PROJECTION"] = [f"months:{mon}", "products", "overview", "insights"]
        deps[f"SHEET_{mon_up}_TOUR"]       = [f"months:{mon}", "delegates", "insights"]
        deps[f"SHEET_{mon_up}_VISITS"]     = [f"months:{mon}", "delegates", "insights"]
    return deps


# Kept for backwards-compat with local mode (static, jan/feb/mar only)
SHEET_DEPENDENCIES = build_sheet_dependencies(["jan", "feb", "mar"])

async def get_api_cache(key: str) -> dict | None:
    try:
        val = await redis_client.get(f"api:{key}")
        if val:
            return json.loads(val)
    except Exception as e:
        logger.warning(f"[cache] Failed to get API cache for {key}: {e}")
    return None

async def set_api_cache(key: str, data: dict) -> None:
    try:
        val = json.dumps(data, cls=NaNEncoder)
        await redis_client.set(f"api:{key}", val)
    except Exception as e:
        logger.warning(f"[cache] Failed to set API cache for {key}: {e}")

async def invalidate_api_keys(keys: list[str]) -> None:
    if not keys:
        return
    try:
        redis_keys = [f"api:{k}" for k in keys]
        await redis_client.delete(*redis_keys)
    except Exception as e:
        logger.warning(f"[cache] Failed to invalidate API cache: {e}")

async def get_sheet_metadata(sheet_id: str) -> dict | None:
    try:
        last_updated = await redis_client.get(f"sheets:{sheet_id}:last_updated")
        drive_modified = await redis_client.get(f"sheets:{sheet_id}:drive_modified")
        if last_updated and drive_modified:
            return {
                "last_updated": last_updated,
                "drive_modified": drive_modified
            }
    except Exception as e:
        logger.warning(f"[cache] Failed to get sheet metadata for {sheet_id}: {e}")
    return None

async def set_sheet_metadata(sheet_id: str, last_updated: str, drive_modified: str) -> None:
    try:
        ttl = 25 * 3600  # 25 hours
        await redis_client.setex(f"sheets:{sheet_id}:last_updated", ttl, last_updated)
        await redis_client.setex(f"sheets:{sheet_id}:drive_modified", ttl, drive_modified)
    except Exception as e:
        logger.warning(f"[cache] Failed to set sheet metadata for {sheet_id}: {e}")

async def flush_all_api_cache() -> None:
    try:
        keys = await redis_client.keys("api:*")
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.warning(f"[cache] Failed to flush API cache: {e}")

async def health_check() -> bool:
    try:
        return await redis_client.ping()
    except Exception as e:
        logger.warning(f"[cache] Redis unavailable: {e}")
        return False
