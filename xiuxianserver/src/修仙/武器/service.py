"""武器组件服务。"""

from __future__ import annotations

from ..common import (
    business_day,
    dump_json,
    enchant_label_name,
    hint,
    load_json,
    money,
    quality_factor,
    split_words,
    to_int,
    ts,
    weapon_label_name,
)
from ..rules import (
    weapon_enchant_slots,
    weapon_recycle_price_rate,
    weapon_recycle_single_cap,
    weapon_upgrade_cost,
)
from ..sql import db
from ..weapon_core import WeaponCore


class WeaponService(WeaponCore):
    """武器持有、切换、升级、附魔和掉落。"""

    def list_weapons(self, client_id: str) -> str:
        """查看武器。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        self.ensure_starter_weapon(client_id)
        rows = self.weapons(client_id)
        lines = ["☆武器☆"]
        for row in rows:
            mark = "已装备" if row["equipped"] else "备用"
            skill = self.skill(row["skill_id"])
            enchant_ids = load_json(row["enchant_effects"], [])
            enchants = len(enchant_ids)
            enchant_text = self._enchant_text(row["weapon_id"], enchant_ids)
            lines.append(
                f"#{row['weapon_id']} {weapon_label_name(row)}[{row['quality']}] {mark} "
                f"等级:{row['level']}/{row['max_level']} 攻击:{row['attack']} "
                f"技能:{skill['name']} 附魔:{enchants}/{row['enchant_slots']}{enchant_text}"
            )
        return "\n".join(lines)

    def switch(self, client_id: str, message: str) -> str:
        """切换武器。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        weapon_id = to_int(message)
        weapon = self.weapon(client_id, weapon_id)
        if not weapon:
            return hint("没有找到这把武器。", "发送：武器 查看自己的武器 ID。")
        with self.db.transaction() as conn:
            conn.execute("UPDATE player_weapons SET equipped = 0 WHERE owner_id = ?", (client_id,))
            conn.execute("UPDATE player_weapons SET equipped = 1 WHERE owner_id = ? AND weapon_id = ?", (client_id, weapon_id))
        return f"已切换武器：{weapon_label_name(weapon)}。"

    def upgrade(self, client_id: str, message: str) -> str:
        """升级武器。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        weapon_id = to_int(message)
        with self.db.transaction() as conn:
            weapon = conn.execute(
                """
                SELECT w.*, d.name
                FROM player_weapons w
                JOIN weapon_defs d ON d.weapon_def_id = w.weapon_def_id
                WHERE w.owner_id = ? AND w.weapon_id = ?
                """,
                (client_id, weapon_id),
            ).fetchone()
            if not weapon:
                return hint("没有找到这把武器。", "发送：武器 查看自己的武器 ID。")
            if weapon["level"] >= weapon["max_level"]:
                return hint("这把武器已经到达自身等级上限。", "可以切换或继续探险获取更高上限武器。")
            next_level = weapon["level"] + 1
            cost = weapon_upgrade_cost(next_level, quality_factor(weapon["quality"]))
            if not self.spend_stones_conn(conn, client_id, cost):
                return hint(f"源石不足，升级需要 {money(cost)}。", "发送：源库 查看存量，或通过签到、探险、出售物品获取源石。")
            attack = weapon["attack"] + max(1, int(weapon["attack"] * 0.04))
            slots = weapon_enchant_slots(weapon["max_level"], next_level)
            conn.execute(
                """
                UPDATE player_weapons
                SET level = ?, attack = ?, enchant_slots = ?
                WHERE weapon_id = ? AND owner_id = ?
                """,
                (next_level, attack, slots, weapon_id, client_id),
            )
        return (
            f"升级成功，{weapon_label_name(weapon)} 等级 {next_level}/{weapon['max_level']}，"
            f"攻击 {attack}，附魔栏 {slots}。"
        )

    def recycle(self, client_id: str, message: str) -> str:
        """在武器回收地点处理备用武器。"""

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        location = self._recycle_location(player["location_name"])
        if not location:
            return hint("当前位置不是武器回收地点。", "发送：商场列表 查看地点，再发送：导航 铸剑阁")

        weapon_id = self._parse_weapon_id(message)
        if weapon_id <= 0:
            return self._recycle_preview(client_id, location)

        with self.db.transaction() as conn:
            weapon = conn.execute(
                """
                SELECT w.*, d.name
                FROM player_weapons w
                JOIN weapon_defs d ON d.weapon_def_id = w.weapon_def_id
                WHERE w.owner_id = ? AND w.weapon_id = ?
                """,
                (client_id, weapon_id),
            ).fetchone()
            if not weapon:
                return hint("没有找到这把武器。", "发送：武器 查看自己的武器 ID。")
            if int(weapon["equipped"]):
                return hint("已装备武器不能回收。", "先切换到其他武器，再回收这把备用武器。")

            count = conn.execute(
                "SELECT COUNT(*) AS total FROM player_weapons WHERE owner_id = ?",
                (client_id,),
            ).fetchone()
            if int(count["total"]) <= 1:
                return hint("不能回收最后一把武器。", "至少保留一把自用武器，避免无法探险战斗。")

            today_income = self._today_recycle_income_conn(conn, client_id)
            quote = self._recycle_quote(
                dict(weapon),
                float(location["price_factor"]),
                int(player["level"]),
                today_income,
            )
            value = quote["value"]
            conn.execute("DELETE FROM weapon_enchant_names WHERE weapon_id = ?", (weapon_id,))
            conn.execute("DELETE FROM player_weapons WHERE owner_id = ? AND weapon_id = ?", (client_id, weapon_id))
            conn.execute(
                "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                (value, client_id),
            )
            conn.execute(
                """
                INSERT INTO weapon_recycle_records (
                    client_id, weapon_id, weapon_name, quality, level, max_level,
                    raw_value, capped_value, price_rate, total_price,
                    location_name, business_day, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    weapon_id,
                    weapon_label_name(weapon),
                    weapon["quality"],
                    int(weapon["level"]),
                    int(weapon["max_level"]),
                    quote["raw_value"],
                    quote["capped_value"],
                    quote["rate"],
                    value,
                    location["name"],
                    business_day(),
                    ts(),
                ),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '武器回收', ?, ?)",
                (client_id, f"weapon_id={weapon_id}, stones={value}, rate={quote['rate']:.2f}", ts()),
            )

        return (
            f"回收成功：#{weapon_id} {weapon_label_name(weapon)}[{weapon['quality']}]，"
            f"获得源石 {money(value)}，当前倍率 {int(quote['rate'] * 100)}%。"
        )

    def enchant(self, client_id: str, message: str) -> str:
        """给武器附魔。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        parts = split_words(message)
        if len(parts) < 2:
            return hint("附魔格式不正确。", "发送：附魔武器 武器ID 技能书名，例如：附魔武器 1 破甲残卷")
        weapon_id = to_int(parts[0])
        book_name = " ".join(parts[1:])
        book = self.equipment_item_def_by_name(book_name)
        if not book or book["category"] != "技能书":
            return hint(f"没有找到技能书：{book_name}。", "发送：查看纳戒 查看已有技能书。")
        effect = load_json(book["effect"], {})
        enchant_id = effect.get("enchant_id")
        enchant = self.db.fetch_one("SELECT * FROM weapon_enchants WHERE enchant_id = ?", (enchant_id,))
        if not enchant:
            return hint("这本技能书暂时不能附魔。", "换一本技能书，或发送：查看装备库 技能书名 查看说明。")
        with self.db.transaction() as conn:
            weapon = conn.execute(
                """
                SELECT w.*, d.name
                FROM player_weapons w
                JOIN weapon_defs d ON d.weapon_def_id = w.weapon_def_id
                WHERE w.owner_id = ? AND w.weapon_id = ?
                """,
                (client_id, weapon_id),
            ).fetchone()
            if not weapon:
                return hint("没有找到这把武器。", "发送：武器 查看自己的武器 ID。")
            current = load_json(weapon["enchant_effects"], [])
            if len(current) >= weapon["enchant_slots"]:
                return hint("这把武器没有空余附魔栏。", "升级武器可能解锁附魔栏，或换一把更高上限武器。")
            if not self.remove_ring_conn(conn, client_id, book["equipment_item_id"], 1):
                return hint(f"纳戒里没有 {book['name']}。", "发送：查看纳戒 确认库存，或继续探险获取技能书。")
            current.append(enchant_id)
            conn.execute(
                "UPDATE player_weapons SET enchant_effects = ? WHERE weapon_id = ? AND owner_id = ?",
                (dump_json(current), weapon_id, client_id),
            )
        return f"附魔成功：{weapon_label_name(weapon)} 获得 {book['name']}。"

    def _recycle_preview(self, client_id: str, location: dict) -> str:
        """展示当前可回收武器和估价。"""

        self.ensure_starter_weapon(client_id)
        rows = self.weapons(client_id)
        spares = [row for row in rows if not int(row["equipped"])]
        if not spares:
            return hint(
                f"{location['name']}可以稳定回收备用武器，但你当前没有可回收武器。",
                "继续探险获取备用武器；已装备武器和最后一把武器不能回收。",
            )

        player = self.player(client_id) or {}
        today_income = self._today_recycle_income(client_id)
        rate = weapon_recycle_price_rate(int(player.get("level", 1)), today_income)
        lines = [f"☆{location['name']}武器回收☆ 当前倍率 {int(rate * 100)}%"]
        lines.append(f"今日已回收:{money(today_income)}。估价会随今日回收收入降低。")
        lines.append("已装备武器和最后一把武器不能回收。")
        for row in spares:
            quote = self._recycle_quote(
                row,
                float(location["price_factor"]),
                int(player.get("level", 1)),
                today_income,
            )
            enchants = len(load_json(row["enchant_effects"], []))
            lines.append(
                f"#{row['weapon_id']} {weapon_label_name(row)}[{row['quality']}] "
                f"等级:{row['level']}/{row['max_level']} 攻击:{row['attack']} "
                f"附魔:{enchants}/{row['enchant_slots']} 估价:{money(quote['value'])}"
            )
        return "\n".join(lines)

    def _enchant_text(self, weapon_id: int, enchant_ids: object) -> str:
        """把武器已附魔技能书按槽位展示出来。"""

        if not isinstance(enchant_ids, list) or not enchant_ids:
            return ""
        custom_rows = self.db.fetch_all(
            "SELECT slot_no, custom_name FROM weapon_enchant_names WHERE weapon_id = ?",
            (weapon_id,),
        )
        custom_names = {int(row["slot_no"]): row["custom_name"] for row in custom_rows}
        labels = []
        for slot_no, enchant_id in enumerate(enchant_ids, start=1):
            row = self.db.fetch_one("SELECT name FROM weapon_enchants WHERE enchant_id = ?", (enchant_id,))
            base_name = row["name"] if row else str(enchant_id)
            labels.append(f"{slot_no}.{enchant_label_name(base_name, custom_names.get(slot_no, ''))}")
        return "（" + "、".join(labels) + "）"

    @staticmethod
    def _parse_weapon_id(message: str) -> int:
        """解析 武器ID / 武器#ID / #ID / ID。"""

        value = message.strip()
        for prefix in ("武器#", "武器ID", "武器", "#"):
            if value.startswith(prefix):
                value = value[len(prefix):]
                break
        return to_int(value)

    def _recycle_location(self, location_name: str) -> dict | None:
        """读取当前地点是否支持武器回收。"""

        return self.db.fetch_one(
            "SELECT * FROM weapon_recycle_locations WHERE name = ?",
            (location_name.strip(),),
        )

    def _today_recycle_income(self, client_id: str) -> int:
        """读取玩家今日武器回收收入。"""

        with self.db.transaction() as conn:
            return self._today_recycle_income_conn(conn, client_id)

    @staticmethod
    def _today_recycle_income_conn(conn, client_id: str) -> int:
        """在事务里读取玩家今日武器回收收入。"""

        row = conn.execute(
            """
            SELECT COALESCE(SUM(total_price), 0) AS total
            FROM weapon_recycle_records
            WHERE client_id = ? AND business_day = ?
            """,
            (client_id, business_day()),
        ).fetchone()
        return int(row["total"]) if row else 0

    @staticmethod
    def _recycle_quote(weapon: dict, price_factor: float, player_level: int, today_income: int) -> dict[str, float | int]:
        """计算武器回收报价。

        先按武器属性估价，再限制单把上限，最后按今日回收收入降价。
        """

        enchants = len(load_json(weapon.get("enchant_effects"), []))
        raw_value = int(
            (
                int(weapon["attack"]) * 60
                + int(weapon["max_level"]) * 100
                + int(weapon["level"]) * 250
                + enchants * 5_000
            )
            * quality_factor(weapon["quality"])
            * price_factor
        )
        single_cap = weapon_recycle_single_cap(player_level)
        capped_value = min(raw_value, single_cap)
        rate = weapon_recycle_price_rate(player_level, today_income + capped_value // 2)
        value = max(1, int(capped_value * rate))
        return {
            "raw_value": raw_value,
            "single_cap": single_cap,
            "capped_value": capped_value,
            "rate": rate,
            "value": value,
        }


service = WeaponService(db)

__all__ = ["WeaponService", "service"]
