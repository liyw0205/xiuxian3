"""修仙物品详情服务。"""

from __future__ import annotations

from ..common import CoreService, format_effect, hint
from ..sql import db


class TreasureService(CoreService):
    """查询修仙物品定义。

    玩家真正的存储只有两个：
    - 背包：存放占负重的普通物品。
    - 纳戒：存放不占负重的恢复类、宝石和技能书。

    这里查的是“定义资料”，不是玩家库存。
    """

    def info(self, client_id: str, item_name: str) -> str:
        """查看任意修仙物品说明。"""

        _, error = self.require_player(client_id)
        if error:
            return error
        name = item_name.strip()
        if not name:
            return hint("缺少物品名称。", "发送：查看修仙物品 福袋")

        item = self.item_def_by_name(name)
        if item:
            return self._backpack_item_text(item)

        item = self.equipment_item_def_by_name(name)
        if item:
            return self._ring_item_text(item)

        return hint(f"没有找到修仙物品：{name}。", "发送：背包 或 纳戒，复制准确物品名后再查。")

    @staticmethod
    def _backpack_item_text(item: dict) -> str:
        """格式化背包物品定义。"""

        return (
            f"☆{item['name']}☆\n"
            f"存放:背包 分类:{item['category']} 品级:{item['quality']} 重量:{item['weight']}\n"
            f"跑商:{'可' if item['tradeable'] else '不可'} 使用:{'可' if item['usable'] else '不可'}\n"
            f"基准价:{item['base_price']}\n"
            f"效果:{format_effect(item['effect'])}\n"
            f"说明:{item['desc']}"
        )

    @staticmethod
    def _ring_item_text(item: dict) -> str:
        """格式化纳戒物品定义。"""

        return (
            f"☆{item['name']}☆\n"
            f"存放:纳戒 分类:{item['category']} 品级:{item['quality']}\n"
            f"目标:{item['target_type']} 使用:{'可' if item['usable'] else '不可'}\n"
            f"效果:{format_effect(item['effect'])}\n"
            f"说明:{item['desc']}"
        )


service = TreasureService(db)

__all__ = ["TreasureService", "service"]
