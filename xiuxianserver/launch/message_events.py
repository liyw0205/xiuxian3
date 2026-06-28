"""适配器消息事件总线。

这里是框架层的中立观察口：QQ、WS 或未来驱动器只把“收到/发出了一条
可展示消息”发布出来，不反向依赖任何业务组件。真正的归属解析、过滤、
落库和页面展示由订阅方自己完成。
"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .log import C, logger


@dataclass(frozen=True)
class MessageEvent:
    """一条驱动器收发消息的最小展示事件。"""

    direction: str
    adapter: str
    request_id: str
    client_id: str
    message_type: str
    content: str


MessageEventListener = Callable[[MessageEvent], Awaitable[None] | None]
_LISTENERS: list[MessageEventListener] = []


def subscribe_message_events(listener: MessageEventListener) -> None:
    """订阅消息事件；同一个 listener 只登记一次。"""

    if listener not in _LISTENERS:
        _LISTENERS.append(listener)


def unsubscribe_message_events(listener: MessageEventListener) -> None:
    """取消订阅消息事件。"""

    try:
        _LISTENERS.remove(listener)
    except ValueError:
        return


def emit_message_event(event: MessageEvent) -> None:
    """发布消息事件。

    订阅者异常只写日志，不影响驱动器收发。异步订阅者会被调度成后台任务，
    避免消息发送链路被展示组件拖住。
    """

    if not _LISTENERS:
        return
    for listener in tuple(_LISTENERS):
        try:
            result = listener(event)
        except Exception as exc:
            logger.opt(colors=True, exception=exc).warning(C.warn("消息事件订阅者异常"))
            continue
        if inspect.isawaitable(result):
            try:
                task = asyncio.create_task(_await_listener(result))
                task.add_done_callback(_consume_listener_result)
            except RuntimeError as exc:
                logger.opt(colors=True, exception=exc).warning(C.warn("消息事件异步订阅调度失败"))


def event_from_incoming(
    *,
    adapter: str,
    client_id: object,
    request_id: object = "",
    message_type: object = "text",
    content: object = "",
) -> MessageEvent:
    """整理驱动器收到的消息事件。"""

    return MessageEvent(
        direction="incoming",
        adapter=_clean_token(adapter, "unknown"),
        request_id=_clean_token(request_id),
        client_id=_clean_token(client_id),
        message_type=_normalize_message_type(message_type),
        content=_clean_content(content),
    )


def event_from_outgoing(
    *,
    adapter: str,
    client_id: object,
    request_id: object = "",
    message: object = "",
) -> MessageEvent:
    """整理驱动器发出的业务回复事件。"""

    message_type, content = display_content_from_message(message)
    return MessageEvent(
        direction="outgoing",
        adapter=_clean_token(adapter, "unknown"),
        request_id=_clean_token(request_id),
        client_id=_clean_token(client_id),
        message_type=message_type,
        content=content,
    )


def display_content_from_message(message: object) -> tuple[str, str]:
    """从业务回复对象里提取适合消息流水展示的正文。

    这里只做协议中立的“取正文”：markdown 取 content，image 尽量取可访问
    地址，keyboard/buttons 不进入 content。修仙玩家头、系统通知等业务层
    装饰由订阅组件再过滤。
    """

    if isinstance(message, dict):
        raw_type = str(message.get("type") or "").strip().lower()
        if raw_type == "markdown":
            return "markdown", _markdown_content(message.get("message"))
        if raw_type == "image":
            return "image", _image_content(message.get("message"))
        if raw_type in {"text", "raw"}:
            return raw_type, _message_text(message.get("message"))
        if "content" in message:
            return "markdown", _message_text(message.get("content"))
        if "message" in message:
            return display_content_from_message(message.get("message"))
        return "raw", json.dumps(message, ensure_ascii=False, default=str)

    if isinstance(message, (list, tuple)):
        return "text", "\n".join(_message_text(item) for item in message if _message_text(item))
    if message is None:
        return "unknown", ""
    return "text", str(message).strip()


async def _await_listener(result: Awaitable[None]) -> None:
    await result


def _consume_listener_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.opt(colors=True, exception=exc).warning(C.warn("消息事件异步订阅者异常"))


def _markdown_content(message: object) -> str:
    if isinstance(message, dict):
        return _message_text(message.get("content"))
    return _message_text(message)


def _image_content(message: object) -> str:
    if isinstance(message, dict):
        for key in ("url", "src", "path", "image"):
            value = _image_content(message.get(key))
            if value and value != "〔图片〕":
                return value
        return "〔图片〕"
    if isinstance(message, str):
        return message.strip() or "〔图片〕"
    if isinstance(message, Path):
        return str(message)
    return "〔图片〕"


def _message_text(message: object) -> str:
    if isinstance(message, dict):
        if "content" in message:
            return _message_text(message.get("content"))
        if "message" in message:
            return _message_text(message.get("message"))
        return json.dumps(message, ensure_ascii=False, default=str)
    if isinstance(message, (list, tuple)):
        return "\n".join(_message_text(item) for item in message if _message_text(item)).strip()
    if message is None:
        return ""
    return str(message).strip()


def _clean_token(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _clean_content(value: object) -> str:
    return str(value or "").strip()


def _normalize_message_type(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"text", "markdown", "image", "raw"} else "unknown"


__all__ = [
    "MessageEvent",
    "display_content_from_message",
    "emit_message_event",
    "event_from_incoming",
    "event_from_outgoing",
    "subscribe_message_events",
    "unsubscribe_message_events",
]
