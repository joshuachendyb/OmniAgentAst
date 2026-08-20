# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - 新建: token_usage 四维度查询 API(10.1.7②-6 / 10.1.8 S2)。chat 域,
#   GET /api/v1/token-usage?session_id=&task_id=&model= → storage.query_token_usage 聚合;
#   亦可被文档2 6.1.7(上下文链 token 聚合接口)复用。
# 2026-08-20 - 小欧 - 11.1 token 四层同构: query_token_usage 聚合链路改用 storage.query_task/session_accumulation 读真实累计(去重 parse_json), 与 react_cycle 同源基线; 三层累计口径统一
"""
token_usage — LLM token 用量四维度查询 API（chat 域）

维度 = session / task / model（llm_call 由 COUNT(*) 聚合体现），口径同文档1 9.7。
"""
from typing import Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import db
from app.services.chat.storage import query_token_usage, query_chain_accumulation, query_task_accumulation, query_session_accumulation  # 11.1 复用查询函数统一口径+缺行兜底 — 小欧 2026-08-20
from app.utils.response_utils import handle_api_errors

router = APIRouter()


class TokenUsageResponse(BaseModel):
    """token 用量聚合响应"""
    success: bool = Field(..., description="是否成功")
    calls: int = Field(..., description="LLM 调用次数(COUNT)")
    prompt_tokens: int = Field(..., description="输入 tokens 合计")
    completion_tokens: int = Field(..., description="输出 tokens 合计")
    total_tokens: int = Field(..., description="总 tokens 合计")
    # 11.1 token 四层同构 — 小欧 2026-08-20
    task_accumulated_tokens: Optional[Dict[str, int]] = Field(None, description="任务级累计{prompt_tokens,completion_tokens,total_tokens}")
    session_accumulated_tokens: Optional[Dict[str, int]] = Field(None, description="会话级累计(全量SUM){prompt_tokens,completion_tokens,total_tokens}")
    chain_accumulated_tokens: Optional[Dict[str, int]] = Field(None, description="当前上下文链累计(按context_root_task_id聚合,不落库){prompt_tokens,completion_tokens,total_tokens}")


@router.get("/token-usage", response_model=TokenUsageResponse)
@handle_api_errors("查询token用量")
async def get_token_usage(session_id: Optional[str] = None,
                          task_id: Optional[str] = None,
                          model: Optional[str] = None):
    """
    查询 LLM token 用量（四维度：session / task / model / llm_call 聚合）

    Args:
        session_id: 按会话过滤
        task_id: 按任务过滤
        model: 按模型名过滤
    """
    with db.get_conn("chat") as conn:
        row = query_token_usage(conn, session_id=session_id, task_id=task_id, model=model)
        # 11.1 新增：读 DB 累计值(复用 storage 查询函数, 统一口径+缺行兜底) + chain 计算派生 — 小欧 2026-08-20
        _task_acc = query_task_accumulation(conn, task_id=task_id) if task_id else None
        _sess_acc = query_session_accumulation(conn, session_id=session_id) if session_id else None
        _chain_acc = None
        if task_id:
            _root = conn.execute("SELECT context_root_task_id FROM chat_tasks WHERE task_id=?", (task_id,)).fetchone()
            if _root and _root["context_root_task_id"]:
                _chain_acc = query_chain_accumulation(conn, context_root_task_id=_root["context_root_task_id"], current_task_id=task_id)
    return TokenUsageResponse(
        success=True,
        calls=row["calls"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["total_tokens"],
        task_accumulated_tokens=_task_acc,        # 11.1 新增
        session_accumulated_tokens=_sess_acc,      # 11.1 新增
        chain_accumulated_tokens=_chain_acc,       # 11.1 新增
    )
