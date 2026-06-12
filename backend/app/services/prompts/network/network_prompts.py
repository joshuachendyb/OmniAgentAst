# -*- coding: utf-8 -*-
"""
NetworkPrompts - 网络通信 Prompt模板

P0优先级:URL/参数易错,超时重试策略需引导

Author: 小健 - 2026-05-06
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from app.services.prompts.base_prompt_template import BasePrompts


class NetworkPrompts(BasePrompts):
    """网络通信 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "你是一个网络操作助手,负责HTTP请求、文件下载、网页内容获取、网络搜索、连通性测试和端口检查。"

