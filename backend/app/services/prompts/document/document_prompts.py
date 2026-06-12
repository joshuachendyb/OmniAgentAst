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

【调用决策示例】:
用户: "读取C:/docs/test.docx"
→ 判断: Word文档读取 → 调用read_document(file_path="C:/docs/test.docx")

用户: "查看C:/data/sales.xlsx的数据"
→ 判断: Excel读取 → 调用read_document(file_path="C:/data/sales.xlsx")

用户: "查询用户表数据"
→ 判断: SQL查询 → 调用query_sql(sql="SELECT * FROM users")"""
    


    def _get_domain_name(self) -> str:
        return "文檔处理"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要的文档操作\n2. 使用合适的文档工具\n3. 用中文总结文档处理结果"
