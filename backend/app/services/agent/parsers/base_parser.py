# -*- coding: utf-8 -*-
"""
@deprecated 2026-05-20 小健
此文件属于 parsers/ 策略模式模块（2026-04-19设计），当前未被使用。
请使用 react_output_parser.py 的解析器链（_HANDLERS）替代。
详情见：doc-5月优化/parse_react_response解析器链重构设计-小沈-2026-05-19.md

解析器基类 - P5策略模式拆分

根据文档6.2.2设计
创建时间: 2026-04-19
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    type: str  # "action", "answer", "implicit", "thought_only", "parse_error"
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    thought: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为dict格式（兼容原有接口）"""
        return {
            "type": self.type,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "thought": self.thought,
            "content": self.thought,
            "response": self.response,
            "error": self.error,
        }


class BaseParser(ABC):
    """解析器基类"""
    
    @abstractmethod
    def can_parse(self, output: str) -> bool:
        """判断是否能解析此输出"""
        pass
    
    @abstractmethod
    def parse(self, output: str) -> ParseResult:
        """解析输出"""
        pass