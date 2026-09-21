import threading
import time

import requests

from .config import config

CACHE_TTL_SECONDS = 24 * 60 * 60  # los departamentos/municipios de Colombia no cambian en caliente

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, list[dict]]] = {}


def _get_cached_or_fetch(key: str, path: str) -> list[dict]:
    with _cache_lock:
        cached = _cache.get(key)
        if cached and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

    response = requests.get(f"{config.API_COLOMBIA_BASE_URL}{path}", timeout=15)
    response.raise_for_status()
    data = response.json()

    with _cache_lock:
        _cache[key] = (time.monotonic(), data)
    return data


def get_departments() -> list[dict]:
    """Devuelve los 33 departamentos (incluye Bogotá D.C.) con id, name y description."""
    return _get_cached_or_fetch("departments", "/Department")


def get_cities() -> list[dict]:
    """Devuelve los ~1123 municipios de Colombia con id, name, description y departmentId."""
    return _get_cached_or_fetch("cities", "/City")
