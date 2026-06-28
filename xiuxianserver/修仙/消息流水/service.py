"""消息流水服务。"""

from __future__ import annotations

import asyncio
import html
import json
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Deque

from launch.message_events import MessageEvent

from ..constants import (
    MESSAGE_FLOW_GLOBAL_BUFFER,
    MESSAGE_FLOW_MAX_ROWS,
    MESSAGE_FLOW_PER_PLAYER_BUFFER,
    MESSAGE_FLOW_RETENTION_DAYS,
)
from ..identity import resolve_player_id
from ..markdown_utils import markdown_link
from ..public_url import public_url
from ..sql import db


MAX_CONTENT_LENGTH = 6000
MESSAGE_FLOW_PATH = "/xiuxian/message-flow"
HEADER_LINE_RE = re.compile(r"^【[^】]{0,80}】$")
SYSTEM_LINE_RE = re.compile(r"^(?:🔴\s*)?系统：")
NOTICE_LINE_RE = re.compile(r"^(?:🔴\s*)?通知：")


@dataclass(frozen=True)
class FlowRecord:
    """页面和 SSE 使用的消息流水记录。"""

    flow_id: int
    direction: str
    adapter: str
    request_id: str
    client_id: str
    player_id: str
    message_type: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MessageFlowService:
    """消息流水核心服务。"""

    def __init__(self, database: Any | None = None) -> None:
        self.db = database if database is not None else db
        self._lock = asyncio.Lock()
        self._global_records: Deque[FlowRecord] = deque(maxlen=MESSAGE_FLOW_GLOBAL_BUFFER)
        self._player_records: dict[str, Deque[FlowRecord]] = defaultdict(
            lambda: deque(maxlen=MESSAGE_FLOW_PER_PLAYER_BUFFER)
        )
        self._subscribers: dict[str, set[asyncio.Queue[FlowRecord]]] = defaultdict(set)
        self._last_flow_id = 0

    def overview(self) -> str:
        """返回消息流水后台入口。"""

        return (
            f"消息流水后台：{message_flow_link()}\n"
            "进入页面前需要先完成用户组后台登录。"
        )

    async def start(self) -> None:
        """从短期表恢复最新流水，供热重启后页面回放。"""

        self._last_flow_id = self._read_last_flow_id()
        for row in self._recent_rows_from_db(limit=MESSAGE_FLOW_GLOBAL_BUFFER):
            record = _record_from_row(row)
            self._remember_record(record)

    async def shutdown(self) -> None:
        """关闭所有 SSE 等待队列。"""

        async with self._lock:
            subscribers = [queue for queues in self._subscribers.values() for queue in queues]
            self._subscribers.clear()
        for queue in subscribers:
            queue.put_nowait(_closed_record())

    async def handle_event(self, event: MessageEvent) -> None:
        """接收驱动器事件，过滤后写入内存和短期表。"""

        record = await self.record_event(event)
        if record is None:
            return
        await self._publish(record)

    async def record_event(self, event: MessageEvent) -> FlowRecord | None:
        """把驱动器事件转换成消息流水记录。"""

        content = sanitize_event_content(event)
        if not content:
            return None

        player_id = resolve_player_id(event.client_id, self.db)
        record = await self._make_record(event, player_id, content)
        self._insert_record(record)
        await self._remember_record_locked(record)
        return record

    async def recent(self, player_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """读取某个主用户的最近消息。"""

        normalized = str(player_id or "").strip()
        if not normalized:
            return []
        count = max(1, min(int(limit or 100), MESSAGE_FLOW_PER_PLAYER_BUFFER))
        async with self._lock:
            cached = list(self._player_records.get(normalized, ()))
        if len(cached) >= count or cached:
            return [record.to_dict() for record in cached[-count:]]

        rows = self.db.fetch_all(
            """
            SELECT *
            FROM message_flows
            WHERE player_id = ?
            ORDER BY flow_id DESC
            LIMIT ?
            """,
            (normalized, count),
        )
        return [dict(row) for row in reversed(rows)]

    async def subscribe(self, player_id: str) -> asyncio.Queue[FlowRecord]:
        """订阅某个主用户的实时流水。"""

        normalized = str(player_id or "").strip()
        queue: asyncio.Queue[FlowRecord] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[normalized].add(queue)
        return queue

    async def unsubscribe(self, player_id: str, queue: asyncio.Queue[FlowRecord]) -> None:
        """取消实时流水订阅。"""

        normalized = str(player_id or "").strip()
        async with self._lock:
            queues = self._subscribers.get(normalized)
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._subscribers.pop(normalized, None)

    def cleanup(self) -> None:
        """清理短期表，按 2 天和 5000 条双限制收口。"""

        cutoff = (datetime.now() - timedelta(days=MESSAGE_FLOW_RETENTION_DAYS)).isoformat(timespec="seconds")
        with self.db.transaction() as conn:
            conn.execute(
                """
                DELETE FROM message_flows
                WHERE datetime(replace(created_at, 'T', ' ')) < datetime(replace(?, 'T', ' '))
                """,
                (cutoff,),
            )
            conn.execute(
                """
                DELETE FROM message_flows
                WHERE flow_id NOT IN (
                    SELECT flow_id
                    FROM message_flows
                    ORDER BY flow_id DESC
                    LIMIT ?
                )
                """,
                (MESSAGE_FLOW_MAX_ROWS,),
            )

    async def _make_record(self, event: MessageEvent, player_id: str, content: str) -> FlowRecord:
        async with self._lock:
            self._last_flow_id = max(self._last_flow_id, self._read_last_flow_id()) + 1
            flow_id = self._last_flow_id
        return FlowRecord(
            flow_id=flow_id,
            direction=_safe_choice(event.direction, {"incoming", "outgoing"}, "incoming"),
            adapter=_short_token(event.adapter, "unknown"),
            request_id=_short_token(event.request_id),
            client_id=_short_token(event.client_id),
            player_id=_short_token(player_id or event.client_id),
            message_type=_safe_choice(event.message_type, {"text", "markdown", "image", "raw", "unknown"}, "unknown"),
            content=_truncate_content(content),
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _insert_record(self, record: FlowRecord) -> None:
        self.db.execute(
            """
            INSERT INTO message_flows (
                flow_id, direction, adapter, request_id, client_id, player_id,
                message_type, content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.flow_id,
                record.direction,
                record.adapter,
                record.request_id,
                record.client_id,
                record.player_id,
                record.message_type,
                record.content,
                record.created_at,
            ),
        )
        if record.flow_id % 100 == 0:
            self.cleanup()

    async def _remember_record_locked(self, record: FlowRecord) -> None:
        async with self._lock:
            self._remember_record(record)

    def _remember_record(self, record: FlowRecord) -> None:
        self._global_records.append(record)
        self._player_records[record.player_id].append(record)

    async def _publish(self, record: FlowRecord) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(record.player_id, ()))
        for queue in queues:
            if queue.full():
                try:
                    queue.get_nowait()
                    queue.task_done()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(record)

    def _read_last_flow_id(self) -> int:
        try:
            row = self.db.fetch_one("SELECT COALESCE(MAX(flow_id), 0) AS last_id FROM message_flows")
        except Exception:
            return self._last_flow_id
        return int(row.get("last_id") or 0) if row else 0

    def _recent_rows_from_db(self, *, limit: int) -> list[dict[str, Any]]:
        try:
            rows = self.db.fetch_all(
                """
                SELECT *
                FROM message_flows
                ORDER BY flow_id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
        except Exception:
            return []
        return list(reversed(rows))


def sanitize_event_content(event: MessageEvent) -> str:
    """整理消息展示正文。"""

    text = str(event.content or "").strip()
    if not text:
        return ""
    if event.direction == "outgoing":
        text = _strip_reply_prefix_lines(text)
    return _truncate_content(text)


def render_markdown_fragment(text: str) -> str:
    """把项目内常用 Markdown 子集渲染成安全 HTML 片段。"""

    lines = str(text or "").splitlines()
    rendered: list[str] = []
    in_list = False
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            if in_list:
                rendered.append("</ul>")
                in_list = False
            rendered.append("<br>")
            continue

        if line.lstrip().startswith(">"):
            if in_list:
                rendered.append("</ul>")
                in_list = False
            content = line.lstrip()[1:].strip()
            rendered.append(f"<blockquote>{_inline_markdown(content)}</blockquote>")
            continue

        if line.lstrip().startswith("- "):
            if not in_list:
                rendered.append("<ul>")
                in_list = True
            rendered.append(f"<li>{_inline_markdown(line.lstrip()[2:].strip())}</li>")
            continue

        if in_list:
            rendered.append("</ul>")
            in_list = False
        rendered.append(f"<p>{_inline_markdown(line)}</p>")

    if in_list:
        rendered.append("</ul>")
    return "\n".join(rendered)


def message_flow_url() -> str:
    """返回消息流水后台公开地址。"""

    return public_url(MESSAGE_FLOW_PATH)


def message_flow_link(label: str = "消息流水后台") -> str:
    """返回隐藏真实地址的消息流水后台链接。"""

    return markdown_link(label, message_flow_url())


def _strip_reply_prefix_lines(text: str) -> str:
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        value = lines[index].strip()
        if not value:
            index += 1
            continue
        if HEADER_LINE_RE.match(value) or SYSTEM_LINE_RE.match(value) or NOTICE_LINE_RE.match(value):
            index += 1
            continue
        break
    return "\n".join(lines[index:]).strip()


def _inline_markdown(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = _render_images(escaped)
    escaped = _render_links(escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", escaped)
    return escaped


def _render_links(text: str) -> str:
    return re.sub(
        r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)",
        lambda match: (
            f'<a href="{html.escape(match.group(2), quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{match.group(1)}</a>'
        ),
        text,
    )


def _render_images(text: str) -> str:
    return re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda match: (
            f'<img src="{html.escape(match.group(2), quote=True)}" '
            f'alt="{html.escape(match.group(1), quote=True)}" loading="lazy">'
        ),
        text,
    )


def _record_from_row(row: dict[str, Any]) -> FlowRecord:
    return FlowRecord(
        flow_id=int(row.get("flow_id") or 0),
        direction=str(row.get("direction") or ""),
        adapter=str(row.get("adapter") or ""),
        request_id=str(row.get("request_id") or ""),
        client_id=str(row.get("client_id") or ""),
        player_id=str(row.get("player_id") or ""),
        message_type=str(row.get("message_type") or "unknown"),
        content=str(row.get("content") or ""),
        created_at=str(row.get("created_at") or ""),
    )


def _closed_record() -> FlowRecord:
    return FlowRecord(0, "system", "", "", "", "", "text", "", "")


def _safe_choice(value: object, choices: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in choices else default


def _short_token(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text[:160]


def _truncate_content(text: str) -> str:
    value = str(text or "").strip()
    if len(value) <= MAX_CONTENT_LENGTH:
        return value
    return f"{value[:MAX_CONTENT_LENGTH]}..."


def sse_data(record: FlowRecord) -> str:
    """把记录转成 SSE data 行。"""

    return json.dumps(record.to_dict(), ensure_ascii=False)


service = MessageFlowService(db)


__all__ = [
    "FlowRecord",
    "MessageFlowService",
    "message_flow_link",
    "message_flow_url",
    "render_markdown_fragment",
    "sanitize_event_content",
    "service",
    "sse_data",
]
