# -*- coding: utf-8 -*-
# v2.0 C1/C2 任务级回放与统计接口 — 小欧 2026-08-19
# 2026-08-29 - 小沈 - 修复#17: 两端点读库由同步 db.get_conn 改为 db.atxn 离载子线程, 不阻塞事件循环
# 2026-10-11 10:13:16 - 小欧 - 北京老陈令「final 的时候回填事件列表」: 新增 POST /chat/execution/task/{task_id}/process-events 端点 + ProcessEventsBody(不设条数上限/不校验 kind, 送什么存什么); 落库经 db.atxn offload(同文件 C1/C2 范式), 存在性用轻量 SELECT 1(不用 get_task_detail 避白跑解析), 404 显式回抛、其余异常只记日志不阻断 — 小欧-2026-10-11
"""
task_execution — C1 任务详情统计 + C2 按 task_id 步骤回放
落在 chat 域（与 execution_stream C3 同域）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.db import db
from app.logger import logger
from app.services.chat.storage import (
    get_task_detail, get_task_tool_stats, load_steps_by_task, load_user_message_by_task,
    save_process_events,
)

router = APIRouter()

class ProcessEventsBody(BaseModel):
    """事件列表快照请求体 — 小欧 2026-10-11

    **不做条数限制, 不校验 kind 合法性**(北京老陈令「不能限制」+「送什么存什么」):
    本层零事件类型知识、不维护任何类型清单、不设条数上限, 原样存前端送来的事件列表。
    真实任务的事件量由前端 useTaskInfo 自然决定(条数等同该任务实际发生的过程事件)。

    typescript 侧对应: TaskDetail.process_events(历史回放读侧) — 小欧-2026-10-11
    """
    events: list = Field(default_factory=list)


@router.get("/chat/execution/task/{task_id}")
async def get_task_detail_endpoint(task_id: str):
    """C1: 任务详情 + 工具统计"""
    def _read(conn):
        task = get_task_detail(conn, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        tool_stats = get_task_tool_stats(conn, task_id)
        user_msg = load_user_message_by_task(conn, task_id)
        return {
            "task": task,
            "tool_stats": tool_stats,
            "user_message": user_msg,
        }
    return await db.atxn("chat", _read)


@router.get("/chat/execution/task/{task_id}/steps")
async def get_task_steps_endpoint(task_id: str):
    """C2: 按 task_id 步骤回放"""
    def _read(conn):
        steps = load_steps_by_task(conn, task_id)
        return {"task_id": task_id, "steps": steps, "count": len(steps)}
    return await db.atxn("chat", _read)


@router.post("/chat/execution/task/{task_id}/process-events")
async def save_task_process_events_endpoint(task_id: str, body: ProcessEventsBody):
    """事件列表快照回填(北京老陈令「final 的时候回填事件列表」) — 小欧 2026-10-11

    数据源是前端 useTaskInfo 产出的 processEvents(即事件列表/浮层显示的那份),
    前端收到 type='final' 帧时调用一次。**排除 heartbeat 由前端 filter 完成, 本层不判类型。**

    **不做条数限制**(北京老陈令「不能限制」), 原样存前端送来的事件列表。

    落库 offload 出事件循环(同本文件 C1/C2 范式): 被动写端点不做 loop 内同步 DB I/O。
    失败只记日志不回滚 —— 北京老陈定案「回填失败就失败, 不紧要」, 且绝不让
    快照写入失败打断任务收尾链路。

    幂等: 同 task_id 重复调用覆盖为最新快照。
    """
    def _write(conn):
        # 存在性校验用轻量单列查询, 不用 get_task_detail —— 后者会连带跑 parse_json(artifacts/
        # process_events)+ parse_session_model + history_context 子查询, 为一次存在性判断白跑
        # 四段解析(KISS-DIRECT/SLAP: 写端点只需"这行在不在")。
        exists = conn.execute(
            "SELECT 1 FROM chat_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        save_process_events(conn, task_id, body.events)
    try:
        await db.atxn("chat", _write)
    except HTTPException:
        raise                              # 任务不存在 = 调用方错误, 显式 404 不吞
    except Exception as e:
        # 北京老陈定案「回填失败就失败, 不紧要」: 非 404 的异常(如 DB 锁/IO)只记日志,
        # 返回 success 避免前端误判打断任务收尾。atxn 会回抛异常, 故此处能捕获。
        logger.warning(f"[task] 事件列表快照回填失败(task={task_id}): {e}")
    return {"success": True, "count": len(body.events)}
