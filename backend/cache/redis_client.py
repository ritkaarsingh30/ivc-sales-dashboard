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

SHEET_DEPENDENCIES = {
    "SHEET_SALES": ["overview", "months:jan", "months:feb", "months:mar", "products", "delegates", "expenses", "insights"],
    "SHEET_COPY_REPORT": ["overview", "months:jan", "months:feb", "months:mar", "products", "insights"],
    
    "SHEET_JAN_EXPENSE": ["overview", "months:jan", "expenses", "insights"],
    "SHEET_JAN_MONTHLY": ["months:jan", "delegates", "insights"],
    "SHEET_JAN_PROJECTION": ["months:jan", "products", "overview", "insights"],
    "SHEET_JAN_TOUR": ["months:jan", "delegates", "insights"],
    "SHEET_JAN_VISITS": ["months:jan", "delegates", "insights"],

    "SHEET_FEB_EXPENSE": ["overview", "months:feb", "expenses", "insights"],
    "SHEET_FEB_MONTHLY": ["months:feb", "delegates", "insights"],
    "SHEET_FEB_PROJECTION": ["months:feb", "products", "overview", "insights"],
    "SHEET_FEB_TOUR": ["months:feb", "delegates", "insights"],
    "SHEET_FEB_VISITS": ["months:feb", "delegates", "insights"],

    "SHEET_MAR_EXPENSE": ["overview", "months:mar", "expenses", "insights"],
    "SHEET_MAR_MONTHLY": ["months:mar", "delegates", "insights"],
    "SHEET_MAR_PROJECTION": ["months:mar", "products", "overview", "insights"],
    "SHEET_MAR_TOUR": ["months:mar", "delegates", "insights"],
    "SHEET_MAR_VISITS": ["months:mar", "delegates", "insights"],
}

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
