"""装备组件服务。"""

from __future__ import annotations

from ..common import (
    CoreService,
    business_day,
    fixed_equipment_label,
    hint,
    money,
    parse_name_level,
    quality_factor,
    split_words,
    to_int,
    ts,
)
from ..constants import EQUIPMENT_SLOTS, FIXED_EQUIPMENT_SLOT_FACTORS
from ..rules import equipment_upgrade_cost, gem_recycle_price_rate, gem_recycle_single_cap
from ..sql import db

DEFAULT_HOLES = 3
MAX_HOLES = 9
HOLE_ITEM_ID = "kaikongqi"


class EquipmentService(CoreService):
    """装备升级和镶嵌。"""

    def list_equipment(self, client_id: str) -> str:
        """查看装备。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        self.db.ensure_fixed_equipment(client_id)
        rows = self.db.fetch_all(
            "SELECT * FROM fixed_equipment WHERE client_id = ? ORDER BY slot",
            (client_id,),
        )
        bonuses = self.equipment_bonuses(client_id)
        lines = [f"{fixed_equipment_label(row)}：{row['level']}级，孔位 {row['hole_count']}/{MAX_HOLES}" for row in rows]
        lines.append(
            f"当前总生存加成：血气+{int(bonuses['max_hp_bonus'])} "
            f"精神+{int(bonuses['max_mp_bonus'])} 防御+{int(bonuses['defense_bonus'])}"
            + "<升 左手><升 右手><升 左脚><升 右脚>"
            + "<升 头部><升 护甲><升 饰品>"
        )
        return "\n".join(lines) 

    def upgrade(self, client_id: str, slot: str) -> str:
        """升级装备。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        slot = slot.strip()
        if slot not in EQUIPMENT_SLOTS:
            return hint(f"装备位只能是：{'、'.join(EQUIPMENT_SLOTS)}", "发送：装备 查看已有装备位。<装备>")
        self.db.ensure_fixed_equipment(client_id)
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM fixed_equipment WHERE client_id = ? AND slot = ?",
                (client_id, slot),
            ).fetchone()
            level = row["level"] if row else 0
            if level >= 100:
                return hint(f"{slot} 已满级。", "可以升级其他装备位，或继续镶嵌、升级宝石。")
            cost = equipment_upgrade_cost(level + 1, FIXED_EQUIPMENT_SLOT_FACTORS[slot])
            if not self.spend_stones_conn(conn, client_id, cost):
                return hint(f"源石不足，升级需要 {money(cost)}。", "发送：源库 查看存量，或通过签到、探险、出售物品获取源石。<商场自动出售><特殊自动出售>")
            conn.execute(
                "UPDATE fixed_equipment SET level = level + 1 WHERE client_id = ? AND slot = ?",
                (client_id, slot),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '升级装备', ?, ?)",
                (client_id, f"slot={slot}, level={level + 1}, cost={cost}", ts()),
            )
        self.recalc_player(client_id)
        return f"{fixed_equipment_label(row) if row else slot} 升级成功，当前 {level + 1} 级。"

    def holes(self, client_id: str, slot: str) -> str:
        """查看装备孔位。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        slot = slot.strip()
        if slot not in EQUIPMENT_SLOTS:
            return hint(f"装备位只能是：{'、'.join(EQUIPMENT_SLOTS)}", "发送：装备 查看已有装备位。<装备>")
        equipment = self._equipment_row(client_id, slot)
        hole_count = int(equipment["hole_count"]) if equipment else DEFAULT_HOLES
        rows = self.db.fetch_all(
            """
            SELECT i.hole_no, i.level, e.name
            FROM fixed_equipment_inlays i
            LEFT JOIN equipment_item_defs e ON e.equipment_item_id = i.gem_id
            WHERE i.client_id = ? AND i.slot = ?
            ORDER BY i.hole_no
            """,
            (client_id, slot),
        )
        used = {row["hole_no"]: f"{row['name']} {row['level']}级" for row in rows}
        lines = [f"☆{fixed_equipment_label(equipment) if equipment else slot}孔位☆ {hole_count}/{MAX_HOLES}"]
        for index in range(1, MAX_HOLES + 1):
            if index > hole_count:
                lines.append(f"{index}：未开孔")
            else:
                lines.append(f"{index}：{used.get(index, '空')}")
        return "\n".join(lines)

    def open_hole(self, client_id: str, slot: str) -> str:
        """消耗开孔器，为装备增加 1 个孔位。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        slot = slot.strip()
        if slot not in EQUIPMENT_SLOTS:
            return hint(f"装备位只能是：{'、'.join(EQUIPMENT_SLOTS)}", "发送：装备 查看已有装备位。")
        self.db.ensure_fixed_equipment(client_id)
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT hole_count FROM fixed_equipment WHERE client_id = ? AND slot = ?",
                (client_id, slot),
            ).fetchone()
            hole_count = int(row["hole_count"]) if row else DEFAULT_HOLES
            if hole_count >= MAX_HOLES:
                return hint(f"{slot} 已经达到 {MAX_HOLES} 孔上限。", "可以给其他装备开孔，或继续镶嵌、升级宝石。")
            if not self.remove_ring_conn(conn, client_id, HOLE_ITEM_ID, 1):
                return hint("纳戒里没有开孔器。", "开孔器通过岁时情劫首领奖励获得，获得后发送：开孔 装备位")
            conn.execute(
                """
                UPDATE fixed_equipment
                SET hole_count = hole_count + 1
                WHERE client_id = ? AND slot = ?
                """,
                (client_id, slot),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '装备开孔', ?, ?)",
                (client_id, f"slot={slot}, holes={hole_count + 1}", ts()),
            )
        equipment = self._equipment_row(client_id, slot)
        return f"开孔成功：{fixed_equipment_label(equipment) if equipment else slot} 当前孔位 {hole_count + 1}/{MAX_HOLES}。"

    def inlay(self, client_id: str, message: str) -> str:
        """镶嵌装备。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        parts = split_words(message)
        if len(parts) < 3:
            return hint("镶嵌格式不正确。", "发送：镶嵌 装备位 孔位号 宝石名称，例如：镶嵌 护甲 1 护心玉")
        slot = parts[0]
        hole_no = to_int(parts[1])
        item_name, wanted_level = parse_name_level(" ".join(parts[2:]))
        if slot not in EQUIPMENT_SLOTS or hole_no < 1 or hole_no > MAX_HOLES:
            return hint("装备位或孔位号不正确。", f"装备位只能是：{'、'.join(EQUIPMENT_SLOTS)}；孔位号只能是 1 到 {MAX_HOLES}。")
        item = self.equipment_item_def_by_name(item_name)
        if not item or item["category"] != "宝石":
            return hint(f"没有找到宝石：{item_name}。", "发送：宝石 查看已有宝石名称。<宝石>")
        with self.db.transaction() as conn:
            equipment = conn.execute(
                "SELECT hole_count FROM fixed_equipment WHERE client_id = ? AND slot = ?",
                (client_id, slot),
            ).fetchone()
            hole_count = int(equipment["hole_count"]) if equipment else DEFAULT_HOLES
            if hole_no > hole_count:
                return hint(f"{slot} 当前只开启到 {hole_count} 号孔。", "先发送：开孔 装备位，消耗开孔器后再镶嵌。")
            exists = conn.execute(
                """
                SELECT 1 FROM fixed_equipment_inlays
                WHERE client_id = ? AND slot = ? AND hole_no = ?
                """,
                (client_id, slot, hole_no),
            ).fetchone()
            if exists:
                return hint("该孔位已经有宝石。", "发送：拆卸 装备位 孔位号 后再重新镶嵌。")
            gem_level, level_error = self.resolve_gem_level_conn(
                conn,
                client_id,
                item["equipment_item_id"],
                item["name"],
                wanted_level,
                "镶嵌 护甲 1 {name} {level}级",
            )
            if level_error:
                return level_error
            assert gem_level is not None
            if not self.remove_gem_conn(conn, client_id, item["equipment_item_id"], gem_level, 1):
                return hint(f"纳戒里没有 {item['name']} {gem_level}级。", "发送：宝石 查看已有宝石等级，或继续探险获取。<宝石><探险>")
            conn.execute(
                """
                INSERT INTO fixed_equipment_inlays (client_id, slot, hole_no, gem_id, level)
                VALUES (?, ?, ?, ?, ?)
                """,
                (client_id, slot, hole_no, item["equipment_item_id"], gem_level),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '镶嵌宝石', ?, ?)",
                (client_id, f"slot={slot}, hole={hole_no}, gem={item['equipment_item_id']}, level={gem_level}", ts()),
            )
        self.recalc_player(client_id)
        equipment = self._equipment_row(client_id, slot)
        return f"镶嵌成功：{fixed_equipment_label(equipment) if equipment else slot} {hole_no}号孔 -> {item['name']} {gem_level}级。"

    def remove_inlay(self, client_id: str, message: str) -> str:
        """拆卸宝石。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        parts = split_words(message)
        if len(parts) < 2:
            return hint("拆卸格式不正确。", "发送：拆卸 装备位 孔位号，例如：拆卸 护甲 1")
        slot = parts[0]
        hole_no = to_int(parts[1])
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT i.*, e.name
                FROM fixed_equipment_inlays i
                JOIN equipment_item_defs e ON e.equipment_item_id = i.gem_id
                WHERE i.client_id = ? AND i.slot = ? AND i.hole_no = ?
                """,
                (client_id, slot, hole_no),
            ).fetchone()
            if not row:
                return hint("该孔位没有宝石。", "发送：孔位 装备位 查看当前孔位。")
            self.add_gem_conn(conn, client_id, row["gem_id"], row["level"], 1)
            conn.execute(
                "DELETE FROM fixed_equipment_inlays WHERE client_id = ? AND slot = ? AND hole_no = ?",
                (client_id, slot, hole_no),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '拆卸宝石', ?, ?)",
                (client_id, f"slot={slot}, hole={hole_no}, gem={row['gem_id']}, level={row['level']}", ts()),
            )
        self.recalc_player(client_id)
        return f"拆卸成功：{row['name']} {row['level']}级已回到纳戒。"

    def my_inlays(self, client_id: str) -> str:
        """查看纳戒里尚未镶嵌的宝石库存。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        rows = self.gem_rows(client_id)
        if not rows:
            return hint("纳戒中没有宝石。", "继续探险有概率获得宝石。")
        return "\n".join(f"{row['name']} {row['level']}级 x{row['quantity']}" for row in rows)

    def recycle_gem(self, client_id: str, message: str) -> str:
        """在回收地点处理纳戒里的未镶嵌宝石。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        location = self.recycle_location(player["location_name"], "gem")
        if not location:
            return hint("当前位置不是宝石回收地点。", "发送：商场列表 查看地点，再发送：导航 琢玉楼<导航 琢玉楼>")

        text = message.strip()
        if not text:
            return self._gem_recycle_preview(client_id, location)

        item_name, wanted_level, quantity = self._parse_gem_recycle_message(text)
        if quantity <= 0:
            return hint("宝石回收格式不正确。", "发送：回收宝石 宝石名 等级 数量，例如：回收宝石 护心玉 2级 1")
        item = self.equipment_item_def_by_name(item_name)
        if not item or item["category"] != "宝石":
            return hint(f"没有找到宝石：{item_name}。", "发送：宝石 查看纳戒里的宝石。<宝石>")

        with self.db.transaction() as conn:
            gem_level, level_error = self.resolve_gem_level_conn(
                conn,
                client_id,
                item["equipment_item_id"],
                item["name"],
                wanted_level,
                "回收宝石 {name} {level}级 1",
            )
            if level_error:
                return level_error
            assert gem_level is not None

            row = conn.execute(
                """
                SELECT quantity FROM gem_items
                WHERE client_id = ? AND gem_id = ? AND level = ?
                """,
                (client_id, item["equipment_item_id"], gem_level),
            ).fetchone()
            owned = int(row["quantity"]) if row else 0
            if owned < quantity:
                return hint(f"纳戒里 {item['name']} {gem_level}级 只有 {owned} 个。", "发送：宝石 查看库存后再回收。<宝石>")

            today_income = self._today_gem_recycle_income_conn(conn, client_id)
            quote = self._gem_recycle_quote(
                item,
                gem_level,
                quantity,
                float(location["price_factor"]),
                int(player["level"]),
                today_income,
            )
            if not self.remove_gem_conn(conn, client_id, item["equipment_item_id"], gem_level, quantity):
                return hint("宝石库存已变化，回收失败。", "发送：宝石 查看当前库存后再试。<宝石>")
            conn.execute(
                "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                (quote["value"], client_id),
            )
            conn.execute(
                """
                INSERT INTO gem_recycle_records (
                    client_id, gem_id, gem_name, quality, level, quantity,
                    raw_value, capped_value, price_rate, total_price,
                    location_name, business_day, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    item["equipment_item_id"],
                    item["name"],
                    item["quality"],
                    gem_level,
                    quantity,
                    quote["raw_value"],
                    quote["capped_value"],
                    quote["rate"],
                    quote["value"],
                    location["name"],
                    business_day(),
                    ts(),
                ),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '宝石回收', ?, ?)",
                (client_id, f"gem={item['equipment_item_id']}, level={gem_level}, quantity={quantity}, stones={quote['value']}", ts()),
            )
        return (
            f"回收成功：{item['name']} {gem_level}级 x{quantity}，"
            f"获得源石 {money(quote['value'])}，当前倍率 {int(quote['rate'] * 100)}%。"
        )

    def upgrade_inlay(self, client_id: str, message: str) -> str:
        """升级已镶嵌的宝石。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        text = message.strip()
        if not text:
            return hint("宝石升级格式不正确。", "发送：宝石升级 装备位 孔位号，例如：宝石升级 护甲 1")
        with self.db.transaction() as conn:
            row, error = self._upgrade_target_conn(conn, client_id, text)
            if error:
                return error
            assert row is not None
            if row["level"] >= 10:
                return hint(f"{row['name']} 已经 10 级。", "可以升级其他宝石，或镶嵌到其他装备孔位。")
            next_level = row["level"] + 1
            cost = 5000 * (next_level**2)
            if not self.spend_stones_conn(conn, client_id, cost):
                return hint(f"源石不足，升级需要 {money(cost)}。", "发送：源库 查看存量，或通过签到、探险、出售物品获取源石<商场自动出售><特殊自动出售>。")
            conn.execute(
                """
                UPDATE fixed_equipment_inlays
                SET level = ?
                WHERE client_id = ? AND slot = ? AND hole_no = ?
                """,
                (next_level, client_id, row["slot"], row["hole_no"]),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '升级宝石', ?, ?)",
                (
                    client_id,
                    f"slot={row['slot']}, hole={row['hole_no']}, gem={row['gem_id']}, level={next_level}, cost={cost}",
                    ts(),
                ),
            )
        self.recalc_player(client_id)
        return f"{row['slot']} {row['hole_no']}号孔 {row['name']} 升级成功：{row['level']} -> {next_level}，消耗源石 {money(cost)}。"

    def _upgrade_target_conn(self, conn, client_id: str, text: str):
        """解析宝石升级目标；只按 装备位+孔位 精确定位。"""

        parts = split_words(text)
        if len(parts) >= 2 and parts[0] in EQUIPMENT_SLOTS:
            hole_no = to_int(parts[1])
            row = conn.execute(
                """
                SELECT i.*, e.name
                FROM fixed_equipment_inlays i
                JOIN equipment_item_defs e ON e.equipment_item_id = i.gem_id
                WHERE i.client_id = ? AND i.slot = ? AND i.hole_no = ?
                """,
                (client_id, parts[0], hole_no),
            ).fetchone()
            if not row:
                return None, hint("该孔位没有可升级宝石。", "发送：孔位 装备位 查看当前孔位。")
            return row, None

        item = self.equipment_item_def_by_name(text)
        if not item or item["category"] != "宝石":
            return None, hint("宝石升级格式不正确。", "发送：宝石升级 装备位 孔位号，例如：宝石升级 护甲 1")
        rows = conn.execute(
            """
            SELECT i.*, e.name
            FROM fixed_equipment_inlays i
            JOIN equipment_item_defs e ON e.equipment_item_id = i.gem_id
            WHERE i.client_id = ? AND i.gem_id = ?
            ORDER BY i.slot, i.hole_no
            """,
            (client_id, item["equipment_item_id"]),
        ).fetchall()
        if not rows:
            return None, hint(f"你还没有镶嵌 {item['name']}。", "先发送：镶嵌 装备位 孔位号 宝石名称。")
        options = "、".join(f"{row['slot']}{row['hole_no']}号孔({row['level']}级)" for row in rows)
        return None, hint(
            "宝石升级需要用装备位和孔位号定位。",
            f"发送：宝石升级 装备位 孔位号，例如：宝石升级 {rows[0]['slot']} {rows[0]['hole_no']}。可选：{options}",
        )

    def _gem_recycle_preview(self, client_id: str, location: dict) -> str:
        """展示当前可回收宝石和估价。"""

        rows = self.gem_rows(client_id)
        if not rows:
            return hint(f"{location['name']}可以回收纳戒里的未镶嵌宝石，但你当前没有宝石。", "继续探险或挑战首领、虫洞获取宝石。")

        player = self.player(client_id) or {}
        player_level = int(player.get("level", 1))
        today_income = self._today_gem_recycle_income(client_id)
        rate = gem_recycle_price_rate(player_level, today_income)
        lines = [f"☆{location['name']}宝石回收☆ 当前倍率 {int(rate * 100)}%"]
        lines.append(f"今日已回收:{money(today_income)}。估价会随今日回收收入降低。")
        lines.append("只回收纳戒里未镶嵌的宝石；已镶嵌宝石请先拆卸。")
        for row in rows:
            quote = self._gem_recycle_quote(
                row,
                int(row["level"]),
                1,
                float(location["price_factor"]),
                player_level,
                today_income,
            )
            lines.append(
                f"{row['name']} {row['level']}级 x{row['quantity']} "
                f"单颗估价:{money(quote['value'])}"
            )
        return "\n".join(lines)

    def _today_gem_recycle_income(self, client_id: str) -> int:
        """读取玩家今日宝石回收收入。"""

        with self.db.transaction() as conn:
            return self._today_gem_recycle_income_conn(conn, client_id)

    @staticmethod
    def _today_gem_recycle_income_conn(conn, client_id: str) -> int:
        """在事务里读取玩家今日宝石回收收入。"""

        row = conn.execute(
            """
            SELECT COALESCE(SUM(total_price), 0) AS total
            FROM gem_recycle_records
            WHERE client_id = ? AND business_day = ?
            """,
            (client_id, business_day()),
        ).fetchone()
        return int(row["total"]) if row else 0

    @staticmethod
    def _gem_recycle_quote(
        gem: dict,
        level: int,
        quantity: int,
        price_factor: float,
        player_level: int,
        today_income: int,
    ) -> dict[str, float | int]:
        """计算宝石回收报价。"""

        gem_level = max(1, int(level))
        amount = max(1, int(quantity))
        raw_unit = int((gem_level * gem_level * 2200 + gem_level * 600) * quality_factor(gem["quality"]) * price_factor)
        single_cap = int(gem_recycle_single_cap(player_level) * (1 + (gem_level - 1) * 0.25))
        capped_unit = min(raw_unit, single_cap)
        capped_value = capped_unit * amount
        raw_value = raw_unit * amount
        rate = gem_recycle_price_rate(player_level, today_income + capped_value // 2)
        value = max(1, int(capped_value * rate))
        return {
            "raw_value": raw_value,
            "single_cap": single_cap,
            "capped_value": capped_value,
            "rate": rate,
            "value": value,
        }

    @staticmethod
    def _parse_gem_recycle_message(message: str) -> tuple[str, int | None, int]:
        """解析 回收宝石 宝石名 [等级] [数量]。"""

        parts = split_words(message)
        if not parts:
            return "", None, 0
        quantity = 1
        if len(parts) > 1 and parts[-1].isdigit():
            quantity = to_int(parts[-1], 1)
            parts = parts[:-1]
        item_name, wanted_level = parse_name_level(" ".join(parts))
        return item_name, wanted_level, quantity

    def _equipment_row(self, client_id: str, slot: str) -> dict | None:
        """读取某个装备位。"""

        self.db.ensure_fixed_equipment(client_id)
        return self.db.fetch_one(
            "SELECT * FROM fixed_equipment WHERE client_id = ? AND slot = ?",
            (client_id, slot),
        )


service = EquipmentService(db)

__all__ = ["EquipmentService", "service"]
