"""
文件操作Prompt模板 - 增强版

【重构日期】2026-03-19 小强
【迁移】2026-03-21 小沈 - 从 agent/prompts.py 迁移到 prompts/file/
【重构】2026-03-21 小沈 - 继承 BasePrompts 基类
【增强】2026-03-24 小沈 - 嵌入Prompt中间层(服务器OS信息)

改进点:
1. 添加参数命名规则(全局约束)
2. 详细工具描述(每个工具3-5句话)
3. 添加input_examples示例
4. 统一中英文提示
5. 继承 BasePrompts 基类
6. 嵌入服务器OS信息(Prompt中间层)- 2026-03-24
7. 升级Examples添加reasoning字段 - 2026-04-14
8. 新增finish示例和result字段 - 2026-04-14

更新时间: 2026-03-19 23:55:00
迁移时间: 2026-03-21
重构时间: 2026-03-21
增强时间: 2026-03-24
升级reasoning时间: 2026-04-14
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


class FileOperationPrompts(BasePrompts):
    """文件操作Prompt模板类"""

    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt(角色+业务规则) - 小沈 2026-06-11 系统信息提到Base公共层"""
        return """
【互斥参数规则 - 同一工具内禁止同时使用】:
- read_file: file_paths 单路径=单文件,多路径=批量
- edit_file: old_string 与 edits 互斥
- rename_file: path 与 directory 互斥
- archive_tool: compress→source+destination; extract→source
- file_operation: move/copy→destination; delete→无需destination

【write_text_file text规则】:
- text 参数必须传实际文件内容(代码/文本/正文)
- ❌ 禁止传入思考/计划/状态确认
- ✅ text=\"第一章:觉醒\\n\\n林凡是一名普通的大学生...\""""

    def get_tool_details(self) -> str:
        """获取工具描述和示例(FC模式下由Schema承载,可选跳过) - 小沈 2026-06-11"""
        tools = [
            "read_file", "write_text_file", "list_directory",
            "search_files", "grep_file_content", "edit_file",
            "rename_file", "file_operation", "archive_tool",
            "read_media_file", "data_file_format",
        ]
        tool_descriptions = self.build_tool_descriptions(tools, category_label="FILE")
        return f"""# File Operation Tools

{tool_descriptions}
【Tool Call Examples】:
Example 1: 读取文件
{{"thought": "用户要读取配置文件", "reasoning": "调用read_file单文件模式", "tool_name": "read_file", "tool_params": {{"file_paths": ["C:/config.json"]}}}}

Example 2: 搜索文件内容
{{"thought": "搜索包含TODO的Python文件", "reasoning": "使用grep_file_content搜索", "tool_name": "grep_file_content", "tool_params": {{"pattern": "TODO", "search_dir": "D:/project", "glob": "*.py"}}}}

Example 3: 写入文件
{{"thought": "用户要写入新文件", "reasoning": "使用write_text_file写入", "tool_name": "write_text_file", "tool_params": {{"file_path": "D:/output.txt", "text": "Hello World"}}}}"""

    def _get_domain_name(self) -> str:
        return "文件管理"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要做什么操作\n2. 使用合适的工具完成任务\n3. 用中文总结结果"

    def _get_domain_extra_notes(self) -> str:
        return "Remember:\n- 不要将思考内容传入text参数\n- text参数必须是实际的文件内容"

    def get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """文件管理任务 — 覆盖基类以支持context参数"""
        base_prompt = super().get_task_prompt(task)
        if context:
            base_prompt += f"\n\nAdditional context:\n{context}"
        return base_prompt

    def get_rollback_instructions(self) -> str:
        """获取回滚指令Prompt - 小沈 2026-06-11 英文→中文"""
        return """操作失败时的处理步骤:
1. 检查是否有备份(文件操作已自动备份)
2. 使用回滚功能撤销操作
3. 验证文件已正确恢复"""

    def get_safety_reminder(self) -> str:
        return "写入文件会覆盖已有内容,写入前确认是否要覆盖"
