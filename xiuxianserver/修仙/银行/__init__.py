"""银行组件 WS 命令。"""

from __future__ import annotations

from launch.adapter.ws import WsMessageHandler, manager as ws_manager

from ..common import to_int
from ..reply import send_reply
from .service import service


@WsMessageHandler.handler(cmd="银行", priority=100, block=True)
async def ws_bank_info(client_id: str) -> None:
    """查看银行。"""

    await send_reply(client_id, service.info(client_id), ws_manager, service)


@WsMessageHandler.handler(cmd="银行结息", priority=100, block=True)
async def ws_bank_settle(client_id: str) -> None:
    """银行结息。"""

    await send_reply(client_id, service.settle(client_id), ws_manager, service)


@WsMessageHandler.handler(cmd=("银行升级", "升级银行"), priority=100, block=True)
async def ws_bank_upgrade(client_id: str) -> None:
    """升级银行。"""

    await send_reply(client_id, service.upgrade(client_id), ws_manager, service)


@WsMessageHandler.handler(cmd=("货币存入", "存入货币"), priority=100, block=True)
async def ws_bank_deposit(client_id: str, message: str) -> None:
    """存入货币。"""

    await send_reply(client_id, service.deposit(client_id, to_int(message)), ws_manager, service)


@WsMessageHandler.handler(cmd=("货币取出", "取出货币"), priority=100, block=True)
async def ws_bank_withdraw(client_id: str, message: str) -> None:
    """取出货币。"""

    await send_reply(client_id, service.withdraw(client_id, to_int(message)), ws_manager, service)
