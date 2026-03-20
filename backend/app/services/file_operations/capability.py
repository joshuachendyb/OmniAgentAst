"""
LLM 能力枚举与数据结构

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.1节

功能：
1. LLMCapability 枚举 - LLM能力标志
2. LLMFeature 数据类 - LLM能力特征
3. LLMProbeResult 数据类 - 探测结果
"""

from enum import Flag, auto
from dataclasses import dataclass
from typing import Optional


class LLMCapability(Flag):
    """LLM 能力标志"""
    NONE = 0
    RESPONSE_FORMAT = auto()      # 支持 response_format
    TOOLS = auto()                 # 支持 tools/function_calling
    STREAMING = auto()             # 支持流式输出
    REASONING = auto()             # 支持 reasoning_content


@dataclass
class LLMFeature:
    """
    LLM 能力特征
    
    从 API 响应中提取的特征
    """
    capability: LLMCapability = LLMCapability.NONE
    supports_response_format: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_reasoning: bool = False
    
    # API 特征
    uses_reasoning_content: bool = False  # 使用 reasoning_content 字段
    uses_outer_content: bool = False      # 使用外层 content 字段
    
    # 元信息
    detected_at: Optional[str] = None
    detection_method: str = "auto"


@dataclass
class LLMProbeResult:
    """
    探测结果
    
    记录探测过程的详细信息
    """
    success: bool
    feature: LLMFeature
    response_format_tested: bool = False
    response_format_works: bool = False
    tools_tested: bool = False
    tools_works: bool = False
    error: Optional[str] = None


# 导出
__all__ = [
    "LLMCapability",
    "LLMFeature",
    "LLMProbeResult",
]
