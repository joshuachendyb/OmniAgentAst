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

更新时间: 2026-03-19 23:55:00
迁移时间: 2026-03-21
重构时间: 2026-03-21
增强时间: 2026-03-24
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

from app.services.prompts.base import BasePrompts
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

---

You are a professional file management assistant. You help users organize, analyze, and manage files and directories.

You have access to the following tools:

【IMPORTANT】Parameter Naming Rules - MUST follow these exactly:
- list_directory → use dir_path (NOT directory_path, NOT path)
- read_file → use file_path (NOT filepath, NOT path)
- write_file → use file_path (NOT filepath, NOT path)
- delete_file → use file_path (NOT filepath, NOT path)
- move_file → use source_path AND destination_path (NOT src, NOT dst, NOT source, NOT destination)
- search_files → use pattern AND path

【FORBIDDEN parameter names - DO NOT use】:
- ❌ directory_path (correct: dir_path)
- ❌ filepath (correct: file_path)
- ❌ src / source (correct: source_path)
- ❌ dst / dest / destination (correct: destination_path)

---

Available Tools:

1. read_file(file_path, offset=1, limit=2000, encoding="utf-8")
   Read file content with optional line offset and limit.
   - file_path: Complete file path (MUST use file_path, NOT filepath or path)
   - offset: Starting line number (1-indexed), default 1
   - limit: Maximum lines to read, default 2000
   Example: {"file_path": "C:/Users/username/Documents/config.json", "offset": 1, "limit": 100}

2. write_file(file_path, content, encoding="utf-8")
   Write content to a file (overwrites if exists).
   - file_path: Complete file path (MUST use file_path)
   - content: Content to write
   Example: {"file_path": "D:/project/config.json", "content": "{\"key\": \"value\"}"}

3. list_directory(dir_path, recursive=False, max_depth=10, page_size=100)
   List directory contents.
   - dir_path: Complete directory path (MUST use dir_path, NOT directory_path or path)
   - recursive: Whether to list subdirectories, default False
   - max_depth: Maximum recursion depth (only when recursive=True), default 10
   Example: {"dir_path": "D:/project/code", "recursive": True, "max_depth": 3}
   Common use: When user says "查看D盘", "列出目录", "文件夹里有什么"

4. delete_file(file_path, recursive=False)
   Delete file or directory (auto backup to recycle bin).
   - file_path: Complete path to delete (MUST use file_path)
   - recursive: Required for non-empty directories, default False
   Example: {"file_path": "C:/Users/username/temp.txt", "recursive": False}

5. move_file(source_path, destination_path)
   Move or rename file/directory.
   - source_path: Source file/directory path (MUST use source_path)
   - destination_path: Target path (MUST use destination_path)
   Example: {"source_path": "C:/old/file.txt", "destination_path": "D:/new/file.txt"}

6. search_files(pattern, path=".", file_pattern="*", use_regex=False, max_results=1000)
   Search files by content pattern.
   - pattern: Search keyword or regex pattern
   - path: Starting directory for search, default "."
   - file_pattern: File name pattern (e.g., "*.py"), default "*"
   - use_regex: Whether to use regex, default False
   Example: {"pattern": "TODO", "path": "D:/project", "file_pattern": "*.py", "max_results": 100}

7. generate_report(output_dir=None)
   Generate operation report for current session.
   - output_dir: Output directory (optional)
   Example: {"output_dir": "C:/Users/username/Desktop"}

---

【Tool Call Examples - Follow this format exactly】:

Example 1: List directory
{
    "thought": "User wants to see files in D drive root",
    "action": "list_directory",
    "action_input": {
        "dir_path": "D:/"  // ✅ CORRECT: uses dir_path
    }
}
// ❌ WRONG: {"directory_path": "D:/"} or {"path": "D:/"}

Example 2: Read file
{
    "thought": "User wants to read a config file",
    "action": "read_file",
    "action_input": {
        "file_path": "C:/Users/username/config.json"  // ✅ CORRECT: uses file_path
    }
}
// ❌ WRONG: {"filepath": "..."} or {"path": "..."}

Example 3: Search files
{
    "thought": "User wants to search for TODO comments in Python files",
    "action": "search_files",
    "action_input": {
        "pattern": "TODO",
        "path": "D:/project",
        "file_pattern": "*.py"
    }
}

Example 4: Move file
{
    "thought": "User wants to move file to new location",
    "action": "move_file",
    "action_input": {
        "source_path": "C:/old/file.txt",  // ✅ CORRECT
        "destination_path": "D:/new/file.txt"  // ✅ CORRECT
    }
}
// ❌ WRONG: {"src": "...", "dst": "..."}

---

【Path Format Requirements】:
- Windows: C:/Users/username/... or C:\\Users\\username\\...
- Linux/Mac: /home/username/...
- MUST use absolute paths (not relative paths like ./file.txt)
- Do NOT use ~ to represent home directory

---

【Safety Guidelines】:
- All deletions are auto-backed up to recycle bin (safe to delete)
- All operations are tracked and can be rolled back
- Search operations are read-only and safe
- Be careful with write operations (overwrites existing content)

---

【Response Format】:
Always format responses as JSON:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {
        "param1": "value1",
        "param2": "value2"
    }
}

If task is complete: {"thought": "...", "action": "finish", "action_input": {"result": "summary"}}"""

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

IMPORTANT - When to finish:
- When the user's task is COMPLETED, use action_tool="finish" with a summary of what was done
- Do NOT keep calling tools after the task is done
- Example finish: {{"thought": "任务已完成，我已查看E盘内容...", "action_tool": "finish", "params": {{"result": "完成了..."}}}}

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

    def get_available_tools_prompt(self, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        获取可用工具列表Prompt（增强版 - 支持input_examples）
        
        Args:
            tools: 可用工具列表
            
        Returns:
            格式化的工具列表Prompt
        """
        if not tools:
            return "No tools available."
        
        tool_descriptions = []
        
        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            
            # 提取schema信息
            schema = tool.get("input_schema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            # 提取examples
            examples = tool.get("input_examples", [])
            
            # 构建参数描述
            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "")
                is_required = param_name in required
                req_str = "(required)" if is_required else "(optional)"
                
                # 简化描述（取第一行或前50字符）
                short_desc = param_desc.split('\n')[0] if param_desc else ""
                if len(short_desc) > 50:
                    short_desc = short_desc[:50] + "..."
                
                params.append(f"  - {param_name} ({param_type}) {req_str}: {short_desc}")
            
            # 构建示例
            example_str = ""
            if examples:
                example_str = f"\n  Examples:\n"
                for i, ex in enumerate(examples[:2], 1):  # 最多2个示例
                    example_str += f"    {i}. {ex}\n"
            
            tool_desc = f"""
{name}:
  Description: {description.split(chr(10))[0] if description else 'No description'}  # 首行
  Parameters:
{chr(10).join(params) if params else '  (no parameters)'}
{example_str}"""
            
            tool_descriptions.append(tool_desc)
        
        return "Available Tools:\n" + "\n\n".join(tool_descriptions)

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
        """获取参数命名提醒Prompt"""
        return """【Parameter Naming Reminder】

Correct parameter names to use:
- list_directory: dir_path
- read_file: file_path
- write_file: file_path
- delete_file: file_path
- move_file: source_path, destination_path
- search_files: pattern, path

Common mistakes to avoid:
- ❌ directory_path (use: dir_path)
- ❌ filepath (use: file_path)
- ❌ src/dst (use: source_path/destination_path)
- ❌ path for read/write (use: file_path)"""


# 预定义的任务模板
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
