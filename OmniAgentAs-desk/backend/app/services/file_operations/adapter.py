"""
参数适配器模块 (Parameter Adapter Module)
解决chat.py与FileOperationAgent之间的参数类型不匹配问题

问题背景:
- chat.py使用: List[Message] (来自app.services.base.Message)
- FileOperationAgent使用: List[Dict[str, str]]
- 本模块提供类型转换适配器

使用示例:
    from app.services.file_operations.adapter import messages_to_dict_list
    from app.services.base import Message
    
    # chat.py中的Message列表
    history = [Message(role="user", content="你好")]
    
    # 转换为Agent可用的字典列表
    dict_history = messages_to_dict_list(history)
"""

from typing import List, Dict, Optional
import logging

from app.services.base import Message

logger = logging.getLogger(__name__)


def messages_to_dict_list(messages: Optional[List[Message]]) -> List[Dict[str, str]]:
    """
    将Message对象列表转换为字典列表
    
    用于将chat.py中的List[Message]转换为FileOperationAgent可用的List[Dict[str, str]]
    
    Args:
        messages: Message对象列表，每个Message包含role和content属性
        
    Returns:
        字典列表，格式为 [{"role": "user", "content": "消息内容"}, ...]
        
    Example:
        >>> from app.services.base import Message
        >>> messages = [
        ...     Message(role="system", content="你是助手"),
        ...     Message(role="user", content="你好")
        ... ]
        >>> result = messages_to_dict_list(messages)
        >>> print(result)
        [{'role': 'system', 'content': '你是助手'}, {'role': 'user', 'content': '你好'}]
    """
    # 【修复】添加空值检查
    if messages is None:
        return []
    
    result = []
    for idx, msg in enumerate(messages):
        # 【修复】检查None元素
        if msg is None:
            logger.warning(f"Null message at index {idx}, skipping")
            continue
        
        # 【修复】防御性编程：检查对象类型和属性
        if not hasattr(msg, 'role') or not hasattr(msg, 'content'):
            logger.warning(f"Invalid message object at index {idx}: missing role or content attribute, skipping")
            continue
        
        # 【修复】确保值为字符串（处理None值）
        role = str(msg.role) if msg.role is not None else ""
        content = str(msg.content) if msg.content is not None else ""
        
        result.append({"role": role, "content": content})
    
    return result


def dict_list_to_messages(dict_list: Optional[List[Dict[str, str]]]) -> List[Message]:
    """
    将字典列表转换为Message对象列表
    
    用于将FileOperationAgent的List[Dict[str, str]]转换回List[Message]
    在需要将Agent的对话历史传递回chat.py时使用
    
    Args:
        dict_list: 字典列表，格式为 [{"role": "user", "content": "消息内容"}, ...]
        
    Returns:
        Message对象列表
        
    Example:
        >>> dict_list = [
        ...     {"role": "user", "content": "你好"},
        ...     {"role": "assistant", "content": "你好！有什么可以帮助你？"}
        ... ]
        >>> messages = dict_list_to_messages(dict_list)
        >>> print(messages[0].role, messages[0].content)
        user 你好
    """
    # 【修复】添加空值检查
    if dict_list is None:
        return []
    
    result = []
    for idx, msg in enumerate(dict_list):
        # 【修复】检查None元素
        if msg is None:
            logger.warning(f"Null dict at index {idx}, skipping")
            continue
        
        # 【修复】安全获取键值（使用.get()避免KeyError）
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        # 【修复】确保为字符串
        role = str(role) if role is not None else ""
        content = str(content) if content is not None else ""
        
        try:
            result.append(Message(role=role, content=content))
        except Exception as e:
            logger.error(f"Failed to create Message at index {idx}: {e}")
            continue
    
    return result


def convert_chat_history(
    chat_messages: List[Message],
    target_format: str = "dict"
) -> List[Dict[str, str]]:
    """
    通用的聊天历史转换函数
    
    支持在Message对象和字典格式之间双向转换
    
    Args:
        chat_messages: 输入的消息列表
        target_format: 目标格式，"dict"或"message"（当前仅支持"dict"）
        
    Returns:
        转换后的消息列表
        
    Raises:
        ValueError: 当target_format不支持时
        
    Note:
        当前主要用于chat.py向FileOperationAgent传递历史记录
    """
    if target_format == "dict":
        return messages_to_dict_list(chat_messages)
    else:
        raise ValueError(f"Unsupported target format: {target_format}. Use 'dict'.")


# 【修复】修正别名指向，使其语义正确
# dict_history_to_messages 的语义是 "dict -> messages"
dict_history_to_messages = dict_list_to_messages
