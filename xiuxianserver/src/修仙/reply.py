"""修仙 WS 回复包装。"""

from __future__ import annotations

from typing import Any

from .markdown_utils import markdown_message_from_text
from .sql import db


async def send_reply(client_id: str, message: Any, manager: Any, service: Any = None) -> None:
    """发送修仙回复，并在文本消息前标出玩家名。"""

    database = getattr(service, "db", None) or db
    await manager.send(_with_player_name(client_id, message, database), client_id)


def _with_player_name(client_id: str, message: Any, database: Any) -> Any:
    """给 text/markdown 回复加上玩家名，并把手写按钮标记转成按钮。"""

    name = _display_name(client_id, database)
    if isinstance(message, dict):
        payload = dict(message)
        if payload.get("type") == "text":
            payload["message"] = _prefix_text(name, payload.get("message", ""))
            _try_markdown_payload(payload)
        elif payload.get("type") == "markdown":
            payload["message"] = _prefix_markdown(name, payload.get("message"))
        return payload

    text = _prefix_text(name, message)
    markdown = markdown_message_from_text(text)
    if markdown:
        return {"code": 202, "type": "markdown", "message": markdown}
    return text


def _try_markdown_payload(payload: dict) -> None:
    """text 里有手写按钮标记时，原地改成 markdown 按钮消息。"""

    markdown = markdown_message_from_text(str(payload.get("message", "")))
    if not markdown:
        return
    payload["type"] = "markdown"
    payload["message"] = markdown


def _prefix_markdown(name: str, message: Any) -> dict:
    """给已有 markdown 正文加玩家名，键盘等字段保持不变。"""

    if not isinstance(message, dict):
        return {"content": _prefix_text(name, message)}

    payload = dict(message)
    payload["content"] = _prefix_text(name, payload.get("content", ""))
    return payload


def _prefix_text(name: str, message: Any) -> str:
    """生成带玩家名的文本。"""

    prefix = f"【{name}】"
    text = str(message)
    if text.startswith(prefix):
        return text + "<指南><休息><结束休息>"
    return f"{prefix}\n{text}" + "<指南><休息><结束休息>"


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
