# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: 后台命令完成通知路由(services 层)。tools/shell_background 只产生
#   完成事实并经注入回调转交, 本模块负责注入活跃任务或唤醒续跑, 保持 tools→services 不越层
# 编辑历史:
# (初版)
"""
S: bg_shell_notifier — 后台命令完成后的业务路由

按 session 级两级判定:
  同会话有活跃任务 → 注入 system_notice 到活跃任务 inbox(下一轮吸收)
  同会话无活跃任务 → resume_session_with_notice 自动续跑(wake-on-idle)
两者都失败时由调用方(shell_background)保留输出文件供 bg_task_query 兜底查询。
"""
from app.db import db
from app.logger import logger
from app.services.chat.storage import get_task_session_id
from app.services.chat.stream_orchestrator import resume_session_with_notice
from app.services.task.task_registry import (
    has_active_task_in_session,
    inject_system_notice,
)


async def notify_bg_shell_done(*, shell_id: str, task_id: str, notice_id: str,
                               text: str, output_file: str) -> None:
    """后台命令完成通知路由 — 商量 2026-11-13"""
    try:
        session_id = await db.atxn("chat", lambda c: get_task_session_id(c, task_id))
    except Exception as e:
        logger.warning(f"[bg_shell] {shell_id} 会话反查DB异常(task={task_id}): {e}")
        session_id = None
    if not session_id:
        logger.warning(f"[bg_shell] {shell_id} 任务已清理/无会话归属, 通知降级落盘: {output_file}")
        return
    active_tid = await has_active_task_in_session(session_id)
    if active_tid is not None:
        ok = await inject_system_notice(active_tid, text)
        if not ok:
            logger.warning(f"[bg_shell] {shell_id} 注入失败(inbox满/终态窗口), 降级落盘: {output_file}")
        return
    ok = await resume_session_with_notice(
        session_id, text, notice_id=notice_id, source_task_id=task_id)
    if not ok:
        logger.warning(f"[bg_shell] {shell_id} 续跑发起失败, 降级落盘: {output_file}")
