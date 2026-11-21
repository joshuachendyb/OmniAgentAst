# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: 后台命令完成通知路由(services 层)。tools/shell_background 只产生
#   完成事实并经注入回调转交, 本模块负责注入活跃任务或唤醒续跑, 保持 tools→services 不越层
# 编辑历史:
# (初版)
# 2026-11-14 商量 - 注入失败分流: 目标任务窗口内终态 → 改走续跑唤醒(原直接落盘会丢唤醒);
#   任务仍活跃(inbox满)时保持落盘兜底, 不再无意义重试 — 商量-2026-11-14
# 2026-11-21 小欧 - 后台查询工具删除后, 落盘兜底的说明同步: 输出文件保留供后续直接读取
# 2026-11-21 小欧 - 降级落盘落实: 四条投递失败路径(无会话归属/inbox满/续跑失败)原只写日志,
#   通知正文实际丢失; 改为追加进输出文件尾部(shell_background.persist_notice_text) — 小欧-2026-11-21
"""
S: bg_shell_notifier — 后台命令完成后的业务路由

按 session 级两级判定:
  同会话有活跃任务 → 注入 system_notice 到活跃任务 inbox(下一轮吸收)
  同会话无活跃任务 → resume_session_with_notice 自动续跑(wake-on-idle)
两者都失败时由调用方(shell_background)保留输出文件, 供后续直接读取。
"""
from app.db import db
from app.logger import logger
from app.services.chat.storage import get_task_session_id
from app.services.chat.stream_orchestrator import resume_session_with_notice
from app.services.task.task_registry import (
    has_active_task_in_session,
    inject_system_notice,
)
from app.tools.fundamental.shell_background import persist_notice_text


async def notify_bg_shell_done(*, shell_id: str, task_id: str, notice_id: str,
                               text: str, output_file: str) -> None:
    """后台命令完成通知路由 — 商量 2026-11-13

    投递失败(无会话归属/inbox满/续跑失败)一律把通知正文追加到输出文件尾部:
    否则 LLM 永远收不到"命令已结束", 磁盘上只剩裸输出 — 小欧-2026-11-21
    """
    try:
        session_id = await db.atxn("chat", lambda c: get_task_session_id(c, task_id))
    except Exception as e:
        logger.warning(f"[bg_shell] {shell_id} 会话反查DB异常(task={task_id}): {e}")
        session_id = None
    if not session_id:
        logger.warning(f"[bg_shell] {shell_id} 任务已清理/无会话归属, 通知降级落盘: {output_file}")
        persist_notice_text(output_file, text)
        return
    active_tid = await has_active_task_in_session(session_id)
    if active_tid is not None:
        ok = await inject_system_notice(active_tid, text)
        if ok:
            return
        # 注入失败两种成因: 目标任务恰在窗口内终态 / inbox 满(任务仍活跃)。
        #   仅前者可改走续跑; 后者再发只会被 register 守卫挡回, 保持落盘兜底 — 商量-2026-11-14
        if await has_active_task_in_session(session_id) is not None:
            logger.warning(f"[bg_shell] {shell_id} 注入失败(inbox满), 降级落盘: {output_file}")
            persist_notice_text(output_file, text)
            return
        logger.info(f"[bg_shell] {shell_id} 目标任务已终态, 改走续跑唤醒")
    ok = await resume_session_with_notice(
        session_id, text, notice_id=notice_id, source_task_id=task_id)
    if not ok:
        logger.warning(f"[bg_shell] {shell_id} 续跑发起失败, 降级落盘: {output_file}")
        persist_notice_text(output_file, text)
