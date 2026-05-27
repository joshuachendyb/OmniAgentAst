"""
文件操作Prompt模板 - 增强版

【重构日期】2026-03-19 小强
【迁移】2026-03-21 小沈 - 从 agent/prompts.py 迁移到 prompts/file/
【重构】2026-03-21 小沈 - 继承 BasePrompts 基类
【增强】2026-03-24 小沈 - 嵌入Prompt中间层（服务器OS信息）

改进点：
1. 添加参数命名规则（全局约束）
2. 详细工具描述（每个工具3-5句话）
3. 添加input_examples示例
4. 统一中英文提示
5. 继承 BasePrompts 基类
6. 嵌入服务器OS信息（Prompt中间层）- 2026-03-24
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

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class FileOperationPrompts(BasePrompts):
    """文件操作Prompt模板类"""

    def _build_tool_descriptions(self, category: str, tools: List[str]) -> str:
        """从 ToolRegistry 动态生成工具描述字符串 — 委托到 BasePrompts.build_tool_descriptions"""
        return self.build_tool_descriptions(tools, category_label=category.upper())

    def get_system_prompt(self) -> str:
        """获取增强版系统Prompt - 小沈 2026-05-25 重构拆分"""
        system_info = get_system_info(include_commands=False)
        logger.info(f"[FileOperationPrompts] get_system_prompt() 被调用，中间层已注入系统信息，长度: {len(system_info)}")

        from app.utils.prompt_logger import get_prompt_logger
        prompt_logger = get_prompt_logger()
        prompt_logger.log_system_prompt(
            step_name="中间层注入-服务器OS信息",
            prompt_content=system_info,
            source="system_adapter.py:generate_system_prompt()",
            details={
                "系统信息长度": len(system_info),
                "包含内容": "服务器OS、路径格式、命令格式"
            },
            round_number=1
        )

        tools = [
            "read_file", "write_text_file", "list_directory",
            "search_files", "grep_file_content", "edit_file",
            "rename_file", "file_operation", "archive_tool",
            "read_media_file", "data_file_format",
        ]
        tool_descriptions = self._build_tool_descriptions("file", tools)

        prompt = f"{system_info}\n\n# File Operation Tools\n\n{tool_descriptions}"

        return prompt + """
【Tool Call Examples】:
Example 1: 读取文件
{"thought": "用户要读取配置文件", "reasoning": "调用read_file单文件模式", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/config.json"]}}

Example 2: 搜索文件内容
{"thought": "搜索包含TODO的Python文件", "reasoning": "使用grep_file_content搜索", "tool_name": "grep_file_content", "tool_params": {"pattern": "TODO", "search_dir": "D:/project", "glob": "*.py"}}

Example 3: 写入文件
{"thought": "用户要写入新文件", "reasoning": "使用write_text_file写入", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/output.txt", "text": "Hello World"}}

Example 4: 任务完成
{"thought": "文件操作已完成", "reasoning": "全部操作成功，结果已返回", "tool_name": "finish", "tool_params": {"result": "已读取配置文件并完成搜索"}}


【⚠️ P17互斥参数规则 - 极其重要】:
- read_file: file_paths传1个路径=单文件, 传多个=批量
- edit_file: old_string 和 edits 不能同时使用
- rename_file: path 和 directory 不能同时使用
- archive_tool: compress模式需要source+destination，extract模式需要source
- file_operation: move/copy需要destination，delete不需要

【⚠️ write_text_file text规则 - 极其重要】:
- text参数必须传入实际的文件内容（代码、文本、正文等）
- ❌ 绝对禁止将你的思考/计划/状态确认当作text传入
- ❌ 错误示例: text="已成功创建并写入第一章，需要继续创建第二章"
- ✅ 正确示例: text="第一章：觉醒

林凡是一名普通的大学生..."""

    def get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        获取任务Prompt
        
        Args:
            task_description: 任务描述
            context: 额外上下文信息
            
        Returns:
            格式化的任务Prompt
        """
        base_prompt = f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此文件管理任务，按以下步骤：
1. 分析需要做什么操作
2. 使用合适的工具完成任务
3. 用中文总结结果

Remember:
- 不要将思考内容传入text参数
- text参数必须是实际的文件内容"""
        if context:
            base_prompt += f"\n\nAdditional context:\n{context}"
        
        return base_prompt

    def get_observation_prompt(self, observation: str) -> str:
        """
        格式化观察结果Prompt
        
        Args:
            observation: 工具执行结果（字符串格式）
            
        Returns:
            格式化的观察Prompt
        """
        # 如果observation是JSON字符串，尝试解析
        try:
            obs_dict = json.loads(observation) if isinstance(observation, str) else observation
        except (json.JSONDecodeError, TypeError):
            obs_dict = {}
        
        if obs_dict.get("success", False):
            result = obs_dict.get("result", {})
            return f"""Observation: The operation was successful.

Result details:
- Operation: {result.get('operation_type', 'unknown')}
- File: {result.get('file_path', 'N/A')}
- Additional info: {result.get('message', 'No additional information')}

What's your next step?"""
        else:
            error = obs_dict.get("error", "Unknown error")
            return f"""Observation: The operation failed.

Error: {error}

Please reconsider your approach and suggest an alternative action."""


    def get_rollback_instructions(self) -> str:
        """获取回滚指令Prompt"""
        return """If an operation fails:
1. Check if backup exists (file operations are backed up automatically)
2. Use the rollback functionality to undo the operation
3. Verify the file has been restored correctly"""

    def get_safety_reminder(self) -> str:
        """获取安全提醒Prompt"""
        return """Safety reminders:
1. Be careful when writing files - existing content will be overwritten
2. text parameter must contain actual file content, NOT your thoughts/plans"""
    
    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.FILE)
        forbidden = (
            "\n\nCommon mistakes to avoid:\n"
            "- ❌ directory_path (use: dir_path)\n"
            "- ❌ filepath (use: file_path)\n"
            "- ❌ content for write (use: text)\n"
            "- ❌ file_pattern for search (use: pattern)\n"
            "- ❌ path for search_dir (use: search_dir)\n"
            "- ❌ src/dst (use: source/destination)\n"
            "- ❌ read_text_file (use: read_file)\n"
            "- ❌ write_file (use: write_text_file)"
        )
        return auto_reminder + forbidden
