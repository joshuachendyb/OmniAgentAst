"""
流式执行过程API路由
提供执行过程的SSE流式输出
"""

import json
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime
import sqlite3
from pathlib import Path

router = APIRouter()

# 数据库路径
DB_PATH = Path.home() / ".omniagent" / "chat_history.db"


def _get_db_connection():
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


class ExecutionStep:
    """执行步骤数据模型"""
    def __init__(self, step_type: str, content: str = "", tool: str = "", 
                 params: dict = None, result: any = None, timestamp: int = 0):
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


async def generate_execution_stream(session_id: str):
    """
    生成执行过程的SSE流
    
    Args:
        session_id: 会话ID
        
    Yields:
        SSE格式的数据
    """
    try:
        # 连接数据库获取会话消息
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 获取会话消息和执行步骤
        cursor.execute(
            '''SELECT id, session_id, role, content, timestamp, execution_steps 
               FROM chat_messages 
               WHERE session_id = ?
               ORDER BY timestamp ASC''',
            (session_id,)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            # 会话不存在或没有消息
            yield "event: error\ndata: {\"error\": \"会话不存在或没有消息\"}\n\n"
            return
        
        # 遍历所有消息，构建执行步骤流
        for row in rows:
            role = row['role']
            content = row['content']
            execution_steps_json = row['execution_steps']
            
            if role == 'user':
                # 用户消息，发送thought事件
                yield f"event: step\ndata: {json.dumps(ExecutionStep('thought', f'用户: {content}').to_dict(), ensure_ascii=False)}\n\n"
            
            elif role == 'assistant':
                # AI回复
                if execution_steps_json:
                    # 有执行步骤，解析并发送
                    try:
                        steps = json.loads(execution_steps_json)
                        if isinstance(steps, list):
                            for step in steps:
                                step_type = step.get('type', 'thought')
                                step_data = ExecutionStep(
                                    step_type=step_type,
                                    content=step.get('content', ''),
                                    tool=step.get('tool', ''),
                                    params=step.get('params', {}),
                                    result=step.get('result'),
                                    timestamp=step.get('timestamp', int(datetime.now().timestamp() * 1000))
                                ).to_dict()
                                yield f"event: step\ndata: {json.dumps(step_data, ensure_ascii=False)}\n\n"
                                # 添加小延迟，模拟流式输出
                                await asyncio.sleep(0.1)
                        else:
                            # 单个步骤对象
                            step_data = ExecutionStep(
                                step_type=steps.get('type', 'thought'),
                                content=steps.get('content', content),
                                tool=steps.get('tool', ''),
                                params=steps.get('params', {}),
                                result=steps.get('result'),
                                timestamp=int(datetime.now().timestamp() * 1000)
                            ).to_dict()
                            yield f"event: step\ndata: {json.dumps(step_data, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        # 解析失败，发送纯文本
                        yield f"event: step\ndata: {json.dumps(ExecutionStep('final', content).to_dict(), ensure_ascii=False)}\n\n"
                else:
                    # 没有执行步骤，发送最终内容
                    yield f"event: step\ndata: {json.dumps(ExecutionStep('final', content).to_dict(), ensure_ascii=False)}\n\n"
        
        # 发送完成事件
        yield f"event: complete\ndata: {json.dumps(ExecutionStep('final', '执行完成').to_dict(), ensure_ascii=False)}\n\n"
        
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@router.get("/chat/execution/{session_id}/stream")
async def get_execution_stream(session_id: str):
    """
    获取执行过程（流式）
    
    通过SSE (Server-Sent Events) 流式返回执行步骤
    
    - **session_id**: 会话ID
    
    返回SSE格式的流数据，事件类型包括：
    - thought: AI思考过程
    - action: 工具调用
    - observation: 工具执行结果
    - error: 执行错误
    - final: 最终结果
    - complete: 流结束
    """
    # 验证会话是否存在
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'SELECT id FROM chat_sessions WHERE id = ? AND is_deleted = FALSE',
            (session_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
            
    finally:
        conn.close()
    
    # 返回SSE流
    return StreamingResponse(
        generate_execution_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
