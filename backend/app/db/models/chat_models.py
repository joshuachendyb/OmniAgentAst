# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - MessageResponse 增 thought 字段, API 返回消息时携带 thought
# 2026-08-08 - 小欧 - 全程统一本地时区: MessageResponse.timestamp 描述 `ISO 8601 UTC格式` → `本地ISO无Z`
# 2026-08-22 - 小欧 - 6.1.1 L2 会话级 sessionModel 回读字段(SessionResponse/Session)落地，与 SessionUpdate 写入口、storage.get_session_model 执行侧读取闭环
"""
聊天数据模型 (Chat Data Models)
定义会话、消息等数据结构

Author: 小沈 - 2026-05-22
"""
from pydantic import BaseModel, Field
from typing import Optional


class SessionModelOverride(BaseModel):
    """会话级模型覆盖结构(L2) — 北京老陈 2026-08-22
    系统内【首次】以结构化方式定义 model 变量: 至少 provider + model, 可选 display_name。
    后续其他 model 类字段(如全局当前模型、任务级模型等)将逐步统一为同一结构(provider+model),
    本类即规范模板, 新增/改造 model 字段应复用此结构而非裸字符串。"""
    provider: str = Field(..., description="模型供应商, 如 openai / anthropic")
    model: str = Field(..., description="模型名, 如 gpt-4o")
    display_name: Optional[str] = Field(None, description="展示名(可选, 缺省由 provider+model 构建)")


class Session(BaseModel):
    """会话模型"""
    id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")
    sessionModel: Optional[SessionModelOverride] = Field(None, description="会话级模型覆盖(L2)，空=跟随全局")


class Message(BaseModel):
    """消息模型"""
    id: Optional[int] = Field(None, description="消息ID")
    session_id: str = Field(..., description="会话ID")
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳")
    execution_steps: Optional[str] = Field(None, description="执行步骤JSON")


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, description="会话标题(可选,不提供则自动生成)")
    is_valid: Optional[bool] = Field(False, description="是否为有效会话(前端用户创建时传入True;测试代码不传默认为False)")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(..., description="消息数量")
    sessionModel: Optional[SessionModelOverride] = Field(None, description="会话级模型覆盖(L2)，空=跟随全局")
    is_valid: Optional[bool] = Field(None, description="是否为有效会话")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总会话数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    sessions: list[SessionResponse] = Field(..., description="会话列表")


class BatchTitleResponse(BaseModel):
    """批量获取会话标题响应(12.1.3节)"""
    sessions: list[dict] = Field(..., description="会话标题信息列表")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int = Field(..., description="消息 ID")
    session_id: str = Field(..., description="会话 ID")
    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: str = Field(..., description="时间戳(本地ISO无Z)")  # 小欧 2026-08-08 全程统一本地时区: 本地无Z
    execution_steps: Optional[list] = Field(None, description="执行步骤(数组格式)")
    display_name: Optional[str] = Field(None, description="模型显示名称(记录消息收发时使用的模型)")
    thought: Optional[str] = Field(None, description="LLM 推理过程")  # 小欧 2026-07-16
