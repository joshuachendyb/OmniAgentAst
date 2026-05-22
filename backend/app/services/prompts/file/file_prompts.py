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

You have access to the following 11 tools:


Available Tools (F1-F11):

F1. read_file(file_paths, head=None, tail=None, offset=None, limit=None, encoding=None)
   Read text file(s) - unified entry. Supports single file with head/tail/offset/limit, or batch read.
   - file_paths: List of file paths. 1 path=single file(pagination supported), multiple=batch read
   - head/tail/offset/limit: Pagination for single file mode only
   - encoding: File encoding, default utf-8
   Example (single): {"file_paths": ["C:/config.json"], "offset": 1, "limit": 100}
   Example (batch): {"file_paths": ["C:/file1.txt", "C:/file2.txt"]}

F2. write_text_file(file_path, text, encoding=None, append=False, create_parents=True, unescape=True)
   Write or append text to a file.
   - file_path: Complete file path
   - text: Text content to write (MUST be actual content, NOT thoughts/plans)
   - append: Append mode, default False (overwrite)
   Example: {"file_path": "D:/output.txt", "text": "Hello World"}
   Example (append): {"file_path": "D:/app.log", "text": "new line\\n", "append": true}

F3. read_media_file(file_path)
   Read image, audio, video, or PDF file, returns Base64 encoded data and MIME type.
   - file_path: Media file path (JPG/PNG/GIF/BMP/WebP/SVG/MP3/WAV/MP4/AVI/MKV/PDF etc.)
   Example: {"file_path": "D:/screenshot.png"}

F4. edit_file(file_path, old_string=None, new_string=None, edits=None, replace_all=False, dry_run=False, encoding=None)
   Edit text file - unified entry. MUTUALLY EXCLUSIVE: old_string OR edits (not both).
   - old_string+new_string: Single precise replacement
   - edits: Array of {oldText, newText} for multi-edit (MUTUALLY EXCLUSIVE with old_string)
   - dry_run: Preview only without modifying, default False
   Example (single): {"file_path": "D:/main.py", "old_string": "def old():", "new_string": "def new():"}
   Example (multi): {"file_path": "D:/main.py", "edits": [{"oldText": "old", "newText": "new"}]}

F5. list_directory(dir_path, format="list", recursive=False, max_depth=10, sortBy="name", include_hidden=False, page_token=None)
   List directory contents. format="list" returns flat list, format="tree" returns JSON tree. Always includes statistics.
   - dir_path: Directory path
   - format: "list" or "tree", default "list"
   - recursive: List subdirectories, default False
   Example: {"dir_path": "D:/project", "recursive": true}
   Example (tree): {"dir_path": "D:/project", "format": "tree"}

F6. search_files(pattern, search_dir, recursive=True, max_depth=50, ignore_case=True, type=None, page_token=None)
   Search files by name pattern (glob supported, Chinese filenames supported).
   - pattern: File name pattern (e.g., "**/*.py", "config*") (REQUIRED)
   - search_dir: Starting directory (REQUIRED)
   Example: {"pattern": "**/*.py", "search_dir": "D:/project"}

F7. grep_file_content(pattern, search_dir=None, output_mode=None, glob=None, context=None, ignore_case=True, head_limit=None, multiline=False, page_token=None)
   Search files by content pattern (regex supported, Chinese supported).
   - pattern: Regex search pattern (REQUIRED)
   - search_dir: Starting directory, default current dir
   - glob: File name filter (e.g., "*.py")
   - context: Context lines, e.g. {"around": 3} or {"after": 2, "before": 1}
   Example: {"pattern": "TODO", "search_dir": "D:/project", "glob": "*.py"}
   Example (context): {"pattern": "def main", "search_dir": "D:/src", "context": {"around": 3}}

F8. rename_file(mode="single", path=None, new_name=None, directory=None, pattern=None, replacement=None)
   Rename file(s). mode="single" for single file, mode="batch" for batch regex rename.
   - mode="single": path + new_name (single file rename)
   - mode="batch": directory + pattern + replacement (batch regex rename)
   Example (single): {"mode": "single", "path": "C:/old.txt", "new_name": "new.txt"}
   Example (batch): {"mode": "batch", "directory": "D:/project", "pattern": "file_(\\\\d+).txt", "replacement": "renamed_\\\\1.txt"}

F9. archive_tool(action, source=None, destination=None, format="zip", compression_level=6, password=None, overwrite=False, exclude_patterns=None)
   Compress/extract archives. action: "compress" or "extract".
   - action: "compress" or "extract" (REQUIRED)
   - compress needs: source + destination
   - extract needs: source (destination optional)
   Example (compress): {"action": "compress", "source": "D:/project", "destination": "D:/backup.zip"}
   Example (extract): {"action": "extract", "source": "D:/backup.zip", "destination": "D:/extracted"}

F10. file_operation(action, source, destination=None, recursive=False, overwrite=False, force=False, preserve_metadata=True)
   File operations - unified entry for move/copy/delete.
   - action: "move" | "copy" | "delete" (REQUIRED)
   - source: Source path (REQUIRED)
   - destination: Target path (REQUIRED for move/copy, NOT for delete)
   - force: For delete only: True=permanent delete(skip recycle bin), False=use recycle bin; default False
   - preserve_metadata: For copy only: preserve file timestamps/metadata; default True
   Example (move): {"action": "move", "source": "C:/old.txt", "destination": "D:/new.txt"}
   Example (delete): {"action": "delete", "source": "C:/temp.txt"}
   Example (permanent delete dir): {"action": "delete", "source": "C:/temp", "recursive": true, "force": true}

F11. data_file_format(action="read", file_path, format=None, data=None, encoding="utf-8", indent=None)
   Read/write structured data files (JSON/YAML/TOML/INI/XML/Properties). Unified entry.
   - action: "read" or "write" (REQUIRED)
   - file_path: File path (REQUIRED)
   - data: Data to write (REQUIRED for write). For JSON/YAML/TOML: pass dict or list. INI/XML/Properties do NOT support write.
   - format: Force format (optional, auto-detect from extension if not specified)
   - indent: JSON write indentation spaces (default 2). YAML/TOML do NOT support indent.
   Example (read): {"action": "read", "file_path": "D:/config.json"}
   Example (write): {"action": "write", "file_path": "D:/config.yaml", "data": {"key": "value"}}


【Tool Call Examples - Follow this format exactly】:

Example 1: List directory
{"thought": "查看D盘根目录文件", "reasoning": "调用list_directory", "tool_name": "list_directory", "tool_params": {"dir_path": "D:/"}}

Example 2: Read file
{"thought": "读取配置文件", "reasoning": "调用read_file单文件模式", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/config.json"]}}

Example 3: Read multiple files
{"thought": "批量读取", "reasoning": "调用read_file批量模式", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/a.txt", "C:/b.txt"]}}

Example 4: Write file
{"thought": "写入文件", "reasoning": "调用write_text_file", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/output.txt", "text": "Hello World"}}

Example 5: Edit file (single replacement)
{"thought": "精确替换", "reasoning": "调用edit_file单处替换", "tool_name": "edit_file", "tool_params": {"file_path": "D:/main.py", "old_string": "def old():", "new_string": "def new():"}}

Example 6: Edit file (multi-edit)
{"thought": "多处编辑", "reasoning": "调用edit_file多处编辑", "tool_name": "edit_file", "tool_params": {"file_path": "D:/main.py", "edits": [{"oldText": "old", "newText": "new"}, {"oldText": "foo", "newText": "bar"}]}}

Example 7: Move file
{"thought": "移动文件", "reasoning": "调用file_operation移动", "tool_name": "file_operation", "tool_params": {"action": "move", "source": "C:/old.txt", "destination": "D:/new.txt"}}

Example 8: Delete file
{"thought": "删除文件", "reasoning": "调用file_operation删除", "tool_name": "file_operation", "tool_params": {"action": "delete", "source": "C:/temp.txt"}}

Example 9: Compress
{"thought": "压缩目录", "reasoning": "调用archive_tool压缩", "tool_name": "archive_tool", "tool_params": {"action": "compress", "source": "D:/project", "destination": "D:/backup.zip"}}

Example 10: Read JSON
{"thought": "读取JSON配置", "reasoning": "调用data_file_format", "tool_name": "data_file_format", "tool_params": {"action": "read", "file_path": "D:/config.json"}}

Example 11: Rename
{"thought": "重命名文件", "reasoning": "调用rename_file单文件模式", "tool_name": "rename_file", "tool_params": {"path": "D:/old.txt", "new_name": "new.txt"}}

Example 12: Error handling
{"thought": "操作失败", "reasoning": "向用户报告错误", "tool_name": "finish", "tool_params": {"result": "操作失败：文件不存在，请确认路径"}}

Example 13: Task completed
{"thought": "任务完成", "reasoning": "无更多操作", "tool_name": "finish", "tool_params": {"result": "已完成文件操作"}}



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
