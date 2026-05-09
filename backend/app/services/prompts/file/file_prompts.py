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
        system_info = get_system_info()
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
            }
        )
        
        # 直接字符串拼接，避免f-string解析问题
        return system_info + """


You are a professional file management assistant. You help users organize, analyze, and manage files and directories.

You have access to the following tools:


Available Tools:

1. read_text_file(file_path, head=None, tail=None, offset=None, limit=None, encoding=None)
   Read text file content, supports head/tail/offset/limit modes. Always UTF-8.
   - file_path: Complete file path (MUST use file_path, NOT filepath or path)
   - head: Read first N lines (cannot use with tail/offset)
   - tail: Read last N lines (cannot use with head/offset)
   - offset: Starting line number (1-indexed, cannot use with head/tail)
   - limit: Maximum lines to read (use with offset)
   Example: {"file_path": "C:/Users/username/Documents/config.json", "offset": 1, "limit": 100}

2. write_text_file(file_path, text, encoding=None, append=False, create_parents=True, unescape=True)
   Write or append text to a file (overwrites if exists, unless append=True).
   - file_path: Complete file path (MUST use file_path)
   - text: Text content to write (MUST use text, NOT content)
   - append: Append to file instead of overwrite, default False
   Example: {"file_path": "D:/project/config.json", "text": "{\"key\": \"value\"}"}

3. list_directory(dir_path, recursive=False, max_depth=10, sortBy=None, include_hidden=False)
   List directory contents with file size, modification time.
   - dir_path: Complete directory path (MUST use dir_path, NOT directory_path or path)
   - recursive: Whether to list subdirectories, default False
   - max_depth: Maximum recursion depth (only when recursive=True), default 10
   Example: {"dir_path": "D:/project/code", "recursive": True, "max_depth": 3}
   Common use: When user says "查看D盘", "列出目录", "文件夹里有什么"

4. delete_file(file_path, recursive=False, force=False)
   Delete file or directory. Default: move to recycle bin (safe). force=True: permanent delete.
   - file_path: Complete path to delete (MUST use file_path)
   - recursive: Required for non-empty directories, default False
   - force: Permanent delete without recycle bin, default False
   Example: {"file_path": "C:/Users/username/temp.txt", "recursive": False}

5. move_file(source_path, destination_path, overwrite=False)
   Move or rename file/directory.
   - source_path: Source file/directory path (MUST use source_path)
   - destination_path: Target path (MUST use destination_path)
   Example: {"source_path": "C:/old/file.txt", "destination_path": "D:/new/file.txt"}

6. search_files(pattern, search_dir, recursive=True, max_depth=10, ignore_case=True)
   Search files by file name pattern (glob supported, Chinese filenames supported).
   - pattern: File name pattern with wildcard (e.g., "**/*.py", "config*") (REQUIRED)
   - search_dir: Starting directory for search (REQUIRED, CANNOT be empty)
   - recursive: Whether to search subdirectories, default True
   Example: {"pattern": "**/*.py", "search_dir": "D:/project", "recursive": True}

7. grep_file_content(pattern, search_dir=None, glob=None, ignore_case=False, head_limit=None, show_line_no=True)
   Search files by content pattern (regex supported, Chinese supported).
   - pattern: Regex search pattern (REQUIRED, CANNOT be empty)
   - search_dir: Starting directory for search, default current dir
   - glob: File name filter (e.g., "*.py"), default None
   - ignore_case: Whether to ignore case, default False
   - head_limit: Max results to return, default None
   Example: {"pattern": "TODO", "search_dir": "D:/project", "glob": "*.py", "ignore_case": true}

8. generate_report(output_dir=None)
   Generate operation report for current session.
   - output_dir: Output directory (optional)
   Example: {"output_dir": "C:/Users/username/Desktop"}

9. precise_replace_in_file(file_path, old_string, new_string, replace_all=False)
   Precise string replacement in text file. Supports Chinese content matching.
   - file_path: File absolute path
   - old_string: Exact text to find and replace
   - new_string: Replacement text
   Example: {"file_path": "D:/project/main.py", "old_string": "def old():", "new_string": "def new():"}

10. edit_text_file(file_path, edits, dryRun=False)
    Advanced multi-edit with pattern matching, supports dryRun preview.
    - file_path: File path to edit
    - edits: Array of {oldText, newText} edit operations
    - dryRun: Preview only without modifying file, default False
    Example: {"file_path": "D:/project/main.py", "edits": [{"oldText": "old", "newText": "new"}]}

11. get_directory_tree(dir_path, excludePatterns=None, max_depth=None)
    Get recursive JSON tree structure of directory.
    - dir_path: Starting directory
    Example: {"dir_path": "D:/project"}


【Tool Call Examples - Follow this format exactly】:

Example 1: List directory
{"thought": "查看D盘根目录文件", "reasoning": "调用list_directory", "tool_name": "list_directory", "tool_params": {"dir_path": "D:/"}}

Example 2: Read file
{"thought": "读取配置文件", "reasoning": "调用read_text_file", "tool_name": "read_text_file", "tool_params": {"file_path": "C:/Users/username/config.json"}}

Example 3: Write file
{"thought": "写入文件内容", "reasoning": "调用write_text_file", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/project/output.txt", "text": "Hello World"}}

Example 4: Error handling
{"thought": "文件读取失败，路径可能不存在", "reasoning": "向用户报告错误并建议检查路径", "tool_name": "finish", "tool_params": {"result": "读取失败：文件C:/not-exist.txt不存在，请确认路径是否正确"}}

Example 5: Task completed
{"thought": "任务已完成", "reasoning": "无更多操作", "tool_name": "finish", "tool_params": {"result": "已列出D盘根目录的文件：..."}}



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

Please help me complete this file management task. Follow these steps:
1. First, analyze what needs to be done
2. Use the appropriate tools to accomplish the task
3. Provide a summary when finished

Remember:
- You can use multiple tools in sequence
- Each tool call should be well-reasoned
- If an operation fails, explain why and suggest alternatives
- All file operations are tracked for safety"""

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
        return """If you need to undo previous operations, you can use the rollback functionality.

To rollback:
1. Single operation rollback - undo the last operation
2. Session rollback - undo all operations in this session

Rollback will:
- Restore deleted files from backup
- Move files back to their original locations
- Delete newly created files (if safe to do so)

Warning: Rollback operations cannot be undone. Be certain before proceeding."""

    def get_safety_reminder(self) -> str:
        """获取安全提醒Prompt"""
        return """Safety reminders:
1. All file deletions are backed up automatically
2. File moves are tracked with source/destination mapping
3. All operations are recorded in the operation history
4. You can rollback any operation or the entire session
5. Be careful when writing files - existing content will be overwritten
6. Search operations are read-only and safe to use anytime"""
    
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
            "- ❌ src/dst (use: source_path/destination_path)\n"
            "- ❌ read_file (use: read_text_file)\n"
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
