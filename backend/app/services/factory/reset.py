# -*- coding: utf-8 -*-
"""
reset — 从 factory.py 拷出

拷贝来源: factory.py 第252-262行
P1-07/P2-07修复: 使用公开reset_instance替代直接操作私有变量
"""

from app.services.factory.close_instance_sync import close_instance_sync
from app.services.factory.get_service import reset_instance


def _log_reset() -> None:
    """记录重置日志 - 小沈 2026-06-08"""
    print("[AIServiceFactory] 工厂状态已重置")


def reset():
    """拷贝自 factory.py 第252-262行"""
    old = reset_instance()
    close_instance_sync(old)
    _log_reset()
