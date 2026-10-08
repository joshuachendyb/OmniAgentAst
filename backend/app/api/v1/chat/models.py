# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - S1(10.1.4②): ChatRequest 增 context_link_mode(任务上下文链, 默认 independent 新任务/linked 续聊需显式),
#   白名单校验在 orchestrator(10.1.4⑧), 本处仅 DTO 默认值定义
# 2026-10-03 - 小欧 - 文档[4] 5.7 项6: ChatRequest 删 context_link_mode(真源上移至会话 link 开关)
# 2026-10-03 - 小欧 - 文档[4] 5.7.14 单元1: ChatRequest 增 link_enabled(会话 link 开关值随消息到达),
#   None=未携带沿用会话当前值。禁复用 context_link_mode(旧"临时模式"通道, 复活即双通道)。
"""
models — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第152-166行
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """拷贝自 chat_router.py 第152-155行"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """拷贝自 chat_router.py 第158-166行"""
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式返回")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="温度参数")
    provider: Optional[str] = Field(default=None, description="前端指定的提供商")
    model: Optional[str] = Field(default=None, description="前端指定的模型")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    # context_link_mode 已废止(真源上移至会话 link 开关); 本 DTO 未设 model_config,
    # Pydantic v2 默认 extra='ignore' → 旧前端多发该字段被静默丢弃, 故前后端必须同批交付(决策 9)。
    # link_enabled 是新的唯一写入口: 禁复用 context_link_mode(旧"临时模式"通道, 复活即双通道)。
    # — 小欧 2026-10-03 文档[4] 5.7.14 单元1
    link_enabled: Optional[bool] = Field(default=None, description="会话link开关值(随消息携带; None=沿用会话当前值)")
    # 2026-10-06 小欧 - 文档[11] 3.4.3: 会话插话开关值随消息携带, None=沿用会话当前值(与 link_enabled 同语义)。
    #   唯一写入口同 link: 严禁另开 PATCH 端点(见 sessions.py:19 已废止先例)。
    allow_interject: Optional[bool] = Field(default=None, description="会话插话开关值(随消息携带; None=沿用会话当前值)")