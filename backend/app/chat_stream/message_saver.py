# app/chat_stream/message_saver.py
# 消息保存工具函数
# 创建时间: 2026-03-23
# 创建人: 小沈
# 用途: 统一管理所有消息保存逻辑，被 chat_stream.py 和 chat2.py 调用

"""
消息保存工具函数模块

统一管理所有消息保存逻辑：
1. 用户消息保存 - 调用 sessions.save_message()（由前端触发）
2. AI消息保存 - save_execution_steps_to_db()
3. 步骤添加并保存 - add_step_and_save()

依赖关系：
    message_saver.py → sessions 模块
                       ├── _user_message_ids 缓存
                       ├── save_execution_steps() 方法
                       └── ExecutionStepsUpdate 数据类
"""

from typing import List, Dict, Optional, Callable, Any
from app.chat_stream.chat_helpers import create_timestamp


# ============================================================
# 核心保存函数
# ============================================================

async def save_execution_steps_to_db(
    session_id: Optional[str],
    execution_steps: List[Dict],
    content: Optional[str] = None,
    user_message_id: Optional[int] = None
) -> None:
    """
    保存 execution_steps 和 content 到数据库
    
    功能：
    - 实时保存 AI 消息的 execution_steps 到数据库
    - 支持同时保存 content 字段
    - 自动处理 user_message_id 和 assistant_message_id 的关联
    
    Args:
        session_id: 会话ID
        execution_steps: 执行步骤列表
        content: AI 生成的文本内容（可选）
        user_message_id: 用户消息ID（可选，从缓存获取）
    
    Returns:
        None
    
    Author: 小沈 - 2026-03-23
    """
    from app.api.v1 import sessions
    
    if session_id is None:
        return
    
    try:
        # 如果没传 user_message_id，从缓存获取
        if user_message_id is None:
            user_message_id = sessions._user_message_ids.get(session_id)
        
        # 调用 sessions 模块的 save_execution_steps 函数
        await sessions.save_execution_steps(
            session_id,
            sessions.ExecutionStepsUpdate(
                execution_steps=execution_steps,
                content=content,
                reply_to_message_id=user_message_id
            )
        )
    except Exception as e:
        # 记录错误但不抛出异常，避免中断流式响应
        from app.utils.logger import logger
        logger.error(f"[Save] 保存失败: {e}", exc_info=True)


async def add_step_and_save(
    current_execution_steps: List[Dict],
    step: Dict,
    session_id: Optional[str],
    content: Optional[str] = None
) -> None:
    """
    统一的添加 step 到 execution_steps 并保存到数据库的函数
    
    功能：
    - 将 step 添加到 current_execution_steps 列表
    - 保存到数据库
    
    Args:
        current_execution_steps: 执行步骤列表（引用）
        step: step 字典（包含 type 等字段）
        session_id: 会话ID
        content: 可选的 content 内容
    
    Returns:
        None
    
    Author: 小沈 - 2026-03-23
    """
    current_execution_steps.append(step)
    save_content = content if content else ""
    await save_execution_steps_to_db(session_id, current_execution_steps, save_content)


# ============================================================
# 创建 add_step_and_save 的工厂函数
# 用于需要绑定状态的场景
# ============================================================

def create_add_step_and_save(
    current_execution_steps: List[Dict],
    session_id: Optional[str]
) -> Callable:
    """
    创建 add_step_and_save 函数（绑定到特定的 execution_steps 和 session_id）
    
    用途：
    - 当需要在闭包中使用时，用此工厂函数创建
    - 避免每次调用都传递 current_execution_steps 和 session_id
    
    Args:
        current_execution_steps: 执行步骤列表
        session_id: 会话ID
    
    Returns:
        Callable: add_step_and_save 函数
    
    Example:
        add_step = create_add_step_and_save(current_execution_steps, session_id)
        await add_step(step_data, content)
    """
    async def add_step_and_save_func(step: Dict, content: Optional[str] = None) -> None:
        await add_step_and_save(current_execution_steps, step, session_id, content)
    
    return add_step_and_save_func


# ============================================================
# 解析 SSE 数据并保存的辅助函数
# 用于 ver1_run_stream 返回的 SSE 字符串解析和保存
# ============================================================

async def parse_and_save_sse(
    sse_data: str,
    current_execution_steps: List[Dict],
    session_id: str,
    current_content: str = ""
) -> Dict:
    """
    解析 SSE 数据字符串并保存到数据库
    
    用途：
    - 解析 ver1_run_stream 返回的 SSE 格式字符串
    - 提取 step 数据并添加到 current_execution_steps
    - 自动保存到数据库
    
    Args:
        sse_data: SSE 格式字符串，如 "data: {...}\n\n"
        current_execution_steps: 执行步骤列表（引用）
        session_id: 会话ID
        current_content: 当前累积的文本内容
    
    Returns:
        Dict: 解析后的 step 数据
    
    Author: 小沈 - 2026-03-23
    """
    import json
    
    # 解析 SSE 格式
    if sse_data.startswith("data: "):
        sse_data = sse_data[6:]  # 去掉 "data: " 前缀
    
    step_data = json.loads(sse_data)
    
    # 添加到 execution_steps
    current_execution_steps.append(step_data)
    
    # 保存到数据库
    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
    
    return step_data
