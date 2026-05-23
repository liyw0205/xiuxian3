"""WebSocket 通讯格式工具。"""

from __future__ import annotations

import json
from base64 import b64encode
from io import BytesIO
from typing import Any


def is_ws_code(value: object) -> bool:
    """只接受新版协议 code：整数 202 或 404。"""

    return type(value) is int and value in {202, 404}


def ws_message(
    message: Any = "",
    *,
    code: int = 202,
    type: str = "text",
    request_id: object | None = None,
) -> dict[str, Any]:
    """手动生成一条 WS 消息。"""

    return make_payload(
        {
            "code": code,
            "type": type,
            "message": message,
        },
        request_id=request_id,
    )


def make_payload(message: Any, request_id: object | None = None) -> dict[str, Any]:
    """把任意回复整理成统一 WS 格式。

    输出字段顺序固定为：code、type、message、request_id。
    文本默认返回 202/text；图片字节会转成不带 data:image 头的 Base64。
    """

    if isinstance(message, dict):
        code = message.get("code", 202)
        msg_type = message.get("type", "text")
        content = message.get("message", "")
    else:
        code = 202
        msg_type = "text"
        content = message

    payload: dict[str, Any] = {
        "code": code if is_ws_code(code) else 202,
        "type": str(msg_type or "text"),
        "message": _payload_message(content),
    }
    if request_id is not None:
        payload["request_id"] = str(request_id)
    return payload


def loads_message(text: str) -> dict[str, Any]:
    """读取服务端 WS 文本；解析失败时返回 404/text。"""

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            "code": 404,
            "type": "text",
            "message": "Invalid JSON format",
        }
    if not isinstance(data, dict):
        return {
            "code": 404,
            "type": "text",
            "message": "Invalid WS message format",
        }
    return data


def _payload_message(value: Any) -> str:
    """把消息主体转成可 JSON 序列化的字符串。"""

    if isinstance(value, BytesIO):
        return b64encode(value.getvalue()).decode("utf-8")
    if isinstance(value, bytes | bytearray | memoryview):
        return b64encode(bytes(value)).decode("utf-8")
    return str(value)


__all__ = [
    "is_ws_code",
    "loads_message",
    "make_payload",
    "ws_message",
]
