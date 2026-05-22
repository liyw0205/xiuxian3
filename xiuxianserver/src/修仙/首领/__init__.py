"""首领组件 WS 命令。"""

from __future__ import annotations

from launch.adapter.ws import WsMessageHandler, manager as ws_manager

from .service import service


@WsMessageHandler.handler(cmd=("首领", "岁时情劫"), priority=100, block=True)
async def ws_seasonal_boss_status(client_id: str, message: str) -> None:
    """查看今日岁时情劫。"""

    await ws_manager.send(service.status(client_id), client_id)


@WsMessageHandler.handler(cmd=("首领状态", "状态首领"), priority=100, block=True)
async def ws_seasonal_boss_status_alias(client_id: str, message: str) -> None:
    """查看今日岁时情劫状态。"""

    await ws_manager.send(service.status(client_id), client_id)


@WsMessageHandler.handler(cmd=("挑战首领", "首领挑战"), priority=100, block=True)
async def ws_seasonal_boss_challenge(client_id: str, message: str) -> None:
    """挑战今日岁时情劫。"""

    await ws_manager.send(service.challenge(client_id), client_id)


@WsMessageHandler.handler(cmd=("首领排行", "排行首领"), priority=100, block=True)
async def ws_seasonal_boss_ranking(client_id: str, message: str) -> None:
    """查看岁时情劫伤害排行。"""

    await ws_manager.send(service.ranking(client_id), client_id)


@WsMessageHandler.handler(cmd=("首领奖励", "奖励首领"), priority=100, block=True)
async def ws_seasonal_boss_reward(client_id: str, message: str) -> None:
    """领取岁时情劫贡献奖励。"""

    await ws_manager.send(service.reward(client_id), client_id)
