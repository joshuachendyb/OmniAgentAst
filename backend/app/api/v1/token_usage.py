# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - 新建: token_usage 四维度查询 API(10.1.7②-6 / 10.1.8 S2)。chat 域,
#   GET /api/v1/token-usage?session_id=&task_id=&model= → storage.query_token_usage 聚合;
#   亦可被文档2 6.1.7(上下文链 token 聚合接口)复用。
# 2026-08-20 - 小欧 - 11.1 token 四层同构: query_token_usage 聚合链路改用 storage.query_task/session_accumulation 读真实累计(去重 parse_json), 与 react_cycle 同源基线; 三层累计口径统一
# 2026-08-20 - 小欧 - 11.1 测试驱动修复(chain 语义, 小欧单测 tests/test_token_accumulation_11_1.py 2 用例锁定): 原 GET /token-usage 的 chain_accumulated_tokens 直接返回 query_chain_accumulation(排除当前任务), 与 SSE 终态(含当前任务运行累计)口径不一致(独立任务恒为0、NULL context_root 返 None); 改为对 token_usage 全链(含当前任务)求和, 与 SSE 实时口径一致; 同步删未用 import query_chain_accumulation。
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.3: GET /token-usage ?model= 裸名过滤 → 组装
#   ModelRef(provider+model) 结构传 query_token_usage(model_ref=), 落 task_model JSON 列 json_extract 双键过滤;
#   import 补 ModelRef — 方案B 契约随归一
# 2026-08-29 - 小沈 - 修复#15: 读库由同步 db.get_conn 改为 db.atxn 离载到子线程, 避免阻塞事件循环(其余逻辑零改动)
"""
token_usage — LLM token 用量四维度查询 API（chat 域）

维度 = session / task / model（llm_call 由 COUNT(*) 聚合体现），口径同文档1 9.7。
"""
from typing import Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import db
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.services.chat.storage import query_token_usage, query_task_accumulation, query_session_accumulation  # 11.1 复用查询函数统一口径+缺行兜底 — 小欧 2026-08-20
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
    2026-08-22 小欧 归一报告v1.25 6.3: ?model= 裸名过滤 → 组装 ModelRef(provider+model) 结构过滤
      (task_model 为 JSON 单列, 需 provider+model 成对定位; 仅传 model 时 provider 取 None 通配)

    Args:
        session_id: 按会话过滤
        task_id: 按任务过滤
        model: 按模型名过滤(与当前 provider 组合成对过滤)
    """
    from app.config import get_config as _get_cfg   # 归一: 取当前 provider 与 model 组成 ModelRef — 小欧 2026-08-22
    _model_ref = None
    if model:
        _provider = _get_cfg().get("ai", {}).get("provider", "")
        _model_ref = ModelRef(provider=_provider, model=model)
    def _read(conn):
        row = query_token_usage(conn, session_id=session_id, task_id=task_id, model_ref=_model_ref)
        # 11.1 新增：读 DB 累计值(复用 storage 查询函数, 统一口径+缺行兜底) + chain 计算派生 — 小欧 2026-08-20
        _task_acc = query_task_accumulation(conn, task_id=task_id) if task_id else None
        _sess_acc = query_session_accumulation(conn, session_id=session_id) if session_id else None
        # 11.1 修正(2026-08-20 小欧): chain 语义须与 SSE 终态一致 = 全链(含当前任务)token_usage 求和。
        #   SSE 终态 chain = query_chain_accumulation(排除当前) + agent.task_accumulated_tokens(当前运行) = 全链之和;
        #   原实现直接返回 query_chain_accumulation(排除当前) → 与 SSE 不一致(独立任务恒为0), 且依赖缓存列非实时。
        #   故改为直接对 token_usage 全链(含当前)求和, 与 SSE 实时口径一致。context_root 为 NULL 时退化为当前任务自身。
        _chain_acc = None
        if task_id:
            _root = conn.execute("SELECT context_root_task_id FROM chat_tasks WHERE task_id=?", (task_id,)).fetchone()
            _root_id = _root["context_root_task_id"] if (_root and _root["context_root_task_id"]) else None
            if _root_id:
                _row = conn.execute(
                    "SELECT COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), COALESCE(SUM(total_tokens),0) "
                    "FROM token_usage WHERE task_id IN (SELECT task_id FROM chat_tasks WHERE context_root_task_id = ?)",
                    (_root_id,)).fetchone()
            else:
                _row = conn.execute(
                    "SELECT COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), COALESCE(SUM(total_tokens),0) "
                    "FROM token_usage WHERE task_id = ?", (task_id,)).fetchone()
            _chain_acc = {"prompt_tokens": int(_row[0] or 0), "completion_tokens": int(_row[1] or 0), "total_tokens": int(_row[2] or 0)}
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
    return await db.atxn("chat", _read)
