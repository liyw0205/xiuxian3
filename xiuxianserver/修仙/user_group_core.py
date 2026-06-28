"""用户组公共能力。

用户组本身是二级组件，但“后台 session 是否有效”和“用户组后台公开
地址”会被其它 HTTP 组件复用。公共能力放在根目录，避免二级组件之间
互相导入。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .markdown_utils import markdown_link
from .public_url import public_url
from .sql import db


USER_GROUP_ADMIN_PATH = "/xiuxian/user-groups"


def read_user_group_session(session_id: str, database: Any | None = None) -> dict[str, Any] | None:
    """读取仍在有效期内的用户组后台 session。"""

    value = str(session_id or "").strip()
    if not value:
        return None

    database = database if database is not None else db
    row = database.fetch_one(
        """
        SELECT session_id, player_id, expires_at
        FROM user_group_sessions
        WHERE session_id = ?
          AND expires_at > ?
        LIMIT 1
        """,
        (value, datetime.now().replace(microsecond=0).isoformat()),
    )
    return row if row else None


def user_group_admin_url() -> str:
    """返回当前环境下的用户组后台公开地址。"""

    return public_url(USER_GROUP_ADMIN_PATH)


def user_group_admin_link(label: str = "用户组后台") -> str:
    """返回用户组后台 Markdown 改名链接，消息里不裸露真实地址。"""

    return markdown_link(label, user_group_admin_url())


__all__ = [
    "USER_GROUP_ADMIN_PATH",
    "read_user_group_session",
    "user_group_admin_link",
    "user_group_admin_url",
]
