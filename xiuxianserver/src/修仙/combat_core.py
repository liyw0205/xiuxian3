"""战斗公共结算。

探险和对战都需要战斗计算，所以放在根目录。
二级组件只调用这里，避免“探险引用战斗、对战引用战斗”的组件互绑。
"""

from __future__ import annotations

from .common import CoreService, load_json, random, ts
from .constants import MAX_COMBAT_ROUNDS, WEAPON_TYPE_INTERVAL_FACTORS
from .rules import damage_after_defense, monster_exp
from .sql import db
from .weapon_core import service as weapon_core


class CombatCore(CoreService):
    """玩家打怪和玩家对战的基础结算。"""

    def fight_monster(
        self,
        client_id: str,
        monster: dict,
        start_hp: int | None = None,
        start_mp: int | None = None,
    ) -> dict:
        """玩家和怪物打一场，返回本场摘要。"""

        player = self.player(client_id)
        if not player:
            return {"win": False, "summary": "玩家不存在", "exp": 0, "hp_left": 0}

        weapon = weapon_core.equipped_weapon(client_id)
        skill = weapon_core.skill(weapon["skill_id"]) if weapon else None
        effects = self._merge_effects(self.equipment_bonuses(client_id), self._weapon_effects(weapon))
        skill_interval = self._skill_interval(skill, weapon, effects) if skill else 0
        skill_cost = self._skill_cost(skill, effects) if skill else 0

        hp = int(player["hp"] if start_hp is None else start_hp)
        mp = int(player["mp"] if start_mp is None else start_mp)
        monster_hp = int(monster["hp"])
        rounds = 0
        skill_times = 0
        player_attack = int(player["base_attack"]) + (int(weapon["attack"]) if weapon else 0)

        while hp > 0 and monster_hp > 0 and rounds < MAX_COMBAT_ROUNDS:
            rounds += 1
            raw = self._attack_raw(player_attack, int(player["level"]), effects)
            skill_used = False
            if skill and skill_interval and rounds % skill_interval == 0:
                if mp >= skill_cost:
                    raw = int(raw * self._skill_power(skill, effects))
                    mp -= skill_cost
                    skill_used = True
                    skill_times += 1
            damage = damage_after_defense(raw, monster["defense"], self._pierce_rate(effects))
            damage += self._combo_damage(raw, monster["defense"], effects)
            monster_hp -= damage
            if effects.get("life_steal"):
                hp = min(int(player["max_hp"]), hp + int(damage * effects["life_steal"]))
            if monster_hp <= 0:
                break
            if random.random() >= effects.get("dodge_bonus", 0):
                hurt = damage_after_defense(monster["attack"], player["defense"])
                hp -= self._reduce_damage(hurt, effects, skill_used)

        win = hp > 0 and monster_hp <= 0
        exp = monster_exp(monster["level"], 1.0 if win else 0.25, player["level"])
        summary = (
            f"遭遇 {monster['name']}，战斗 {rounds} 回合，"
            f"{'胜利' if win else '失败'}，技能触发 {skill_times} 次，经验+{exp}"
        )
        return {
            "win": win,
            "summary": summary,
            "exp": exp,
            "hp_left": max(0, hp),
            "mp_left": max(0, mp),
            "monster": monster["name"],
            "drop_item_id": monster["drop_item_id"] if win and random.random() <= monster["drop_chance"] else "",
        }

    def duel(self, left_id: str, right_id: str, write_log: bool = True) -> dict:
        """两个玩家切磋；只算胜负，不写回真实血气精神。"""

        left = self.player(left_id)
        right = self.player(right_id)
        if not left or not right:
            return {"winner_id": "", "loser_id": "", "summary": "玩家不存在"}

        left_weapon = weapon_core.equipped_weapon(left_id)
        right_weapon = weapon_core.equipped_weapon(right_id)
        left_skill = weapon_core.skill(left_weapon["skill_id"]) if left_weapon else None
        right_skill = weapon_core.skill(right_weapon["skill_id"]) if right_weapon else None
        left_effects = self._merge_effects(self.equipment_bonuses(left_id), self._weapon_effects(left_weapon))
        right_effects = self._merge_effects(self.equipment_bonuses(right_id), self._weapon_effects(right_weapon))
        left_hp = int(left["max_hp"])
        right_hp = int(right["max_hp"])
        left_mp = int(left["max_mp"])
        right_mp = int(right["max_mp"])
        left_interval = self._skill_interval(left_skill, left_weapon, left_effects) if left_skill else 0
        right_interval = self._skill_interval(right_skill, right_weapon, right_effects) if right_skill else 0
        left_cost = self._skill_cost(left_skill, left_effects) if left_skill else 0
        right_cost = self._skill_cost(right_skill, right_effects) if right_skill else 0
        rounds = 0

        while left_hp > 0 and right_hp > 0 and rounds < 60:
            rounds += 1
            left_attack = int(left["base_attack"]) + (int(left_weapon["attack"]) if left_weapon else 0)
            right_attack = int(right["base_attack"]) + (int(right_weapon["attack"]) if right_weapon else 0)
            left_skill_used = bool(left_skill and left_interval and rounds % left_interval == 0 and left_mp >= left_cost)
            right_skill_used = bool(right_skill and right_interval and rounds % right_interval == 0 and right_mp >= right_cost)
            if left_skill_used:
                left_mp -= left_cost
            if right_skill_used:
                right_mp -= right_cost
            if random.random() >= right_effects.get("dodge_bonus", 0):
                left_raw = self._attack_raw(left_attack, int(left["level"]), left_effects)
                if left_skill_used:
                    left_raw = int(left_raw * self._skill_power(left_skill, left_effects))
                left_damage = damage_after_defense(left_raw, right["defense"], self._pierce_rate(left_effects))
                left_damage += self._combo_damage(left_raw, right["defense"], left_effects)
                right_hp -= self._reduce_damage(left_damage, right_effects, right_skill_used)
                right_mp = self._suppress_mp(right_mp, int(right["max_mp"]), left_effects)
                if left_effects.get("life_steal"):
                    left_hp = min(int(left["max_hp"]), left_hp + int(left_damage * left_effects["life_steal"]))
            if right_hp <= 0:
                break
            if random.random() >= left_effects.get("dodge_bonus", 0):
                right_raw = self._attack_raw(right_attack, int(right["level"]), right_effects)
                if right_skill_used:
                    right_raw = int(right_raw * self._skill_power(right_skill, right_effects))
                right_damage = damage_after_defense(right_raw, left["defense"], self._pierce_rate(right_effects))
                right_damage += self._combo_damage(right_raw, left["defense"], right_effects)
                left_hp -= self._reduce_damage(right_damage, left_effects, left_skill_used)
                left_mp = self._suppress_mp(left_mp, int(left["max_mp"]), right_effects)
                if right_effects.get("life_steal"):
                    right_hp = min(int(right["max_hp"]), right_hp + int(right_damage * right_effects["life_steal"]))

        if left_hp == right_hp:
            winner_id = left_id if random.random() >= 0.5 else right_id
        elif left_hp > right_hp:
            winner_id = left_id
        else:
            winner_id = right_id
        loser_id = right_id if winner_id == left_id else left_id
        summary = (
            f"{self.format_player_name(left_id)} 对战 {self.format_player_name(right_id)}，"
            f"{rounds} 回合后 {self.format_player_name(winner_id)} 获胜。"
        )
        if write_log:
            self.db.execute(
                "INSERT INTO combat_logs (client_id, target, summary, created_at) VALUES (?, ?, ?, ?)",
                (left_id, right_id, summary, ts()),
            )
        return {"winner_id": winner_id, "loser_id": loser_id, "summary": summary}

    def _weapon_effects(self, weapon: dict | None) -> dict[str, float]:
        """汇总武器已附魔的战斗效果。"""

        effects: dict[str, float] = {}
        if not weapon:
            return effects
        enchant_ids = load_json(weapon.get("enchant_effects"), [])
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

    @staticmethod
    def _merge_effects(*groups: dict[str, float]) -> dict[str, float]:
        """合并装备、宝石和武器附魔效果。"""

        merged: dict[str, float] = {}
        for group in groups:
            for key, value in group.items():
                if isinstance(value, int | float):
                    merged[key] = merged.get(key, 0) + float(value)
        return merged

    @staticmethod
    def _attack_raw(base_attack_value: int, level: int, effects: dict[str, float]) -> int:
        """计算一次普通出手的原始伤害。"""

        stable_bonus = effects.get("hit_bonus", 0) * 0.5
        raw = int(base_attack_value * (1 + stable_bonus))
        return raw + random.randint(0, max(2, level * 2))

    @staticmethod
    def _skill_power(skill: dict, effects: dict[str, float]) -> float:
        """计算武器技能倍率。"""

        power = float(skill["power"])
        power += effects.get("skill_power_bonus", 0)
        power += effects.get("heavy_bonus", 0)
        power += effects.get("single_hit_bonus", 0)
        return max(1.0, power)

    @staticmethod
    def _skill_cost(skill: dict | None, effects: dict[str, float]) -> int:
        """计算释放武器技能需要的精神。"""

        if not skill:
            return 0
        return max(0, int(skill["cost_mp"]) + int(effects.get("mp_delta", 0)))

    @staticmethod
    def _skill_interval(skill: dict | None, weapon: dict | None, effects: dict[str, float]) -> int:
        """计算武器技能间隔。

        技能书不再限制武器类型；武器类型只在这里影响触发频率。
        轻快武器更容易频繁触发，重武器触发更慢但通常基础攻击更高。
        """

        if not skill:
            return 0
        weapon_type = str(weapon.get("weapon_type") if weapon else "")
        type_factor = WEAPON_TYPE_INTERVAL_FACTORS.get(weapon_type, 1.0)
        rate = max(0.6, 1.0 + effects.get("interval_rate", 0))
        interval = round(int(skill["interval"]) * type_factor * rate)
        interval += int(effects.get("interval_delta", 0))
        return max(2, min(12, interval))

    @staticmethod
    def _pierce_rate(effects: dict[str, float]) -> float:
        """把穿透和压防统一成防御穿透率。"""

        return min(0.8, effects.get("pierce_bonus", 0) + effects.get("defense_suppress", 0))

    @staticmethod
    def _combo_damage(raw: int, defense_value: int, effects: dict[str, float]) -> int:
        """按连击类附魔追加一段轻伤害。"""

        if random.random() >= min(0.5, effects.get("combo_bonus", 0)):
            return 0
        rate = min(0.8, 0.35 + effects.get("combo_damage_bonus", 0))
        return damage_after_defense(int(raw * rate), defense_value, CombatCore._pierce_rate(effects))

    @staticmethod
    def _reduce_damage(damage: int, effects: dict[str, float], skill_used: bool) -> int:
        """按防御类附魔降低最终受伤。"""

        rate = effects.get("damage_reduce", 0) + effects.get("crit_resist_bonus", 0)
        if skill_used:
            rate += effects.get("shield_bonus", 0)
        return max(1, int(damage * (1 - min(0.7, rate))))

    @staticmethod
    def _suppress_mp(mp: int, max_mp_value: int, effects: dict[str, float]) -> int:
        """按断念类附魔削掉对手精神。"""

        rate = min(0.25, effects.get("mp_suppress", 0))
        if rate <= 0:
            return mp
        return max(0, mp - int(max_mp_value * rate))


service = CombatCore(db)

__all__ = ["CombatCore", "service"]
