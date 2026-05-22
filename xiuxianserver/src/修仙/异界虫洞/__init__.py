"""异界虫洞组件 WS 命令。"""

from __future__ import annotations

from launch.adapter.ws import WsMessageHandler, manager as ws_manager

from .service import service


@WsMessageHandler.handler(cmd=("虫洞", "异界虫洞"), priority=100, block=True)
async def ws_wormhole_status(client_id: str, message: str) -> None:
    """查看当前异界虫洞。"""

    await ws_manager.send(service.status(client_id), client_id)


@WsMessageHandler.handler(cmd=("虫洞状态", "状态虫洞"), priority=100, block=True)
async def ws_wormhole_status_alias(client_id: str, message: str) -> None:
    """查看当前异界虫洞状态。"""

    await ws_manager.send(service.status(client_id), client_id)


@WsMessageHandler.handler(cmd=("挑战虫洞", "虫洞挑战"), priority=100, block=True)
async def ws_wormhole_challenge(client_id: str, message: str) -> None:
    """挑战当前虫洞 Boss。"""

    await ws_manager.send(service.challenge(client_id), client_id)


@WsMessageHandler.handler(cmd=("虫洞排行", "排行虫洞"), priority=100, block=True)
async def ws_wormhole_ranking(client_id: str, message: str) -> None:
    """查看虫洞伤害排行。"""

    await ws_manager.send(service.ranking(client_id), client_id)


@WsMessageHandler.handler(cmd=("虫洞奖励", "奖励虫洞"), priority=100, block=True)
async def ws_wormhole_reward(client_id: str, message: str) -> None:
    """领取虫洞贡献奖励。"""

    await ws_manager.send(service.reward(client_id), client_id)
