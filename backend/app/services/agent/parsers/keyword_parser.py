# -*- coding: utf-8 -*-
"""
@deprecated 2026-05-20 小健
此文件属于 parsers/ 策略模式模块（2026-04-19设计），当前未被使用。
请使用 react_output_parser.py 的解析器链（_HANDLERS）替代。
详情见：doc-5月优化/parse_react_response解析器链重构设计-小沈-2026-05-19.md

关键词解析器 - P5策略模式拆分

根据文档6.2.2设计，从react_output_parser.py提取关键词匹配逻辑
创建时间: 2026-04-19
"""

import re
from typing import Dict, Any, Optional

from .base_parser import BaseParser, ParseResult
from .tool_name_parser import ToolNameParser


# 从react_output_parser.py提取的关键词
REACT_KEYWORDS = {
    "thought": r"(?:Thought|思考|推理):\s*",
    "action": r"(?:Action|行动|工具调用|(?:调用|使用|执行)\s+|(?:工具|函数)\s*为):\s*",
    "action_input": r"(?:Action Input|工具参数|输入|参数):\s*",
}


class KeywordParser(BaseParser):
    """关键词匹配解析器"""
    
    def __init__(self):
        self.tool_name_parser = ToolNameParser()
    
    def can_parse(self, output: str) -> bool:
        """检查是否包含Thought/Action关键词"""
        output = output.strip()
        return bool(re.search(REACT_KEYWORDS["thought"], output, re.IGNORECASE))
    
    def parse(self, output: str) -> ParseResult:
        """使用关键词匹配解析"""
        try:
            # 提取Thought
            thought_match = re.search(
                r'(?:Thought|思考|推理):\s*(.+?)(?=\n(?:Action|工具|$))',
                output,
                re.IGNORECASE | re.DOTALL
            )
            thought = thought_match.group(1).strip() if thought_match else ""
            
            # 提取Action
            action_match = re.search(
                r'(?:Action|行动|工具调用|(?:调用|使用|执行)\s+|(?:工具|函数)\s*为):\s*(\w+)',
                output,
                re.IGNORECASE
            )
            tool_name = action_match.group(1).strip() if action_match else None
            
            # 提取Action Input
            tool_params: Dict[str, Any] = {}
            input_match = re.search(
                r'(?:Action Input|工具参数|输入|参数):\s*(.+)',
                output,
                re.IGNORECASE | re.DOTALL
            )
            if input_match:
                input_text = input_match.group(1).strip()
                # 简单参数解析
                tool_params = self._parse_simple_params(input_text)
            
            if tool_name:
                return ParseResult(
                    success=True,
                    type="action",
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=thought
                )
            else:
                return ParseResult(
                    success=True,
                    type="thought_only",
                    thought=thought
                )
        except Exception as e:
            return ParseResult(
                success=False,
                type="parse_error",
                error=f"关键词解析失败: {str(e)}"
            )
    
    def _parse_simple_params(self, text: str) -> Dict[str, Any]:
        """简单参数解析"""
        params: Dict[str, Any] = {}
        # 尝试key=value格式
        for line in text.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                params[key.strip()] = value.strip()
        return params