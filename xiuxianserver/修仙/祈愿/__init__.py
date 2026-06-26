"""祈愿组件命令。"""

from __future__ import annotations

from launch.adapter import Depends, MessageHandler, manager

from ..identity import current_player_id
from ..reply import send_reply
from .service import WishDrawResult, service


@MessageHandler.handler(cmd=("祈愿", "抽奖"), priority=100, block=True)
async def ws_wish_draw(player_id: str = Depends(current_player_id)) -> None:
    """消耗一枚流光签进行一次祈愿。"""

    await _send_wish_draw_result(player_id, service.draw_result(player_id, 1))


@MessageHandler.handler(cmd=("十连祈愿", "十连抽奖"), priority=100, block=True)
async def ws_wish_draw_ten(player_id: str = Depends(current_player_id)) -> None:
    """消耗十枚流光签进行十次祈愿。"""

    await _send_wish_draw_result(player_id, service.draw_result(player_id, 10))


@MessageHandler.handler(cmd=("祈愿奖池", "抽奖奖池"), priority=100, block=True)
async def ws_wish_pool(player_id: str = Depends(current_player_id)) -> None:
    """查看当前祈愿奖池。"""

    await send_reply(player_id, service.pool_info(player_id), manager, service)


@MessageHandler.handler(cmd=("我的凭证", "我的奖品"), priority=100, block=True)
async def ws_wish_vouchers(player_id: str = Depends(current_player_id)) -> None:
    """查看祈愿获得的凭证。"""

    await send_reply(player_id, service.my_vouchers(player_id), manager, service)


@MessageHandler.handler(cmd=("祈愿记录", "抽奖记录"), priority=100, block=True)
async def ws_wish_records(player_id: str = Depends(current_player_id)) -> None:
    """查看最近祈愿记录。"""

    await send_reply(player_id, service.records(player_id), manager, service)


async def _send_wish_draw_result(player_id: str, result: WishDrawResult) -> None:
    """祈愿成功时把演出 GIF 嵌入结算富文本，同一条消息发出。"""

    await send_reply(player_id, result.message_with_animation(), manager, service)
