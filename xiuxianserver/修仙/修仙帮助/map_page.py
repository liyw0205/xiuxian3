"""修仙帮助站地图页面。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi_cache.decorator import cache

from ..sql import db
from .map_builder import build_map_data


MAP_HTML = Path(__file__).resolve().parents[2] / "static" / "map" / "world-map.html"
router = APIRouter()


@router.get("/xiuxian/map", response_class=HTMLResponse)
async def map_index() -> HTMLResponse:
    """交互地图页面。"""

    if not MAP_HTML.exists():
        raise HTTPException(status_code=404, detail="map page not found")
    return HTMLResponse(MAP_HTML.read_text(encoding="utf-8"))


@router.get("/xiuxian/map/data")
@cache(expire=60, namespace="help:map")
async def map_data(player_id: str = "") -> dict:
    """地图动态数据；页面每 60 秒刷新一次。"""

    return build_map_data(db, player_id=player_id)
