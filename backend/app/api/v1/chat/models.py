# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 - 小欧 - S1(10.1.4②): ChatRequest 增 context_link_mode(任务上下文链, 默认 independent 新任务/linked 续聊需显式),
#   白名单校验在 orchestrator(10.1.4⑧), 本处仅 DTO 默认值定义
# 2026-10-03 - 小欧 - 文档[4] 5.7 项6: ChatRequest 删 context_link_mode(真源上移至会话 link 开关)
# 2026-10-03 - 小欧 - 文档[4] 5.7.14 单元1: ChatRequest 增 link_enabled(会话 link 开关值随消息到达),
#   None=未携带沿用会话当前值。禁复用 context_link_mode(旧"临时模式"通道, 复活即双通道)。

# 2026-10-29 小欧 - 输入框引用读取权收归后端: ChatRef 删 content 字段(wire 不承载正文, 正文由
#   resolver 在编排层读盘); 删 MAX_REF_CONTENT_CHARS 常量(字符上限改由 services/refs/limits 按预算
#   反推, DTO 不再设); ChatRequest.refs 增 max_length=MAX_REFS(条数上限, 与 limits 单一真源双保险) — 小欧-2026-10-29

"""
models — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第152-166行
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# 2026-10-29 小欧 - MAX_REF_CONTENT_CHARS 已删除(YAGNI): 读取权收归后端, wire 不承载正文,
#   引用正文上限由 services/refs/limits 按预算反推, DTO 不再设字符上限; 条数上限 MAX_REFS
#   由 services/refs/limits.py 单一真源, 前端入队即拦、后端 DTO 再拦(双保险)。
from app.services.refs.limits import MAX_REFS


class ChatMessage(BaseModel):
    """拷贝自 chat_router.py 第152-155行"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRef(BaseModel):
    """输入框引用条目 — 2026-10-13 小欧 - 文档[28] 4.1.6

    user content 只带 `@文件名` 提及，**正文由后端按标识读盘**且不入库、不进历史
    （chat_user_message.content 保持干净），由 resolver 在编排层读盘后拼入。
    2026-10-29 小欧 - 读取权收归后端: content 字段删除(wire 不承载正文, 见 2.3-8)。
    """
    kind: str = Field(default="file", description="来源类型: file/selection/log/message")
    label: str = Field(default="", description="展示名（文件名 / 选区说明）")
    path: Optional[str] = Field(default=None, description="相对项目根的路径")
    size: Optional[int] = Field(default=None, description="字节数（仅展示）")
    lineRange: Optional[Dict[str, int]] = Field(default=None, description="行号区间 {start,end}")


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
    # 2026-10-13 小欧 - 文档[28] 4.1.6: 输入框引用(ComposerRef)随消息上行，正文不进 content。
    #   当轮消费（message_builder 拼入 LLM 消息）且不落库 → user content 保持干净、compaction 不受污染。
    #   ⚠️ 本 DTO 未设 model_config，Pydantic v2 默认 extra='ignore' → 前后端必须同批交付，
    #   否则 refs 被静默丢弃（引用卡片显示了但 Agent 收不到，且无任何报错）— 同 link_enabled 注释的教训。
    refs: Optional[List[ChatRef]] = Field(default=None, max_length=MAX_REFS,
                                          description="输入框引用条目列表(当轮有效, 不入库; 上限 20 条)")