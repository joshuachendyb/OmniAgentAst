"""
文件操作Prompt模板 (File Operation Prompts)
为ReAct Agent提供文件操作任务的Prompt模板
"""
from datetime import datetime
from typing import List, Dict, Any


class FileOperationPrompts:
    """文件操作Prompt模板类"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """获取系统Prompt"""
        return """You are a file management assistant. You help users organize, analyze, and manage files and directories.

You have access to the following tools:
1. read_file - Read file content with optional offset and limit
2. write_file - Write content to a file
3. list_directory - List directory contents
4. delete_file - Delete a file (with automatic backup)
5. move_file - Move or rename a file
6. search_files - Search files by content pattern

When you need to perform file operations:
1. Think about what needs to be done
2. Use the appropriate tool with proper parameters
3. Observe the results
4. Continue until the task is complete

Always format your responses as JSON with the following structure:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {
        "param1": "value1",
        "param2": "value2"
    }
}

If the task is complete, set action to "finish" and action_input to {"result": "summary of what was done"}.

Safety guidelines:
- Before deleting files, consider if they should be backed up (they will be automatically)
- When moving files, ensure the destination directory exists
- When writing files, ensure the parent directory exists
- Be careful with search patterns to avoid matching unintended files

All operations are tracked and can be rolled back if needed."""

    @staticmethod
    def get_task_prompt(task_description: str, context: Dict[str, Any] = None) -> str:
        """
        获取任务Prompt
        
        Args:
            task_description: 任务描述
            context: 额外上下文信息
            
        Returns:
            格式化的任务Prompt
        """
        base_prompt = f"""Task: {task_description}

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

    @staticmethod
    def get_observation_prompt(observation: Dict[str, Any]) -> str:
        """
        格式化观察结果Prompt
        
        Args:
            observation: 工具执行结果
            
        Returns:
            格式化的观察Prompt
        """
        if observation.get("success", False):
            result = observation.get("result", {})
            return f"""Observation: The operation was successful.

Result details:
- Operation: {result.get('operation_type', 'unknown')}
- File: {result.get('file_path', 'N/A')}
- Additional info: {result.get('message', 'No additional information')}

What's your next step?"""
        else:
            error = observation.get("error", "Unknown error")
            return f"""Observation: The operation failed.

Error: {error}

Please reconsider your approach and suggest an alternative action."""

    @staticmethod
    def get_available_tools_prompt(tools: List[Dict[str, Any]]) -> str:
        """
        获取可用工具列表Prompt
        
        Args:
            tools: 可用工具列表
            
        Returns:
            格式化的工具列表Prompt
        """
        tool_descriptions = []
        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            params = tool.get("parameters", {})
            
            param_str = ", ".join([
                f"{k}: {v.get('type', 'any')}"
                for k, v in params.get("properties", {}).items()
            ])
            
            tool_descriptions.append(
                f"- {name}({param_str}): {description}"
            )
        
        return "Available tools:\n" + "\n".join(tool_descriptions)

    @staticmethod
    def get_rollback_instructions() -> str:
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

    @staticmethod
    def get_safety_reminder() -> str:
        """获取安全提醒Prompt"""
        return """Safety reminders:
1. All file deletions are backed up automatically
2. File moves are tracked with source/destination mapping
3. All operations are recorded in the operation history
4. You can rollback any operation or the entire session
5. Be careful when writing files - existing content will be overwritten
6. Search operations are read-only and safe to use anytime"""


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
