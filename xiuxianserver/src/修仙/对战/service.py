"""玩家对战组件服务。"""

from __future__ import annotations

from ..combat_core import CombatCore, service as combat_service
from ..common import CoreService, hint, money, split_words, to_int, ts
from ..sql import db


class DuelService(CoreService):
    """切磋和押注决斗。"""

    def spar(self, client_id: str, message: str) -> str:
        """发起切磋。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        target_id = self._player_id_from_last_arg(message)
        return self._create_request(client_id, target_id, "spar", 0)

    def accept_spar(self, client_id: str, message: str) -> str:
        """接受切磋。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        return self._accept(client_id, message, "spar")

    def reject_spar(self, client_id: str, message: str) -> str:
        """拒绝切磋。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        return self._reject(client_id, message, "spar")

    def duel(self, client_id: str, message: str) -> str:
        """发起押注决斗。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        target_ref, stake = self._parse_duel_message(message)
        if stake <= 0:
            return hint("决斗格式不正确。", "发送：决斗 源石数量 对方名称，也可以直接@对方。")
        return self._create_request(client_id, target_ref, "duel", stake)

    def accept_duel(self, client_id: str, message: str) -> str:
        """接受押注决斗。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        return self._accept(client_id, message, "duel")

    def reject_duel(self, client_id: str, message: str) -> str:
        """拒绝押注决斗。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        return self._reject(client_id, message, "duel")

    def records(self, client_id: str) -> str:
        """查看切磋和押注决斗记录。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        self.cleanup_battle_records()
        rows = self.db.fetch_all(
            """
            SELECT * FROM duel_records
            WHERE from_client_id = ? OR to_client_id = ?
            ORDER BY created_at DESC, record_id DESC
            LIMIT 10
            """,
            (client_id, client_id),
        )
        if not rows:
            return hint("暂无切磋/决斗记录。", "发送：切磋 对方名称，或发送：决斗 源石数量 对方名称。")
        lines = ["☆最近切磋/决斗记录☆"]
        lines.extend(f"{row['mode']}：{row['summary']}" for row in rows)
        return "\n".join(lines)

    def _create_request(self, client_id: str, target_id: str, mode: str, stake: int) -> str:
        """创建对战请求。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        player, error = self.require_player(client_id)
        if error:
            return error
        assert player is not None
        if not target_id:
            command = "决斗 源石数量 对方名称" if mode == "duel" else "切磋 对方名称"
            return hint("没有找到对方。", f"发送：{command}，也可以直接@对方。")
        target, error = self.require_player(target_id)
        if error:
            return hint("对方还没有创建用户。", "请对方先发送：创建用户 名称")
        if target_id == client_id:
            return hint("不能挑战自己。", "请输入其他玩家名称，或直接@对方。")
        if player["status"] != "空闲" or target["status"] != "空闲":
            return hint("双方都需要处于空闲状态。", "双方可先发送：修仙信息 查看状态，处理探险或休息后再挑战。")
        with self.db.transaction() as conn:
            self._expire_requests_conn(conn, client_id, target_id)
            exists = conn.execute(
                """
                SELECT duel_id FROM duel_requests
                WHERE status = '等待'
                  AND (from_client_id = ? OR to_client_id = ? OR from_client_id = ? OR to_client_id = ?)
                LIMIT 1
                """,
                (client_id, client_id, target_id, target_id),
            ).fetchone()
            if exists:
                return hint("你或对方已有未处理的对战请求。", "先接受/拒绝当前请求，或等待请求超时后再发起。")
            if mode == "duel" and not self.spend_stones_conn(conn, client_id, stake):
                return hint(f"源石不足，决斗需要冻结 {money(stake)}。", "发送：源库 查看存量，或先取出源石、签到、探险、出售物品。")
            conn.execute(
                """
                INSERT INTO duel_requests
                (mode, from_client_id, to_client_id, stake, status, expires_at, created_at)
                VALUES (?, ?, ?, ?, '等待', datetime('now', 'localtime', '+10 minutes'), ?)
                """,
                (mode, client_id, target_id, stake, ts()),
            )
        mode_text = "切磋" if mode == "spar" else f"决斗 {money(stake)} 源石"
        accept_cmd = "接受切磋" if mode == "spar" else "接受决斗"
        reject_cmd = "拒绝切磋" if mode == "spar" else "拒绝决斗"
        from_name = str(player["display_name"])
        return (
            f"已向 {self.format_player_name(target_id)} 发起{mode_text}，等待对方处理。\n"
            f"对方 10 分钟内发送：{accept_cmd} {from_name}\n"
            f"如果不接受，发送：{reject_cmd} {from_name}"
        )

    def _accept(self, client_id: str, message: str, mode: str) -> str:
        """接受对战请求并结算。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        self.cleanup_battle_records()
        from_id = self._player_id_from_last_arg(message)
        if not from_id:
            command = "接受切磋" if mode == "spar" else "接受决斗"
            return hint("没有找到发起人。", f"发送：{command} 发起人名称，也可以直接@发起人。")
        with self.db.transaction() as conn:
            self._expire_requests_conn(conn, client_id, from_id)
            request_row = conn.execute(
                """
                SELECT * FROM duel_requests
                WHERE mode = ? AND from_client_id = ? AND to_client_id = ? AND status = '等待'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (mode, from_id, client_id),
            ).fetchone()
            request = dict(request_row) if request_row else None
        if not request:
            return hint("没有找到待接受的请求。", "确认对方名称是否正确，或让对方重新发起切磋/决斗。")
        result = combat_service.duel(from_id, client_id, write_log=False)

        with self.db.transaction() as conn:
            self._expire_requests_conn(conn, client_id, from_id)
            request_row = conn.execute(
                """
                SELECT * FROM duel_requests
                WHERE duel_id = ? AND status = '等待'
                """,
                (request["duel_id"],),
            ).fetchone()
            if not request_row:
                return hint("没有找到待接受的请求。", "可能已超时或被处理，请让对方重新发起。")
            request = dict(request_row)
            if mode == "duel" and not self.spend_stones_conn(conn, client_id, request["stake"]):
                conn.execute(
                    "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                    (request["stake"], from_id),
                )
                conn.execute(
                    "UPDATE duel_requests SET status = '已拒绝' WHERE duel_id = ? AND status = '等待'",
                    (request["duel_id"],),
                )
                return hint("你的源石不足，决斗已取消，发起人的冻结源石已退回。", "补足源石后让对方重新发起决斗。")

            cursor = conn.execute(
                "UPDATE duel_requests SET status = '已接受' WHERE duel_id = ? AND status = '等待'",
                (request["duel_id"],),
            )
            if cursor.rowcount <= 0:
                return hint("没有找到待接受的请求。", "可能已超时或被处理，请让对方重新发起。")

            fee = 0
            if mode == "duel" and result["winner_id"]:
                pool = request["stake"] * 2
                fee = int(pool * 0.03)
                conn.execute(
                    "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                    (pool - fee, result["winner_id"]),
                )
            conn.execute(
                """
                INSERT INTO duel_records
                (duel_id, mode, from_client_id, to_client_id, winner_id, loser_id, stake, fee, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request["duel_id"],
                    "切磋" if mode == "spar" else "决斗",
                    from_id,
                    client_id,
                    result["winner_id"],
                    result["loser_id"],
                    request["stake"],
                    fee,
                    result["summary"],
                    ts(),
                ),
            )
            conn.execute(
                "INSERT INTO combat_logs (client_id, target, summary, created_at) VALUES (?, ?, ?, ?)",
                (from_id, client_id, result["summary"], ts()),
            )
            action = "切磋结束" if mode == "spar" else "决斗结束"
            detail = (
                f"duel_id={request['duel_id']}, opponent={client_id}, "
                f"winner={result['winner_id'] or ''}, stake={request['stake']}, fee={fee}"
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
                (from_id, action, detail, ts()),
            )
            conn.execute(
                "INSERT INTO game_logs (client_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
                (
                    client_id,
                    action,
                    (
                        f"duel_id={request['duel_id']}, opponent={from_id}, "
                        f"winner={result['winner_id'] or ''}, stake={request['stake']}, fee={fee}"
                    ),
                    ts(),
                ),
            )
            if result.get("winner_id") == result.get("left_id"):
                self.record_weapon_combat_conn(
                    conn,
                    result["left_id"],
                    int(result.get("left_weapon_id", 0)),
                    duel_win=True,
                    damage=int(result.get("left_highest_damage", 0)),
                )
            elif result.get("winner_id") == result.get("right_id"):
                self.record_weapon_combat_conn(
                    conn,
                    result["right_id"],
                    int(result.get("right_weapon_id", 0)),
                    duel_win=True,
                    damage=int(result.get("right_highest_damage", 0)),
                )
        settlement = ""
        if mode == "duel":
            settlement = f"决斗结算：胜者获得 {money(request['stake'] * 2 - fee)}，手续费 {money(fee)}。"
        return self._duel_log_block(
            title="切磋结束" if mode == "spar" else "决斗结束",
            result=result,
            settlement=settlement,
        )

    def _duel_log_block(self, *, title: str, result: dict, settlement: str = "") -> str:
        """把切磋/决斗整理成逐次出手代码块。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        lines = [
            title,
            result["summary"],
            "",
            "一、战斗明细",
        ]
        actions = result.get("actions")
        if isinstance(actions, list) and actions:
            for action in actions:
                lines.extend(self._duel_round_lines(action))
        else:
            lines.append("无逐次出手记录。")

        left_id = result.get("left_id", "")
        right_id = result.get("right_id", "")
        lines.extend(
            [
                "",
                "二、最终结算",
                f"胜者：{self.format_player_name(result.get('winner_id', ''))}",
                f"败者：{self.format_player_name(result.get('loser_id', ''))}",
                (
                    f"{self.format_player_name(left_id)}：血气 {result.get('left_hp_left', 0)}/{result.get('left_max_hp', 0)}，"
                    f"精神 {result.get('left_mp_left', 0)}/{result.get('left_max_mp', 0)}"
                ),
                (
                    f"{self.format_player_name(right_id)}：血气 {result.get('right_hp_left', 0)}/{result.get('right_max_hp', 0)}，"
                    f"精神 {result.get('right_mp_left', 0)}/{result.get('right_max_mp', 0)}"
                ),
            ]
        )
        if settlement:
            lines.append(settlement)
        return "```javascript\r\n" + "\r\n".join(lines) + "\r\n```"

    def _parse_duel_message(self, message: str) -> tuple[str, int]:
        """解析决斗参数，返回对方 client_id 和押注金额。"""

        parts = split_words(message)
        if len(parts) < 2:
            return "", 0

        fallback_stake = 0
        for index, part in enumerate(parts):
            stake = to_int(part)
            if stake <= 0:
                continue

            target_parts = parts[:index] + parts[index + 1 :]
            if not target_parts:
                continue

            if fallback_stake <= 0:
                fallback_stake = stake

            target_id = self._player_id(target_parts[-1])
            if target_id:
                return target_id, stake
        return "", fallback_stake

    def _duel_round_lines(self, action: dict) -> list[str]:
        """整理一次行动条出手。"""

        lines = [f"第 {int(action.get('round', 0))} 次行动"]
        for side in ("left", "right"):
            attack = action.get(side)
            if not isinstance(attack, dict):
                continue
            lines.append("  " + self._duel_attack_text(attack))
        return lines

    def _duel_attack_text(self, attack: dict) -> str:
        """整理一次玩家出手。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        actor = self.format_player_name(str(attack.get("actor_id", "")))
        target = self.format_player_name(str(attack.get("target_id", "")))
        if attack.get("skill_used"):
            move = f"技能「{attack.get('skill_name', '')}」"
            cost = f"，消耗精神 {int(attack.get('mp_cost', 0))}"
        else:
            move = "普通攻击"
            cost = ""
        if attack.get("dodged"):
            effect = CombatCore.action_effect_text(attack)
            effect_text = f"，{effect}" if effect else ""
            return (
                f"{actor} 出手：{move} 被 {target} 闪过{effect_text}{cost}；"
                f"{target} 血气 {attack.get('target_hp_left', 0)}，精神 {attack.get('target_mp_left', 0)}"
            )
        combo = int(attack.get("combo_damage", 0))
        combo_text = f"，连击追加 {combo}" if combo > 0 else ""
        steal = int(attack.get("life_steal", 0))
        steal_text = f"，吸血 +{steal}" if steal > 0 else ""
        effect = CombatCore.action_effect_text(attack)
        effect_text = f"，{effect}" if effect else ""
        return (
            f"{actor} 出手：{move}，对 {target} 造成 {int(attack.get('damage', 0))} 伤害"
            f"{combo_text}{steal_text}{effect_text}{cost}；"
            f"{target} 血气 {attack.get('target_hp_left', 0)}，精神 {attack.get('target_mp_left', 0)}"
        )

    def _reject(self, client_id: str, message: str, mode: str) -> str:
        """拒绝对战请求。"""
        #TODO 按钮审查：这里会生成回复文本，按需把命令写成 <命令>。

        _, error = self.require_player(client_id)
        if error:
            return error
        from_id = self._player_id_from_last_arg(message)
        if not from_id:
            command = "拒绝切磋" if mode == "spar" else "拒绝决斗"
            return hint("没有找到发起人。", f"发送：{command} 发起人名称，也可以直接@发起人。")
        with self.db.transaction() as conn:
            self._expire_requests_conn(conn, client_id, from_id)
            request = conn.execute(
                """
                SELECT * FROM duel_requests
                WHERE mode = ? AND from_client_id = ? AND to_client_id = ? AND status = '等待'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (mode, from_id, client_id),
            ).fetchone()
            if not request:
                return hint("没有找到待拒绝的请求。", "确认对方名称是否正确，或忽略已超时的请求。")
            cursor = conn.execute(
                "UPDATE duel_requests SET status = '已拒绝' WHERE duel_id = ? AND status = '等待'",
                (request["duel_id"],),
            )
            if cursor.rowcount <= 0:
                return hint("没有找到待拒绝的请求。", "可能已超时或被处理，无需重复拒绝。")
            if mode == "duel":
                conn.execute(
                    "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                    (request["stake"], from_id),
                )
        return "已拒绝。"

    def _player_id_from_last_arg(self, message: str) -> str:
        """取最后一个参数，并按 client_id / 名称查玩家。"""

        parts = split_words(message)
        return self._player_id(parts[-1]) if parts else ""

    def _player_id(self, value: str) -> str:
        """把一个参数当作 client_id 或玩家名查询。"""

        text = value.strip()
        if not text:
            return ""
        if self.player(text):
            return text
        row = self.db.fetch_one(
            "SELECT client_id FROM players WHERE display_name = ?",
            (text,),
        )
        return str(row["client_id"]) if row else ""

    def _expire_requests_conn(self, conn, *client_ids: str) -> None:
        """把已超时的等待请求标记为超时，并退回决斗冻结源石。"""

        ids = [client_id for client_id in dict.fromkeys(client_ids) if client_id]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = conn.execute(
                f"""
                SELECT * FROM duel_requests
                WHERE status = '等待'
                  AND expires_at <= datetime('now', 'localtime')
                  AND (
                    from_client_id IN ({placeholders})
                    OR to_client_id IN ({placeholders})
                  )
                """,
                (*ids, *ids),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM duel_requests
                WHERE status = '等待'
                  AND expires_at <= datetime('now', 'localtime')
                """
            ).fetchall()

        for row in rows:
            cursor = conn.execute(
                "UPDATE duel_requests SET status = '已超时' WHERE duel_id = ? AND status = '等待'",
                (row["duel_id"],),
            )
            if cursor.rowcount <= 0:
                continue
            if row["mode"] == "duel" and row["stake"] > 0:
                conn.execute(
                    "UPDATE players SET source_stones = source_stones + ? WHERE client_id = ?",
                    (row["stake"], row["from_client_id"]),
                )
            conn.execute(
                """
                INSERT INTO game_logs (client_id, action, detail, created_at)
                VALUES (?, '对战超时', ?, datetime('now', 'localtime'))
                """,
                (row["from_client_id"], f"duel_id={row['duel_id']}, stake={row['stake']}"),
            )


service = DuelService(db)

__all__ = ["DuelService", "service"]
