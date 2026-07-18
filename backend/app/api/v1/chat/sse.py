"""
sse — 执行步骤流式查看
提供从DB读取执行步骤并通过SSE流式输出的端点
小欧 2026-07-10
"""
# 编辑历史:
# 2026-07-14 - 小欧 - _generate_execution_stream改为从chat_message_steps读取步骤列表, SELECT去除execution_steps列, 统一步骤解析走load_execution_steps
# 2026-07-18 - 小欧 - 默认 timestamp 改 get_utc_timestamp() 时间统一
 
import json
import asyncio
from typing import Optional, Any, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.utils.time_utils import get_utc_timestamp
from app.db import db
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14

router = APIRouter()


class ExecutionStep:
    """执行步骤数据模型 — 小欧 2026-07-10"""
    def __init__(self, step_type: str, content: str = "", tool: str = "",
                 params: Optional[Dict] = None, result: Any = None, timestamp: int = 0):
        self.type = step_type
        self.content = content
        self.tool = tool
        self.params = params or {}
        self.result = result
        self.timestamp = timestamp

    def to_dict(self):
        data = {"type": self.type, "timestamp": self.timestamp}
        if self.content:
            data["content"] = self.content
        if self.tool:
            data["tool"] = self.tool
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        return data


async def _generate_execution_stream(session_id: str):
    """
    生成执行过程的SSE流
    
    Args:
        session_id: 会话ID
        
    Yields:
        SSE格式的数据
    """
    try:
        # 连接数据库获取会话消息
        with db.get_conn("chat") as conn:
            cursor = conn.cursor()
            
            # 获取会话消息和执行步骤
            cursor.execute(
                '''SELECT id, session_id, role, content, timestamp
                   FROM chat_messages 
                   WHERE session_id = ?
                   ORDER BY timestamp ASC''',
                (session_id,)
            )
            
            rows = cursor.fetchall()
        
            if not rows:
                # 会话不存在或没有消息
                yield "event: error\ndata: {\"error\": \"会话不存在或没有消息\"}\n\n"
                return
            
            # 遍历所有消息,构建执行步骤流
            for row in rows:
                msg_id = row['id']
                role = row['role']
                content = row['content']
                
                if role == 'user':
                    # 用户消息,发送thought事件
                    yield f"event: step\ndata: {json.dumps(ExecutionStep('thought', f'用户: {content}').to_dict(), ensure_ascii=False)}\n\n"
                
                elif role == 'assistant':
                    # AI回复
                    # 从 chat_message_steps 组装 — 小欧 2026-07-14
                    steps = load_execution_steps(conn, msg_id)
                    if steps and isinstance(steps, list):
                        for step in steps:
                            step_type = step.get('type', 'thought')
                            step_data = ExecutionStep(
                                step_type=step_type,
                                content=step.get('content', ''),
                                tool=step.get('tool', ''),
                                params=step.get('params', {}),
                                result=step.get('result'),
                                timestamp=step.get('timestamp', get_utc_timestamp())
                            ).to_dict()
                            yield f"event: step\ndata: {json.dumps(step_data, ensure_ascii=False)}\n\n"
                    elif content:
                        # 没有执行步骤,发送最终内容
                        yield f"event: step\ndata: {json.dumps(ExecutionStep('final', content).to_dict(), ensure_ascii=False)}\n\n"
        
        # 发送完成事件
        yield f"event: complete\ndata: {json.dumps({'type': 'complete', 'content': '执行完成'}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@router.get("/chat/execution/{session_id}/stream")
async def get_execution_stream(session_id: str):
    """
    获取执行过程(流式)
    
    通过SSE (Server-Sent Events) 流式返回执行步骤
    
    - **session_id**: 会话ID
    
    返回SSE格式的流数据,事件类型包括:
    - thought: AI思考过程
    - action: 工具调用
    - observation: 工具执行结果
    - error: 执行错误
    - final: 最终结果
    - complete: 流结束
    """
    # 验证会话是否存在
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    
    # 返回SSE流
    return StreamingResponse(
        _generate_execution_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
