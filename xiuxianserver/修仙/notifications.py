"""玩家回复头下方的轻量通知。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .common import business_day, dt, load_json, row_value
from .constants import (
    ENCOUNTER_SECONDS,
    EXPLORE_MINUTES,
    REST_FAST_SECONDS,
    REST_FULL_MINUTES,
    TRADE_ACTIVE_WINDOW_DAYS,
)
from .rules import trade_daily_reward_thresholds, trade_global_soft_line, trade_player_soft_line

NOTICE_PREFIX = "🔴 通知："
DEFAULT_NOTICE_LIMIT = 3


@dataclass(frozen=True)
class Notification:
    """一条适合常驻展示的用户待办。"""

    key: str
    text: str
    priority: int


def notification_line(client_id: str, database: Any, limit: int = DEFAULT_NOTICE_LIMIT) -> str:
    """生成通知栏文本；查询失败时静默，避免回复出口被通知拖垮。"""

    try:
        notifications = collect_notifications(client_id, database)
    except Exception:
        return ""
    if not notifications:
        return ""
    ordered = sorted(notifications, key=lambda item: item.priority)
    texts = [item.text for item in ordered[: max(1, int(limit))]]
    return f"{NOTICE_PREFIX}{'｜'.join(texts)}"


def collect_notifications(
    client_id: str,
    database: Any,
    *,
    current_time: datetime | None = None,
) -> list[Notification]:
    """收集强通知：只提示已经成熟、错过会亏、需要用户处理的事项。"""

    current = current_time or _now()
    result: list[Notification] = []
    result.extend(_player_state_notifications(client_id, database, current))
    result.extend(_exploration_notifications(client_id, database, current))
    result.extend(_reward_notifications(client_id, database, current))
    result.extend(_duel_request_notifications(client_id, database, current))
    return _dedupe_notifications(result)


def _player_state_notifications(client_id: str, database: Any, current: datetime) -> list[Notification]:
    row = database.fetch_one(
        """
        SELECT status, hp, max_hp, mp, max_mp, rest_full_at, rest_window_elapsed_seconds
        FROM players
        WHERE client_id = ?
        """,
        (client_id,),
    )
    if not row:
        return []

    result: list[Notification] = []
    status = str(row_value(row, "status", "") or "")
    hp = int(row_value(row, "hp", 0) or 0)
    mp = int(row_value(row, "mp", 0) or 0)
    if status != "休息中" and (hp <= 0 or mp <= 0):
        result.append(Notification("critical_state", "重伤待休息", 10))

    if status == "休息中":
        if _rest_ready(row, current):
            result.append(Notification("rest_ready", "休息可结束", 20))
    return result


def _exploration_notifications(client_id: str, database: Any, current: datetime) -> list[Notification]:
    row = database.fetch_one(
        """
        SELECT started_at, ready_at, result
        FROM exploration_records
        WHERE client_id = ? AND claimed = 0
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    if not row:
        return []
    ready_at = _effective_exploration_ready_at(row)
    if ready_at and current >= ready_at:
        return [Notification("exploration_ready", "探险可结束", 30)]
    return []


def _reward_notifications(client_id: str, database: Any, current: datetime) -> list[Notification]:
    checks: tuple[tuple[str, str, int, str, tuple[Any, ...]], ...] = (
        (
            "boss_reward",
            "首领奖励待领",
            40,
            """
            SELECT 1
            FROM seasonal_boss_events AS e
            JOIN seasonal_boss_participants AS p ON p.event_id = e.event_id
            WHERE p.client_id = ?
              AND p.reward_claimed = 0
              AND e.status IN ('已击破', '已退去')
            LIMIT 1
            """,
            (client_id,),
        ),
        (
            "wormhole_reward",
            "虫洞奖励待领",
            50,
            """
            SELECT 1
            FROM wormholes AS w
            JOIN wormhole_participants AS p ON p.wormhole_id = w.wormhole_id
            WHERE p.client_id = ?
              AND p.reward_claimed = 0
              AND w.status IN ('已击杀', '已退去')
            LIMIT 1
            """,
            (client_id,),
        ),
    )
    result = [
        Notification(key, text, priority)
        for key, text, priority, sql, params in checks
        if database.fetch_one(sql, params)
    ]

    pending_sect_reward = database.fetch_one(
        """
        SELECT 1
        FROM sect_war_rewards
        WHERE client_id = ? AND claimed = 0
        LIMIT 1
        """,
        (client_id,),
    )
    if pending_sect_reward:
        result.append(Notification("sect_war_reward", "宗门战奖励待领", 60))
    if _trade_reward_ready(client_id, database, current):
        result.append(Notification("trade_reward", "跑商奖励待领", 65))
    return result


def _trade_reward_ready(client_id: str, database: Any, current: datetime) -> bool:
    """判断今日普通跑商奖励是否已达到领取条件。"""

    day = business_day(current)
    claimed = database.fetch_one(
        """
        SELECT 1
        FROM trade_daily_rewards
        WHERE client_id = ? AND business_day = ?
        LIMIT 1
        """,
        (client_id, day),
    )
    if claimed:
        return False
    stat = database.fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN action = 'sell' THEN quantity ELSE 0 END), 0) AS quantity,
            COALESCE(SUM(
                CASE
                    WHEN action = 'sell' THEN total_price - fee
                    WHEN action = 'buy' THEN -(total_price + fee)
                    ELSE 0
                END
            ), 0) AS net_profit
        FROM trade_records
        WHERE client_id = ?
          AND business_day = ?
          AND action IN ('buy', 'sell')
        """,
        (client_id, day),
    )
    quantity = int(row_value(stat, "quantity", 0) or 0) if stat else 0
    net_profit = int(row_value(stat, "net_profit", 0) or 0) if stat else 0
    if quantity <= 0 or net_profit <= 0:
        return False
    active_count = _active_trade_player_count(database, current)
    global_soft = trade_global_soft_line(active_count)
    player_soft = trade_player_soft_line(active_count, global_soft)
    min_quantity, min_net = trade_daily_reward_thresholds(player_soft)
    return quantity >= min_quantity or net_profit >= min_net


def _active_trade_player_count(database: Any, current: datetime) -> int:
    """读取近期活跃人数，用来和跑商实际奖励门槛保持一致。"""

    cutoff = _ts(current - timedelta(days=TRADE_ACTIVE_WINDOW_DAYS))
    row = database.fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM players p
        WHERE p.created_at >= ?
           OR EXISTS (SELECT 1 FROM game_logs g WHERE g.client_id = p.client_id AND g.created_at >= ?)
           OR EXISTS (SELECT 1 FROM trade_records t WHERE t.client_id = p.client_id AND t.created_at >= ?)
           OR EXISTS (SELECT 1 FROM exploration_records e WHERE e.client_id = p.client_id AND e.started_at >= ?)
           OR EXISTS (SELECT 1 FROM wormhole_participants wp WHERE wp.client_id = p.client_id AND wp.updated_at >= ?)
           OR EXISTS (SELECT 1 FROM seasonal_boss_participants sp WHERE sp.client_id = p.client_id AND sp.updated_at >= ?)
           OR EXISTS (SELECT 1 FROM duel_records d WHERE (d.from_client_id = p.client_id OR d.to_client_id = p.client_id) AND d.created_at >= ?)
           OR EXISTS (SELECT 1 FROM combat_logs c WHERE c.client_id = p.client_id AND c.created_at >= ?)
        """,
        (cutoff, cutoff, cutoff, cutoff, cutoff, cutoff, cutoff, cutoff),
    )
    return max(1, int(row_value(row, "count", 0) or 0))


def _duel_request_notifications(client_id: str, database: Any, current: datetime) -> list[Notification]:
    row = database.fetch_one(
        """
        SELECT 1
        FROM duel_requests
        WHERE to_client_id = ?
          AND status = '等待'
          AND datetime(expires_at) > datetime(?)
        LIMIT 1
        """,
        (client_id, _ts(current)),
    )
    if row:
        return [Notification("duel_request", "对战请求待处理", 70)]
    return []


def _effective_exploration_ready_at(row: Any) -> datetime | None:
    ready_at = dt(str(row_value(row, "ready_at", "") or ""))
    started_at = dt(str(row_value(row, "started_at", "") or ""))
    if not ready_at or not started_at:
        return ready_at
    result = load_json(row_value(row, "result", "{}"), {})
    duration_seconds = _exploration_duration_seconds(result)
    expected_ready_at = started_at if duration_seconds <= 0 else started_at + _seconds_offset(duration_seconds)
    if ready_at > expected_ready_at:
        return expected_ready_at
    return ready_at


def _exploration_duration_seconds(result: Any) -> int:
    if not isinstance(result, dict):
        return EXPLORE_MINUTES * 60
    for key in ("duration_seconds", "total_seconds"):
        value = result.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return max(ENCOUNTER_SECONDS, int(value))
    realm = result.get("secret_realm")
    if isinstance(realm, dict):
        value = realm.get("duration_seconds")
        if isinstance(value, (int, float)) and value > 0:
            return max(ENCOUNTER_SECONDS, int(value))
    return EXPLORE_MINUTES * 60


def _dedupe_notifications(notifications: list[Notification]) -> list[Notification]:
    result: list[Notification] = []
    seen: set[str] = set()
    for item in sorted(notifications, key=lambda value: value.priority):
        if item.key in seen:
            continue
        seen.add(item.key)
        result.append(item)
    return result


def _rest_ready(player: Any, current: datetime) -> bool:
    rest_full_at = dt(str(row_value(player, "rest_full_at", "") or ""))
    if not rest_full_at:
        return False
    full_seconds = REST_FULL_MINUTES * 60
    elapsed = max(0, min(full_seconds, int(row_value(player, "rest_window_elapsed_seconds", 0) or 0)))
    remaining_seconds = max(0, full_seconds - elapsed)
    active_started_at = rest_full_at - timedelta(seconds=remaining_seconds)
    active_seconds = max(0, int((current - active_started_at).total_seconds()))
    return active_seconds >= REST_FAST_SECONDS


def _seconds_offset(seconds: int):
    return timedelta(seconds=max(0, int(seconds)))


def _now() -> datetime:
    from .common import now

    return now()


def _ts(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


__all__ = [
    "DEFAULT_NOTICE_LIMIT",
    "NOTICE_PREFIX",
    "Notification",
    "collect_notifications",
    "notification_line",
]
