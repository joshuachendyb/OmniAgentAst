# 消息管理API路由(单条消息 CRUD)
# 编程人:小沈
# 创建时间:2026-05-28
# 编辑历史:
# 2026-07-14 - 小欧 - GET消息历史改为从chat_message_steps读取步骤列表, SELECT去除execution_steps列,无数据时从chat_messages.execution_steps列读取
# 2026-07-16 - 小欧 - SELECT 加 thought 列; MessageResponse 传 thought
# 2026-07-18 - 小欧 - timestamp 改 format_timestamp 对外统一 UTC Z; save_message 传 get_utc_timestamp; created_at 补 format_timestamp 兜底
# 2026-07-18 - 小欧 - timestamp配合MessageResponse.timestamp改为str, format_timestamp格式字符串正常传递
# 2026-08-08 - 小欧 - 全程统一本地时区: save_message 传 get_local_iso_timestamp; title_updated_at 输出改 to_local_iso(不再转UTC)
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤3): 业务逻辑(get_session_messages/save_message/display_name_cache)迁入
#   services/chat/message_service.py, 本文件降为路由薄壳(DTO+路由+调service)。display_name_cache 归属 message_service 独占。
# 2026-08-21 - 小欧 - 新增 GET /sessions/{session_id}/user_messages 从 chat_user_message 读取（替代 chat_messages）— 小欧 2026-08-21
 
"""
消息管理API路由(薄壳)

A7 后: 路由 + MessageCreate DTO → 调 message_service(方案4.7.3)
1. 获取会话消息历史 - GET /sessions/{session_id}/messages
2. 保存消息 - POST /sessions/{session_id}/messages
3. 获取用户消息(chat_user_message) - GET /sessions/{session_id}/user_messages
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from app.services.chat.message_service import get_session_messages, save_message
from app.db import db
from app.services.chat.storage import load_user_messages_by_session

router = APIRouter()


class MessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色:user/assistant/system")
    content: str = Field(..., description="消息内容")
    display_name: Optional[str] = Field(None, description="模型显示名称(可选,记录消息收发时使用的模型)")
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    client_os: Optional[str] = Field(None, description="客户端操作系统")
    browser: Optional[str] = Field(None, description="浏览器类型")
    device: Optional[str] = Field(None, description="设备类型")
    network: Optional[str] = Field(None, description="网络类型")


@router.get("/sessions/{session_id}/messages")
def get_session_messages_endpoint(session_id: str):
    return get_session_messages(session_id)


@router.post("/sessions/{session_id}/messages")
def save_message_endpoint(session_id: str, message: MessageCreate):
    return save_message(session_id, message)


@router.get("/sessions/{session_id}/user_messages")
def get_session_user_messages_endpoint(session_id: str):
    """从 chat_user_message 读取用户消息列表（替代 chat_messages）— 小欧 2026-08-21"""
    with db.get_conn("chat") as conn:
        messages = load_user_messages_by_session(conn, session_id)
    return {"session_id": session_id, "messages": messages, "count": len(messages)}