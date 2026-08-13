# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - A2-越层(方案4.2.4): 回滚统计逻辑从 operation_rollback 下沉到 task 域,
#   消除 services/safety→services/task 越层依赖; rollback_session 只做文件回滚, 统计由本服务编排
# 2026-08-13 - 小沈 - BUG-36修复(三堂会审): 统计更新失败时在 result 中附加 stats_updated=False 标记,
#   让调用方知晓统计状态(不静默吞没), 但不抛异常(回滚已成功, 不应致 API 报错); 调用方可按需告警
"""
task_rollback_service — 任务回滚编排服务(task 域)

职责: 执行任务回滚(调 safety 域 rollback_session) + 串联 task_tracker 统计(回滚状态贯通)
依赖方向: api → services/task → services/safety (单向, 无循环)
小欧 2026-08-12 A2-越层拆分
"""
from typing import Dict, Any

from app.logger import logger
from app.safety.operation_rollback import rollback_session
from app.services.task.task_db import get_tracker


def rollback_task_with_stats(task_id: str) -> Dict[str, Any]:
    """回滚任务所有操作并贯通 task_tracker 统计

    编排: ①safety 域执行文件回滚 → ②task 域更新回滚统计。
    返回结构与 rollback_session 一致(operation_id/type/success 列表 + 汇总), 兼容原调用方契约。
    """
    result = rollback_session(task_id)
    success_op_ids = [
        op.get("operation_id") for op in result.get("operations", []) if op.get("success")
    ]
    # BUG-36修复(三堂会审 小沈 2026-08-13): 统计更新失败时在 result 中附加 stats_updated=False 标记,
    #   让调用方知晓统计状态(不静默吞没), 但不抛异常(回滚已成功, 不应致 API 报错); 调用方可按需告警。
    stats_updated = True
    if success_op_ids:
        try:
            get_tracker().mark_rolled_back(task_id, op_ids=success_op_ids)
            logger.info(f"Rollback stats updated for {task_id}: {len(success_op_ids)} ops")
        except Exception as e:
            stats_updated = False
            logger.error(f"Failed to update rollback stats for {task_id}: {e}")
    if isinstance(result, dict):
        result["stats_updated"] = stats_updated
    return result
