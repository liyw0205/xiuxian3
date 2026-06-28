"""缘契组件服务。"""

from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import timedelta
from typing import Any

from ..common import CoreService, now, random, ts
from ..constants import YUANQI_CODE_TTL_HOURS, YUANQI_VOUCHER_KEY
from ..format_text import T
from ..markdown_utils import markdown_link
from ..public_url import public_url
from ..sql import WISH_VOUCHERS, db
from .stories import YuanqiStory, discover_stories, find_story, load_story


YUANQI_CODE_PREFIX = "YQ"
YUANQI_PAGE_PATH = "/xiuxian/yuanqi"
VOUCHER_NAMES = {key: name for key, name in WISH_VOUCHERS}


class YuanqiService(CoreService):
    """缘契开启码、凭证消耗和剧本启动。"""

    def issue(self, client_id: str, story_name: str = "") -> str:
        """消耗一枚缘契凭证，并生成一天有效的一次性开启码。"""

        player, error = self.require_player(client_id)
        if error:
            return error

        display_name = str(player.get("display_name") or "").strip()
        if not display_name:
            return T.hint("当前角色缺少显示名。", "请先确认角色状态。<修仙信息>")
        try:
            stories = discover_stories()
        except ValueError as exc:
            return T.hint(str(exc), "请检查 修仙/缘契/stories 下的剧本 JSON。")
        if not stories:
            return T.hint("缘契暂时没有可体验的剧本。", "请先把剧本放到 修仙/缘契/stories/剧本目录/story-data.json。")

        requested_story = self._resolve_requested_story(story_name, stories)
        if isinstance(requested_story, str):
            return requested_story

        current = ts()
        expires_at = ts(now() + timedelta(hours=YUANQI_CODE_TTL_HOURS))
        voucher_name = VOUCHER_NAMES.get(YUANQI_VOUCHER_KEY, "缘契凭证")
        with self.db.transaction() as conn:
            quantity = self._voucher_quantity_conn(conn, client_id)
            if quantity <= 0:
                return T.hint(
                    f"你的 {voucher_name} 不足。",
                    "发送：祈愿 或 十连祈愿 获取凭证，再发送：开启缘契。<祈愿><十连祈愿><我的凭证>",
                )

            cursor = conn.execute(
                """
                UPDATE wish_user_vouchers
                SET quantity = quantity - 1, updated_at = ?
                WHERE player_id = ? AND voucher_key = ? AND quantity > 0
                """,
                (current, client_id, YUANQI_VOUCHER_KEY),
            )
            if cursor.rowcount <= 0:
                return T.hint(f"你的 {voucher_name} 不足。", "发送：我的凭证 查看当前库存。<我的凭证>")

            requested_story_id = requested_story.key if requested_story else ""
            code = self._insert_code_conn(
                conn,
                client_id,
                display_name,
                current,
                expires_at,
                requested_story_id,
            )
            detail = f"code={code}"
            if requested_story:
                detail += f", requested_story={requested_story.key}"
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '开启缘契', ?, ?)",
                (client_id, detail, current),
            )

        panel = T.panel()
        panel.section("缘契开启")
        panel.line(f"已消耗：{voucher_name} x1")
        panel.line(f"绑定角色：**{display_name}**")
        panel.line(f"剧本：{_story_issue_label(requested_story)}")
        panel.line(f"开启码：**{code}**")
        panel.line(f"有效期：{YUANQI_CODE_TTL_HOURS} 小时；网页进入成功后立即失效，刷新也不会恢复。")
        panel.line(markdown_link("进入缘契", public_url(YUANQI_PAGE_PATH)))
        panel.hr()
        panel.line("网页内需要填写绑定角色名和开启码，角色名必须完全一致。")
        return T.attach(panel.render(), T.buttons("查看所有缘契", "我的凭证", "祈愿奖池"))

    def start(self, name: str, code: str) -> dict[str, Any]:
        """校验角色名和开启码，成功后立即消费并返回剧本。"""

        player_name = _normalize_name(name)
        clean_code = _normalize_code(code)
        if not player_name:
            raise ValueError("请填写角色名。")
        if not clean_code:
            raise ValueError("请填写缘契开启码。")

        stories = discover_stories()
        if not stories:
            raise ValueError("缘契暂时没有可体验的剧本。")

        current = ts()
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM yuanqi_codes
                WHERE code = ?
                LIMIT 1
                """,
                (clean_code,),
            ).fetchone()
            if not row:
                raise ValueError("没有找到这个缘契开启码。")
            if row["used_at"]:
                raise ValueError("这个缘契开启码已经被使用。")
            if str(row["expires_at"]) <= current:
                raise ValueError("这个缘契开启码已经过期。")
            if player_name != str(row["player_name"] or "").strip():
                raise ValueError("角色名与开启码绑定角色不一致。")

            story = self._story_for_code(row, stories)
            story_data = load_story(story)
            cursor = conn.execute(
                """
                UPDATE yuanqi_codes
                SET used_at = ?, used_story_id = ?
                WHERE code = ? AND used_at IS NULL AND expires_at > ?
                """,
                (current, story.key, clean_code, current),
            )
            if cursor.rowcount <= 0:
                raise ValueError("这个缘契开启码已经被使用。")
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '进入缘契', ?, ?)",
                (str(row["player_id"]), f"code={clean_code}, story={story.key}", current),
            )

        return {
            "story_id": story.key,
            "story_title": story.title,
            "story_subtitle": story.subtitle,
            "player_name": player_name,
            "story_data": story_data,
        }

    def list_stories(self) -> str:
        """查看当前可用的全部缘契剧本。"""

        try:
            stories = discover_stories()
        except ValueError as exc:
            return T.hint(str(exc), "请检查 修仙/缘契/stories 下的剧本 JSON。")
        if not stories:
            return T.hint("缘契暂时没有可体验的剧本。", "请先把剧本放到 修仙/缘契/stories/剧本目录/story-data.json。")

        panel = T.panel()
        panel.section("缘契剧本")
        panel.line("发送：开启缘契 随机生成开启码。")
        panel.line("发送：开启缘契 书页醒来 可指定剧本。")
        panel.hr()
        for index, story in enumerate(stories, start=1):
            panel.line(f"{index}. {story.title}")
        return T.attach(panel.render(), T.buttons("开启缘契", "我的凭证"))

    @staticmethod
    def _voucher_quantity_conn(conn: sqlite3.Connection, client_id: str) -> int:
        """读取缘契凭证数量。"""

        row = conn.execute(
            """
            SELECT quantity
            FROM wish_user_vouchers
            WHERE player_id = ? AND voucher_key = ?
            LIMIT 1
            """,
            (client_id, YUANQI_VOUCHER_KEY),
        ).fetchone()
        return max(0, int(row["quantity"] or 0)) if row else 0

    def _insert_code_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        player_name: str,
        issued_at: str,
        expires_at: str,
        requested_story_id: str = "",
    ) -> str:
        """事务内写入开启码，极低概率碰撞时自动重试。"""

        for _attempt in range(6):
            code = _new_code()
            try:
                conn.execute(
                    """
                    INSERT INTO yuanqi_codes
                    (code, player_id, player_name, issued_at, expires_at, requested_story_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (code, client_id, player_name, issued_at, expires_at, requested_story_id),
                )
                return code
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("缘契开启码生成失败，请重新尝试。")

    @staticmethod
    def _resolve_requested_story(story_name: str, stories: list[YuanqiStory]) -> YuanqiStory | str | None:
        """把命令参数解析成目标剧本；空参数表示随机。"""

        clean_name = str(story_name or "").strip()
        if not clean_name:
            return None

        story, matched_name = _find_story_with_suffix_trimming(clean_name, stories)
        if story:
            return story

        title_list = "、".join(item.title for item in stories[:8])
        if len(stories) > 8:
            title_list += " 等"
        return T.hint(
            f"没有找到缘契剧本：{matched_name}",
            f"可用剧本：{title_list}。发送：查看所有缘契 查看完整列表。<查看所有缘契>",
        )

    @staticmethod
    def _story_for_code(row: sqlite3.Row, stories: list[YuanqiStory]) -> YuanqiStory:
        """读取开启码绑定剧本；未绑定时随机。"""

        requested_story_id = str(row["requested_story_id"] or "").strip()
        if not requested_story_id:
            return random.choice(stories)

        story = find_story(requested_story_id, stories)
        if not story:
            raise ValueError("这个缘契开启码绑定的剧本已不存在，请重新生成开启码。")
        return story


def _new_code() -> str:
    """生成玩家可复制的一次性开启码。"""

    raw = secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()
    return f"{YUANQI_CODE_PREFIX}{raw[:12]}"


def _normalize_code(value: str) -> str:
    """规范化玩家输入的开启码。"""

    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _normalize_name(value: str) -> str:
    """规范化网页登录角色名，保留玩家显示名本身。"""

    return str(value or "").strip()


def _story_issue_label(story: YuanqiStory | None) -> str:
    """生成开启码绑定剧本的展示文本。"""

    if story is None:
        return "随机"
    return f"**{story.title}**"


def _find_story_with_suffix_trimming(value: str, stories: list[YuanqiStory]) -> tuple[YuanqiStory | None, str]:
    """优先按完整输入匹配；如果尾部混入了额外 token，则逐段剥掉重试。

    QQ 入口偶尔会把一串额外标识拼到参数后面，缘契剧本名本身没有空格，
    所以这里允许把最后一段“脏尾巴”剥掉后再查找，不影响正常剧本标题。
    """

    current = str(value or "").strip()
    while current:
        story = find_story(current, stories)
        if story:
            return story, current

        parts = current.split()
        if len(parts) <= 1:
            break
        current = " ".join(parts[:-1]).strip()

    return None, str(value or "").strip()


service = YuanqiService(db)
