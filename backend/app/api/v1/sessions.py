# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 修复: 删手动BEGIN/COMMIT，归属get_conn事务管理
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处写入改 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤3): 业务逻辑(create/list/update/delete/titles_batch + 辅助函数)迁入
#   services/chat/session_service.py; 删除会话的 display_name 缓存清理改经 message_service.delete_session_display_names
#   (不再 direct import messages 缓存对象)。本文件降为路由薄壳(DTO+路由+调service)。
# 2026-08-20 - 小欧 - 10.5 问题4/6 三堂会审落地: 新增 GET /sessions/{id}/tasks(B1会话任务列表+任务数=用户消息数) +
#   GET /sessions/{id}/trust(D1信任清单) + DELETE /sessions/{id}/trust/{tool}(D3撤销信任)。
# 2026-08-26 - 小欧 - D-2(8.D): 新增 GET /sessions/{session_id} 单会话信息路由(调 session_service.get_session_info),
#   使用场景: 设置界面读取会话级信息(title/created_at/updated_at/sessionModel) + 顶栏创建/更新时间悬浮数据源。
#   路由置于文件末尾(防御性习惯; 本路由与 /titles/batch、/{id}/tasks 等子路径段数不同, 实际无遮蔽关系)。
# 2026-08-30 - 小欧 - 会话响应增强 v1.103: 响应新增 latest_task_id(最新任务显式锚点, 配合 storage.list_session_tasks 三元组返回解包, 排序一义后顶栏锚点不依赖 DESC 首行)。
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5(北京老陈定案, 详见doc-9月优化/会话信任功能修复方案): DELETE /sessions/{id}/trust/{tool_name} 端点增可选 query `path` 精确撤销——
#   path 传入则精确 DELETE (session_id, tool_name, path) 该路径行; path=None(默认) 删工具级通配行(path IS NULL); 无匹配行返回 404 Trust not found
# 2026-09-03 - 小欧/北京老陈 - sessions端点补日志: trust相关端点(list/delete)补info/warning, 改前无log无法排查信任操作
# 2026-10-01 - 小欧 - 解 [1] E8: 删除 POST /sessions/{id}/execution_steps 端点及其 save_execution_steps/ExecutionStepsUpdate 导入(连带 session_service 同名导入)。该端点全仓零调用方，其底层实现自 2026-08-27 起已不写任何步骤，留着会误导为"步骤落库入口"。真入口见 storage.append_execution_step
# 2026-10-03 - 小欧 - 文档[4] 5.7 项5: 新增 PATCH /sessions/{id}/link(全链路唯一新增端点)
# 2026-10-03 - 小欧 - 文档[4] 5.7.7/5.7.8 废止: 删除 PATCH /sessions/{id}/link 端点(北京老陈定案开关只准随消息发出, 严禁独立影响后端; 前端零调用)。写入口收敛为唯一一条: 消息体 link_enabled -> stream_orchestrator -> storage.set_session_link_conn。
# 2026-10-10 - 小欧 - 新增会话 Workspace 读写端点(GET/PATCH /sessions/{id}/workspaces), 写口唯一,
#   body 即全量覆盖; 禁区整单 422, 会话不存在 404。

# 2026-10-30 小欧 - [54]全链路重构: WorkspaceItem/WorkspaceUpdate 收单形态(list[WorkspaceItem], 不收 list[str]);
#   GET 返回四字段(path/workspace_property/memo/is_default); PATCH 传 dict 三元组。 — 小欧-2026-10-30

"""
sessions — 会话API路由薄壳 (A7 后路由+DTO 调 session_service)
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import db
from app.db.models.chat_models import SessionCreate, SessionListResponse  # noqa: F401 DTO 透传
from app.services.chat.session_service import (
    create_session,
    list_sessions,
    update_session,
    delete_session,
    get_session_titles_batch,
    get_session_info,
    SessionUpdate,
)
from app.services.chat.storage import (
    list_session_tasks,
    list_session_trust,
    delete_session_trust,
)

router = APIRouter()


class _SessionCreate(SessionCreate):
    """会话创建 DTO(继承 models 以兼容现有响应) — 薄壳透传"""
    pass


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


@router.get("/sessions/{session_id}/tasks")
def list_session_tasks_endpoint(session_id: str):
    """B1/问题6(10.5): 会话任务列表 + 任务数 + 最新任务id（任务数=用户消息数, chat_tasks 行数新口径）— 小欧 2026-08-20
    2026-08-30 小欧 会话响应增强 v1.103: 响应新增 latest_task_id(配合 storage 三元组返回, 排序一义后锚点解耦)"""
    with db.get_conn("chat") as conn:
        tasks, total, latest_task_id = list_session_tasks(conn, session_id)
    return {"session_id": session_id, "total": total, "tasks": tasks, "latest_task_id": latest_task_id}


@router.get("/sessions/{session_id}/trust")
def list_session_trust_endpoint(session_id: str):
    """D1(10.5 问题4): 会话已信任工具清单 — 小欧 2026-08-20"""
    # 2026-09-03 小欧/北京老陈: trust查询补日志
    from app.logger import logger as _log
    with db.get_conn("chat") as conn:
        rows = list_session_trust(conn, session_id)
    _log.info(f"[trust] 查询信任清单: session_id={session_id}, count={len(rows)}")
    return {"session_id": session_id, "total": len(rows), "trusted_tools": rows}


@router.delete("/sessions/{session_id}/trust/{tool_name}")
def delete_session_trust_endpoint(session_id: str, tool_name: str, path: Optional[str] = None):
    """D3(10.5 问题4): 撤销会话对指定信任对象的信任 — 小欧 2026-08-20; v1.5 增 query path 精确撤销(path=None 删工具级通配行)"""
    # 2026-09-03 小欧/北京老陈: trust撤销补日志
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
def get_session_workspaces_endpoint(session_id: str):
    """读该会话使用的目录列表。
    BUG-6 订正：不再纯读表直吐 —— 禁区行会原样进面板误导用户。
    改走 `classify_workspace_rows` 同一真源过滤，有效进 `workspaces`，
    不可用(禁区/非法/非目录)进 `unusable` 带原因，前端可置灰。
    会话不存在/已删 → 404(不再对垃圾 id 返回空 200)。
    [16]§3.1#4：顺带返回 `project_root`＋`allowed_dirs` 只读字段，
    供面板只读区展示（全局 config 口径，与删除根同源；只读，绝不进 PATCH）。"""
    from app.config import get_config
    from app.services.chat.workspace_service import (
        get_session_workspaces,
        classify_workspace_rows,
        session_exists,
    )
    with db.get_conn("chat") as conn:
        if not session_exists(conn, session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        rows = get_session_workspaces(conn, session_id)
    effective, unusable = classify_workspace_rows(rows)
    _cfg = get_config()
    return {
        "session_id": session_id,
        "workspaces": [{"path": p, "workspace_property": r, "memo": m, "is_default": bool(d)}
                       for p, r, m, d in effective],
        "unusable": unusable,
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
        set_session_workspaces,
        session_exists,
        WORKSPACE_REJECTED_FIELD,
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