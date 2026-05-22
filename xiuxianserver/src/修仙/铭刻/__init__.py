"""铭刻组件 WS 命令。"""

from __future__ import annotations

from launch.adapter.ws import WsMessageHandler, manager as ws_manager

from .service import service


@WsMessageHandler.handler(cmd="铭刻", priority=100, block=True)
async def ws_inscription_guide_or_dispatch(client_id: str, message: str) -> None:
    """查看铭刻格式，或按目标分发铭刻。"""

    await ws_manager.send(service.dispatch(client_id, message), client_id)


@WsMessageHandler.handler(cmd="铭刻之羽", priority=100, block=True)
async def ws_inscription_feathers(client_id: str, message: str) -> None:
    """查看未使用的铭刻之羽。"""

    await ws_manager.send(service.feathers(client_id), client_id)


@WsMessageHandler.handler(cmd=("铭刻固定装备", "固定装备铭刻", "铭刻装备", "装备铭刻"), priority=100, block=True)
async def ws_inscription_fixed_equipment(client_id: str, message: str) -> None:
    """铭刻固定装备。"""

    await ws_manager.send(service.fixed_equipment(client_id, message), client_id)


@WsMessageHandler.handler(cmd=("铭刻武器", "武器铭刻"), priority=100, block=True)
async def ws_inscription_weapon(client_id: str, message: str) -> None:
    """铭刻武器。"""

    await ws_manager.send(service.weapon(client_id, message), client_id)


@WsMessageHandler.handler(cmd=("铭刻附魔", "附魔铭刻", "铭刻技能", "技能铭刻"), priority=100, block=True)
async def ws_inscription_enchant(client_id: str, message: str) -> None:
    """铭刻武器上已附魔的技能书。"""

    await ws_manager.send(service.enchant(client_id, message), client_id)
