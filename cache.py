# cache.py
"""
Simple file-based article cache.
Prevents re-processing the same articles across multiple daily runs.
Cache entries expire after CACHE_TTL_HOURS hours.
"""

import json
import os
import time
from pathlib import Path

CACHE_FILE    = Path(".digest_cache.json")
CACHE_TTL_SEC = 22 * 3600  # 22 hours — slightly under 1 day


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print(f"⚠️  Cache write failed: {exc}")


def get_cached_result(article_id: str) -> dict | None:
    """Return cached analysis result if fresh, else None."""
    cache = _load_cache()
    entry = cache.get(article_id)
    if not entry:
        return None
    age = time.time() - entry.get("cached_at", 0)
    if age > CACHE_TTL_SEC:
        return None
    return entry.get("data")


def set_cached_result(article_id: str, data: dict | None) -> None:
    """
    Store analysis result (or None for filtered-out articles).
    Storing None prevents re-querying rejected articles.
    """
    cache = _load_cache()
    cache[article_id] = {
        "cached_at": time.time(),
        "data": data,
    }
    # Keep cache lean — max 500 entries, drop oldest
    if len(cache) > 500:
        sorted_keys = sorted(cache, key=lambda k: cache[k].get("cached_at", 0))
        for old_key in sorted_keys[:100]:
            del cache[old_key]
    _save_cache(cache)


def cache_stats() -> str:
    cache = _load_cache()
    now   = time.time()
    fresh = sum(1 for v in cache.values() if now - v.get("cached_at", 0) < CACHE_TTL_SEC)
    return f"Cache: {fresh} fresh / {len(cache)} total entries"