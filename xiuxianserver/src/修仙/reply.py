"""修仙 WS 回复包装。"""

from __future__ import annotations

from typing import Any

from .sql import db


async def send_reply(client_id: str, message: Any, manager: Any, service: Any = None) -> None:
    """发送修仙回复，并在文本消息前标出玩家名。"""

    database = getattr(service, "db", None) or db
    await manager.send(_with_player_name(client_id, message, database), client_id)


def _with_player_name(client_id: str, message: Any, database: Any) -> Any:
    """给 text 回复加上玩家展示名；非 text 消息保持原协议。"""

    name = _display_name(client_id, database)
    if isinstance(message, dict):
        payload = dict(message)
        if payload.get("type") == "text":
            payload["message"] = _prefix_text(name, payload.get("message", ""))
        return payload
    return _prefix_text(name, message)


def _prefix_text(name: str, message: Any) -> str:
    """生成带玩家名的文本。"""

    prefix = f"【{name}】"
    text = str(message)
    if text.startswith(prefix):
        return text
    return f"{prefix}\n{text}"


def _display_name(client_id: str, database: Any) -> str:
    """读取玩家展示名；未建档或数据库不可用时返回固定名称。"""

    try:
        row = database.fetch_one(
            "SELECT display_name FROM players WHERE client_id = ?",
            (client_id,),
        )
    except Exception:
        return "未建档"
    if not row:
        return "未建档"
    return str(row["display_name"] or "未建档")
