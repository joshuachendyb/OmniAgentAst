# -*- coding: utf-8 -*-
"""
工具名解析器 - P5策略模式拆分

根据文档6.2.2设计
创建时间: 2026-04-19
"""

import re
from typing import Dict, Any, Optional, List

from .base_parser import BaseParser, ParseResult


def _get_known_tools() -> List[str]:
    """从工具注册中心动态获取已知工具名 - 小健 2026-05-02"""
    try:
        from app.services.tools.file.file_register import FILE_TOOL_DESCRIPTIONS
        from app.services.tools.registry import _FILE_TOOL_NAMES
        tools = set(_FILE_TOOL_NAMES) | set(FILE_TOOL_DESCRIPTIONS.keys())
        tools.update(["execute_command", "run_command", "get_current_time",
                      "get_system_info", "finish", "finish_with_error"])
        return sorted(tools)
    except Exception:
        return ["read_file", "write_file", "delete_file", "list_directory",
                "search_files", "grep_file_content", "execute_command",
                "move_file", "get_current_time", "get_system_info",
                "finish", "finish_with_error"]


class ToolNameParser(BaseParser):
    """工具名兜底匹配解析器"""
    
    def can_parse(self, output: str) -> bool:
        """检查是否包含已知工具名"""
        output = output.strip()
        return any(tool in output for tool in _get_known_tools())
    
    def parse(self, output: str) -> ParseResult:
        """工具名兜底匹配"""
        output = output.strip()
        
        # 查找已知工具名
        for tool_name in _get_known_tools():
            if tool_name in output:
                # 尝试提取参数
                tool_params = self._extract_params(output, tool_name)
                return ParseResult(
                    success=True,
                    type="action",
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=output
                )
        
        return ParseResult(
            success=True,
            type="thought_only",
            thought=output
        )
    
    def _extract_params(self, output: str, tool_name: str) -> Dict[str, Any]:
        """提取工具参数"""
        params: Dict[str, Any] = {}
        
        # 简单参数提取：查找工具名后的内容
        pattern = rf'{tool_name}\s*\(\([^)]*\))?'
        match = re.search(pattern, output)
        if match and match.group(1):
            param_str = match.group(1).strip('()')
            # 简单解析key=value
            for param in param_str.split(','):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.strip()] = value.strip().strip('"\'')
        
        return params