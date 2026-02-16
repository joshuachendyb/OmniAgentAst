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

from typing import List, Dict
from app.services.base import Message


def messages_to_dict_list(messages: List[Message]) -> List[Dict[str, str]]:
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
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


def dict_list_to_messages(dict_list: List[Dict[str, str]]) -> List[Message]:
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
    return [
        Message(role=msg["role"], content=msg["content"])
        for msg in dict_list
    ]


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


# 向后兼容的别名（如果其他地方已经使用了这个函数名）
dict_history_to_messages = messages_to_dict_list
