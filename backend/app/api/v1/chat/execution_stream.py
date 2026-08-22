"""
execution_stream — 执行步骤流式查看
提供从DB读取执行步骤并通过SSE流式输出的端点
小欧 2026-07-10
"""
# 编辑历史:
# 2026-07-14 - 小欧 - _generate_execution_stream改为从chat_message_steps读取步骤列表, SELECT去除execution_steps列, 统一步骤解析走load_execution_steps
# 2026-07-18 - 小欧 - 默认 timestamp 改 get_utc_timestamp() 时间统一
# 2026-07-18 - 小欧 - #18 fix: execution_steps 遍历加 step is None continue 防御, 单条 json 解析失败不触发 AttributeError
# 2026-07-18 - 小欧 - #21 fix: 预读数据退出with再yield,连接不占SSE流
# 2026-07-18 - 小欧 - ExecutionStep.timestamp 注解 int→str, 默认值 0→"" 与时间归一化 UTC Z 字符串对齐, 消除 int 注解与 str 实际值不一致
# 2026-08-08 - 小欧 - 全程统一本地时区: 默认 timestamp 改 get_local_iso_timestamp()
# 2026-08-14 - 小欧 - 改名名实相符: sse.py → execution_stream.py(实为执行步骤流式查看业务端点, 非通用SSE设施)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 铁律(chat_messages 只写严禁读): _generate_execution_stream 改读 fetch_session_user_message_pairs
#     (chat_user_message+chat_tasks 重建历史, assistant 正文取 response; 不读 chat_messages)

import json
import asyncio
from typing import Optional, Any, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.db import db
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14
from app.services.chat.storage import fetch_session_user_message_pairs  # 北京老陈 2026-08-22: 替代 chat_messages 读取(只写铁律)

router = APIRouter()


class ExecutionStep:
    """执行步骤数据模型 — 小欧 2026-07-10"""
    def __init__(self, step_type: str, content: str = "", tool: str = "",
                 params: Optional[Dict] = None, result: Any = None, timestamp: str = ""):
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
        # #21 fix: 先取数据退出 with 再 yield，连接不占 SSE 流 — 小欧 2026-07-18
        _rows_with_steps = []
        with db.get_conn("chat") as conn:
            # 北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 改读 chat_user_message+chat_tasks(复用 fetch_session_user_message_pairs)
            pairs = fetch_session_user_message_pairs(conn, session_id)
            if not pairs:
                yield "event: error\ndata: {\"error\": \"会话不存在或没有消息\"}\n\n"
                return
            for p in pairs:
                # 用户消息气泡
                _rows_with_steps.append(("user", p["user_content"] or "", None))
                ai_id = p["ai_message_id"]
                if ai_id is None:
                    continue
                _rows_with_steps.append(("assistant", p["ai_content"] or "", load_execution_steps(conn, ai_id)))
        # 退出 with 后再 yield，连接及时释放

        for role, content, steps in _rows_with_steps:
            if role == 'user':
                yield f"event: step\ndata: {json.dumps(ExecutionStep('thought', f'用户: {content}').to_dict(), ensure_ascii=False)}\n\n"
            elif role == 'assistant':
                if steps and isinstance(steps, list):
                    for step in steps:
                        if step is None:
                            continue
                        step_type = step.get('type', 'thought')
                        step_data = ExecutionStep(
                            step_type=step_type,
                            content=step.get('content', ''),
                            tool=step.get('tool', ''),
                            params=step.get('params', {}),
                            result=step.get('result'),
                            timestamp=step.get('timestamp', get_local_iso_timestamp())
                        ).to_dict()
                        yield f"event: step\ndata: {json.dumps(step_data, ensure_ascii=False)}\n\n"
                elif content:
                    yield f"event: step\ndata: {json.dumps(ExecutionStep('final', content).to_dict(), ensure_ascii=False)}\n\n"
        
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
