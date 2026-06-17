"""宗门战公共规则。"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
import sqlite3

from .common import now, ts


SECT_WAR_REWARD_ITEM_ID = "cuifengdan"
SECT_WAR_REWARD_ITEM_NAME = "淬锋丹"
SECT_WAR_SECT_REWARD_RATE = 0.30
SECT_WAR_PERSONAL_REWARD_RATE = 0.15
SECT_WAR_REWARD_TYPE_SECT_RANDOM = "sect_random"
SECT_WAR_REWARD_TYPE_PERSONAL_TOP = "personal_top"


def sect_war_cycle_bounds(value: datetime | None = None) -> tuple[str, str]:
    """返回当前宗门战周期，周一开始，下周一零点结束。"""

    current = value or now()
    current_date = current.date()
    start = current_date - timedelta(days=current.weekday())
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def sect_war_display_cycle_end(cycle_end: str) -> str:
    """周期结束日展示为周日。"""

    return (datetime.fromisoformat(cycle_end).date() - timedelta(days=1)).isoformat()


def sect_war_cycle_finished(cycle_end: str, value: datetime | None = None) -> bool:
    """判断某个周期是否已经进入可结算时间。

    周日是本周期领取日；虽然周期边界到下周一零点，
    但周日全天不再计分，可以生成并领取本期奖励。
    """

    current = value or now()
    if current >= datetime.fromisoformat(cycle_end):
        return True
    cycle_start = datetime.fromisoformat(cycle_end).date() - timedelta(days=7)
    return current.date() >= cycle_start + timedelta(days=6)


def sect_war_qualified_count(total: int) -> int:
    """前 20% 宗门入围，向上取整。"""

    return ceil(max(0, int(total)) * 0.2) if total > 0 else 0


def sect_war_reward_member_count(total: int) -> int:
    """入围宗门 30% 成员获得奖励，向上取整。"""

    return ceil(max(0, int(total)) * 0.3) if total > 0 else 0


def sect_war_personal_reward_count(total: int) -> int:
    """个人贡献前 15% 获奖，向上取整。"""

    return ceil(max(0, int(total)) * 0.15) if total > 0 else 0


def sect_war_is_member_locked(value: datetime | None = None) -> bool:
    """周六和周日锁定宗门成员变动。"""

    current = value or now()
    return current.weekday() in (5, 6)


def sect_war_in_battle_window(value: datetime | None = None) -> bool:
    """宗门战斗计分窗口：周一到周六。"""

    current = value or now()
    return current.weekday() in (0, 1, 2, 3, 4, 5)


def sect_war_in_reward_claim_window(value: datetime | None = None) -> bool:
    """宗门战奖励领取窗口：周日全天。"""

    current = value or now()
    return current.weekday() == 6


def sect_war_member_lock_text(value: datetime | None = None) -> str:
    """展示当前成员变动规则。"""

    if sect_war_is_member_locked(value):
        return "锁定中，周六/周日不能建立、加入或退出宗门"
    return "开放中，周一到周五可以加入或退出"


def sect_war_robbery_influence(*, success: bool, item_value: int, battle: dict) -> int:
    """按抢劫结果计算宗门影响力。"""

    actions = battle.get("actions")
    action_count = len(actions) if isinstance(actions, list) else 0
    left_level = max(1, int(battle.get("left_level", 1) or 1))
    right_level = max(1, int(battle.get("right_level", 1) or 1))
    difficulty = max(1, right_level)
    level_gap = max(-20, right_level - left_level)
    duration_bonus = min(30, action_count * 2)
    difficulty_bonus = min(80, difficulty * 2 + max(0, level_gap) * 4)
    value_bonus = min(400, max(0, int(item_value)) // 120)
    if success:
        return max(20, 30 + duration_bonus + difficulty_bonus + value_bonus)
    return max(8, 10 + duration_bonus // 2 + difficulty_bonus // 3)


def record_sect_robbery_influence_conn(
    conn: sqlite3.Connection,
    client_id: str,
    *,
    sect_id: int,
    success: bool,
    item_value: int,
    battle: dict,
    detail: str = "",
    occurred_at: datetime | None = None,
) -> int:
    """把抢劫产生的宗门影响力记到抢劫者当时所属宗门。"""

    occurred_time = occurred_at or now()
    if not sect_war_in_battle_window(occurred_time):
        return 0
    if sect_id <= 0:
        return 0

    influence = sect_war_robbery_influence(success=success, item_value=item_value, battle=battle)
    if influence <= 0:
        return 0
    cycle_start, cycle_end = sect_war_cycle_bounds(occurred_time)
    conn.execute(
        """
        INSERT INTO sect_influence_records
        (sect_id, client_id, action, influence, item_value, success, cycle_start, cycle_end, detail, created_at)
        VALUES (?, ?, '抢劫', ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sect_id, cycle_start) DO UPDATE SET
            client_id = excluded.client_id,
            action = excluded.action,
            influence = sect_influence_records.influence + excluded.influence,
            item_value = sect_influence_records.item_value + excluded.item_value,
            success = sect_influence_records.success + excluded.success,
            cycle_end = excluded.cycle_end,
            detail = excluded.detail,
            created_at = excluded.created_at
        """,
        (
            int(sect_id),
            client_id,
            influence,
            max(0, int(item_value)),
            1 if success else 0,
            cycle_start,
            cycle_end,
            detail,
            ts(occurred_time),
        ),
    )
    conn.execute(
        """
        INSERT INTO sect_contribution_records
        (sect_id, client_id, influence, item_value, success, cycle_start, cycle_end, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sect_id, client_id, cycle_start) DO UPDATE SET
            influence = sect_contribution_records.influence + excluded.influence,
            item_value = sect_contribution_records.item_value + excluded.item_value,
            success = sect_contribution_records.success + excluded.success,
            cycle_end = excluded.cycle_end,
            detail = excluded.detail,
            created_at = excluded.created_at
        """,
        (
            int(sect_id),
            client_id,
            influence,
            max(0, int(item_value)),
            1 if success else 0,
            cycle_start,
            cycle_end,
            detail,
            ts(occurred_time),
        ),
    )
    return influence
