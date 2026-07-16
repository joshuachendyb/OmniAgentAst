# -*- coding: utf-8 -*-
"""
id_utils — ID 生成公用函数

抽自 task_db.add_operation 与 operation_recorder.record_operation 的 op-{hex} 生成（DRY）— 小欧 2026-07-16
复用优先: 全仓 operation_id 统一由此生成, 禁止各处再写 f"op-{uuid4().hex}"
"""
from uuid import uuid4


def generate_operation_id() -> str:
    """生成统一格式 op-{hex}, 全链路文件/任务操作 ID 同源 — 小欧 2026-07-16"""
    return f"op-{uuid4().hex}"
