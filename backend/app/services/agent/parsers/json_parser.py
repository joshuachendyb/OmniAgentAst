# -*- coding: utf-8 -*-
"""
@deprecated 2026-05-20 小健
此文件属于 parsers/ 策略模式模块（2026-04-19设计），当前未被使用。
请使用 react_output_parser.py 的解析器链（_HANDLERS）替代。
详情见：doc-5月优化/parse_react_response解析器链重构设计-小沈-2026-05-19.md

JSON解析器 - P5策略模式拆分

根据文档6.2.2设计
创建时间: 2026-04-19
"""

import json
import re
from typing import Dict, Any

from .base_parser import BaseParser, ParseResult


class JsonParser(BaseParser):
    """JSON格式解析器"""
    
    def can_parse(self, output: str) -> bool:
        """检查是否包含JSON对象"""
        output = output.strip()
        return (output.startswith('{') and output.endswith('}')) or \
               ('```' in output and '{' in output)
    
    def parse(self, output: str) -> ParseResult:
        """解析JSON格式输出"""
        try:
            # 清理输出中的代码块标记
            cleaned = output.strip()
            
            # 提取```块内的JSON
            json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', cleaned)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 尝试直接解析
                json_str = cleaned
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 提取工具信息
            tool_name = data.get("tool_name") or data.get("action")
            tool_params = data.get("tool_params") or data.get("action_input") or {}
            
            # 判断类型
            if tool_name == "finish" or "answer" in data:
                return ParseResult(
                    success=True,
                    type="answer",
                    tool_name=None,
                    tool_params=None,
                    thought=data.get("thought", ""),
                    response=data.get("answer", "")
                )
            else:
                return ParseResult(
                    success=True,
                    type="action",
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=data.get("thought", "")
                )
        except json.JSONDecodeError as e:
            return ParseResult(
                success=False,
                type="parse_error",
                error=f"JSON解析失败: {str(e)}"
            )
        except Exception as e:
            return ParseResult(
                success=False,
                type="parse_error",
                error=f"解析错误: {str(e)}"
            )