"""缘契组件入口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from launch.adapter import Depends, MessageHandler, manager
from launch.paths import static_path

from ..identity import current_player_id
from ..reply import send_reply
from .service import service


router = APIRouter(prefix="/xiuxian/yuanqi")
YUANQI_INDEX = static_path("yuanqi", "index.html")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def yuanqi_index() -> HTMLResponse:
    """缘契体验页。"""

    try:
        html = YUANQI_INDEX.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=404, detail="缘契体验页不存在。") from exc
    return HTMLResponse(html)


@router.post("/start")
async def yuanqi_start(request: Request) -> dict:
    """校验开启码并返回对应剧本。"""

    payload = await _json_payload(request)
    try:
        return service.start(str(payload.get("name") or ""), str(payload.get("code") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _json_payload(request: Request) -> dict:
    """读取缘契启动 JSON。"""

    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - 只在坏请求时进入
        raise HTTPException(status_code=400, detail="缘契启动数据不是有效 JSON。") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="缘契启动数据不是有效 JSON。")
    return payload


@MessageHandler.handler(cmd="开启缘契", priority=100, block=True)
async def ws_yuanqi_issue(message: str = "", player_id: str = Depends(current_player_id)) -> None:
    """生成缘契一次性开启码。"""

    await send_reply(player_id, service.issue(player_id, message), manager, service)


@MessageHandler.handler(cmd=("查看所有缘契", "缘契列表"), priority=100, block=True)
async def ws_yuanqi_list(player_id: str = Depends(current_player_id)) -> None:
    """查看当前可用的缘契剧本。"""

    await send_reply(player_id, service.list_stories(), manager, service)
