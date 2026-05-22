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
    
    def get_system_prompt(self) -> str:
        """获取增强版系统Prompt"""
        # 获取系统信息（来自中间层）
        system_info = get_system_info(include_commands=False)  # 【修复 2026-05-14 小沈】FileAgent不注入命令格式
        logger.info(f"[FileOperationPrompts] get_system_prompt() 被调用，中间层已注入系统信息，长度: {len(system_info)}")
        
        # ========== Prompt 日志记录 ==========
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
        
        # 直接字符串拼接，避免f-string解析问题
        return system_info + """

You are a professional file management assistant. You help users organize, analyze, and manage files and directories.

【Available FILE Tools — 共11个】:

1. read_file - Read text file(s), unified entry for single/batch mode
   - When to use: read/peek/view text files, config files, logs
   - Returns: content, file_path, encoding, total_lines (single) or results (batch)
   - Examples:
     * read_file(file_paths=["C:/config.json"], offset=1, limit=100)
     * read_file(file_paths=["C:/file1.txt", "C:/file2.txt"])

2. write_text_file - Write or append text to file
   - When to use: create new files, overwrite existing content, append to logs
   - Returns: file_path, success, message
   - Examples:
     * write_text_file(file_path="D:/output.txt", text="Hello World")
     * write_text_file(file_path="D:/app.log", text="new line\\n", append=True)

3. list_directory - List directory contents
   - When to use: browse files, check directory structure
   - Returns: items, total_count, dir_count, file_count, page_token
   - Examples:
     * list_directory(dir_path="D:/project", recursive=True)
     * list_directory(dir_path="D:/project", format="tree")

4. search_files - Search files by name pattern
   - When to use: find files by name, glob pattern matching
   - Returns: matches, total_matched, page_token
   - Examples:
     * search_files(pattern="**/*.py", search_dir="D:/project")

5. grep_file_content - Search files by content pattern
   - When to use: find files containing specific text, regex search
   - Returns: matches, total_matched, page_token
   - Examples:
     * grep_file_content(pattern="TODO", search_dir="D:/project", glob="*.py")
     * grep_file_content(pattern="def main", search_dir="D:/src", context={"around": 3})

6. edit_file - Edit text file (single or multi-edit)
   - When to use: precise text replacement, batch edits
   - Returns: file_path, changes_made, diff
   - Examples:
     * edit_file(file_path="D:/main.py", old_string="def old():", new_string="def new():")
     * edit_file(file_path="D:/main.py", edits=[{"oldText": "old", "newText": "new"}])

7. rename_file - Rename file(s)
   - When to use: rename single file, batch rename with regex
   - Returns: old_path, new_path, success (single) or results (batch)
   - Examples:
     * rename_file(mode="single", path="C:/old.txt", new_name="new.txt")
     * rename_file(mode="batch", directory="D:/project", pattern="file_(\\\\d+).txt", replacement="renamed_\\\\1.txt")

8. file_operation - File operations: move/copy/delete
   - When to use: move/copy files, delete files/directories
   - Returns: operation, source, destination, success, message
   - Examples:
     * file_operation(action="move", source="C:/old.txt", destination="D:/new.txt")
     * file_operation(action="delete", source="C:/temp.txt")
     * file_operation(action="delete", source="C:/temp", recursive=True, force=True)

9. archive_tool - Compress/extract archives
   - When to use: zip/unzip files, create archives
   - Returns: operation, source, destination, file_count, size
   - Examples:
     * archive_tool(action="compress", source="D:/project", destination="D:/backup.zip")
     * archive_tool(action="extract", source="D:/backup.zip", destination="D:/extracted")

10. read_media_file - Read image, audio, video, PDF file
    - When to use: view image, play audio/video, read PDF content
    - Returns: base64_data, mime_type, file_name
    - Examples:
      * read_media_file(file_path="D:/screenshot.png")

11. data_file_format - Read/write structured data files
    - When to use: read/write JSON, YAML, TOML, INI, XML, Properties files
    - Returns: data (read) or success (write), file_path, format
    - Examples:
      * data_file_format(action="read", file_path="D:/config.json")
      * data_file_format(action="write", file_path="D:/config.yaml", data={"key": "value"})


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

class TaskTemplates:
    """预定义任务模板"""
    
    @staticmethod
    def organize_files_by_extension(directory: str) -> str:
        """按扩展名组织文件"""
        return f"""Please organize the files in directory: {directory}

Task requirements:
1. List all files in the directory
2. Group files by their extensions (e.g., .txt, .py, .jpg)
3. Create subdirectories for each extension type
4. Move files into their corresponding subdirectories
5. Handle any naming conflicts by appending a number
6. Provide a summary of what was organized

Start by listing the directory contents to see what files are present."""

    @staticmethod
    def find_and_remove_duplicates(directory: str) -> str:
        """查找并删除重复文件"""
        return f"""Please find and handle duplicate files in: {directory}

Task requirements:
1. Search for files with similar names or identical content
2. Identify potential duplicates
3. For each set of duplicates:
   - Keep the original (oldest) file
   - Move duplicates to a "duplicates_backup" folder
4. Do NOT delete files permanently (move instead)
5. Generate a report of all actions taken

Be careful to only move actual duplicates, not similar-named files that are different."""

    @staticmethod
    def cleanup_empty_directories(directory: str) -> str:
        """清理空目录"""
        return f"""Please clean up empty directories in: {directory}

Task requirements:
1. Recursively scan the directory structure
2. Identify directories that are empty (no files or subdirectories)
3. Remove empty directories safely
4. Keep doing this until no more empty directories are found
5. Report how many directories were removed

Safety note: Only remove truly empty directories."""

    @staticmethod
    def analyze_directory_structure(directory: str) -> str:
        """分析目录结构"""
        return f"""Please analyze the directory structure of: {directory}

Task requirements:
1. List all files and directories recursively
2. Count files by type (extension)
3. Calculate total size and file counts
4. Identify the largest files
5. Find any unusual patterns (very deep nesting, many small files, etc.)
6. Provide recommendations for organization

This is an analysis task - do not make any changes to the files."""

    @staticmethod
    def search_and_replace_content(directory: str, pattern: str, replacement: str) -> str:
        """搜索替换文件内容"""
        return f"""Please perform search and replace in files within: {directory}

Task requirements:
1. Search for files containing pattern: "{pattern}"
2. For each matching file:
   - Read the file content
   - Replace "{pattern}" with "{replacement}"
   - Write the modified content back
3. Create backups before modifying (handled automatically)
4. Report how many files were modified
5. Show examples of changes made

Warning: This operation modifies file contents. Be sure the pattern is correct before proceeding."""
