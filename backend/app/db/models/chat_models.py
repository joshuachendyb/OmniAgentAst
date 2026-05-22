"""
聊天数据模型 (Chat Data Models)
定义会话、消息等数据结构

Author: 小沈 - 2026-05-22
"""
from pydantic import BaseModel, Field
from typing import Optional


class Session(BaseModel):
    """会话模型"""
    id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")


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
    title: Optional[str] = Field(None, description="会话标题（可选，不提供则自动生成）")
    is_valid: Optional[bool] = Field(False, description="是否为有效会话（前端用户创建时传入True；测试代码不传默认为False）")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str = Field(..., description="会话ID")
    title: str = Field(..., description="会话标题")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    message_count: int = Field(..., description="消息数量")
    is_valid: Optional[bool] = Field(None, description="是否为有效会话")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总会话数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    sessions: list[SessionResponse] = Field(..., description="会话列表")


class BatchTitleResponse(BaseModel):
    """批量获取会话标题响应（12.1.3节）"""
    sessions: list[dict] = Field(..., description="会话标题信息列表")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int = Field(..., description="消息 ID")
    session_id: str = Field(..., description="会话 ID")
    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: int = Field(..., description="时间戳（毫秒，int类型）")  # 【修复 2026-04-01 小沈】从str改为int
    execution_steps: Optional[list] = Field(None, description="执行步骤（数组格式）")
    display_name: Optional[str] = Field(None, description="模型显示名称（记录消息收发时使用的模型）")
