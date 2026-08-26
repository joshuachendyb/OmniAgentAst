# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 会话业务服务(方案4.7.3步骤3)。从 api/v1/sessions.py 复制 create_session/list_sessions/
#   update_session/get_session_titles_batch/delete_session + 辅助函数(build_list_where/resolve_update_mode/build_update_sql/
#   build_update_params/record_title_history), 仅改导入归属, 业务逻辑一字不改。删除会话的 display_name 清理改为调
#   message_service.delete_session_display_names(经方法调用, 不 direct import 缓存对象, 单向方法调用)。API 层薄壳化改调本服务。
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.5): 删record_title_history函数及update_session内调用
#   (chat_session_title_history死表退役, 系统已不消费该历史)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 定: L2 会话级模型覆盖 model_override→sessionModel 结构化(系统首个结构化 model 定义):
#   ①SessionUpdate.sessionModel: Optional[SessionModelOverride](provider+model+display_name?); ②update_session 改 exclude_unset 区分"未提供/显式清空(null)/设置",
#     sessionModel 以 JSON 落库(替原 model_override 字符串); ③list_sessions SELECT sessionModel 列 + _parse_session_model 还原结构; ④新增 _parse_session_model(容错返 None)
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): ①删除本文件重复的 _parse_session_model, 改从 storage 导入全系统唯一 parse_session_model(DRY, 杜绝双份实现漂移); ②update_session 乐观锁加固: UPDATE WHERE 追加 `AND version = ?`(比对 SELECT 时的旧版本)+ rowcount==0 抛 409, 兜住 SELECT→UPDATE 并发竞态窗口的丢失更新(与 line160 客户端版本检查互补)
# 2026-08-22 - 小欧 - BUG修复(北京老陈 2026-08-22 铁律"系统代码不得退化"): 三堂会审乐观锁加固引入的参数顺序错乱——params 先 append session["version"] 后 append session_id, 而 SQL WHERE 为 `id = ? ... version = ?`, 致 id 占位被填成版本号→恒 rowcount==0→所有 update_session 必 409。修正: 先 append session_id 再 append session["version"], 与 WHERE 占位顺序一致。冒烟测试(临时脚本)捕获此回归
# 2026-08-26 - 小欧 - D-2(文档2 8.D): 新增 get_session_info(session_id), GET /sessions/{session_id} 单会话信息路由,
#   使用场景: 设置界面读取会话级信息(title/created_at/updated_at/sessionModel), 现有端点无单会话详情。
# 2026-08-26 - 小欧 - 三堂会审整改(get_session_info): ①SELECT 删除未消费的 title_locked/title_updated_at 两列(YAGNI,
#   SessionResponse 无此二字段, 查了不用); ②conn.cursor() 两步改为 conn.execute 直取, 与本文件 update/delete 路径风格一致;
#   ③docstring 使用场景补顶栏时间悬浮(文档2 8.B 已知事项①), 与设置界面并列。pytest -k "task or session" 158 passed 回归通过。
"""
session_service — 会话业务服务(services/chat)

职责(方案4.7.3, 小欧 2026-08-13): 会话 CRUD(创建/列表/更新/删除/批量标题) + 乐观锁 + 标题历史。
API 层仅路由薄壳 + DTO, 业务逻辑单一归属本服务(SRP)。
"""
from typing import Optional, List, Tuple
import uuid
import json

from pydantic import BaseModel, Field
from fastapi import HTTPException

from app.logger import logger
from app.utils.time_utils import get_local_iso_timestamp, now_str, format_timestamp, to_local_iso  # 小欧 2026-08-08 全程统一本地时区
from app.db import db
from app.db.models.chat_models import SessionCreate, SessionResponse, SessionListResponse, BatchTitleResponse, SessionModelOverride
from app.services.chat.message_service import delete_session_display_names
from app.services.chat.storage import save_execution_steps, ExecutionStepsUpdate, parse_session_model


class SessionUpdate(BaseModel):
    """会话更新请求 — 小沈 2026-02-17; 2026-08-22 小欧 增 sessionModel(L2 会话级模型覆盖, 结构化 provider+model)"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号")
    updated_by: Optional[str] = Field(None, description="修改者")
    sessionModel: Optional[SessionModelOverride] = Field(None, description="会话级模型覆盖(L2, 结构化 provider+model), None/不带=不改动; 显式传 null=清空跟随全局")


def build_list_where(keyword: Optional[str], is_valid: Optional[bool],
                      for_count: bool = False) -> Tuple[str, List]:
    """拷贝自 sessions.py 第38-49行"""
    where = "WHERE is_deleted = FALSE"
    params: List = []
    if keyword:
        where += " AND title LIKE ?"
        params.append(f"%{keyword}%")
    if is_valid is not None:
        where += " AND is_valid = ?"
        params.append(1 if is_valid else 0)
    return where, params


# ===== CRUD 业务函数 =====

def create_session(session_create):
    """创建会话 — 自 api/v1/sessions.py 迁入"""
    session_id = str(uuid.uuid4())
    title = session_create.title if session_create and session_create.title else f"新会话 {now_str('%Y-%m-%d %H:%M')}"
    is_valid = session_create.is_valid if session_create and session_create.is_valid is not None else False
    local_time = get_local_iso_timestamp()

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO chat_sessions
               (id, title, created_at, updated_at, title_locked, title_updated_at, version, is_valid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session_id, title, local_time, local_time, False, local_time, 1, is_valid)
        )

    logger.info(f"创建会话成功: id={session_id}, title={title}, is_valid={is_valid}")

    return SessionResponse(
        session_id=session_id,
        title=title,
        created_at=local_time,
        updated_at=local_time,
        message_count=0,
        is_valid=is_valid
    )


def list_sessions(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    is_valid: Optional[bool] = None,
):
    """获取会话列表 — 自 api/v1/sessions.py 迁入"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()

        where, params = build_list_where(keyword, is_valid, for_count=True)
        cursor.execute(f"SELECT COUNT(*) FROM chat_sessions {where}", params)
        total = cursor.fetchone()[0]

        where, params = build_list_where(keyword, is_valid, for_count=False)
        offset = (page - 1) * page_size
        cursor.execute(
            f"SELECT id, title, created_at, updated_at, message_count, is_valid, sessionModel "
            f"FROM chat_sessions {where} ORDER BY updated_at DESC, created_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        rows = cursor.fetchall()

    sessions = [
        SessionResponse(
            session_id=row['id'],
            title=row['title'],
            created_at=format_timestamp(row['created_at']),
            updated_at=format_timestamp(row['updated_at']),
            message_count=row['message_count'],
            is_valid=row['is_valid'],
            sessionModel=parse_session_model(row['sessionModel'])
        )
        for row in rows
    ]

    logger.info(f"获取会话列表: page={page}, page_size={page_size}, "
                 f"keyword={keyword}, count={len(sessions)}")
    return SessionListResponse(total=total, page=page, page_size=page_size, sessions=sessions)


def update_session(session_id: str, update_data: SessionUpdate):
    """更新会话(标题 / 会话级模型覆盖 sessionModel, 各自独立可选) — 北京老陈 2026-08-22 L2 会话级闭环:
    用 exclude_unset 区分"未提供/显式清空/设置": 仅用户实际传入的字段进 SET; sessionModel 以 JSON 结构化落库;
    version 仅自增一次; 乐观锁(version 提供且不符则 409)。"""
    provided = update_data.model_dump(exclude_unset=True)
    if "title" not in provided and "sessionModel" not in provided:
        raise HTTPException(status_code=400, detail="标题或模型覆盖至少提供一个")
    try:
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            local_time = get_local_iso_timestamp()
            cursor.execute(
                "SELECT id, COALESCE(version, 1) as version "
                "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE",
                (session_id,),
            )
            session = cursor.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            if update_data.version is not None and update_data.version != session["version"]:
                logger.warning(f"版本冲突: session_id={session_id}, client_version={update_data.version}, server_version={session['version']}")
                raise HTTPException(status_code=409, detail="会话已被其他用户修改,请刷新后重试")

            set_parts: list = []
            params: list = []
            if "title" in provided:
                set_parts.append("title = ?")
                params.append(provided["title"])
                set_parts.append("title_locked = ?")
                params.append(1)
                set_parts.append("title_updated_at = ?")
                params.append(local_time)
            if "sessionModel" in provided:
                set_parts.append("sessionModel = ?")
                sm = provided["sessionModel"]  # dict 或 None(显式清空)
                params.append(json.dumps(sm, ensure_ascii=False) if sm else None)
            set_parts.append("updated_at = ?")
            params.append(local_time)
            set_parts.append("version = version + 1")
            params.append(session_id)   # WHERE id = ? 占位(顺序须与SQL一致)
            params.append(session["version"])  # 乐观锁: WHERE version = ? 比对 SELECT 时的旧版本, 防并发丢失更新
            cursor.execute(
                f"UPDATE chat_sessions SET {', '.join(set_parts)} WHERE id = ? AND is_deleted = FALSE AND version = ?",
                params,
            )
            if cursor.rowcount == 0:
                # SELECT 与 UPDATE 之间版本被其他请求改写, 原子级冲突 → 409(与 line160 客户端版本检查互补, 兜住并发竞态窗口)
                raise HTTPException(status_code=409, detail="会话已被其他用户修改,请刷新后重试")
            new_version = session["version"] + 1
        _sm_out = provided.get("sessionModel")
        logger.info(f"更新会话成功: id={session_id}, title={provided.get('title')}, sessionModel={_sm_out}, version={new_version}")
        return {"success": True, "title": provided.get("title"), "sessionModel": _sm_out, "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: session_id={session_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="更新会话失败,请重试")


def delete_session(session_id: str):
    """删除会话(软删) + 清理 display_name 缓存 — 自 api/v1/sessions.py 迁入, 缓存清理改经 message_service 方法"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        local_time = get_local_iso_timestamp()
        cursor.execute(
            'UPDATE chat_sessions SET is_deleted = TRUE, updated_at = ? WHERE id = ?',
            (local_time, session_id)
        )

    delete_session_display_names(session_id)
    logger.info(f"删除会话成功: id={session_id}")
    return {"success": True, "message": "会话删除成功"}


def get_session_titles_batch(session_ids: str):
    """批量获取会话标题 — 自 api/v1/sessions.py 迁入"""
    id_list = [sid.strip() for sid in session_ids.split(',') if sid.strip()]

    if not id_list:
        raise HTTPException(status_code=400, detail="会话ID列表不能为空")

    if len(id_list) > 100:
        raise HTTPException(status_code=400, detail="最多一次查询100个会话")

    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in id_list])
        cursor.execute(
            f'''SELECT id, title,
                     COALESCE(title_locked, 0) as title_locked,
                     COALESCE(title_updated_at, created_at) as title_updated_at
                FROM chat_sessions
                WHERE id IN ({placeholders}) AND is_deleted = FALSE''',
            id_list
        )
        rows = cursor.fetchall()

    sessions = []
    for row in rows:
        sessions.append({
            "session_id": row['id'],
            "title": row['title'],
            "title_locked": bool(row['title_locked']),
            "title_updated_at": to_local_iso(row['title_updated_at'])
        })

    logger.info(f"批量获取会话标题: count={len(sessions)}, session_ids={session_ids}")
    return BatchTitleResponse(sessions=sessions)


def get_session_info(session_id: str):
    """D-2(文档2 8.D): 单会话信息 — 返回 chat_sessions 单行(title/created_at/updated_at/message_count/is_valid/sessionModel)。
    使用场景: 设置界面读取会话级信息(文档2 8.D-2 验收) + 顶栏创建/更新时间悬浮数据源(8.B 已知事项①), 现有端点无单会话信息 — 小欧 2026-08-26"""
    with db.get_conn("chat") as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at, message_count, is_valid, "
            "sessionModel "
            "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE",
            (session_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return SessionResponse(
        session_id=row['id'],
        title=row['title'],
        created_at=format_timestamp(row['created_at']),
        updated_at=format_timestamp(row['updated_at']),
        message_count=row['message_count'],
        is_valid=row['is_valid'],
        sessionModel=parse_session_model(row['sessionModel']),
    )