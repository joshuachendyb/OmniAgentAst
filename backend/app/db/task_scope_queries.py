# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-19 小欧 - 新建: 目录清单快照写入。chat_tasks.path_scope_snapshot 的落库口,
#   与 operation_queries 同层同源(db.get_conn 上下文管理器 + 单条 UPDATE), 供 safety 层调用。
#   放 db 层而非 services 层: safety 不得反向依赖 services(2026-08-17 架构修复约定)。
"""
task_scope_queries · chat_tasks 目录清单快照写入

小欧 2026-10-19
"""

from typing import Optional

from app.db import db
from app.logger import logger


def save_path_scope_snapshot(task_id: Optional[str], snapshot_json: str) -> bool:
    """把目录清单快照原样写入 chat_tasks.path_scope_snapshot(幂等覆盖)

    Returns:
        True = 命中 1 行已写入; False = task_id 为空或未命中任务行(非异常)
    """
    if not task_id:
        return False
    with db.get_conn("chat") as conn:
        n = conn.execute(
            "UPDATE chat_tasks SET path_scope_snapshot=? WHERE task_id=?",
            (snapshot_json, task_id),
        ).rowcount
    if n == 0:
        logger.debug(f"[task_scope_queries] 快照未写入: 任务行缺失或已清理 task_id={task_id}")
    return n == 1


__all__ = ["save_path_scope_snapshot"]
