# -*- coding: utf-8 -*-
"""
DocumentPrompts - 文档读写 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
【2026-05-18 小沈】更新工具列表:8合2路由重构,移除旧工具名
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from datetime import datetime

from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


class DocumentPrompts(BasePrompts):
    """文档读写 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "You are a professional document operations assistant. You help users read/write PDF, Word, Excel, PPT documents, and perform data analysis."

    def get_tool_details(self) -> str:
        """获取工具描述和示例(FC模式下可选跳过) - 小沈 2026-06-11"""
        tools = [
            "read_document", "write_document", "convert_document",
            "analyze_data", "filter_data", "generate_chart",
            "query_sql", "execute_sql", "get_db_schema",
        ]
        tool_descriptions = self.build_tool_descriptions(tools, category_label="DOCUMENT")
        return f"""【Available DOCUMENT Tools】:
{tool_descriptions}

【Tool Call Examples】:
Example 1: 读取文档
{{"thought": "用户要读取Word文档", "reasoning": "使用read_document", "tool_name": "read_document", "tool_params": {{"file_path": "C:/docs/test.docx"}}}}

Example 2: 读取Excel
{{"thought": "用户要读取Excel数据", "reasoning": "调用read_document读取", "tool_name": "read_document", "tool_params": {{"file_path": "C:/data/sales.xlsx"}}}}

Example 3: 查询数据库
{{"thought": "用户要查询数据", "reasoning": "使用query_sql", "tool_name": "query_sql", "tool_params": {{"sql": "SELECT * FROM users"}}}}"""
    

    def get_safety_reminder(self) -> str:
        return "⚠️ Document Safety: write_document overwrites existing files. Read before write to confirm."

    def _get_domain_name(self) -> str:
        return "文檔处理"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要的文档操作\n2. 使用合适的文档工具\n3. 用中文总结文档处理结果"
