# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: 后台唤醒续跑的上下文链判定(设计文档[33]第8.11章)。
# 2026-11-13 商量 - 三堂会审复核修正: ①链根继承来源任务自身登记的 context_root_task_id(链不断代),
#   原取会话最新任务链根会把"来源任务之前的链"截断; ②删 USER/SYSTEM_TRIGGERED 死分支
#   (全仓唯一调用点只走续跑, 用户路径仍由编排器现役逻辑承担, YAGNI/禁止backward)。
# 编辑历史:
# (初版)
"""
S: creation_source — 后台唤醒续跑(SYSTEM_RESUME)的上下文链判定

创建来源落库值: user(用户手动, 默认) / system_resume(后台唤醒续跑)。
本模块只承接 system_resume 的 link 判定: 恒 linked, 链根继承来源任务登记的链根。
"""
from typing import Optional, Tuple

from app.db import db
from app.logger import logger
from app.services.chat.storage import get_task_chain_root


async def resolve_resume_link_context(
    session_id: str,
    task_id: str,
    source_task_id: Optional[str] = None,
) -> Tuple[str, str, Optional[str]]:
    """后台唤醒续跑的上下文链判定 — 商量 2026-11-13

    返回 (context_link_mode, context_root_task_id, _history_root)。
    _history_root 为装历史用的根: None=不装历史。
    恒 linked 且不回写会话 link 开关; 链根继承来源任务登记的链根(链不断代),
    来源任务无登记(异常/未落库)时 fail-closed 以自身为根不装历史。
    """
    mode, root, hist = "linked", task_id, None
    if not source_task_id:
        logger.warning(f"[creation_source] 续跑缺来源任务(session={session_id}), 以自身为根不装历史")
        return mode, root, hist
    try:
        src_root = await db.atxn("chat", lambda c: get_task_chain_root(c, source_task_id))
    except Exception as e:
        logger.warning(f"[creation_source] 续跑取来源任务链根失败(source={source_task_id}): {e}")
        src_root = None
    if src_root:
        root, hist = src_root, src_root
    return mode, root, hist
