# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 注释说明 TASK_TIMEOUT 兜底清理意义(防 running_tasks 内存注册表泄漏); 老陈裁定改为按终态+超时清理: 仅清非活跃(running/paused 外)且超1h任务, 避免误伤长任务/暂停任务
# 2026-09-20 - 小欧 - B组修复(B-3并发守卫/B-4/B-7收尾窗口orphan兜底): ①register_task 锁内同会话活跃任务互斥守卫(TOCTOU根治, 同会话任务必须串行, 违反即抛RuntimeError);
#   ②cleanup_task 删任务前把未吸收的 inbox 消息转入模块级 _orphaned_inbox(task_id→list), drain_inbox 任务已删时从 orphan 找回——收尾窗口注入不静默丢失(B-4/B-7)。
#   compliance: SRP/KISS-DIRECT/DRY(复用inbox队列)/禁止backward
# 2026-09-20 - 小欧 - 三堂会审BUG-10修复: cleanup_expired_tasks过期清理前补orphan转移(与cleanup_task对齐, 防收尾窗口静默丢失)
# 2026-09-20 - 小欧 - 提交前审查缺口补(3项): ①B-3串行守卫命中加专属log(编排泛化error看不清TOCTOU根因);
#   ②drain_inbox orphan找回路径加warning log(B-4/B-7兜底命中可查); ③_orphaned_inbox加_ORPHAN_MAX_ITEMS=100上限
#   与_trim_orphaned_inbox(终态任务无drain_inbox消费, 无上限即永久滞留内存), cleanup/过期两处转移后接入。
#   compliance: KISS-DIRECT(上限防滞留即可, 不做TTL定时器)/禁止backward
# 2026-09-20 - 小欧 - B-3守卫改方案②(北京老陈定案, 弃抛异常): register_task 守卫命中由 raise RuntimeError 改为
#   返回占位活跃task_id(str), 注册成功返回 None —— 调用方(编排层)拿返回值改道注入占位任务, 竞态下消息不丢;
#   签名 None → Optional[str]。compliance: 与B机制"注入不静默丢失"红线同哲学(KISS-DIRECT)
"""
task_registry — running_tasks 数据层唯一入口

写操作(register/cleanup/set)保留在本文件。
纯读查询函数已迁移至 task_state_queries.py，本文件re-export保持兼容。

Author: 小健 - 2026-05-31
更新: 小健 - 2026-06-17 读查询函数迁移至task_state_queries.py
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional   # 2026-09-20 小欧 13.4.1: drain_inbox 返回 List[str] 所需 — 小欧-2026-09-20
from app.services.agent.steps import MetaStep  # 小欧 2026-07-13: build_step_dict 统一走 MetaStep

from app.logger import logger
from app.constants import TASK_TIMEOUT
from app.utils.response_utils import api_success, api_failure

from app.services.task.task_state import (
    check_cancelled,
    check_paused,
    check_was_paused,
    get_task_status,
    is_task_running,
    get_cancel_request_time,
    get_pause_event,
    get_task_field,
    running_tasks_lock,
    running_tasks,
)


# B组调制(B-4/B-7 2026-09-20 小欧): 任务被 cleanup 删除后, 未吸收的 inbox 消息转入此处,
# drain_inbox 找不到任务时从 orphan 找回, 保证收尾窗口注入不静默丢失 — SRP: 孤儿缓存独立于 running_tasks 生命周期
_orphaned_inbox: Dict[str, List[str]] = {}

# 缺口补(2026-09-20 小欧): orphan 上限, 超出丢弃最旧 —— 终态任务不会再有 drain_inbox 消费, 无上限即永久滞留。
# 受控: 上限100条(dict保持插入序, next(iter)即最旧), KISS不做TTL定时器(该场景值小, 定时器过度设计)
_ORPHAN_MAX_ITEMS = 100


def _trim_orphaned_inbox() -> None:
    """孤儿缓存超上限丢弃最旧条目 — 2026-09-20 小欧(缺口补)"""
    while len(_orphaned_inbox) > _ORPHAN_MAX_ITEMS:
        _old_tid = next(iter(_orphaned_inbox))
        _dropped = _orphaned_inbox.pop(_old_tid, None)
        logger.warning(
            f"[TaskRegistry] orphan缓存超限({_ORPHAN_MAX_ITEMS}), 丢弃最旧任务 {_old_tid} "
            f"未吸收注入消息 {len(_dropped) if _dropped else 0} 条")

# ============================================================
# 注册 / 清理
# ============================================================

async def register_task(task_id: str, ai_service: Any, session_id: Optional[str] = None) -> Optional[str]:
    """注册任务到 running_tasks — 小欧 2026-09-20 X5: 增 session_id + 任务级 inbox(运行中注入) — 小欧-2026-09-20
    B-3 守卫(2026-09-20 小欧, 北京老陈定案方案②): 锁内检查同 session 已有活跃任务(running/paused), 存在即
    **返回该活跃任务 task_id** 而非抛异常 —— 根治编排层 has_active_task_in_session 与 register_task 分离 await
    的 TOCTOU(两会话并发双请求可注册双任务), 且不丢消息: 调用方(编排层)拿返回值改道注入占位任务, 消息保住。
    返回 None=注册成功(本任务已入表); 返回 str=同会话已占位(本任务未入表)。同会话任务必须串行(北京老陈铁则)。"""
    async with running_tasks_lock:
        if session_id:
            for _tid, _t in running_tasks.items():
                if (_tid != task_id
                        and _t.get("session_id") == session_id
                        and _t.get("status") in ("running", "paused")):
                    # B-3方案②(2026-09-20 小欧): 返回占位tid, 由调用方改道注入(不丢消息), 不再抛异常
                    logger.warning(
                        f"[B-3串行守卫] 会话 {session_id} 已被占位 {_tid}, 拒绝并行注册 {task_id}"
                        f"(TOCTOU: 编排层 has_active_task 与本注册存在分离窗口, 返回占位tid供注入)")
                    return _tid
        running_tasks[task_id] = {
            "status": "running",
            "cancelled": False,
            "paused": False,
            "session_id": session_id,          # X5/X6 同会话判定
            "_inbox": asyncio.Queue(),         # B机制: 运行中注入消息队列(多条), agent 侧每轮 LLM 调用前合并吸收
            "created_at": datetime.now(),
            "ai_service": ai_service,
            "_task": asyncio.current_task(),
            "_pause_event": asyncio.Event(),
        }
        running_tasks[task_id]["_pause_event"].set()


async def has_active_task_in_session(session_id: str) -> Optional[str]:
    """X5/B: 该会话是否已有活跃任务(running/paused)。返回活跃 task_id(供注入); 无则 None。 — 小欧 2026-09-20"""
    if not session_id:
        return None
    async with running_tasks_lock:
        for _tid, _t in running_tasks.items():
            if _t.get("session_id") == session_id and _t.get("status") in ("running", "paused"):
                return _tid
    return None


async def inject_message_to_task(task_id: str, content: str) -> bool:
    """B机制: 向运行中任务 inbox 投递一条新用户消息(不打断工具执行, 由 agent 下一轮 LLM 调用前合并吸收)。
    返回 True=已投递; False=任务不存在/已终态(投递失败, 由编排降级为新任务)。 — 小欧 2026-09-20"""
    async with running_tasks_lock:
        _t = running_tasks.get(task_id)
        if not _t or _t.get("status") not in ("running", "paused"):
            return False
        _q = _t.get("_inbox")
        if _q is None:
            return False
        _q.put_nowait(content)
    return True


async def drain_inbox(task_id: str) -> List[str]:
    """B机制: agent 侧取走 inbox 全部积压消息(每轮 LLM 调用前合并吸收)。返回消息列表(可为空)。
    B-4/B-7 兜底(2026-09-20 小欧): 任务已被 cleanup 删除(收尾窗口)时, 从 _orphaned_inbox 找回未吸收注入消息,
    保证注入成功即不静默丢失(编排可据此降级/续聊)。 — 小欧 2026-09-20"""
    async with running_tasks_lock:
        _t = running_tasks.get(task_id)
        if not _t:
            # 缺口补(2026-09-20 小欧): orphan 找回路径必须可查(收尾窗口兜底命中 = 注入后任务已终态)
            _orphan = _orphaned_inbox.pop(task_id, [])
            if _orphan:
                logger.warning(
                    f"[B-4/B-7] 任务 {task_id} 已从running_tasks删除, 从orphan找回未吸收注入消息 {len(_orphan)} 条")
            return list(_orphan)
        _q = _t.get("_inbox")
        if _q is None:
            return []
        _msgs = []
        while not _q.empty():
            try:
                _msgs.append(_q.get_nowait())
            except asyncio.QueueEmpty:
                break
    return _msgs


async def cleanup_task(task_id: str) -> bool:
    """清理非cancelled任务,返回True=已清理,False=保留(cancelled记录)
    B-4/B-7 兜底(2026-09-20 小欧): 删除任务前把未吸收的 inbox 消息转入 _orphaned_inbox,
    收尾窗口注入不随队列销毁丢失(drain_inbox 可找回)。"""
    async with running_tasks_lock:
        if task_id not in running_tasks:
            return False
        if running_tasks[task_id].get("status") != "cancelled":
            _q = running_tasks[task_id].get("_inbox")
            if _q is not None:
                _leftover = []
                while not _q.empty():
                    try:
                        _leftover.append(_q.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                if _leftover:
                    _orphaned_inbox[task_id] = _leftover
                    _trim_orphaned_inbox()  # 缺口补(2026-09-20 小欧): 防 orphan 无上限滞留内存
                    logger.warning(
                        f"[TaskRegistry] 任务 {task_id} cleanup 时存在未吸收注入消息 {len(_leftover)} 条, "
                        f"已转 orphan 供找回(防收尾窗口静默丢失)")
            del running_tasks[task_id]
            return True
        return False


async def cleanup_expired_tasks() -> None:
    """清理过期任务(running_tasks 内存注册表兜底防泄漏) — 老陈 2026-07-15 注释说明

    设计意图:
      - running_tasks 是进程内内存字典, 正常任务跑完会由 cleanup_task/pop_task_field 自行移除;
        本函数仅作兜底, 清理遗留僵尸任务, 防内存注册表泄漏。
      - 判定依据(老陈 2026-07-15 裁定: 按终态+超时, 避免误伤长任务):
        仅清理「非活跃状态」且「创建超过 TASK_TIMEOUT(1小时)」的任务。
        活跃状态(running/paused)即使超 1 小时也保留 —— running 可能是 legit 长任务,
        paused 是用户暂停待恢复, 均不应被自动清掉; 取消(cancelled)等终态任务无恢复意义, 超时即清理。
        注: 本字典 status 实际取值仅 running/cancelled/paused(status_table 的 completed/failed 是 agent 对象枚举, 不写此字典)。
    """
    now = datetime.now()
    async with running_tasks_lock:
        expired = [
            tid for tid, t in running_tasks.items()
            if t.get("created_at") and now - t["created_at"] > TASK_TIMEOUT
            and t.get("status") not in ("running", "paused")
        ]
        for tid in expired:
            # BUG-10修复(小欧 2026-09-20): 过期清理前把未吸收inbox消息转入orphan, 与cleanup_task对齐(防收尾窗口静默丢失)
            _q = running_tasks[tid].get("_inbox")
            if _q is not None:
                _leftover = []
                while not _q.empty():
                    try:
                        _leftover.append(_q.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                if _leftover:
                    _orphaned_inbox[tid] = _leftover
                    _trim_orphaned_inbox()  # 缺口补(2026-09-20 小欧): 防 orphan 无上限滞留内存
                    logger.warning(
                        f"[TaskRegistry] 过期任务 {tid} cleanup时存在未吸收注入消息 {len(_leftover)} 条, "
                        f"已转orphan供找回")
            del running_tasks[tid]
        if expired:
            logger.info(f"[TaskRegistry] 清理了 {len(expired)} 个过期任务")


# ============================================================
# 读写操作(pop — 读取并删除)
# ============================================================

async def pop_task_field(task_id: str, field: str) -> Any:
    """从任务中弹出一个字段"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if task:
            return task.pop(field, None)
        return None


# ============================================================
# 写操作(set)
# ============================================================

async def set_cancelled(task_id: str, **extra) -> bool:
    """设置任务为cancelled状态,返回是否成功"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return False
        task["cancelled"] = True
        task["status"] = "cancelled"
        task.update(extra)
        return True


async def set_paused(task_id: str) -> dict:
    """设置任务暂停,返回 {"success": bool, "message": str}"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return api_failure(message=f"任务 {task_id} 不存在")
        if task.get("cancelled"):
            return api_failure(message=f"任务 {task_id} 已被中断,无法暂停")
        task["paused"] = True
        task["status"] = "paused"
        pause_event = task.get("_pause_event")
        if pause_event:
            pause_event.clear()
        return api_success(message=f"任务 {task_id} 已暂停")


async def set_resumed(task_id: str) -> dict:
    """设置任务恢复,返回 {"success": bool, "message": str}"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if not task:
            return api_failure(message=f"任务 {task_id} 不存在")
        if task.get("cancelled"):
            return api_failure(message=f"任务 {task_id} 已被中断,无法恢复")
        if not task.get("paused"):
            return api_failure(message=f"任务 {task_id} 未暂停,无法恢复")
        task["paused"] = False
        task["status"] = "running"
        pause_event = task.get("_pause_event")
        if pause_event:
            pause_event.set()
        return api_success(message=f"任务 {task_id} 已继续")


async def set_was_paused(task_id: str, value: bool) -> None:
    """设置 _was_paused 标志"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        if task:
            task["_was_paused"] = value


# ============================================================
# 薄包装: 仅供外部调用
# ============================================================

async def pause_task(task_id: str, session_id=None) -> dict:
    """暂停指定的流式任务"""
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    result = await set_paused(task_id)
    if result["success"]:
        logger.info(f"[Pause] 任务 {task_id} 已暂停")
    return result


async def resume_task(task_id: str, session_id=None) -> dict:
    """继续指定的流式任务"""
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    result = await set_resumed(task_id)
    if result["success"]:
        logger.info(f"[Resume] 任务 {task_id} 已继续")
    return result


async def task_cleanup(task_id: str, llm_call_count: int = 0) -> None:
    """任务完成后清理"""
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {llm_call_count} ======"
    )
    cleaned = await cleanup_task(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成,已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断,保留记录")


def build_step_dict(step: Optional[int], step_type: str, message: str, data=None) -> dict:
    """构建step字典 — 统一走 MetaStep，生命周期事件(type=cancelled/paused/resumed)直接产出 — 小欧 2026-07-13
    说明: 不再产出 incident 裸 dict，前端按 step.type 直接渲染（禁止 backward：代码路径单一）"""
    return MetaStep(type=step_type, step=step, content=message or "", data=data or {}).to_dict()
