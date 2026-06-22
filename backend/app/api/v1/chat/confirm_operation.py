# -*- coding: utf-8 -*-
"""
confirm_operation — HITL人工确认路由(API层)

业务逻辑已下沉到 app.services.task.hitl_confirmation
本文件仅保留FastAPI路由函数,消除API层被服务层反向引用的问题。

小沈 2026-06-09 初始版本
小沈 2026-06-17 业务逻辑下沉到service层
"""

from fastapi import Request

from app.services.task.hitl_confirmation import resolve_confirmation


async def confirm_operation(request: Request):
    """
    用户确认操作

    前端调用此接口回传用户选择
    """
    body = await request.json()
    confirm_id = body.get("confirm_id")
    confirmed = body.get("confirmed", True)
    trust_session = body.get("trust_session", False)

    if not confirm_id:
        return {"success": False, "error": "missing confirm_id"}

    ok = resolve_confirmation(confirm_id, confirmed, trust_session)

    if not ok:
        return {"success": False, "error": "confirm_id not found or already processed"}

    return {"success": True}


__all__ = ["confirm_operation"]
