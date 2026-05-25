"""玩家组件服务。"""

from __future__ import annotations

from ..common import (
    CoreService,
    business_day,
    dt,
    enchant_label_name,
    fixed_equipment_label,
    format_effect,
    hint,
    load_json,
    money,
    now,
    timedelta,
    ts,
    weapon_label_name,
)
from ..constants import EQUIPMENT_SLOTS, NEWBIE_GIFT_STONES, REST_MINUTES
from ..markdown_utils import append_suggest_commands
from ..rules import sign_reward
from ..sql import db


class PlayerService(CoreService):
    """玩家创建、资料、签到和休息。"""

    def command_guide(self) -> str:
        """返回关键组件跳转按钮。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        return f"修仙指南<修仙信息><背包><纳戒><源库><二手市场><商场推荐><探险状态><结束探险><武器><装备><宝石><铭刻><虫洞><首领><修仙早报>"

    def create(self, client_id: str, message: str) -> str:
        """创建用户。"""

        name = message.strip()
        if not name:
            return hint("缺少用户名称。", "发送：创建用户 青衫客")
        return self.create_player(client_id, name)

    def rename(self, client_id: str, message: str) -> str:
        """修改展示名称。"""

        name = message.strip()
        if not name:
            return hint("缺少新名称。", "发送：改名 云游客")
        return self.rename_player(client_id, name)

    def profile(self, client_id: str) -> str:
        """查看玩家信息。"""

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None
        weapon = self.equipped_weapon_row(client_id)
        weapon_attack = int(weapon["attack"]) if weapon else 0
        total_attack = int(player["base_attack"]) + weapon_attack
        title = self.refresh_titles(client_id, player) or "无称号"
        lines = [
            "┌───────────",
            f"│ {player['display_name']} · {title}",
            f"│  Lv.{player['level']}",
            "├────",
            f"│  经验：{self.next_level_text(player)}",
            f"│  血气：{player['hp']} / {player['max_hp']}",
            f"│  精神：{player['mp']} / {player['max_mp']}",
            "├────",
            *self._physique_profile_lines(player),
            "├───",
            f"│  攻击：{total_attack}（基础{player['base_attack']} + 武器{weapon_attack}）",
            f"│  防御：{player['defense']}",
            "├───",
            *self._weapon_profile_lines(weapon),
            "├────",
            *self._fixed_equipment_lines(client_id),
            "├────",
            f"│  源石：{money(player['source_stones'])}",
            f"│  状态：{player['status']}",
            f"│  自动用药：{'开启' if player['auto_use_medicine'] else '关闭'}",
            f"│  地点：{player['location_name']} ({player['x']},{player['y']})",
            "└───────────",
        ]
        return "\n".join(lines)

    def diary(self, client_id: str) -> str:
        """查看个人修仙日记。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None
        self._refresh_diary(client_id, player)
        rows = self.db.fetch_all(
            """
            SELECT text
            FROM player_journals
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (client_id,),
        )
        if not rows:
            return hint("修仙日记还没有内容。", "先签到、探险、跑商或挑战虫洞。<签到><探险><虫洞><商场推荐>")
        lines = [f"☆{player['display_name']}的修仙日记☆"]
        lines.extend(f"- {row['text']}" for row in rows)
        return "\n".join(lines)

    def auto_medicine(self, client_id: str, message: str) -> str:
        """查看或修改探险自动用药开关。"""

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        text = message.strip()
        if not text:
            state = "开启" if player["auto_use_medicine"] else "关闭"
            return f"自动用药当前为：{state}。"

        on_words = {"开启", "打开", "启用", "开", "on", "ON", "1"}
        off_words = {"关闭", "关掉", "停用", "关", "off", "OFF", "0"}
        if text in on_words:
            value = 1
            state = "开启"
        elif text in off_words:
            value = 0
            state = "关闭"
        else:
            return hint("自动用药参数不正确。", "发送：自动用药 开启 或 自动用药 关闭")

        with self.db.transaction() as conn:
            conn.execute("UPDATE players SET auto_use_medicine = ? WHERE client_id = ?", (value, client_id))
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '自动用药', ?, ?)",
                (client_id, state, ts()),
            )
        return f"自动用药已{state}。探险预计算时会按这个开关决定是否消耗纳戒恢复类药物。"

    def sign(self, client_id: str) -> str:
        """每日签到。"""

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        today = business_day()
        reward = sign_reward(player["level"])
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE players
                SET source_stones = source_stones + ?, last_sign_date = ?
                WHERE client_id = ?
                  AND (last_sign_date IS NULL OR last_sign_date != ?)
                """,
                (reward, today, client_id, today),
            )
            if cursor.rowcount <= 0:
                fortune = self.ensure_daily_fortune_conn(conn, client_id)
                text = (
                    f"今日已经签到过了。\n"
                    f"今日气运：{fortune['fortune']}，{fortune['flavor']}"
                    f"（{format_effect(fortune['effect'])}）\n"
                    "每日 04:00 后可再次发送：签到"
                )
                return append_suggest_commands(text, "每日 04:00 后可再次发送：签到")
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '签到', ?, ?)",
                (client_id, f"stones={reward}, day={today}", ts()),
            )
            fortune = self.ensure_daily_fortune_conn(conn, client_id)
        return f"签到成功，获得源石 {money(reward)}。\n" f"今日气运：{fortune['fortune']}，{fortune['flavor']}" f"（{format_effect(fortune['effect'])}）"

    def newbie_gift(self, client_id: str) -> str:
        """领取新手礼包。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE players
                SET newbie_claimed = 1, source_stones = source_stones + ?
                WHERE client_id = ? AND newbie_claimed = 0
                """,
                (NEWBIE_GIFT_STONES, client_id),
            )
            if cursor.rowcount <= 0:
                return hint("新手礼包已经领取过了。", "发送：纳戒 查看礼包物品，或发送：探险 开始升级。<纳戒><探险>")
            self.add_ring_conn(conn, client_id, "xueqidan", 2)
            self.add_ring_conn(conn, client_id, "yinmingcao", 2)
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '新手礼包', ?, datetime('now', 'localtime'))",
                (client_id, "领取"),
            )
        return "新手礼包领取成功：源石 10000、血契丹 2、阴冥草 2。"

    def rest(self, client_id: str) -> str:
        """进入休息状态。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None
        if player["status"] != "空闲":
            return hint(f"当前状态为 {player['status']}，不能休息。", "先处理当前状态")

        until = now() + timedelta(minutes=REST_MINUTES)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE players
                SET status = '休息中', status_until_at = ?
                WHERE client_id = ? AND status = '空闲'
                """,
                (ts(until), client_id),
            )
            if cursor.rowcount <= 0:
                return hint("当前状态已变化，不能休息。", "发送：修仙信息 查看当前状态后再操作。<修仙信息>")
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '开始休息', ?, ?)",
                (client_id, f"until={ts(until)}", ts()),
            )
        return f"开始休息，需要 {REST_MINUTES} 分钟。"

    def end_rest(self, client_id: str) -> str:
        """休息满 1 分钟后恢复并退出。"""
        # TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None
        if player["status"] != "休息中":
            return hint("你当前不在休息中。", "血气不足可发送：休息；想查看状态可发送：修仙信息<修仙信息>")

        until = dt(player["status_until_at"])
        if until and now() < until:
            left = max(1, int((until - now()).total_seconds()))
            return hint(f"还需要休息 {left} 秒。", "时间到后再发送：结束休息")

        recover_bonus = min(0.5, self.equipment_bonuses(client_id).get("recover_bonus", 0))
        hp = player["max_hp"]
        mp_add = int(max(5, player["max_mp"] // 5) * (1 + recover_bonus))
        mp = min(player["max_mp"], player["mp"] + mp_add)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE players SET hp = ?, mp = ?, status = '空闲', status_until_at = NULL WHERE client_id = ?",
                (hp, mp, client_id),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, '结束休息', ?, ?)",
                (client_id, f"hp={hp}, mp={mp}", ts()),
            )
        return f"休息结束，血气恢复到 **{hp}**/{player['max_hp']}，精神恢复到 **{mp}**/{player['max_mp']}。"

    def _weapon_profile_lines(self, weapon: dict | None) -> list[str]:
        """生成修仙信息里的武器区块。"""

        if not weapon:
            return ["│  未装备", "│  技能：无", "│  附魔：无"]

        weapon_id = int(weapon["weapon_id"])
        skill = self.db.fetch_one(
            "SELECT name FROM weapon_skill_defs WHERE skill_id = ?",
            (weapon["skill_id"],),
        )
        skill_name = skill["name"] if skill else "普通攻击"
        custom_skill = self.db.fetch_one(
            "SELECT custom_name FROM weapon_enchant_names WHERE weapon_id = ? AND slot_no = 0",
            (weapon_id,),
        )
        base_skill = enchant_label_name(skill_name, custom_skill["custom_name"] if custom_skill else "")
        enchants = self._weapon_enchant_profile_text(weapon_id, load_json(weapon["enchant_effects"], []))
        return [
            f"│  #{weapon_id} {weapon_label_name(weapon)} [{weapon['quality']}]",
            f"│  攻击 +{weapon['attack']}",
            f"│  技能：{base_skill}",
            f"│  附魔：{enchants}",
        ]

    def _weapon_enchant_profile_text(self, weapon_id: int, enchant_ids: object) -> str:
        """生成面板里的附魔摘要。"""

        if not isinstance(enchant_ids, list) or not enchant_ids:
            return "无"
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
        return "、".join(labels)

    def _fixed_equipment_lines(self, client_id: str) -> list[str]:
        """生成修仙信息里的装备区块。"""

        self.db.ensure_fixed_equipment(client_id)
        rows = self.db.fetch_all(
            "SELECT * FROM fixed_equipment WHERE client_id = ?",
            (client_id,),
        )
        row_map = {row["slot"]: row for row in rows}
        parts = []
        for slot in EQUIPMENT_SLOTS:
            row = row_map.get(slot)
            if row is None:
                parts.append(f"{slot} Lv0 0孔")
                continue
            parts.append(f"{fixed_equipment_label(row)} Lv{row['level']} {row['hole_count']}孔")
        if not parts:
            return ["│  无"]
        return [f"│  {part}" for part in parts]

    def _refresh_diary(self, client_id: str, player: dict) -> None:
        """按当前数据补齐修仙日记里程碑。"""

        def count(table: str, where: str, params: tuple) -> int:
            return self._count(table, where, params)

        def total(sql: str, params: tuple) -> int:
            row = self.db.fetch_one(sql, params)
            if not row:
                return 0
            return int(row["total"] or 0)

        now_text = ts()
        vault = self.db.fetch_one("SELECT balance FROM source_vaults WHERE client_id = ?", (client_id,))
        vault_balance = int(vault["balance"]) if vault else 0
        entries = [
            ("created", f"{player['created_at']} 初入修仙界，名为 {player['display_name']}。", player["created_at"]),
            ("level", f"修为已至 {player['level']} 级，累计经验 {player['exp']}。", now_text),
            (
                "wealth",
                f"随身源石 {money(player['source_stones'])}，源库存量 {money(vault_balance)}。",
                now_text,
            ),
            ("location", f"当前停留在 {player['location_name']}，状态为 {player['status']}。", now_text),
        ]

        sign_count = count("game_logs", "client_id = ? AND action = '签到'", (client_id,))
        if sign_count:
            entries.append(("sign", f"累计签到 {sign_count} 次，日日有进，慢慢成路。", now_text))
        if int(player["newbie_claimed"]):
            entries.append(("newbie_gift", "已经领取新手礼包，最初的一点底气还在账上。", now_text))
        rename_count = count("game_logs", "client_id = ? AND action = '改名'", (client_id,))
        if rename_count:
            entries.append(("rename", f"改名 {rename_count} 次，修仙界称呼几经流转。", now_text))

        explore_count = count("exploration_records", "client_id = ?", (client_id,))
        if explore_count:
            latest = self.db.fetch_one(
                """
                SELECT location_name, status
                FROM exploration_records
                WHERE client_id = ?
                ORDER BY record_id DESC
                LIMIT 1
                """,
                (client_id,),
            )
            latest_text = f"，最近一次在 {latest['location_name']}（{latest['status']}）" if latest else ""
            entries.append(("explore", f"累计探险 {explore_count} 次{latest_text}。", now_text))

        trade_sell_count = count("trade_records", "client_id = ? AND action = 'sell'", (client_id,))
        trade_net = total(
            """
            SELECT COALESCE(SUM(total_price - fee), 0) AS total
            FROM trade_records
            WHERE client_id = ? AND action = 'sell'
            """,
            (client_id,),
        )
        if trade_sell_count:
            entries.append(("trade", f"累计跑商出售 {trade_sell_count} 次，净收入 {money(trade_net)} 源石。", now_text))

        second_hand_sell = count("second_hand_records", "seller_id = ?", (client_id,))
        second_hand_buy = count("second_hand_records", "buyer_id = ?", (client_id,))
        if second_hand_sell or second_hand_buy:
            entries.append(
                (
                    "second_hand",
                    f"二手市场成交：卖出 {second_hand_sell} 次，买入 {second_hand_buy} 次。",
                    now_text,
                )
            )

        weapon_count = count("player_weapons", "owner_id = ?", (client_id,))
        if weapon_count:
            equipped = self.equipped_weapon_row(client_id)
            equipped_text = f"，当前执 {weapon_label_name(equipped)}" if equipped else ""
            entries.append(("weapon", f"武器库已收纳 {weapon_count} 把武器{equipped_text}。", now_text))
        rare_weapon = self.db.fetch_one(
            """
            SELECT quality, COUNT(*) AS count
            FROM player_weapons
            WHERE owner_id = ? AND quality IN ('稀品', '珍品')
            GROUP BY quality
            ORDER BY CASE quality WHEN '珍品' THEN 2 ELSE 1 END DESC
            LIMIT 1
            """,
            (client_id,),
        )
        if rare_weapon:
            entries.append(("rare_weapon", f"曾得 {rare_weapon['quality']} 武器 {rare_weapon['count']} 把，坊间称其手气不浅。", now_text))

        recycle_count = count("weapon_recycle_records", "client_id = ?", (client_id,))
        recycle_income = total(
            "SELECT COALESCE(SUM(total_price), 0) AS total FROM weapon_recycle_records WHERE client_id = ?",
            (client_id,),
        )
        if recycle_count:
            entries.append(("weapon_recycle", f"累计回收武器 {recycle_count} 把，得源石 {money(recycle_income)}。", now_text))
        gem_recycle_count = count("gem_recycle_records", "client_id = ?", (client_id,))
        gem_recycle_income = total(
            "SELECT COALESCE(SUM(total_price), 0) AS total FROM gem_recycle_records WHERE client_id = ?",
            (client_id,),
        )
        if gem_recycle_count:
            entries.append(("gem_recycle", f"累计回收宝石 {gem_recycle_count} 次，得源石 {money(gem_recycle_income)}。", now_text))
        book_recycle_count = count("book_recycle_records", "client_id = ?", (client_id,))
        book_recycle_income = total(
            "SELECT COALESCE(SUM(total_price), 0) AS total FROM book_recycle_records WHERE client_id = ?",
            (client_id,),
        )
        if book_recycle_count:
            entries.append(("book_recycle", f"累计回收技能书 {book_recycle_count} 次，得源石 {money(book_recycle_income)}。", now_text))

        wormhole_count = count("wormhole_participants", "client_id = ?", (client_id,))
        if wormhole_count:
            damage = total("SELECT COALESCE(SUM(damage), 0) AS total FROM wormhole_participants WHERE client_id = ?", (client_id,))
            entries.append(("wormhole", f"挑战过异界虫洞 {wormhole_count} 场，累计伤害 {damage}。", now_text))
        boss_count = count("seasonal_boss_participants", "client_id = ?", (client_id,))
        if boss_count:
            damage = total("SELECT COALESCE(SUM(damage), 0) AS total FROM seasonal_boss_participants WHERE client_id = ?", (client_id,))
            entries.append(("seasonal_boss", f"挑战过岁时首领 {boss_count} 场，累计伤害 {damage}。", now_text))

        duel_count = count("duel_records", "from_client_id = ? OR to_client_id = ?", (client_id, client_id))
        duel_win = count("duel_records", "winner_id = ?", (client_id,))
        if duel_count:
            entries.append(("duel", f"公开对战 {duel_count} 场，其中胜利 {duel_win} 场。", now_text))

        inscription_count = count(
            "game_logs",
            "client_id = ? AND action IN ('铭刻装备', '铭刻武器', '铭刻附魔')",
            (client_id,),
        )
        if inscription_count:
            entries.append(("inscription", f"使用铭刻之羽 {inscription_count} 次，把名字刻进自己的器物里。", now_text))
        item_use_count = count("game_logs", "client_id = ? AND action = '使用物品'", (client_id,))
        if item_use_count:
            entries.append(("item_use", f"使用恢复或成长物品 {item_use_count} 次，生死间也懂得惜身。", now_text))

        with self.db.transaction() as conn:
            for key, text, created_at in entries:
                self.record_journal_conn(
                    conn,
                    client_id,
                    key,
                    text,
                    created_at=created_at,
                    keep_first_time=True,
                )

    def _count(self, table: str, where: str, params: tuple) -> int:
        """执行简单计数。"""

        row = self.db.fetch_one(f"SELECT COUNT(*) AS count FROM {table} WHERE {where}", params)
        return int(row["count"]) if row else 0

    def _physique_profile_lines(self, player: dict) -> list[str]:
        """生成修仙信息里的体质区块。"""

        row = self.db.fetch_one(
            "SELECT name, grade, kind, physique_value, effect FROM physique_defs WHERE physique_id = ?",
            (player["physique_id"],),
        )
        if not row:
            return [
                f"│  🌿 体质值 {player['physique']}",
                "│  ✨ 未知品阶 · 未知向",
                "│  💤 天赋：无特殊效果",
            ]
        effect = format_effect(row["effect"])
        value = int(row["physique_value"])
        icon = "🌿" if value <= 0 else "🌱"
        stage = self._physique_stage_text(str(row["grade"]), str(row["kind"]), value)
        trait_icon = "💤" if effect == "无主动效果" else "🛡️"
        return [
            f"│  {icon} {row['name']}",
            f"│  ✨ {stage}",
            f"│  {trait_icon} 天赋：{effect}",
        ]

    @staticmethod
    def _physique_stage_text(grade: str, kind: str, value: int) -> str:
        """把体质品阶、方向和体质值写成更像玩家面板的文字。"""

        if value <= 0:
            return f"{grade} · {kind}向 · 未觉醒"
        return f"{grade}{PlayerService._chinese_number(value)}重 · {kind}向"

    @staticmethod
    def _chinese_number(value: int) -> str:
        """把 1-99 的整数转成中文数字，用于体质重数。"""

        digits = "零一二三四五六七八九"
        if value <= 10:
            return "十" if value == 10 else digits[value]
        if value < 20:
            return "十" + digits[value % 10]
        tens, ones = divmod(value, 10)
        return digits[tens] + "十" + (digits[ones] if ones else "")


service = PlayerService(db)

__all__ = ["PlayerService", "service"]
