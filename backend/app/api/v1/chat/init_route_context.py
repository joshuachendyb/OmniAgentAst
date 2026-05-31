# -*- coding: utf-8 -*-
"""
init_route_context — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第248-253行
"""

import uuid
from typing import Any, Optional, Tuple

from app.services import AIServiceFactory
from app.services.react_sse_wrapper import running_tasks, running_tasks_lock


def init_route_context(provider: str, model: str, ai_service: Any, session_id: str) -> Tuple:
    """拷贝自 chat_router.py 第248-253行"""
    task_id = str(uuid.uuid4())
    if ai_service is None:
        ai_service = AIServiceFactory.get_service_for_model(provider, model)
    return task_id, ai_service, running_tasks, running_tasks_lock
