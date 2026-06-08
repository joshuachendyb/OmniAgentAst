# -*- coding: utf-8 -*-
"""
reset — 从 factory.py 拷出

拷贝来源: factory.py 第252-262行
"""

from app.services.factory.close_instance_sync import close_instance_sync
from app.services.factory.get_service import _instance, _current_provider


def _clear_global_state() -> None:
    """清空全局状态 - 小沈 2026-06-08"""
    import app.services.factory.get_service as gs
    old = gs._instance
    gs._instance = None
    gs._current_provider = ""
    return old


def _log_reset() -> None:
    """记录重置日志 - 小沈 2026-06-08"""
    print("[AIServiceFactory] 工厂状态已重置")


def reset():
    """拷贝自 factory.py 第252-262行"""
    old = _clear_global_state()
    close_instance_sync(old)
    _log_reset()
