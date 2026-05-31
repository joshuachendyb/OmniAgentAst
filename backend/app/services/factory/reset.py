# -*- coding: utf-8 -*-
"""
reset — 从 factory.py 拷出

拷贝来源: factory.py 第252-262行
"""

from app.services.factory.close_instance_sync import close_instance_sync
from app.services.factory.get_service import _instance, _current_provider


def reset():
    """拷贝自 factory.py 第252-262行"""
    import app.services.factory.get_service as gs
    old = gs._instance
    gs._instance = None
    gs._current_provider = ""
    close_instance_sync(old)
    print("[AIServiceFactory] 工厂状态已重置")
