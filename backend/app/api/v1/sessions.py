# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 修复: 删手动BEGIN/COMMIT，归属get_conn事务管理
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处写入改 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
# 2026-08-13 - 小欧 - 业务逻辑(create/list/update/delete/titles_batch+辅助)迁入 session_service;
#   会话 display_name 缓存清理改经 message_service; 本文件降为路由薄壳(DTO+路由+调service)
# 2026-08-20 - 小欧 - 新增 GET /sessions/{id}/tasks(会话任务列表+任务数=用户消息数) +
#   GET /sessions/{id}/trust(信任清单) + DELETE /sessions/{id}/trust/{tool}(撤销信任)
# 2026-08-26 - 小欧 - 新增 GET /sessions/{session_id} 单会话信息路由(调 session_service.get_session_info),
#   供设置界面读会话级信息与顶栏创建/更新时间悬浮; 路由置文件末尾(与子路径段数不同, 无遮蔽)
# 2026-08-30 - 小欧 - 会话响应增强 v1.103: 响应新增 latest_task_id(最新任务显式锚点, 配合 storage.list_session_tasks 三元组返回解包, 排序一义后顶栏锚点不依赖 DESC 首行)。
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5: DELETE /sessions/{id}/trust/{tool_name} 端点增可选 query `path` 精确撤销——
#   path 传入则精确 DELETE (session_id, tool_name, path) 该路径行; path=None(默认) 删工具级通配行(path IS NULL); 无匹配行返回 404 Trust not found
# 2026-09-03 - 小欧 - sessions 端点补日志: trust 相关端点(list/delete)补 info/warning, 改前无 log 无法排查信任操作
# 2026-10-01 - 小欧 - 删除 POST /sessions/{id}/execution_steps 端点及其 save_execution_steps/ExecutionStepsUpdate 导入(连带 session_service 同名导入)。
#   该端点全仓零调用方, 底层自 2026-08-27 起已不写任何步骤, 留着会误导为"步骤落库入口"; 真入口见 storage.append_execution_step
# 2026-10-03 - 小欧 - 新增 PATCH /sessions/{id}/link(全链路唯一新增端点)
# 2026-10-03 - 小欧 - 废止 PATCH /sessions/{id}/link 端点: 开关只准随消息发出, 严禁独立影响后端, 前端零调用。
#   写入口收敛为唯一一条: 消息体 link_enabled -> stream_orchestrator -> storage.set_session_link_conn
# 2026-10-10 - 小欧 - 新增会话 Workspace 读写端点(GET/PATCH /sessions/{id}/workspaces), 写口唯一,
#   body 即全量覆盖; 禁区整单 422, 会话不存在 404。

# 2026-10-30 小欧 - 全链路重构: WorkspaceItem/WorkspaceUpdate 收单形态(list[WorkspaceItem], 不收 list[str]);
#   GET 返回四字段(path/workspace_property/memo/is_default); PATCH 传 dict 三元组。 — 小欧-2026-10-30

# 2026-11-02 小欧 - GET /workspaces 增 prune(默认 false 纯读): 仅面板打开时显式清不可用行,
#   条数按 rowcount 作 pruned 带回; 响应不含 unusable — 小欧-2026-11-02
# 2026-11-02 小欧 - 删死类 _SessionCreate(私有、全仓零引用, 端点直接吃 SessionCreate) — 小欧-2026-11-02
# 2026-11-03 小欧 - 新增 GET /sessions/tasks/running(跨会话在跑任务, 历史页角标/顶栏浮层权威来源)
#   + GET /sessions/tasks/{task_id}(退订后 60s 复核的单任务轻量读, 替代拉整会话任务正文) — 小欧-2026-11-03

"""
sessions — 会话API路由薄壳 (A7 后路由+DTO 调 session_service)
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import db
from app.db.models.chat_models import SessionCreate, SessionListResponse  # noqa: F401 DTO 透传
from app.services.chat.session_service import (
    SessionUpdate,
    create_session,
    delete_session,
    get_session_info,
    get_session_titles_batch,
    list_sessions,
    update_session,
)
from app.services.chat.storage import (
    delete_session_trust,
    get_task_status,
    list_running_tasks,
    list_session_task_artifacts,
    list_session_tasks,
    list_session_trust,
)

router = APIRouter()


@router.post("/sessions")
def create_session_endpoint(session_create: Optional[SessionCreate] = None):
    return create_session(session_create)


@router.get("/sessions")
def list_sessions_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None)
):
    return list_sessions(page, page_size, keyword, is_valid)


@router.put("/sessions/{session_id}")
def update_session_endpoint(session_id: str, update_data: SessionUpdate):
    return update_session(session_id, update_data)


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    return delete_session(session_id)


@router.get("/sessions/titles/batch")
def get_session_titles_batch_endpoint(
    session_ids: str = Query(..., description="逗号分隔的会话ID列表")
):
    return get_session_titles_batch(session_ids)


@router.get("/sessions/tasks/running")
def list_running_tasks_endpoint():
    """跨会话在跑任务(历史页角标/顶栏浮层的后端权威来源): 非终态且非 idle, 只读。 — 小欧-2026-11-03
    前端只在挂载/窗口聚焦/列表重载时各调一次, 不做轮询。"""
    with db.get_conn("chat") as conn:
        tasks = list_running_tasks(conn)
    return {"total": len(tasks), "tasks": tasks}


@router.get("/sessions/tasks/{task_id}")
def get_task_status_endpoint(task_id: str):
    """单任务状态轻量读口(退订后 60s 后台复核专用): task_id 为 UNIQUE, 单行读, 不拉任务正文。 — 小欧-2026-11-03
    任务行不存在返回 {"task": null} 而非 404 —— 前端据此落 idle, "已结束"是常态不是异常。"""
    with db.get_conn("chat") as conn:
        task = get_task_status(conn, task_id)
    return {"task": task}


@router.get("/sessions/{session_id}/tasks")
def list_session_tasks_endpoint(session_id: str):
    """B1/问题6(10.5): 会话任务列表 + 任务数 + 最新任务id（任务数=用户消息数, chat_tasks 行数新口径）— 小欧 2026-08-20
    2026-08-30 小欧 会话响应增强 v1.103: 响应新增 latest_task_id(配合 storage 三元组返回, 排序一义后锚点解耦)"""
    with db.get_conn("chat") as conn:
        tasks, total, latest_task_id = list_session_tasks(conn, session_id)
    return {"session_id": session_id, "total": total, "tasks": tasks, "latest_task_id": latest_task_id}


@router.get("/sessions/{session_id}/artifacts")
def list_session_artifacts_endpoint(session_id: str):
    """本会话全部任务的产出物清单（chat_tasks.artifacts 真源，任务时间倒序）。

    「AI 产出的」唯一真源：产出物是任务产物，工作区内产物走引用模式从不落 attachments
    表 —— 用附件台账判据取该清单恒为空，故独立读口。
    """
    with db.get_conn("chat") as conn:
        artifacts = list_session_task_artifacts(conn, session_id)
    return {"session_id": session_id, "total": len(artifacts), "artifacts": artifacts}


@router.get("/sessions/{session_id}/trust")
def list_session_trust_endpoint(session_id: str):
    """D1(10.5 问题4): 会话已信任工具清单 — 小欧 2026-08-20"""
    # 2026-09-03 小欧: trust查询补日志
    from app.logger import logger as _log
    with db.get_conn("chat") as conn:
        rows = list_session_trust(conn, session_id)
    _log.info(f"[trust] 查询信任清单: session_id={session_id}, count={len(rows)}")
    return {"session_id": session_id, "total": len(rows), "trusted_tools": rows}


@router.delete("/sessions/{session_id}/trust/{tool_name}")
def delete_session_trust_endpoint(session_id: str, tool_name: str, path: Optional[str] = None):
    """D3(10.5 问题4): 撤销会话对指定信任对象的信任 — 小欧 2026-08-20; v1.5 增 query path 精确撤销(path=None 删工具级通配行)"""
    # 2026-09-03 小欧: trust撤销补日志
    from app.logger import logger as _log
    _log.info(f"[trust] 撤销信任: session_id={session_id}, tool={tool_name}, path={path}")
    with db.get_conn("chat") as conn:
        removed = delete_session_trust(conn, session_id, tool_name, path)
    if not removed:
        _log.warning(f"[trust] 撤销失败(未找到): session_id={session_id}, tool={tool_name}, path={path}")
        raise HTTPException(status_code=404, detail="Trust not found")
    _log.info(f"[trust] 撤销成功: session_id={session_id}, tool={tool_name}, path={path}")
    return {"success": True, "session_id": session_id, "tool_name": tool_name, "path": path}


@router.get("/sessions/{session_id}")
def get_session_detail_endpoint(session_id: str):
    """D-2(8.D): 单会话信息 — 设置界面读取会话级信息 + 顶栏创建/更新时间悬浮数据源, 现有端点无单会话信息 — 小欧 2026-08-26"""
    return get_session_info(session_id)


class WorkspaceItem(BaseModel):
    """PATCH 单条目录：path + workspace_property(属性文字标签) + memo(备注)。

    属性/memo 是标注类字段，不参与安全判定。
    DTO 层**不做长度上限**：超长由 service 的 _normalize_ws_meta 截断放行，
    在此拦会让整单 422，与"属性乱填不拒单"的设计前提冲突。"""
    path: str = Field(..., description="目录绝对路径")
    workspace_property: str = Field(
        "read_write", description="工作区属性（read_only/read_write/write/自定义），缺失/空 → read_write")
    memo: Optional[str] = Field(
        None, description="目录备注说明（可选，≤256字符，禁换行；超长由 service 截断）")


class WorkspaceUpdate(BaseModel):
    """PATCH body 即全量覆盖写：传完整新数组，空数组 = 显式清空。

    固定 list[WorkspaceItem] 单一形态。API 与前端同版本发布，不收 list[str]；
    归一（属性/备注缺省、截断）在 service 一处做，DTO 层不重复。"""
    session_workspaces: list[WorkspaceItem] = Field(
        ..., description="会话工作区目录列表（全量覆盖；[] = 清空）")


@router.get("/sessions/{session_id}/workspaces")
def get_session_workspaces_endpoint(session_id: str, prune: bool = False):
    """读该会话使用的目录列表。

    2026-11-02 小欧 - `prune=true` 才清库(面板打开时显式请求), 默认纯读: 历史页/文件页等
    顺手 GET 的调用方不传参即零副作用。清理只删库行不动磁盘, 条数按 rowcount 作 pruned 带回；
    会话不存在/已删 → 404；顺带返回 project_root/allowed_dirs 只读字段（不进 PATCH）。"""
    from app.config import get_config
    from app.services.chat.workspace_service import (
        classify_workspace_rows,
        get_session_workspaces,
        prune_unusable_rows,
        session_exists,
    )
    with db.get_conn("chat") as conn:
        if not session_exists(conn, session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        rows = get_session_workspaces(conn, session_id)
        effective, unusable = classify_workspace_rows(rows)
        # prune 由调用方显式请求: 默认纯读, 浏览类 GET 不改数据 — 小欧-2026-11-02
        pruned = prune_unusable_rows(conn, session_id, unusable) if prune else 0
    _cfg = get_config()
    return {
        "session_id": session_id,
        "workspaces": [{"path": p, "workspace_property": r, "memo": m, "is_default": bool(d)}
                       for p, r, m, d in effective],
        "pruned": pruned,
        "project_root": _cfg.get_project_root(),
        "allowed_dirs": list(_cfg.get_allowed_dirs() or []),
    }


@router.patch("/sessions/{session_id}/workspaces")
def set_session_workspaces_endpoint(session_id: str, body: WorkspaceUpdate):
    """写该会话使用的目录列表 —— body 即全量覆盖写, 空数组=清空列表。
    命中禁区整单 422, 只拒本次 PATCH, 不牵连任何消息。
    会话不存在/已删 → 404, 先于写库(FK=ON 下免 sqlite3.IntegrityError→500)。
    ⚠ 只改数据库行: **不删除磁盘目录** —— 面板移除条目, 目录留在磁盘由用户自行处置。
    元素类型由 WorkspaceUpdate: list[WorkspaceItem] 单一形态, 路径非法(空串/相对路径)由
    _normalize_ws_path 单一真源归入 rejected, 此处不重复校验。"""
    from app.services.chat.workspace_service import (
        WORKSPACE_REJECTED_FIELD,
        session_exists,
        set_session_workspaces,
    )
    with db.get_conn("chat") as conn:
        if not session_exists(conn, session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        rejected = set_session_workspaces(
            conn, session_id,
            [{"path": i.path, "workspace_property": i.workspace_property, "memo": i.memo}
             for i in body.session_workspaces])
    if rejected:
        raise HTTPException(
            status_code=422,
            detail={WORKSPACE_REJECTED_FIELD: rejected},
        )
    return {"success": True, "session_id": session_id}
