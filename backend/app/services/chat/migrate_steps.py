# -*- coding: utf-8 -*-
"""
migrate_steps — execution_steps 一次性数据迁移

背景: v3.2 终态 Step 统一约定上线前, 历史 chat_messages.execution_steps 存在旧表示:
  - error 末步带 recoverable 布尔(已废弃)
  - 生命周期信号用 step.type='incident' + incident_value('cancelled'/'retrying'/'paused')
  - HITL 用 authorization_required=True
  - 取消终态曾用 FinalStep(type='final', content 含'已取消')

本模块在 init_chat_db 末尾幂等执行一次, 将上述旧表示改写为新统一表示:
  - 删 recoverable
  - incident → type=incident_value(value 注入 step)
  - authorization_required → MetaStep(type='paused', confirm_id=...)
  - 旧取消 FinalStep → MetaStep(type='cancelled')

10规范(DRY): 复用 json_utils.parse_json / safe_json_dumps
小欧 2026-07-13
"""

from typing import Any, Dict, List, Optional

from app.logger import logger
from app.utils.json_utils import parse_json, safe_json_dumps
from app.services.chat.storage import derive_status_from_steps


def _needs_migration(steps: List[dict]) -> bool:
    """判断是否含旧标记, 决定是否需要改写(幂等)"""
    for s in steps:
        if not isinstance(s, dict):
            continue
        if "recoverable" in s:
            return True
        if "authorization_required" in s:
            return True
        if s.get("type") == "incident":
            return True
        if s.get("type") == "final":
            text = (s.get("content") or "") + (s.get("reason") or "")
            if "已取消" in text or "取消" in text:
                return True
    return False


def _confirm_id_of(step: dict) -> str:
    """从 HITL step 提取 confirm_id(兼容 confirm_data / data 两种包裹) — 小欧 2026-07-13"""
    cid = step.get("confirm_id")
    if cid:
        return str(cid)
    for bucket in ("confirm_data", "data"):
        wrapper = step.get(bucket)
        if isinstance(wrapper, dict) and wrapper.get("confirm_id"):
            return str(wrapper.get("confirm_id"))
    return ""


def _migrate_one_step(step: dict) -> dict:
    """改写单条 step; 无旧标记则原样返回"""
    if not isinstance(step, dict):
        return step

    # 1) error 末步 recoverable 删除
    if "recoverable" in step:
        step.pop("recoverable", None)

    # 2) HITL authorization_required → MetaStep(paused)
    if step.get("authorization_required"):
        step.pop("authorization_required", None)
        # 兼容旧 step 把工具信息放在顶层或 data 包裹两种表示 — 小欧 2026-07-13
        _data = step.get("data") if isinstance(step.get("data"), dict) else {}
        return {
            "type": "paused",
            "step": step.get("step"),
            "timestamp": step.get("timestamp"),
            "content": step.get("content") or "等待用户确认授权",
            "confirm_id": _confirm_id_of(step),
            "tool_name": step.get("tool_name") or _data.get("tool_name"),
            "params": step.get("params") or _data.get("params"),
            "safety_level": step.get("safety_level") or _data.get("safety_level"),
        }

    # 3) incident → type=incident_value
    if step.get("type") == "incident":
        incident_value = step.get("incident_value")
        step.pop("incident_value", None)
        new_type = incident_value if incident_value in ("cancelled", "retrying", "paused") else "incident"
        step["type"] = new_type
        if "value" in step:
            step.setdefault("content", step.pop("value"))
        return step

    # 4) 旧取消 FinalStep → MetaStep(cancelled)
    # 小沈 2026-07-13: 旧 FinalStep 取消文本可能在 content 或 response 字段(取决于历史时期),
    # 必须两者都查, 否则用 response 存储的取消 FinalStep 不会被识别, 迁移后仍为 final(误判完成)
    if step.get("type") == "final":
        text = (step.get("content") or "") + (step.get("response") or "") + (step.get("reason") or "")
        if "已取消" in text or "取消" in text:
            return {
                "type": "cancelled",
                "step": step.get("step"),
                "timestamp": step.get("timestamp"),
                "content": step.get("content") or step.get("response") or "任务已被取消",
            }

    return step


def migrate_execution_steps_status(get_conn) -> int:
    """一次性迁移旧 execution_steps; 返回迁移记录数 — 小欧 2026-07-13"""
    updated = 0
    with get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, execution_steps FROM chat_messages WHERE execution_steps IS NOT NULL"
        )
        rows = cursor.fetchall()
        for row in rows:
            msg_id = row["id"]
            steps = parse_json(row["execution_steps"], label="execution_steps")
            if not isinstance(steps, list) or not steps:
                continue
            if not _needs_migration(steps):
                continue
            new_steps = [_migrate_one_step(s) for s in steps]
            status = derive_status_from_steps(new_steps)
            cursor.execute(
                "UPDATE chat_messages SET execution_steps=?, status=? WHERE id=?",
                (safe_json_dumps(new_steps), status, msg_id),
            )
            updated += 1
    if updated:
        logger.info(f"[migrate] 迁移旧 execution_steps 记录数={updated}")
    return updated
