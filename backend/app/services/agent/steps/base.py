# -*- coding: utf-8 -*-
"""
ReasoningStep抽象基类 + ToolMixin混入类

提供Step类层次结构的根基类和工具字段混入：
- ReasoningStep(ABC): 所有Step的抽象基类，定义通用接口
- ToolMixin: tool_name/tool_params字段混入，解决S5重复问题

Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp, create_step_counter


class ReasoningStep(ABC):
    """
    ReasoningStep抽象基类
    
    所有Step类的基类，定义通用接口：
    - step: int → 步骤序号（统一）
    - timestamp: int → 时间戳（毫秒，统一）
    - get_type(): str → 获取type字段值
    - get_content(): str → 获取用户可见文本
    - is_done(): bool → 判断是否结束（抽象方法）
    - to_dict(): dict → 转换为前端SSE格式
    
    设计依据：
    - 13.2.2.2节Step类层次结构设计
    - 5.1.3节LlamaIndex BaseReasoningStep基类设计
    """
    
    def __init__(self, step: int, timestamp: Optional[int] = None):
        """
        初始化ReasoningStep
        
        Args:
            step: 步骤序号
            timestamp: 时间戳（毫秒），默认使用当前时间
        """
        self._step = step
        self._timestamp = timestamp or create_timestamp()
    
    @property
    def step(self) -> int:
        """获取步骤序号"""
        return self._step
    
    @property
    def timestamp(self) -> int:
        """获取时间戳（毫秒）"""
        return self._timestamp
    
    @abstractmethod
    def get_type(self) -> str:
        """
        获取type字段值
        
        Returns:
            type字段值：thought/action_tool/observation/final/error
        """
        pass
    
    @abstractmethod
    def get_content(self) -> str:
        """
        获取用户可见文本
        
        Returns:
            用户可见的文本内容
        """
        pass
    
    @abstractmethod
    def is_done(self) -> bool:
        """
        判断是否结束循环
        
        Returns:
            True - 结束循环
            False - 继续循环
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为前端SSE格式
        
        Returns:
            前端期望的字典格式
        """
        return {
            "type": self.get_type(),
            "step": self._step,
            "timestamp": self._timestamp,
            "content": self.get_content()
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self._step}, type={self.get_type()})"


class ToolMixin:
    """
    ToolMixin混入类
    
    将tool_name和tool_params字段混入Step类，解决字段重复问题：
    - ThoughtStep：需要tool_name/tool_params
    - ActionToolStep：需要tool_name/tool_params
    - ObservationStep：需要tool_name/tool_params
    
    设计依据：13.2.2.2节ToolMixin设计
    """
    
    def __init__(self, tool_name: str, tool_params: Optional[Dict[str, Any]] = None):
        """
        初始化ToolMixin
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数字典
        """
        self._tool_name = tool_name
        self._tool_params = tool_params or {}
    
    @property
    def tool_name(self) -> str:
        """获取工具名称"""
        return self._tool_name
    
    @property
    def tool_params(self) -> Dict[str, Any]:
        """获取工具参数"""
        return self._tool_params
    
    def get_tool_name_safe(self) -> str:
        """获取工具名称（安全版本，空值返回finish）"""
        return self._tool_name or "finish"
