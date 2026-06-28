"""消息流水组件。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from launch import C, OnEvent, logger
from launch.adapter import Depends, MessageHandler, manager
from launch.paths import static_path
from launch.message_events import subscribe_message_events, unsubscribe_message_events

from ..constants import MESSAGE_FLOW_MAX_ROWS, MESSAGE_FLOW_RETENTION_DAYS
from ..identity import current_player_id
from ..reply import send_reply
from ..user_group_core import read_user_group_session, user_group_admin_url
from .service import FlowRecord, render_markdown_fragment, service


router = APIRouter(prefix="/xiuxian/message-flow")
INDEX_HTML = static_path("message-flow", "index.html")


@router.get("", response_class=HTMLResponse)
async def message_flow_page(
    xiuxian_user_group_session: str | None = Cookie(default=None),
) -> str:
    """返回消息流水后台页面。"""

    session = read_user_group_session(xiuxian_user_group_session or "")
    return _render_page(session)


@router.get("/api/recent")
async def message_flow_recent(
    xiuxian_user_group_session: str | None = Cookie(default=None),
    limit: int = 100,
) -> dict[str, Any]:
    """读取当前登录主用户的最近消息流水。"""

    session = _require_session(xiuxian_user_group_session)
    records = await service.recent(str(session["player_id"]), limit=limit)
    return {
        "player_id": session["player_id"],
        "records": [_record_payload(record) for record in records],
    }


@router.get("/stream")
async def message_flow_stream(
    request: Request,
    xiuxian_user_group_session: str | None = Cookie(default=None),
) -> StreamingResponse:
    """推送当前登录主用户的实时消息流水。"""

    session = _require_session(xiuxian_user_group_session)
    player_id = str(session["player_id"])
    queue = await service.subscribe(player_id)

    async def events():
        try:
            while not await request.is_disconnected():
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if record.flow_id <= 0:
                    break
                yield f"data: {json.dumps(_record_payload(record), ensure_ascii=False)}\n\n"
        finally:
            await service.unsubscribe(player_id, queue)

    return StreamingResponse(events(), media_type="text/event-stream")


@MessageHandler.handler(cmd=("消息流水", "消息记录"), priority=100, block=True)
async def ws_message_flow(client_id: str, player_id: str = Depends(current_player_id)) -> None:
    """查看消息流水后台入口。"""

    await send_reply(player_id or client_id, service.overview(), manager, service)


@OnEvent.connect(priority=41)
async def start_message_flow() -> None:
    """启动消息流水订阅。"""

    await service.start()
    subscribe_message_events(service.handle_event)
    logger.opt(colors=True).info(f"{C.ok('执行 消息流水 启动')}")


@OnEvent.disconnect(priority=41)
async def stop_message_flow() -> None:
    """停止消息流水订阅。"""

    unsubscribe_message_events(service.handle_event)
    await service.shutdown()
    logger.opt(colors=True).info(f"{C.warn('执行 消息流水 关闭')}")


def _require_session(session_id: str | None) -> dict[str, Any]:
    session = read_user_group_session(session_id or "")
    if not session:
        raise HTTPException(status_code=401, detail="用户组后台登录已过期，请重新登录。")
    return session


def _record_payload(record: dict[str, Any] | FlowRecord) -> dict[str, Any]:
    data = record.to_dict() if isinstance(record, FlowRecord) else dict(record)
    data["content_html"] = render_markdown_fragment(str(data.get("content") or ""))
    return data


def _render_page(session: dict[str, Any] | None) -> str:
    """读取静态页面模板并注入当前会话配置。"""

    html = INDEX_HTML.read_text(encoding="utf-8")
    config = {
        "loggedIn": bool(session),
        "playerId": str(session["player_id"]) if session else "",
        "loginUrl": user_group_admin_url(),
        "recentUrl": "/xiuxian/message-flow/api/recent?limit=160",
        "streamUrl": "/xiuxian/message-flow/stream",
        "retentionText": f"{MESSAGE_FLOW_RETENTION_DAYS} 天 / {MESSAGE_FLOW_MAX_ROWS} 条",
    }
    return html.replace("__MESSAGE_FLOW_CONFIG__", _json_for_script(config))


def _json_for_script(data: dict[str, Any]) -> str:
    """生成可安全放进 script 标签的 JSON。"""

    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


__all__ = ["router"]
