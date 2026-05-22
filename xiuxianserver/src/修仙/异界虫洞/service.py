"""异界虫洞组件服务。

这里只保留一个很薄的入口，让 WS 命令包调用根目录的公共虫洞核心。
真正的动态 Boss 生成、战斗、排行和奖励都在 `wormhole_core.py`。
"""

from ..wormhole_core import service

__all__ = ["service"]
