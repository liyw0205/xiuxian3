"""修仙模块通用能力。

根目录只放基础函数和公共服务，不反向导入各个玩法包。
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterable

from .constants import (
    BATTLE_RECORD_RETENTION_DAYS,
    DAY_RESET_HOUR,
    DEFAULT_BACKPACK_LIMIT,
    DEFAULT_LOCATION,
    DEFAULT_WEIGHT_LIMIT,
    EQUIPMENT_SLOTS,
    FIXED_EQUIPMENT_SLOT_FACTORS,
    MAX_LEVEL,
    RENAME_COOLDOWN_HOURS,
    WEAPON_TYPE_INTERVAL_FACTORS,
)
from .markdown_utils import append_suggest_commands
from .rules import base_attack, damage_after_defense, defense, exp_need, level_from_exp, max_hp, max_mp, money

FORTUNE_POOL = (
    ("平运", "山河无事，适合稳稳修行。", {}),
    ("小吉", "袖中有风，适合出门寻机缘。", {"explore_bonus": 0.04}),
    ("中吉", "市声入怀，买卖时少些磕绊。", {"trade_bonus": 0.03}),
    ("上吉", "灵台清明，调息恢复更顺。", {"recover_bonus": 0.08}),
    ("轻身", "云履无痕，斗法时身形更活。", {"dodge_bonus": 0.04}),
    ("定心", "心火不摇，承伤更稳。", {"crit_resist_bonus": 0.05}),
    ("天眷", "今日天光偏爱，万事都略顺半分。", {"explore_bonus": 0.08, "recover_bonus": 0.05}),
    ("破云", "心气如剑，出手时更敢一线。", {"damage_reduce": 0.03, "dodge_bonus": 0.03}),
)

def now() -> datetime:
    """返回当前时间。"""

    return datetime.now()


def ts(value: datetime | None = None) -> str:
    """把时间转成数据库保存的字符串。"""

    return (value or now()).isoformat(timespec="seconds")


def dt(value: str | None) -> datetime | None:
    """把数据库时间字符串转成时间对象。"""

    if not value:
        return None
    return datetime.fromisoformat(value)


def business_day(value: datetime | None = None) -> str:
    """按每日 04:00 计算业务日。"""

    return ((value or now()) - timedelta(hours=DAY_RESET_HOUR)).date().isoformat()


def to_int(value: object, default: int = 0) -> int:
    """把输入转成整数。"""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def load_json(text: object, default: Any = None) -> Any:
    """安全读取 JSON 字段。"""

    if default is None:
        default = {}
    if not text:
        return default
    try:
        return json.loads(str(text))
    except json.JSONDecodeError:
        return default


def dump_json(data: Any) -> str:
    """把对象保存成 JSON 文本。"""

    return json.dumps(data, ensure_ascii=False)


def validate_name(name: str) -> tuple[bool, str]:
    """校验展示名称。"""

    clean = name.strip()
    if len(clean) < 2 or len(clean) > 12:
        return False, "名称需要 2 到 12 个字符。"
    if any(ch.isspace() for ch in clean):
        return False, "名称中不能包含空白字符。"
    return True, clean


def row_value(row: Any, key: str, default: Any = "") -> Any:
    """从 dict 或 sqlite.Row 里安全取值。"""

    if row is None:
        return default
    try:
        if hasattr(row, "get"):
            value = row.get(key, default)
        else:
            value = row[key]
    except (IndexError, KeyError, TypeError):
        return default
    return default if value is None else value


def custom_label(base_name: object, custom_name: object = "") -> str:
    """优先展示自定义名，同时保留原名方便识别。"""

    base = str(base_name or "").strip()
    custom = str(custom_name or "").strip()
    return f"{custom}（{base}）" if custom else base


def fixed_equipment_label(equipment: Any) -> str:
    """装备展示名：自定义名（原部位）。"""

    return custom_label(row_value(equipment, "slot"), row_value(equipment, "custom_name"))


def weapon_label_name(weapon: Any) -> str:
    """武器展示名：自定义名（原模板名）。"""

    return custom_label(row_value(weapon, "name"), row_value(weapon, "custom_name"))


def enchant_label_name(enchant_name: object, custom_name: object = "") -> str:
    """附魔展示名：自定义名（原技能书名）。"""

    return custom_label(enchant_name, custom_name)


def hint(reason: str, suggestion: str) -> str:
    """把失败原因和下一步建议拼成统一回复。"""
    # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

    return append_suggest_commands(reason, suggestion)


def equipment_item_use_hint(item: dict[str, Any]) -> str:
    """按纳戒物品类型给出正确消耗入口。"""
    # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。


    if item["name"] == "洗髓液":
        return "<洗髓><宝石><武器>"
    if item["category"] == "宝石":
        return "宝石请发送：镶嵌 装备位 孔位号 宝石名称；同名多等级时加等级，例如：护心玉 2级。<洗髓><宝石><武器>"
    if item["category"] == "技能书":
        return "技能书请发送：附魔武器 武器ID 技能书名。<洗髓><宝石><武器>"
    if item["name"] == "开孔器":
        return "开孔器请发送：开孔 装备位。<洗髓><宝石><武器>"
    return "只有恢复类物品可以直接发送：使用 物品名。<洗髓><宝石><武器>"


def split_words(message: str) -> list[str]:
    """按空白拆参数。"""

    return [part for part in message.strip().split() if part]


def parse_name_level(text: str) -> tuple[str, int | None]:
    """解析“名称 2级 / 名称 Lv2”，没有等级时返回 None。"""

    parts = split_words(text)
    if not parts:
        return "", None

    token = parts[-1].strip().lower()
    level_text = ""
    if token.endswith("级"):
        level_text = token[:-1]
    elif token.startswith("lv"):
        level_text = token[2:]

    if level_text.isdigit() and len(parts) > 1:
        return " ".join(parts[:-1]), max(1, to_int(level_text, 1))
    return text.strip(), None


def parse_weapon_ref(text: str) -> int:
    """把 武器#12 / 武器ID12 / #12 / 12 转成武器实例 ID。"""

    value = text.strip()
    for prefix in ("武器#", "武器ID", "武器", "#"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return to_int(value)


def quality_factor(quality: str) -> float:
    """返回品质系数。"""

    return {"凡品": 1.0, "良品": 1.4, "珍品": 2.0, "稀品": 3.0}.get(quality, 1.0)


def random_quality() -> str:
    """随机品质。"""

    return random.choices(("凡品", "良品", "珍品", "稀品"), weights=(60, 28, 10, 2), k=1)[0]


class CoreService:
    """所有玩法服务共享的基础能力。"""

    def __init__(self, database: Any) -> None:
        self.db = database

    def player(self, client_id: str) -> dict[str, Any] | None:
        """读取玩家。"""

        return self.db.fetch_one("SELECT * FROM players WHERE client_id = ?", (client_id,))

    def equipped_weapon_row(self, client_id: str) -> dict[str, Any] | None:
        """读取玩家当前装备的武器；不自动补初始武器。"""

        return self.db.fetch_one(
            """
            SELECT w.*, d.name, d.drop_location, d.base_attack, d.weapon_type
            FROM player_weapons w
            JOIN weapon_defs d ON d.weapon_def_id = w.weapon_def_id
            WHERE w.owner_id = ? AND w.equipped = 1
            LIMIT 1
            """,
            (client_id,),
        )

    def player_name_taken(self, display_name: str, exclude_client_id: str | None = None) -> bool:
        """判断展示名称是否已被其他玩家使用。"""

        if exclude_client_id is None:
            row = self.db.fetch_one(
                "SELECT 1 FROM players WHERE display_name = ? LIMIT 1",
                (display_name,),
            )
        else:
            row = self.db.fetch_one(
                "SELECT 1 FROM players WHERE display_name = ? AND client_id != ? LIMIT 1",
                (display_name, exclude_client_id),
            )
        return bool(row)

    def recycle_location(self, location_name: str, recycle_type: str | None = None) -> dict[str, Any] | None:
        """读取系统回收地点；可按类型过滤。"""

        name = location_name.strip()
        if recycle_type is None:
            return self.db.fetch_one("SELECT * FROM recycle_locations WHERE name = ?", (name,))
        return self.db.fetch_one(
            "SELECT * FROM recycle_locations WHERE name = ? AND recycle_type = ?",
            (name, recycle_type),
        )

    def require_player(self, client_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """要求玩家已创建。"""

        player = self.player(client_id)
        if not player:
            return None, hint("你还没有创建用户。", "发送：创建用户 名称，例如：创建用户 青衫客")
        return player, None

    def cleanup_battle_records(self, force: bool = False) -> None:
        """每天最多清理一次 7 天前的战斗记录，避免详细日志长期堆积。"""

        today = business_day()
        cutoff = ts(now() - timedelta(days=BATTLE_RECORD_RETENTION_DAYS))
        with self.db.transaction() as conn:
            if not force:
                row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'battle_cleanup_day'",
                ).fetchone()
                if row and row["value"] == today:
                    return
            conn.execute("DELETE FROM combat_logs WHERE created_at < ?", (cutoff,))
            conn.execute("DELETE FROM duel_records WHERE created_at < ?", (cutoff,))
            conn.execute(
                """
                DELETE FROM duel_requests
                WHERE status != '等待' AND created_at < ?
                """,
                (cutoff,),
            )
            conn.execute(
                """
                DELETE FROM exploration_records
                WHERE claimed = 1 AND COALESCE(finished_at, started_at) < ?
                """,
                (cutoff,),
            )
            old_wormholes = conn.execute(
                """
                SELECT wormhole_id FROM wormholes
                WHERE status != '开启' AND COALESCE(killed_at, closes_at, opened_at) < ?
                """,
                (cutoff,),
            ).fetchall()
            for row in old_wormholes:
                conn.execute("DELETE FROM wormhole_notices WHERE wormhole_id = ?", (row["wormhole_id"],))
                conn.execute("DELETE FROM wormhole_participants WHERE wormhole_id = ?", (row["wormhole_id"],))
                conn.execute("DELETE FROM wormholes WHERE wormhole_id = ?", (row["wormhole_id"],))

            old_bosses = conn.execute(
                """
                SELECT event_id FROM seasonal_boss_events
                WHERE status != '开启' AND COALESCE(killed_at, closes_at, opened_at) < ?
                """,
                (cutoff,),
            ).fetchall()
            for row in old_bosses:
                conn.execute("DELETE FROM seasonal_boss_participants WHERE event_id = ?", (row["event_id"],))
                conn.execute("DELETE FROM seasonal_boss_events WHERE event_id = ?", (row["event_id"],))
            conn.execute(
                """
                INSERT INTO schema_meta (key, value)
                VALUES ('battle_cleanup_day', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (today,),
            )

    def create_player(self, client_id: str, display_name: str) -> str:
        """创建玩家。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。


        if self.player(client_id):
            return hint("你已经创建过用户了。", "发送：修仙信息 查看角色，或发送：改名 新名称<指南><探险><修仙帮助>")
        ok, result = validate_name(display_name)
        if not ok:
            return hint(result, "请换一个 2 到 12 个字符、且不含空白的名称。")
        if self.player_name_taken(result):
            return hint("这个名称已经被使用了。", "请换一个不重复的名称后再创建用户。")

        hp = max_hp(1, 0)
        mp = max_mp(1)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO players (
                    client_id, display_name, level, exp, hp, max_hp, mp, max_mp,
                    physique_id, physique, base_attack, defense, source_stones, status,
                    location_name, x, y, backpack_limit, weight_limit, created_at
                )
                VALUES (?, ?, 1, 0, ?, ?, ?, ?, 'fanti', 0, ?, ?, 0, '空闲',
                        ?, 0, 0, ?, ?, ?)
                """,
                (
                    client_id,
                    result,
                    hp,
                    hp,
                    mp,
                    mp,
                    base_attack(1),
                    defense(1, 0),
                    DEFAULT_LOCATION,
                    DEFAULT_BACKPACK_LIMIT,
                    DEFAULT_WEIGHT_LIMIT,
                    ts(),
                ),
            )
            if cursor.rowcount <= 0:
                if conn.execute("SELECT 1 FROM players WHERE client_id = ?", (client_id,)).fetchone():
                    return hint("你已经创建过用户了。", "发送：修仙信息 查看角色，或发送：改名 新名称")
                if conn.execute("SELECT 1 FROM players WHERE display_name = ?", (result,)).fetchone():
                    return hint("这个名称刚刚被别人使用了。", "请换一个不重复的名称后再创建用户。")
                return hint("创建用户失败。", "请稍后重试，或换一个不重复的名称。")
            conn.execute(
                """
                INSERT INTO source_vaults (client_id, level, balance, last_settle_at)
                VALUES (?, 1, 0, ?)
                """,
                (client_id, ts()),
            )
            conn.executemany(
                "INSERT INTO fixed_equipment (client_id, slot, level) VALUES (?, ?, 0)",
                [(client_id, slot) for slot in EQUIPMENT_SLOTS],
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '创建用户', ?, ?)",
                (client_id, result, ts()),
            )
        return f"创建成功，道友 {result}。"

    def rename_player(self, client_id: str, display_name: str) -> str:
        """修改展示名称。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        ok, result = validate_name(display_name)
        if not ok:
            return hint(result, "请换一个 2 到 12 个字符、且不含空白的名称。")
        if result == player["display_name"]:
            return "名称没有变化。<指南><探险><修仙帮助>"
        if self.player_name_taken(result, client_id):
            return hint("这个名称已经被使用了。", "请换一个不重复的新名称。<指南><探险><修仙帮助>")

        last = dt(player.get("last_rename_at"))
        if last and now() - last < timedelta(hours=RENAME_COOLDOWN_HOURS):
            left = timedelta(hours=RENAME_COOLDOWN_HOURS) - (now() - last)
            hours = max(1, int(left.total_seconds() // 3600) + 1)
            return hint(f"改名太频繁，请约 {hours} 小时后再试。", "冷却结束后发送：改名 新名称<指南><探险><修仙帮助>")

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE players
                SET display_name = ?, last_rename_at = ?
                WHERE client_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM players WHERE display_name = ? AND client_id != ?
                  )
                """,
                (result, ts(), client_id, result, client_id),
            )
            if cursor.rowcount <= 0:
                return hint("这个名称刚刚被别人使用了。", "请换一个不重复的新名称。")
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '改名', ?, ?)",
                (client_id, result, ts()),
            )
        return f"改名成功，现在叫 {result}。<指南><探险><修仙帮助>"

    def log(self, client_id: str, action: str, detail: str = "") -> None:
        """写行为日志。"""

        self.db.execute(
            "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (client_id, action, detail, ts()),
        )

    def record_journal(
        self,
        client_id: str,
        milestone_key: str,
        text: str,
        *,
        created_at: str | None = None,
        keep_first_time: bool = False,
    ) -> None:
        """写入或刷新一条玩家日记里程碑。"""

        with self.db.transaction() as conn:
            self.record_journal_conn(
                conn,
                client_id,
                milestone_key,
                text,
                created_at=created_at,
                keep_first_time=keep_first_time,
            )

    def record_journal_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        milestone_key: str,
        text: str,
        *,
        created_at: str | None = None,
        keep_first_time: bool = False,
    ) -> None:
        """在事务里写入或刷新一条玩家日记里程碑。

        player_journals 以 client_id + milestone_key 去重。
        - keep_first_time=True：适合创建角色这类“第一次发生”的记录，只更新文字，不改时间。
        - keep_first_time=False：适合等级、次数、资产等会变化的统计记录，每次刷新都会更新展示。
        """

        current = created_at or ts()
        if keep_first_time:
            conn.execute(
                """
                INSERT INTO player_journals
                (client_id, milestone_key, text, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id, milestone_key)
                DO UPDATE SET text = excluded.text
                """,
                (client_id, milestone_key, text, current),
            )
            return

        conn.execute(
            """
            INSERT INTO player_journals
            (client_id, milestone_key, text, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(client_id, milestone_key)
            DO UPDATE SET text = excluded.text, created_at = excluded.created_at
            """,
            (client_id, milestone_key, text, current),
        )

    def equipment_bonuses(self, client_id: str) -> dict[str, float]:
        """汇总装备和宝石加成。

        装备只给生存属性，宝石和体质按自身效果叠加。
        这里放在公共服务里，所有组件都能读取，不需要二级包互相引用。
        """

        self.db.ensure_fixed_equipment(client_id)
        with self.db.transaction() as conn:
            return self.equipment_bonuses_conn(conn, client_id)

    def equipment_bonuses_conn(self, conn: sqlite3.Connection, client_id: str) -> dict[str, float]:
        """在事务里汇总装备、宝石和体质加成。

        事务内不能调用 ensure_fixed_equipment()，否则会提前 commit 外层事务。
        创建玩家时已经写入装备位，普通查询入口也会兜底补齐。
        """

        bonuses: dict[str, float] = {
            "max_hp_bonus": 0,
            "max_mp_bonus": 0,
            "defense_bonus": 0,
            "dodge_bonus": 0,
            "recover_bonus": 0,
            "explore_bonus": 0,
            "trade_bonus": 0,
            "crit_resist_bonus": 0,
        }

        rows = conn.execute(
            "SELECT slot, level FROM fixed_equipment WHERE client_id = ?",
            (client_id,),
        ).fetchall()
        for row in rows:
            level = int(row["level"])
            factor = FIXED_EQUIPMENT_SLOT_FACTORS.get(row["slot"], 1.0)
            bonuses["max_hp_bonus"] += int(level * 8 * factor)
            bonuses["max_mp_bonus"] += int(level * 3 * factor)
            bonuses["defense_bonus"] += int(level * 2 * factor)

        inlays = conn.execute(
            """
            SELECT i.level, e.effect
            FROM fixed_equipment_inlays i
            JOIN equipment_item_defs e ON e.equipment_item_id = i.gem_id
            WHERE i.client_id = ?
            """,
            (client_id,),
        ).fetchall()
        for row in inlays:
            level = max(1, int(row["level"]))
            effect = load_json(row["effect"], {})
            for key, value in effect.items():
                if not isinstance(value, int | float):
                    continue
                bonus_key = "max_mp_bonus" if key == "mp_bonus" else key
                bonuses[bonus_key] = bonuses.get(bonus_key, 0) + float(value) * level
        physique = conn.execute(
            """
            SELECT d.effect
            FROM players p
            JOIN physique_defs d ON d.physique_id = p.physique_id
            WHERE p.client_id = ?
            """,
            (client_id,),
        ).fetchone()
        if physique:
            for key, value in load_json(physique["effect"], {}).items():
                if isinstance(value, int | float):
                    bonus_key = "max_mp_bonus" if key == "mp_bonus" else key
                    bonuses[bonus_key] = bonuses.get(bonus_key, 0) + float(value)
        fortune = conn.execute(
            """
            SELECT effect
            FROM daily_fortunes
            WHERE client_id = ? AND business_day = ?
            """,
            (client_id, business_day()),
        ).fetchone()
        if fortune:
            for key, value in load_json(fortune["effect"], {}).items():
                if isinstance(value, int | float):
                    bonuses[key] = bonuses.get(key, 0) + float(value)
        return bonuses

    def ensure_daily_fortune(self, client_id: str) -> dict[str, Any]:
        """生成或读取今日气运。"""

        with self.db.transaction() as conn:
            return self.ensure_daily_fortune_conn(conn, client_id)

    def ensure_daily_fortune_conn(self, conn: sqlite3.Connection, client_id: str) -> dict[str, Any]:
        """在事务里生成或读取今日气运。"""

        day = business_day()
        row = conn.execute(
            """
            SELECT * FROM daily_fortunes
            WHERE client_id = ? AND business_day = ?
            """,
            (client_id, day),
        ).fetchone()
        if row:
            return dict(row)

        fortune, flavor, effect = random.choice(FORTUNE_POOL)
        conn.execute(
            """
            INSERT INTO daily_fortunes
            (client_id, business_day, fortune, effect, flavor, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, day, fortune, dump_json(effect), flavor, ts()),
        )
        row = conn.execute(
            """
            SELECT * FROM daily_fortunes
            WHERE client_id = ? AND business_day = ?
            """,
            (client_id, day),
        ).fetchone()
        assert row is not None
        return dict(row)

    def active_title(self, client_id: str) -> str:
        """读取当前自动称号。"""

        row = self.db.fetch_one(
            """
            SELECT title FROM player_titles
            WHERE client_id = ? AND active = 1
            LIMIT 1
            """,
            (client_id,),
        )
        return str(row["title"]) if row else ""

    def refresh_titles(self, client_id: str, player: dict[str, Any] | None = None) -> str:
        """按当前数据刷新称号，并自动佩戴当前最合适的一个。"""

        with self.db.transaction() as conn:
            if player is None:
                row = conn.execute("SELECT * FROM players WHERE client_id = ?", (client_id,)).fetchone()
                if not row:
                    return ""
                player = dict(row)
            return self.refresh_titles_conn(conn, client_id, player)

    def refresh_titles_conn(self, conn: sqlite3.Connection, client_id: str, player: dict[str, Any]) -> str:
        """在事务里刷新称号，并返回自动佩戴的称号。"""

        def count(table: str, where: str, params: tuple[Any, ...]) -> int:
            return self._count_conn(conn, table, where, params)

        def total(sql: str, params: tuple[Any, ...]) -> int:
            row = conn.execute(sql, params).fetchone()
            if not row:
                return 0
            return int(row["total"] or 0)

        vault = conn.execute("SELECT balance FROM source_vaults WHERE client_id = ?", (client_id,)).fetchone()
        vault_balance = int(vault["balance"]) if vault else 0
        source_stones = int(player["source_stones"])
        total_assets = source_stones + vault_balance
        sign_count = count("game_logs", "client_id = ? AND action = '签到'", (client_id,))
        explore_count = count("exploration_records", "client_id = ?", (client_id,))
        trade_sell_count = count("trade_records", "client_id = ? AND action = 'sell'", (client_id,))
        trade_net = total(
            """
            SELECT COALESCE(SUM(total_price - fee), 0) AS total
            FROM trade_records
            WHERE client_id = ? AND action = 'sell'
            """,
            (client_id,),
        )
        weapon_count = count("player_weapons", "owner_id = ?", (client_id,))
        weapon_recycle_count = count("weapon_recycle_records", "client_id = ?", (client_id,))
        gem_recycle_count = count("gem_recycle_records", "client_id = ?", (client_id,))
        book_recycle_count = count("book_recycle_records", "client_id = ?", (client_id,))
        wormhole_count = count("wormhole_participants", "client_id = ?", (client_id,))
        wormhole_damage = total(
            "SELECT COALESCE(SUM(damage), 0) AS total FROM wormhole_participants WHERE client_id = ?",
            (client_id,),
        )
        boss_count = count("seasonal_boss_participants", "client_id = ?", (client_id,))
        boss_damage = total(
            "SELECT COALESCE(SUM(damage), 0) AS total FROM seasonal_boss_participants WHERE client_id = ?",
            (client_id,),
        )
        duel_win_count = count("duel_records", "winner_id = ?", (client_id,))
        inscription_count = count(
            "game_logs",
            "client_id = ? AND action IN ('铭刻装备', '铭刻武器', '铭刻附魔')",
            (client_id,),
        )
        rare_weapon = self._exists_conn(
            conn,
            "player_weapons",
            "owner_id = ? AND quality IN ('稀品', '珍品')",
            (client_id,),
        )
        max_weapon = conn.execute(
            """
            SELECT max_level, level
            FROM player_weapons
            WHERE owner_id = ?
            ORDER BY max_level DESC, level DESC
            LIMIT 1
            """,
            (client_id,),
        ).fetchone()
        max_weapon_level = int(max_weapon["max_level"]) if max_weapon else 0
        highest_weapon_level = int(max_weapon["level"]) if max_weapon else 0

        rules = (
            (10, "初入仙途", "已经创建修仙角色", True),
            (18, "晨钟常客", f"累计签到 {sign_count} 次", sign_count >= 7),
            (20, "小富即安", "随身源石达到 5 万", source_stones >= 50_000),
            (24, "藏源有道", "源库余额达到 10 万", vault_balance >= 100_000),
            (28, "财气盈门", "明面资产达到 30 万", total_assets >= 300_000),
            (30, "探险常客", f"累计探险 {explore_count} 次", explore_count >= 5),
            (34, "山河熟客", f"累计探险 {explore_count} 次", explore_count >= 30),
            (35, "跑商老手", f"普通跑商出售 {trade_sell_count} 次", trade_sell_count >= 20),
            (38, "商路识途", f"跑商净收入 {money(trade_net)}", trade_net >= 100_000),
            (40, "兵器收藏家", f"拥有武器 {weapon_count} 把", weapon_count >= 5),
            (43, "百炼持刃", f"最高武器等级 {highest_weapon_level}", highest_weapon_level >= 40),
            (45, "铸剑客", f"回收武器 {weapon_recycle_count} 次", weapon_recycle_count >= 3),
            (46, "藏经归客", f"回收技能书 {book_recycle_count} 次", book_recycle_count >= 3),
            (47, "琢玉散人", f"回收宝石 {gem_recycle_count} 次", gem_recycle_count >= 3),
            (50, "虫洞先锋", f"参与异界虫洞 {wormhole_count} 次", wormhole_count > 0),
            (52, "虫洞鏖战者", f"虫洞累计伤害 {wormhole_damage}", wormhole_damage >= 20_000),
            (55, "欧气外露", "拥有稀品或珍品武器", rare_weapon),
            (58, "满锋候选", f"最高武器上限 {max_weapon_level}", max_weapon_level >= 80),
            (60, "岁时赴约人", f"挑战岁时首领 {boss_count} 次", boss_count > 0),
            (62, "情劫破阵者", f"首领累计伤害 {boss_damage}", boss_damage >= 20_000),
            (64, "斗法胜手", f"对战胜利 {duel_win_count} 次", duel_win_count >= 3),
            (66, "羽墨留名", f"铭刻 {inscription_count} 次", inscription_count >= 1),
        )
        current = ts()
        valid: list[tuple[int, str]] = []
        for score, title, reason, ok in rules:
            if not ok:
                continue
            valid.append((score, title))
            conn.execute(
                """
                INSERT INTO player_titles
                (client_id, title, reason, active, obtained_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(client_id, title)
                DO UPDATE SET reason = excluded.reason, updated_at = excluded.updated_at
                """,
                (client_id, title, reason, current, current),
            )

        conn.execute("UPDATE player_titles SET active = 0 WHERE client_id = ?", (client_id,))
        if not valid:
            return ""
        active_title = max(valid, key=lambda item: item[0])[1]
        conn.execute(
            """
            UPDATE player_titles
            SET active = 1, updated_at = ?
            WHERE client_id = ? AND title = ?
            """,
            (current, client_id, active_title),
        )
        return active_title

    @staticmethod
    def _count_conn(conn: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]) -> int:
        """在事务里执行简单计数。"""

        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE {where}", params).fetchone()
        return int(row["count"]) if row else 0

    @staticmethod
    def _exists_conn(conn: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]) -> bool:
        """在事务里判断数据是否存在。"""

        return bool(conn.execute(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1", params).fetchone())

    def record_weapon_created_conn(self, conn: sqlite3.Connection, client_id: str, weapon_id: int) -> None:
        """为新武器初始化传奇记录。"""

        if int(weapon_id) <= 0:
            return
        current = ts()
        conn.execute(
            """
            INSERT OR IGNORE INTO weapon_legends
            (weapon_id, original_owner_id, current_owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(weapon_id), client_id, client_id, current, current),
        )

    def record_weapon_combat_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        weapon_id: int,
        *,
        monster_kill: bool = False,
        boss_challenge: bool = False,
        duel_win: bool = False,
        damage: int = 0,
    ) -> None:
        """累积武器传奇数据。"""

        if int(weapon_id) <= 0:
            return
        current = ts()
        conn.execute(
            """
            INSERT INTO weapon_legends
            (weapon_id, original_owner_id, current_owner_id, monster_kills, boss_challenges,
             duel_wins, highest_damage, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(weapon_id)
            DO UPDATE SET
                current_owner_id = excluded.current_owner_id,
                monster_kills = monster_kills + excluded.monster_kills,
                boss_challenges = boss_challenges + excluded.boss_challenges,
                duel_wins = duel_wins + excluded.duel_wins,
                highest_damage = max(highest_damage, excluded.highest_damage),
                updated_at = excluded.updated_at
            """,
            (
                int(weapon_id),
                client_id,
                client_id,
                1 if monster_kill else 0,
                1 if boss_challenge else 0,
                1 if duel_win else 0,
                max(0, int(damage)),
                current,
                current,
            ),
        )

    def weapon_effects_from_ids(self, enchant_ids: object) -> dict[str, float]:
        """按附魔 id 列表汇总武器附魔效果。

        技能书真正参与战斗的是 weapon_enchants 表里的 effect 和 mp_delta。
        这个函数是唯一入口，战斗结算和武器详情都走这里，避免不同玩法漏算技能书。
        """

        effects: dict[str, float] = {}
        if not isinstance(enchant_ids, list):
            return effects
        for enchant_id in enchant_ids:
            row = self.db.fetch_one("SELECT effect, mp_delta FROM weapon_enchants WHERE enchant_id = ?", (enchant_id,))
            if not row:
                continue
            for key, value in load_json(row["effect"], {}).items():
                if isinstance(value, int | float):
                    effects[key] = effects.get(key, 0) + float(value)
            effects["mp_delta"] = effects.get("mp_delta", 0) + int(row["mp_delta"])
        return effects

    def _weapon_effects(self, weapon: dict[str, Any] | None) -> dict[str, float]:
        """读取一把武器已经附魔的全部战斗效果。"""

        if not weapon:
            return {}
        return self.weapon_effects_from_ids(load_json(weapon.get("enchant_effects"), []))

    @staticmethod
    def _merge_effects(*groups: dict[str, float]) -> dict[str, float]:
        """合并装备、宝石、体质和武器附魔效果。"""

        merged: dict[str, float] = {}
        for group in groups:
            for key, value in group.items():
                if isinstance(value, int | float):
                    merged[key] = merged.get(key, 0) + float(value)
        return merged

    @staticmethod
    def _attack_raw(base_attack_value: int, level: int, effects: dict[str, float]) -> int:
        """计算一次普通出手的原始伤害。"""

        stable_bonus = float(effects.get("hit_bonus", 0)) * 0.5
        raw = int(base_attack_value * (1 + stable_bonus))
        return raw + random.randint(0, max(2, int(level) * 2))

    @staticmethod
    def _skill_power(skill: dict[str, Any], effects: dict[str, float]) -> float:
        """计算武器技能实际威力。"""

        power = float(skill["power"])
        power += float(effects.get("skill_power_bonus", 0))
        power += float(effects.get("heavy_bonus", 0))
        power += float(effects.get("single_hit_bonus", 0))
        return max(1.0, power)

    @staticmethod
    def _skill_cost(skill: dict[str, Any] | None, effects: dict[str, float]) -> int:
        """计算武器技能实际精神消耗。"""

        if not skill:
            return 0
        return max(0, int(skill["cost_mp"]) + int(effects.get("mp_delta", 0)))

    @staticmethod
    def _skill_interval(skill: dict[str, Any] | None, weapon: dict[str, Any] | None, effects: dict[str, float]) -> int:
        """计算武器技能速度基准。

        数值越小，技能蓄力越快。它不再表示“固定每 N 回合触发一次”。
        """

        if not skill:
            return 0
        weapon_type = str(weapon.get("weapon_type") if weapon else "")
        type_factor = WEAPON_TYPE_INTERVAL_FACTORS.get(weapon_type, 1.0)
        rate = max(0.6, 1.0 + float(effects.get("interval_rate", 0)))
        interval = round(int(skill["interval"]) * type_factor * rate)
        interval += int(effects.get("interval_delta", 0))
        return max(2, min(12, interval))

    @staticmethod
    def _weapon_attack_load(weapon: dict[str, Any] | None) -> float:
        """计算武器攻击带来的速度负重。

        高攻击武器可以打得疼，但技能条不能也无脑更快。
        这里按武器等级做归一，避免正常升级被过度惩罚。
        """

        if not weapon:
            return 0.0
        attack = max(0, int(weapon.get("attack") or 0))
        level = max(0, int(weapon.get("level") or 0))
        base_line = 28 + level * 2.4
        return max(0.0, (attack - base_line) / max(1.0, base_line))

    @staticmethod
    def _actor_speed(level: int, weapon: dict[str, Any] | None, effects: dict[str, float]) -> float:
        """计算人物行动速度。

        等级提供少量成长，轻武器更快，闪避/命中类效果也会让出手更顺。
        高攻击武器会带来一点负重，避免高攻武器同时成为最快技能流。
        """

        weapon_type = str(weapon.get("weapon_type") if weapon else "")
        type_factor = WEAPON_TYPE_INTERVAL_FACTORS.get(weapon_type, 1.0)
        type_speed = (1.0 / max(0.75, type_factor) - 1.0) * 32
        effect_speed = float(effects.get("dodge_bonus", 0)) * 90 + float(effects.get("hit_bonus", 0)) * 45
        attack_load = CoreService._weapon_attack_load(weapon)
        load_penalty = min(28.0, attack_load * 36.0)
        speed = 96 + min(42, max(0, int(level)) * 0.42) + type_speed + effect_speed - load_penalty
        return max(68.0, min(168.0, speed))

    @staticmethod
    def _skill_charge_gain(
        skill: dict[str, Any] | None,
        weapon: dict[str, Any] | None,
        effects: dict[str, float],
        actor_speed: float,
    ) -> float:
        """计算每次出手获得多少技能蓄力。

        技能速度来自旧的 interval 字段：数值越小，蓄力越快。
        人物速度越高，同样一次出手积累的蓄力也越多。
        """

        if not skill:
            return 0.0
        interval = CoreService._skill_interval(skill, weapon, effects)
        speed_rate = max(0.7, min(1.7, actor_speed / 100))
        attack_load = CoreService._weapon_attack_load(weapon)
        load_rate = max(0.72, 1.0 - min(0.28, attack_load * 0.32))
        gain = (0.78 / interval + 0.18) * speed_rate * load_rate
        return max(0.22, min(0.72, gain))

    @staticmethod
    def _skill_initial_charge(
        skill: dict[str, Any] | None,
        weapon: dict[str, Any] | None,
        effects: dict[str, float],
        actor_speed: float,
    ) -> float:
        """开战时给一点初始蓄力，避免短战完全看不到武器技能。"""

        gain = CoreService._skill_charge_gain(skill, weapon, effects, actor_speed)
        return min(0.9, 0.45 + gain * 0.7)

    @staticmethod
    def _enemy_speed(level: int, kind: str, boss: bool = False) -> float:
        """计算怪物或 Boss 的行动速度。

        怪物没有武器，但也按类型区分打法：妖鬼更快，傀儡和重甲兵更慢。
        Boss 略慢一点，但技能更重，给玩家留下反应空间。
        """

        kind = str(kind or "")
        kind_bonus = {
            "妖": 10,
            "妖君": 10,
            "鬼": 8,
            "游魂": 9,
            "兽": 2,
            "龙": 0,
            "龙影": 0,
            "魔": 4,
            "魔将": 2,
            "兵": -3,
            "古卫": -8,
            "傀": -10,
        }.get(kind, 0)
        boss_penalty = -6 if boss else 0
        speed = 88 + min(36, max(1, int(level)) * 0.36) + kind_bonus + boss_penalty
        return max(62.0, min(150.0, speed))

    @staticmethod
    def _enemy_skill(kind: str, level: int, boss: bool = False) -> dict[str, Any]:
        """生成怪物或 Boss 的技能配置。

        不单独建表，避免为了技能速度重构数据库。
        所有技能仍使用同一套蓄力条：interval 越小越快，power 越大越重。
        """

        kind = str(kind or "")
        boss_bonus = 0.16 if boss else 0.0
        level_bonus = min(0.18, max(1, int(level)) / 600)
        configs = {
            "妖": ("妖影撕咬", 4, 1.12, {"bleed_rate": 0.10}),
            "妖君": ("妖君裂影", 4, 1.18, {"bleed_rate": 0.12}),
            "兽": ("蛮兽冲撞", 5, 1.22, {"stun_rate": 0.08}),
            "龙": ("龙息压顶", 6, 1.30, {"mp_suppress": 0.08}),
            "龙影": ("龙影吐息", 6, 1.32, {"mp_suppress": 0.10}),
            "鬼": ("阴魂噬念", 4, 1.08, {"mp_suppress": 0.10}),
            "游魂": ("游魂缠身", 4, 1.10, {"mp_suppress": 0.08}),
            "魔": ("魔焰灼心", 5, 1.18, {"burn_rate": 0.12}),
            "魔将": ("魔将破阵", 5, 1.24, {"pierce_bonus": 0.08}),
            "兵": ("残兵破甲", 5, 1.16, {"pierce_bonus": 0.06}),
            "古卫": ("古卫镇压", 6, 1.20, {"damage_reduce": 0.08}),
            "傀": ("傀儡重压", 6, 1.18, {"damage_reduce": 0.06}),
        }
        name, interval, power, effects = configs.get(kind, ("凶煞一击", 5, 1.16, {}))
        return {
            "name": name,
            "cost_mp": 0,
            "interval": max(3, int(interval) + (1 if boss and power >= 1.28 else 0)),
            "power": power + boss_bonus + level_bonus,
            "effects": effects,
        }

    @staticmethod
    def _enemy_skill_charge_gain(skill: dict[str, Any], actor_speed: float) -> float:
        """计算怪物或 Boss 每次出手获得多少技能蓄力。"""

        interval = max(3, int(skill.get("interval", 5)))
        speed_rate = max(0.7, min(1.55, actor_speed / 100))
        return max(0.20, min(0.62, (0.66 / interval + 0.16) * speed_rate))

    @staticmethod
    def _enemy_skill_initial_charge(skill: dict[str, Any], actor_speed: float) -> float:
        """怪物/Boss 开场技能条。"""

        gain = CoreService._enemy_skill_charge_gain(skill, actor_speed)
        return min(0.82, 0.30 + gain * 0.65)

    @staticmethod
    def _pierce_rate(effects: dict[str, float]) -> float:
        """把穿透和压防统一成防御穿透率。"""

        return min(0.8, float(effects.get("pierce_bonus", 0)) + float(effects.get("defense_suppress", 0)))

    @staticmethod
    def _combo_damage(raw: int, defense_value: int, effects: dict[str, float]) -> int:
        """按连击类附魔追加一段轻伤害。"""

        if random.random() >= min(0.5, float(effects.get("combo_bonus", 0))):
            return 0
        rate = min(0.8, 0.35 + float(effects.get("combo_damage_bonus", 0)))
        return damage_after_defense(int(raw * rate), defense_value, CoreService._pierce_rate(effects))

    @staticmethod
    def _reduce_damage(damage: int, effects: dict[str, float], skill_used: bool) -> int:
        """计算最终承伤；玄盾书在本回合武器技能触发时生效。"""

        rate = float(effects.get("damage_reduce", 0)) + float(effects.get("crit_resist_bonus", 0))
        if skill_used:
            rate += float(effects.get("shield_bonus", 0))
        return max(1, int(damage * (1 - min(0.7, rate))))

    @staticmethod
    def _suppress_mp(mp: int, max_mp_value: int, effects: dict[str, float]) -> int:
        """按断念类附魔削掉对手精神。"""

        rate = min(0.25, float(effects.get("mp_suppress", 0)))
        if rate <= 0:
            return mp
        return max(0, int(mp) - int(max_mp_value * rate))

    def recalc_player(self, client_id: str) -> dict[str, Any]:
        """按经验重算等级和基础数值。"""

        with self.db.transaction() as conn:
            return self.recalc_player_conn(conn, client_id)

    def recalc_player_conn(self, conn: sqlite3.Connection, client_id: str) -> dict[str, Any]:
        """在事务里按经验重算等级和基础数值。"""

        player = conn.execute("SELECT * FROM players WHERE client_id = ?", (client_id,)).fetchone()
        if not player:
            raise ValueError("玩家不存在")
        level = level_from_exp(player["exp"])
        physique_value = int(player["physique"])
        physique_def = conn.execute(
            "SELECT physique_value FROM physique_defs WHERE physique_id = ?",
            (player["physique_id"],),
        ).fetchone()
        if physique_def:
            physique_value = int(physique_def["physique_value"])
        bonuses = self.equipment_bonuses_conn(conn, client_id)
        hp_max = max_hp(level, physique_value, int(bonuses["max_hp_bonus"]))
        mp_max = max_mp(level, int(bonuses["max_mp_bonus"]))
        attack_value = base_attack(level)
        defense_value = defense(level, physique_value, int(bonuses["defense_bonus"]))
        conn.execute(
            """
            UPDATE players
            SET level = ?, max_hp = ?, max_mp = ?, hp = min(hp, ?), mp = min(mp, ?),
                physique = ?, base_attack = ?, defense = ?
            WHERE client_id = ?
            """,
            (level, hp_max, mp_max, hp_max, mp_max, physique_value, attack_value, defense_value, client_id),
        )
        row = conn.execute("SELECT * FROM players WHERE client_id = ?", (client_id,)).fetchone()
        return dict(row) if row else dict(player)

    def add_exp(self, client_id: str, amount: int) -> tuple[int, int]:
        """增加经验，返回旧等级和新等级。"""

        with self.db.transaction() as conn:
            return self.add_exp_conn(conn, client_id, amount)

    def add_exp_conn(self, conn: sqlite3.Connection, client_id: str, amount: int) -> tuple[int, int]:
        """在事务里增加经验，返回旧等级和新等级。"""

        player = conn.execute("SELECT * FROM players WHERE client_id = ?", (client_id,)).fetchone()
        if not player:
            return 1, 1
        old_level = player["level"]
        conn.execute(
            "UPDATE players SET exp = exp + ? WHERE client_id = ?",
            (max(0, amount), client_id),
        )
        player = self.recalc_player_conn(conn, client_id)
        return old_level, player["level"]

    def add_stones(self, client_id: str, amount: int) -> None:
        """增加随身源石。"""

        if amount <= 0:
            return
        self.db.execute(
            "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
            (amount, client_id),
        )

    def spend_stones_conn(self, conn: sqlite3.Connection, client_id: str, amount: int) -> bool:
        """在事务里扣源石。"""

        if amount < 0:
            return False
        row = conn.execute("SELECT source_stones FROM players WHERE client_id = ?", (client_id,)).fetchone()
        if not row or row["source_stones"] < amount:
            return False
        conn.execute(
            "UPDATE players SET source_stones = source_stones - ? WHERE client_id = ?",
            (amount, client_id),
        )
        return True

    def item_def_by_name(self, name: str) -> dict[str, Any] | None:
        """按名称读取背包物品定义。"""

        return self.db.fetch_one("SELECT * FROM item_defs WHERE name = ?", (name.strip(),))

    def item_def(self, item_id: str) -> dict[str, Any] | None:
        """按 id 读取背包物品定义。"""

        return self.db.fetch_one("SELECT * FROM item_defs WHERE item_id = ?", (item_id,))

    def equipment_item_def_by_name(self, name: str) -> dict[str, Any] | None:
        """按名称读取纳戒物品定义。"""

        return self.db.fetch_one("SELECT * FROM equipment_item_defs WHERE name = ?", (name.strip(),))

    def equipment_item_def(self, equipment_item_id: str) -> dict[str, Any] | None:
        """按 id 读取纳戒物品定义。"""

        return self.db.fetch_one(
            "SELECT * FROM equipment_item_defs WHERE equipment_item_id = ?",
            (equipment_item_id,),
        )

    def add_backpack_conn(self, conn: sqlite3.Connection, client_id: str, item_id: str, quantity: int) -> None:
        """在事务里增加背包物品。"""

        if quantity <= 0:
            return
        conn.execute(
            """
            INSERT INTO backpack_items (client_id, item_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(client_id, item_id)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (client_id, item_id, quantity),
        )

    def can_add_backpack_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        item_id: str,
        quantity: int,
    ) -> tuple[bool, str]:
        """检查背包是否还能放入指定物品。"""

        if quantity <= 0:
            return True, ""

        player = conn.execute(
            "SELECT backpack_limit, weight_limit FROM players WHERE client_id = ?",
            (client_id,),
        ).fetchone()
        item = conn.execute(
            "SELECT name, weight, stack_limit FROM item_defs WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if not player or not item:
            return False, hint("玩家或物品不存在。", "确认已创建用户，并检查物品名称是否正确。")

        weight_row = conn.execute(
            """
            SELECT COALESCE(SUM(b.quantity * i.weight), 0) AS total
            FROM backpack_items b
            JOIN item_defs i ON i.item_id = b.item_id
            WHERE b.client_id = ?
            """,
            (client_id,),
        ).fetchone()
        weight_after = int(weight_row["total"]) + int(item["weight"]) * quantity
        if weight_after > int(player["weight_limit"]):
            return False, hint(
                f"背包负重不足，放入后会变成 {weight_after}/{player['weight_limit']}。",
                "先发送：商场出售 商品名 数量，或发送：商场自动出售 清理跑商货物。",
            )

        current = conn.execute(
            "SELECT quantity FROM backpack_items WHERE client_id = ? AND item_id = ?",
            (client_id, item_id),
        ).fetchone()
        current_quantity = int(current["quantity"]) if current else 0
        if current_quantity + quantity > int(item["stack_limit"]):
            return False, hint(
                f"{item['name']} 堆叠上限不足，最多 {item['stack_limit']}。",
                "先出售或使用一部分同名物品，再重新领取或购买。",
            )

        if not current:
            kind_row = conn.execute(
                "SELECT COUNT(*) AS total FROM backpack_items WHERE client_id = ? AND quantity > 0",
                (client_id,),
            ).fetchone()
            if int(kind_row["total"]) + 1 > int(player["backpack_limit"]):
                return False, hint(
                    f"背包格子不足，最多 {player['backpack_limit']} 种物品。",
                    "先出售不需要的背包物品，再重新领取或购买。",
                )

        return True, ""

    def remove_backpack_conn(self, conn: sqlite3.Connection, client_id: str, item_id: str, quantity: int) -> bool:
        """在事务里扣除背包物品。"""

        row = conn.execute(
            "SELECT quantity FROM backpack_items WHERE client_id = ? AND item_id = ?",
            (client_id, item_id),
        ).fetchone()
        if not row or row["quantity"] < quantity:
            return False
        left = row["quantity"] - quantity
        if left:
            conn.execute(
                "UPDATE backpack_items SET quantity = ? WHERE client_id = ? AND item_id = ?",
                (left, client_id, item_id),
            )
        else:
            conn.execute(
                "DELETE FROM backpack_items WHERE client_id = ? AND item_id = ?",
                (client_id, item_id),
            )
        return True

    def add_ring_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        equipment_item_id: str,
        quantity: int,
    ) -> None:
        """在事务里增加纳戒物品。"""

        if quantity <= 0:
            return
        if self._is_gem_conn(conn, equipment_item_id):
            self.add_gem_conn(conn, client_id, equipment_item_id, 1, quantity)
            return
        conn.execute(
            """
            INSERT INTO ring_items (client_id, equipment_item_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(client_id, equipment_item_id)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (client_id, equipment_item_id, quantity),
        )

    def remove_ring_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        equipment_item_id: str,
        quantity: int,
    ) -> bool:
        """在事务里扣除纳戒物品。"""

        if self._is_gem_conn(conn, equipment_item_id):
            return self.remove_gem_conn(conn, client_id, equipment_item_id, 1, quantity)

        row = conn.execute(
            "SELECT quantity FROM ring_items WHERE client_id = ? AND equipment_item_id = ?",
            (client_id, equipment_item_id),
        ).fetchone()
        if not row or row["quantity"] < quantity:
            return False
        left = row["quantity"] - quantity
        if left:
            conn.execute(
                "UPDATE ring_items SET quantity = ? WHERE client_id = ? AND equipment_item_id = ?",
                (left, client_id, equipment_item_id),
            )
        else:
            conn.execute(
                "DELETE FROM ring_items WHERE client_id = ? AND equipment_item_id = ?",
                (client_id, equipment_item_id),
            )
        return True

    def add_gem_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        gem_id: str,
        level: int,
        quantity: int,
    ) -> None:
        """在事务里增加指定等级的宝石库存。"""

        if quantity <= 0:
            return
        conn.execute(
            """
            INSERT INTO gem_items (client_id, gem_id, level, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(client_id, gem_id, level)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (client_id, gem_id, max(1, int(level)), quantity),
        )

    def remove_gem_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        gem_id: str,
        level: int,
        quantity: int,
    ) -> bool:
        """在事务里扣除指定等级的宝石库存。"""

        row = conn.execute(
            """
            SELECT quantity FROM gem_items
            WHERE client_id = ? AND gem_id = ? AND level = ?
            """,
            (client_id, gem_id, max(1, int(level))),
        ).fetchone()
        if not row or row["quantity"] < quantity:
            return False
        left = row["quantity"] - quantity
        if left:
            conn.execute(
                """
                UPDATE gem_items
                SET quantity = ?
                WHERE client_id = ? AND gem_id = ? AND level = ?
                """,
                (left, client_id, gem_id, max(1, int(level))),
            )
        else:
            conn.execute(
                """
                DELETE FROM gem_items
                WHERE client_id = ? AND gem_id = ? AND level = ?
                """,
                (client_id, gem_id, max(1, int(level))),
            )
        return True

    @staticmethod
    def _is_gem_conn(conn: sqlite3.Connection, equipment_item_id: str) -> bool:
        """判断纳戒物品是否是宝石。"""

        row = conn.execute(
            "SELECT category FROM equipment_item_defs WHERE equipment_item_id = ?",
            (equipment_item_id,),
        ).fetchone()
        return bool(row and row["category"] == "宝石")

    def backpack_weight(self, client_id: str) -> int:
        """计算背包负重。"""

        rows = self.db.fetch_all(
            """
            SELECT b.quantity, i.weight
            FROM backpack_items b
            JOIN item_defs i ON i.item_id = b.item_id
            WHERE b.client_id = ?
            """,
            (client_id,),
        )
        return sum(row["quantity"] * row["weight"] for row in rows)

    def backpack_rows(self, client_id: str) -> list[dict[str, Any]]:
        """读取背包明细。"""

        return self.db.fetch_all(
            """
            SELECT b.item_id, b.quantity, i.name, i.weight, i.category, i.usable, i.base_price, i.effect
            FROM backpack_items b
            JOIN item_defs i ON i.item_id = b.item_id
            WHERE b.client_id = ? AND b.quantity > 0
            ORDER BY i.category, i.name
            """,
            (client_id,),
        )

    def ring_rows(self, client_id: str) -> list[dict[str, Any]]:
        """读取纳戒明细。"""

        rows = self.db.fetch_all(
            """
            SELECT r.equipment_item_id, r.quantity, e.name, e.category, e.usable, e.effect, NULL AS level
            FROM ring_items r
            JOIN equipment_item_defs e ON e.equipment_item_id = r.equipment_item_id
            WHERE r.client_id = ? AND r.quantity > 0
              AND e.category != '宝石'
            ORDER BY e.category, e.name
            """,
            (client_id,),
        )
        rows.extend(self.gem_rows(client_id))
        return sorted(rows, key=lambda row: (row["category"], row["name"], row.get("level") or 0))

    def gem_rows(self, client_id: str) -> list[dict[str, Any]]:
        """读取纳戒里按等级分组的宝石库存。"""

        return self.db.fetch_all(
            """
            SELECT g.gem_id AS equipment_item_id, g.quantity, g.level,
                   e.name, e.category, e.quality, e.usable, e.effect
            FROM gem_items g
            JOIN equipment_item_defs e ON e.equipment_item_id = g.gem_id
            WHERE g.client_id = ? AND g.quantity > 0
            ORDER BY e.name, g.level
            """,
            (client_id,),
        )

    def resolve_gem_level_conn(
        self,
        conn: sqlite3.Connection,
        client_id: str,
        gem_id: str,
        gem_name: str,
        wanted_level: int | None,
        example_template: str,
    ) -> tuple[int | None, str | None]:
        """确定要操作的宝石等级；同名多等级时要求用户写清等级。"""

        if wanted_level is not None:
            return wanted_level, None

        rows = conn.execute(
            """
            SELECT level, quantity FROM gem_items
            WHERE client_id = ? AND gem_id = ? AND quantity > 0
            ORDER BY level
            """,
            (client_id, gem_id),
        ).fetchall()
        if not rows:
            return 1, None
        if len(rows) == 1:
            return int(rows[0]["level"]), None

        level = int(rows[-1]["level"])
        example = example_template.format(name=gem_name, level=level)
        options = "、".join(f"{row['level']}级x{row['quantity']}" for row in rows)
        return None, hint(
            f"纳戒里有多种等级的 {gem_name}。",
            f"请写清等级，例如：{example}。现有：{options}",
        )

    def format_player_name(self, client_id: str) -> str:
        """返回玩家展示名；对外回复不展示 client_id。"""

        player = self.player(client_id)
        if not player:
            return "未知道友"
        return str(player["display_name"])

    def next_level_text(self, player: dict[str, Any]) -> str:
        """返回升级进度文本。"""

        if player["level"] >= MAX_LEVEL:
            return "已满级"
        need_total = sum(exp_need(level) for level in range(1, player["level"] + 1))
        current = player["exp"] - sum(exp_need(level) for level in range(1, player["level"]))
        need = exp_need(player["level"])
        return f"{current}/{need}"


def format_effect(effect_text: str) -> str:
    """把物品效果 JSON 转成展示文本。"""

    effect = load_json(effect_text, {})
    parts: list[str] = []
    if effect.get("exp_delta"):
        parts.append(f"经验+{effect['exp_delta']}")
    if effect.get("random_exp_min") is not None:
        parts.append(f"经验+{effect['random_exp_min']}-{effect['random_exp_max']}")
    if effect.get("random_stones_min") is not None:
        parts.append(f"源石+{effect['random_stones_min']}-{effect['random_stones_max']}")
    if effect.get("random_stones_segments"):
        texts = []
        for segment in effect["random_stones_segments"]:
            if not isinstance(segment, dict):
                continue
            texts.append(f"{segment.get('min_level')}-{segment.get('max_level')}级:" f"{segment.get('min')}-{segment.get('max')}")
        if texts:
            parts.append("源石按等级段随机(" + "；".join(texts) + ")")
    if effect.get("hp_delta"):
        parts.append(f"血气+{effect['hp_delta']}")
    if effect.get("mp_delta"):
        parts.append(f"精神+{effect['mp_delta']}")
    if effect.get("hp_ratio"):
        parts.append(f"血气+{int(effect['hp_ratio'] * 100)}%")
    if effect.get("mp_ratio"):
        parts.append(f"精神+{int(effect['mp_ratio'] * 100)}%")
    if effect.get("wash_physique"):
        parts.append("洗髓体质，大概率升阶，小概率回落")
    if effect.get("enchant_id"):
        parts.append("武器附魔")
    bonus_labels = {
        "max_hp_bonus": "血气上限",
        "max_mp_bonus": "精神上限",
        "mp_bonus": "精神上限",
        "defense_bonus": "防御",
    }
    for key, label in bonus_labels.items():
        value = effect.get(key)
        if isinstance(value, int | float) and value:
            parts.append(f"{label}{value:+g}")
    rate_labels = {
        "dodge_bonus": "闪避",
        "recover_bonus": "恢复",
        "explore_bonus": "探险",
        "crit_resist_bonus": "承伤减免",
    }
    for key, label in rate_labels.items():
        value = effect.get(key)
        if isinstance(value, int | float) and value:
            parts.append(f"{label}{value * 100:+.1f}%")
    combat_labels = {
        "hit_bonus": "命中稳定",
        "pierce_bonus": "防御穿透",
        "life_steal": "吸血",
        "shield_bonus": "技能护盾",
        "mp_suppress": "精神压制",
        "defense_suppress": "压低防御",
        "combo_bonus": "连击概率",
        "damage_reduce": "最终减伤",
        "skill_power_bonus": "技能威力",
        "heavy_bonus": "重击威力",
        "combo_damage_bonus": "连击伤害",
        "single_hit_bonus": "单次爆发",
    }
    for key, label in combat_labels.items():
        value = effect.get(key)
        if isinstance(value, int | float) and value:
            parts.append(f"{label}{value * 100:+.1f}%")
    interval_delta = effect.get("interval_delta")
    if isinstance(interval_delta, int | float) and interval_delta:
        direction = "变慢" if interval_delta > 0 else "变快"
        parts.append(f"技能速度基准{int(interval_delta):+d}({direction})")
    trade_bonus = effect.get("trade_bonus")
    if isinstance(trade_bonus, int | float) and trade_bonus:
        if trade_bonus > 0:
            parts.append(f"跑商手续费-{trade_bonus * 100:.1f}%")
        else:
            parts.append(f"跑商手续费+{abs(trade_bonus) * 100:.1f}%")
    return "，".join(parts) if parts else "无主动效果"


def choose_one(rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """随机选择一行。"""

    values = list(rows)
    if not values:
        return None
    return random.choice(values)


__all__ = [
    "Any",
    "CoreService",
    "business_day",
    "choose_one",
    "custom_label",
    "dt",
    "dump_json",
    "enchant_label_name",
    "fixed_equipment_label",
    "format_effect",
    "hint",
    "load_json",
    "money",
    "now",
    "parse_name_level",
    "quality_factor",
    "random",
    "random_quality",
    "row_value",
    "split_words",
    "sqlite3",
    "timedelta",
    "to_int",
    "ts",
    "validate_name",
    "weapon_label_name",
]
