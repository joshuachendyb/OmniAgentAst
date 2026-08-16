# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - 新建: token_usage 四维度查询 API(10.1.7②-6 / 10.1.8 S2)。chat 域,
#   GET /api/v1/token-usage?session_id=&task_id=&model= → storage.query_token_usage 聚合;
#   亦可被文档2 6.1.7(上下文链 token 聚合接口)复用。
"""
token_usage — LLM token 用量四维度查询 API（chat 域）

维度 = session / task / model（llm_call 由 COUNT(*) 聚合体现），口径同文档1 9.7。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import db
from app.services.chat.storage import query_token_usage
from app.utils.response_utils import handle_api_errors

router = APIRouter()


class TokenUsageResponse(BaseModel):
    """token 用量聚合响应"""
    success: bool = Field(..., description="是否成功")
    calls: int = Field(..., description="LLM 调用次数(COUNT)")
    prompt_tokens: int = Field(..., description="输入 tokens 合计")
    completion_tokens: int = Field(..., description="输出 tokens 合计")
    total_tokens: int = Field(..., description="总 tokens 合计")


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
    return TokenUsageResponse(
        success=True,
        calls=row["calls"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["total_tokens"],
    )
