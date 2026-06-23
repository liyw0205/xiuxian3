"""世界皮肤组件 WS 命令。"""

from __future__ import annotations

from launch.adapter.ws import WsMessageHandler, manager as ws_manager

from ..reply import send_reply
from .service import service


@WsMessageHandler.handler(cmd="世界皮肤", priority=100, block=True)
async def ws_world_skin_info(client_id: str) -> None:
    """查看当前世界皮肤。"""

    await send_reply(client_id, service.info(client_id), ws_manager, service)


@WsMessageHandler.handler(cmd="世界皮肤切换", priority=100, block=True)
async def ws_world_skin_switch(client_id: str, message: str) -> None:
    """切换世界皮肤。"""

    await send_reply(client_id, service.switch(client_id, message), ws_manager, service)
