
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - operations表重命名为task_operations(正名)+在线迁移(RENAME旧表)+操作ID统一generate_operation_id+新增mark_rolled_back方法
# 2026-07-18 - 小欧 - complete_task 的 completed_at 改用 now_str() 序列化入库, 消除对已废弃默认 datetime 适配器(Python3.12+ DeprecationWarning)的依赖, 与 created_at(CURRENT_TIMESTAMP) 空格秒格式统一
# 2026-07-18 - 小欧 - complete_task/create_task/add_operation 时间统一 get_utc_timestamp() UTC Z; TaskQueries 三返回方法 format_timestamp 对外兜底
# 2026-07-18 - 小欧 - add_operation/complete_task INSERT补created_at列对齐第13值get_utc_timestamp()
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处写入 get_utc_timestamp→get_local_iso_timestamp (本地ISO无Z入库)
# 2026-07-23 - 小欧 - #1 fix: get_recent_tasks L210 r.get("completed_at") → r["completed_at"]
#   病根: sqlite3.Row 不支持 .get() 方法(仅支持 [] 和 keys()),
#         r.get("completed_at") 抛出 AttributeError(11次)→main.py全局异常处理器崩溃(10次),
#         修正为 r["completed_at"] 与同方法 L209 r["created_at"] 风格一致。
#         同一行 **dict(r) 已预展开全部列, completed_at 必然在 Row 中, r[] 安全无副作用。
#   方案来源: 欧阳方案 #1 — 一文定位到确切bug行, KISS-DIRECT。
# 2026-07-23 - 小欧 - #1补: get_task 风格统一, 删d=dict(row)临时变量, 改**dict(row) inline
#   原由: L197-198 d.get() 虽不报错(因dict支持.get), 但与get_recent_tasks的**dict(row)+row[]风格不一致
#         ; 保持两方法同一风格, 降低认知负担, KISS-DIRECT。
# 2026-08-09 - 小欧 - task006 P7: create_task 改 INSERT ... ON CONFLICT(task_id) DO NOTHING 幂等化
#   病根: 同一 task_id 重复初始化(agent重建/重放)时裸INSERT抛 UNIQUE constraint failed (日志3个独立日期实据)
#   方案: 仅忽略主键冲突保留首次记录; 验证实证 OR IGNORE 会吞掉CHECK/NOT NULL约束错误(掩盖真实问题),
#         ON CONFLICT(task_id) 只忽略主键, 其它约束照常抛出; P7属agent内部事务, 不产生LLM可见提示
# 2026-08-09 - 小欧 - task005核查P7落地: create_task 幂等冲突(任务已存在)补 logger.info 日志
#   病根: ON CONFLICT DO NOTHING 静默成功, 排查重放/agent重建场景无任何痕迹(可观测性缺失); 仅加日志不改语义
# 2026-08-21 - 小欧 - 12.2-Q4(按文档[1]12.2 diff设计落地): tasks 计数单口径——①Q4-D1 complete_task 删现场
#   COUNT 重算, 只写 status/completed_at; ②Q4-D2 add_operation 成功分支补 success_count+1 增量(与 failed/total
#   同点同事务, 三计数同一口径); rolled_back_count 保留 mark_rolled_back 子查询现场 COUNT 不动(批量迁移=现场数)
"""
task_db — 任务DB持久化（tasks表 + operations表）

合并自: task_tracker + task_queries
小欧 2026-07-10
更新: 小欧 - 2026-07-16 统一TaskID: create_task必填task_id无兜底无返回
"""

import json
import threading
from app.utils.id_utils import generate_operation_id
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08: 全程统一本地时区, 本地ISO无Z入库
from app.utils.time_utils import format_timestamp  # 小欧 2026-07-18: API 对外契约统一兜底
from typing import Optional, Dict, Any, List
from enum import Enum

from app.db import db
from app.logger import logger
from app.utils.json_utils import parse_json
from app.db.models.operation_models import OperationStatus


class TaskStatus(str, Enum):
    """任务生命周期状态 — 小沈 2026-05-29"""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIALLY_ROLLED_BACK = "partially_rolled_back"
    ROLLED_BACK = "rolled_back"


class TaskTracker:
    """任务追踪器 — 双表操作:tasks(task 级)+ operations(operation 级)"""

    # ===== 任务生命周期 =====

    def create_task(self, task_id: str, agent_id: str, description: str) -> None:
        """写入任务记录 — task_id 由调用方统一提供（SSE task_id），tracker 不再自编号 — 小欧 2026-07-16
        2026-08-09 小欧: ON CONFLICT(task_id) DO NOTHING 幂等化 — 同一 task_id 重复初始化(agent重建/重放)
        时保留已存在记录, 消除 UNIQUE 冲突(日志3次实据); 仅忽略主键冲突, 其它约束(CHECK/NOT NULL)照常抛出,
        不掩盖真实问题(验证实证 OR IGNORE 会吞约束错误, 故不用)"""
        with db.get_conn("task_tracker") as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                   (task_id, intent, agent_id, task_description, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO NOTHING""",
                (task_id, "", agent_id, description, TaskStatus.EXECUTING.value, get_local_iso_timestamp()),
            )
            # 2026-08-09 - 小欧 - task005核查P7: 幂等冲突(任务已存在)补日志, 提升可观测性(排查重放/agent重建无痕迹)
            if cur.rowcount == 0:
                logger.info(f"[task_db] create_task 幂等跳过(任务已存在): task_id={task_id}")

    def complete_task(self, task_id: str, success: bool = True) -> None:
        # 12.2-Q4: 删除现场COUNT重算 — success_count 已由 add_operation 实时增量维护(单条操作计数=增量,口径归一) — 小欧 2026-08-21
        status = TaskStatus.SUCCESS.value if success else TaskStatus.FAILED.value
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                """UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?""",
                (status, get_local_iso_timestamp(), task_id),  # 小欧 2026-08-08: 本地ISO无Z入库
            )

    # ===== 操作管理 =====

    def add_operation(
        self,
        task_id: str,
        operation_type: str,
        *,
        operation_id: Optional[str] = None,
        status: Optional[str] = None,
        source_path: Optional[str] = None,
        destination_path: Optional[str] = None,
        backup_path: Optional[str] = None,
        file_size: int = 0,
        file_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> str:
        op_status = status or OperationStatus.SUCCESS.value
        with db.get_conn("task_tracker") as conn:
            task_row = conn.execute(
                "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task_row:
                raise ValueError(f"Task {task_id} not found")

            seq_row = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 "
                "FROM task_operations WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            seq_num = seq_row[0]

            operation_id = operation_id or generate_operation_id()
            conn.execute(
                """INSERT INTO task_operations
                   (operation_id, task_id, operation_type, status,
                    source_path, destination_path, backup_path,
                    file_size, file_hash, sequence_number, details, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",  # 小欧 2026-08-08: created_at 列对齐第13值 get_local_iso_timestamp() 本地ISO无Z入库
                (
                    operation_id, task_id, operation_type, op_status,
                    source_path, destination_path, backup_path,
                    file_size, file_hash, seq_num,
                     json.dumps(details) if details else None, error, get_local_iso_timestamp(),
                 ),
            )
            if op_status == OperationStatus.FAILED.value:
                conn.execute(
                    "UPDATE tasks SET failed_count = failed_count + 1 WHERE task_id = ?",
                    (task_id,),
                )
            else:
                # 12.2-Q4: 成功操作同步增量success_count(与failed/total同点同事务,三计数同一口径) — 小欧 2026-08-21
                conn.execute(
                    "UPDATE tasks SET success_count = success_count + 1 WHERE task_id = ?",
                    (task_id,),
                )
            conn.execute(
                "UPDATE tasks SET total_operations = total_operations + 1 WHERE task_id = ?",
                (task_id,),
            )
        return operation_id

    def mark_rolled_back(
        self, task_id: str, op_ids: Optional[List[str]] = None
    ) -> None:
        with db.get_conn("task_tracker") as conn:
            if op_ids:
                placeholders = ",".join("?" for _ in op_ids)
                conn.execute(
                    f"UPDATE task_operations SET status = ? "
                    f"WHERE operation_id IN ({placeholders})",
                    [OperationStatus.ROLLBACK.value] + op_ids,
                )
                row = conn.execute(
                    "SELECT COUNT(*) FROM task_operations WHERE task_id = ? AND status != ?",
                    (task_id, OperationStatus.ROLLBACK.value),
                ).fetchone()
                all_rolled_back = (row[0] == 0) if row else False
                task_status = (
                    TaskStatus.ROLLED_BACK.value
                    if all_rolled_back
                    else TaskStatus.PARTIALLY_ROLLED_BACK.value
                )
            else:
                conn.execute(
                    "UPDATE task_operations SET status = ? WHERE task_id = ?",
                    (OperationStatus.ROLLBACK.value, task_id),
                )
                task_status = TaskStatus.ROLLED_BACK.value

            conn.execute(
                """UPDATE tasks SET status = ?,
                   rolled_back_count = (
                       SELECT COUNT(*) FROM task_operations WHERE task_id = ? AND status = ?
                   ) WHERE task_id = ?""",
                (task_status, task_id, OperationStatus.ROLLBACK.value, task_id),
            )

    # ===== 报告管理 =====

    def mark_report_generated(self, task_id: str, report_path: str) -> None:
        with db.get_conn("task_tracker") as conn:
            conn.execute(
                "UPDATE tasks SET report_generated = 1, report_path = ? WHERE task_id = ?",
                (report_path, task_id),
            )


# ===== 单例工厂(线程安全) =====

_tracker: Optional[TaskTracker] = None
_lock = threading.Lock()


def get_tracker() -> TaskTracker:
    global _tracker
    if _tracker is None:
        with _lock:
            if _tracker is None:
                _tracker = TaskTracker()
    return _tracker


class TaskQueries:
    """任务查询服务 — 只负责查询,不修改数据"""

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return {
                **dict(row),
                "created_at": format_timestamp(row["created_at"]),
                "completed_at": format_timestamp(row["completed_at"]),
            }

    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{
                **dict(r),
                "created_at": format_timestamp(r["created_at"]),
                "completed_at": format_timestamp(r["completed_at"]),
            } for r in rows]

    def get_operations(self, task_id: str) -> List[Dict[str, Any]]:
        with db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT * FROM task_operations WHERE task_id = ? "
                "ORDER BY sequence_number DESC",
                (task_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("details"):
                    d["details"] = parse_json(d["details"], label="operation_details")
                d["created_at"] = format_timestamp(d.get("created_at"))
                result.append(d)
            return result

