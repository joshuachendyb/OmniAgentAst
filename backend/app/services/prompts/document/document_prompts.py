# -*- coding: utf-8 -*-
"""
DocumentPrompts - 文档读写 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
【2026-05-18 小沈】更新工具列表:8合2路由重构,移除旧工具名
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from app.services.prompts.base_prompt_template import BasePrompts


class DocumentPrompts(BasePrompts):
    """文档读写 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "你是一个文档处理助手,负责PDF/Word/Excel/PPT文档的读写和数据分析。"
