"""
MCP文件操作工具集 - 重写版本

【重构日期】2026-03-19 小强
【参考】FastMCP、MarcusJellinghaus、LangChain、Claude官方Tool Use规范

改进点：
1. 使用Pydantic模型定义参数Schema
2. 动态白名单（自动添加存在的盘符）
3. 自动生成JSON Schema
4. 添加input_examples示例
5. 修复search_file_content空pattern安全漏洞

统一返回格式：{status, summary, data, retry_count}

【分页方案更新】2026-04-03 小沈
- read_file: 默认读取500行（READ_FILE_DEFAULT_LIMIT = 500）
- 其他工具: 返回全部数据（DEFAULT_PAGE_SIZE = 999999999）
"""

import asyncio
import base64
import inspect
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, get_type_hints

# 【修改】移除分页限制，2026-04-03 小沈
# 原因：后端必须返回全部真实数据，前端自己控制显示方式（分页/滚动）
# 前端不再依赖 next-page 接口，后端不再做分页处理

# read_file 特殊处理：默认限制500行（因为大文件不能一次性读取到内存）
READ_FILE_DEFAULT_LIMIT = 500

# 其他工具返回全部数据
DEFAULT_PAGE_SIZE = 999999999  # 远超实际数据量，保证返回全部

from pydantic import BaseModel, Field

from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFileContentInput,
    SearchFilesByNameInput,
    GenerateReportInput,
)

from app.services.agent import (
    get_file_safety_service,
    get_session_service
)
from app.services.safety.file.file_safety import OperationType
from app.utils.visualization import get_visualizer
from app.utils.logger import logger


# ============================================================
# 第一部分：分页配置常量
# ============================================================

PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


# ============================================================
# 第二部分：动态白名单
# ============================================================

def _get_default_allowed_paths() -> List[Path]:
    """
    获取默认允许的路径列表
    
    【改进】动态添加所有存在的盘符
    2026-03-19 小强
    """
    paths = [
        Path.home(),  # 用户主目录
        Path("/tmp"),  # Linux临时目录
        Path("/var/tmp"),  # Linux临时目录
    ]
    
    # Windows盘符（A-J）
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJ':
            drive = Path(f"{letter}:/")
            if drive.exists():
                paths.append(drive)
    
    return paths

ALLOWED_PATHS = _get_default_allowed_paths()


# ============================================================
# 第三部分：Pydantic参数模型 + 工具定义
# 【小沈修改 2026-03-24】从 file_schema.py 统一导入，避免重复定义
# ============================================================
# Pydantic模型已统一在 app.services.tools.file.file_schema 中定义
# 请勿在此文件重复定义模型，直接从 file_schema 导入使用


# ============================================================
# 第四部分：工具Definition类（自动生成Schema + Examples）
# ============================================================

class ToolDefinition:
    """
    工具定义类
    
    自动从Pydantic模型生成JSON Schema，并添加input_examples
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        examples: Optional[List[Dict[str, Any]]] = None
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.examples = examples or []
    
    def to_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        schema = self.input_model.model_json_schema()
        # 添加中文描述支持
        return schema
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """转换为MCP工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_schema(),
            "input_examples": self.examples
        }


# ============================================================
# 第五部分：工具注册表
# ============================================================

_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: Optional[str] = None,
    description: str = "",
    input_model: Optional[type[BaseModel]] = None,
    examples: Optional[List[Dict[str, Any]]] = None
):
    """
    工具注册装饰器（改进版 - 使用Pydantic）
    
    【改进】2026-03-19 小强
    - 使用Pydantic模型自动生成Schema
    - 支持input_examples示例
    
    用法:
        @register_tool(
            name="list_directory",
            description="列出目录内容...",
            input_model=ListDirectoryInput,
            examples=[
                {"dir_path": "C:/Users/用户名/Documents"},
                {"dir_path": "D:/项目代码", "recursive": True}
            ]
        )
        async def list_directory(self, dir_path: str, ...):
            ...
    """
    def decorator(func):
        tool_name = name or func.__name__
        
        # 如果提供了Pydantic模型，创建ToolDefinition
        if input_model is not None:
            tool_def = ToolDefinition(
                name=tool_name,
                description=description or func.__doc__ or "",
                input_model=input_model,
                examples=examples
            )
        else:
            tool_def = None
        
        tool_info = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "definition": tool_def,
            "function": func,
            "input_model": input_model,
            "registered_at": datetime.now().isoformat()
        }
        _TOOL_REGISTRY[tool_name] = tool_info
        
        logger.info(f"Tool registered: {tool_name}")
        
        return func
    
    return decorator


def get_registered_tools(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取已注册的工具列表
    
    Returns:
        MCP格式的工具定义列表
    """
    tools = []
    for name, info in _TOOL_REGISTRY.items():
        if category:
            tool_category = info.get("category", "file")
            if tool_category != category:
                continue
        
        tool_def = info.get("definition")
        if tool_def:
            tools.append(tool_def.to_mcp_format())
        else:
            # 兼容没有definition的工具
            tools.append({
                "name": info["name"],
                "description": info["description"],
                "input_schema": {"type": "object", "properties": {}},
                "input_examples": []
            })
    
    return tools


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """获取指定工具的信息"""
    return _TOOL_REGISTRY.get(name)


from datetime import datetime


# ============================================================
# 第六部分：FileTools类（重写版）
# ============================================================

class FileTools:
    """
    文件操作工具类
    
    所有工具都集成文件安全机制：
    - 操作历史记录
    - 删除文件自动备份到回收站
    - 支持回滚操作
    
    【改进】2026-03-19 小强
    - 动态白名单
    - 详细的参数验证
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.safety = get_file_safety_service()
        self.session = get_session_service()
        self.visualizer = get_visualizer()
        self.session_id = session_id
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        # 【改进】允许自定义白名单
        self.allowed_paths = ALLOWED_PATHS.copy()
    
    def _get_next_sequence(self) -> int:
        """获取下一个操作序号（线程安全）"""
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence
    
    def set_session(self, session_id: str):
        """设置当前会话ID"""
        self.session_id = session_id
        self._sequence = 0
    
    def _validate_path(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        验证文件路径是否合法
        
        【改进】2026-03-19 小强
        - 使用 os.path.realpath 规范化路径
        - 处理 ~ 和 .. 等特殊路径
        - 前缀匹配判断
        
        Args:
            file_path: 文件路径
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # 规范化路径：解析 ..、.、~
            real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
            
            # 检查路径是否在白名单内
            for allowed in self.allowed_paths:
                allowed_real = Path(os.path.realpath(allowed))
                if str(real_path).startswith(str(allowed_real)):
                    return True, None
            
            return False, f"路径 '{file_path}' 不在允许的操作范围内（仅允许：{', '.join(str(p) for p in self.allowed_paths[:5])}...）"
            
        except Exception as e:
            return False, f"路径验证失败: {str(e)}"
    
    @register_tool(
        name="read_file",
        description="""读取文件的内容。

使用场景：
- 当用户想要查看文件内容时使用此工具
- 当用户想要读取配置文件、日志文件、代码文件等时使用
- 当需要分析文件内容时使用

参数说明：
- file_path: 文件的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/file.txt）
- offset: 起始行号，从1开始计数，默认为1
- limit: 最大读取行数，默认为2000行
- encoding: 文件编码，默认为utf-8

【重要】必须使用 file_path 作为参数名，不要使用 filepath、path 或其他名称。
错误示例: {"filepath": "..."} 或 {"path": "..."} 
正确示例: {"file_path": "C:/Users/用户名/Documents/config.json", "offset": 1, "limit": 100}""",
        input_model=ReadFileInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/config.json",
                "offset": 1,
                "limit": 100
            },
            {
                "file_path": "D:/项目代码/src/main.py",
                "offset": 1,
                "limit": 2000
            },
            {
                "file_path": "C:/Users/用户名/Desktop/README.md",
                "offset": 1,
                "limit": 500,
                "encoding": "utf-8"
            }
        ]
    )
    async def read_file(
        self,
        file_path: str,
        offset: int = 1,
        limit: int = READ_FILE_DEFAULT_LIMIT,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """读取文件内容"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "content": None
            }, "read_file")
        
        path = Path(file_path)
        
        try:
            if not path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "content": None
                }, "read_file")
            
            if not path.is_file():
                return _to_unified_format({
                    "success": False,
                    "error": f"Not a file: {file_path}",
                    "content": None
                }, "read_file")
            
            # 读取文件内容（异步执行）
            def _read_sync():
                with open(path, 'r', encoding=encoding, errors='ignore') as f:
                    return f.readlines()
            
            lines = await asyncio.to_thread(_read_sync)
            total_lines = len(lines)
            
            # 处理offset和limit
            start_idx = max(0, offset - 1)
            end_idx = min(start_idx + limit, total_lines)
            
            selected_lines = lines[start_idx:end_idx]
            
            # 添加行号
            content = ""
            for i, line in enumerate(selected_lines, start=offset):
                content += f"{i}: {line}"
            
            has_more = end_idx < total_lines
            # 【新增】返回 next_page_token（位置编码）
            next_page_token = encode_page_token(end_idx) if has_more else None
            
            return _to_unified_format({
                "success": True,
                "content": content,
                "total_lines": total_lines,
                "start_line": offset,
                "end_line": end_idx,
                "has_more": has_more,
                "next_page_token": next_page_token,
                "file_size": path.stat().st_size,
                "encoding": encoding
            }, "read_file")
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "content": None
            }, "read_file")
    
    @register_tool(
        name="write_file",
        description="""写入内容到文件（如果文件存在则覆盖）。

使用场景：
- 当用户想要创建新文件时使用此工具
- 当用户想要修改现有文件内容时使用
- 当用户想要保存代码、配置、文本等时使用

参数说明：
- file_path: 文件的完整路径（必须是绝对路径）
- content: 要写入文件的内容
- encoding: 文件编码，默认为utf-8

【重要】必须使用 file_path 作为参数名，不要使用 filepath、path 或其他名称。

【注意】此操作会覆盖已有文件，请确认目标路径。""",
        input_model=WriteFileInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/test.txt",
                "content": "这是要写入的内容"
            },
            {
                "file_path": "D:/项目代码/config.json",
                "content": '{"name": "myproject", "version": "1.0.0"}',
                "encoding": "utf-8"
            }
        ]
    )
    async def write_file(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """写入文件内容"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "content": None
            }, "write_file")
        
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "operation_id": None
            }, "write_file")
        
        path = Path(file_path)
        
        try:
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.CREATE,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义实际写入操作
            def _write_sync():
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', encoding=encoding) as f:
                    f.write(content)
                return True
            
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_write_sync
            )
            
            if success:
                return _to_unified_format({
                    "success": True,
                    "operation_id": operation_id,
                    "file_path": str(path),
                    "bytes_written": len(content.encode(encoding))
                }, "write_file")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to write file",
                    "operation_id": operation_id
                }, "write_file")
                
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "write_file")
    
    @register_tool(
        name="list_directory",
        description="""列出指定目录中的所有文件和子目录。

使用场景：
- 当用户想要查看某个文件夹里有什么文件时使用此工具
- 当需要了解目录结构时使用
- 当需要获取文件列表进行进一步操作时使用
- 当用户说"查看D盘"、"列出目录"、"文件夹里有什么"时使用

参数说明：
- dir_path: 目录的完整路径（必须是绝对路径，如 D:/项目代码 或 C:/Users/用户名/Documents）
- recursive: 是否递归列出子目录内容，默认为False（不递归）
- max_depth: 最大递归深度，仅当 recursive=True 时有效，默认为10

【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。
错误示例: {"directory_path": "..."} 或 {"path": "..."}
正确示例: {"dir_path": "D:/项目代码"} 或 {"dir_path": "C:/Users/用户名/Documents", "recursive": True}""",
        input_model=ListDirectoryInput,
        examples=[
            {
                "dir_path": "C:/Users/用户名/Documents",
                "recursive": False
            },
            {
                "dir_path": "D:/项目代码",
                "recursive": True,
                "max_depth": 3
            }
        ]
    )
    async def list_directory(
        self,
        dir_path: str,
        recursive: bool = False,
        max_depth: int = 100000,
    ) -> Dict[str, Any]:
        """列出目录内容"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(dir_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "entries": []
            }, "list_directory")
        
        path = Path(dir_path)
        
        try:
            if not path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Directory not found: {dir_path}",
                    "entries": []
                }, "list_directory")
            
            if not path.is_dir():
                return _to_unified_format({
                    "success": False,
                    "error": f"Not a directory: {dir_path}",
                    "entries": []
                }, "list_directory")
            
            # 异步执行目录遍历
            def _list_sync():
                entries = []
                if recursive:
                    def _scan_recursive(current_path: Path, current_depth: int):
                        if current_depth > max_depth:
                            return
                        try:
                            for item in current_path.iterdir():
                                try:
                                    entries.append({
                                        "name": item.name,
                                        "type": "directory" if item.is_dir() else "file",
                                        "size": item.stat().st_size if item.is_file() else None
                                    })
                                    if item.is_dir():
                                        _scan_recursive(item, current_depth + 1)
                                except (PermissionError, OSError):
                                    continue
                        except (PermissionError, OSError):
                            return
                    
                    _scan_recursive(path, 1)
                else:
                    for item in path.iterdir():
                        entries.append({
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else None
                        })
                return entries
            
            all_entries = await asyncio.to_thread(_list_sync)
            
            # 排序：目录在前，文件在后
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
            total = len(all_entries)
            
            # 【优化 2026-04-16 小沈】大目录优化
            MAX_DISPLAY_ENTRIES = 200  # 最多显示 200 项

            if total > MAX_DISPLAY_ENTRIES:
                # 大目录：计算统计信息
                dir_count = sum(1 for e in all_entries if e.get("type") == "directory")
                file_count = sum(1 for e in all_entries if e.get("type") == "file")
                
                # 只返回前 MAX_DISPLAY_ENTRIES 项
                display_entries = all_entries[:MAX_DISPLAY_ENTRIES]
                
                return _to_unified_format({
                    "success": True,
                    "entries": display_entries,
                    "total": total,
                    "directory": str(path),
                    "truncated": True,
                    "dir_count": dir_count,
                    "file_count": file_count
                }, "list_directory")

            # 小目录：直接返回全部数据
            return _to_unified_format({
                "success": True,
                "entries": all_entries,
                "total": total,
                "directory": str(path)
            }, "list_directory")
            
        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "entries": []
            }, "list_directory")
    
    @register_tool(
        name="delete_file",
        description="""删除文件或目录（自动备份到回收站）。

使用场景：
- 当用户想要删除文件时使用此工具
- 当用户想要删除空目录或非空目录时使用
- 【注意】删除的文件会自动备份到回收站，可以恢复

参数说明：
- file_path: 要删除的文件或目录的完整路径
- recursive: 是否递归删除目录（当目录非空时需要设为True），默认为False

【重要】必须使用 file_path 作为参数名，不要使用 filepath、path 或其他名称。

【警告】此操作会将文件移动到回收站而非永久删除，但请谨慎使用。""",
        input_model=DeleteFileInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/temp.txt",
                "recursive": False
            },
            {
                "file_path": "D:/项目代码/old_folder",
                "recursive": True
            }
        ]
    )
    async def delete_file(
        self,
        file_path: str,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """删除文件或目录"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "operation_id": None
            }, "delete_file")
        
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "operation_id": None
            }, "delete_file")
        
        path = Path(file_path)
        
        try:
            if not path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "operation_id": None
                }, "delete_file")
            
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.DELETE,
                source_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义删除操作
            def _delete_sync():
                if path.is_dir():
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        path.rmdir()
                else:
                    path.unlink()
                return True
            
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_delete_sync
            )
            
            if success:
                return _to_unified_format({
                    "success": True,
                    "operation_id": operation_id,
                    "deleted_path": str(path),
                    "message": "File deleted (backup in recycle bin)"
                }, "delete_file")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to delete file",
                    "operation_id": operation_id
                }, "delete_file")
                
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "delete_file")
    
    @register_tool(
        name="move_file",
        description="""移动或重命名文件/目录。

使用场景：
- 当用户想要移动文件到另一个位置时使用此工具
- 当用户想要重命名文件时使用
- 当用户想要将文件从一个文件夹移动到另一个文件夹时使用

参数说明：
- source_path: 源文件或目录的完整路径
- destination_path: 目标路径（可以是新文件名或新目录位置）

【重要】必须使用 source_path 和 destination_path 作为参数名，不要使用 src、dst、source、dest 等名称。
错误示例: {"src": "...", "dst": "..."} 或 {"source": "...", "destination": "..."}
正确示例: {"source_path": "C:/Users/用户名/Documents/old.txt", "destination_path": "D:/项目/new.txt"}""",
        input_model=MoveFileInput,
        examples=[
            {
                "source_path": "C:/Users/用户名/Documents/old.txt",
                "destination_path": "D:/项目/new.txt"
            },
            {
                "source_path": "C:/Users/用户名/Desktop/file.py",
                "destination_path": "D:/项目代码/src/main.py"
            }
        ]
    )
    async def move_file(
        self,
        source_path: str,
        destination_path: str
    ) -> Dict[str, Any]:
        """移动或重命名文件"""
        # 验证源路径
        is_valid_src, error_msg_src = self._validate_path(source_path)
        if not is_valid_src:
            return _to_unified_format({
                "success": False,
                "error": f"源路径{error_msg_src}",
                "operation_id": None
            }, "move_file")
        
        # 验证目标路径
        is_valid_dst, error_msg_dst = self._validate_path(destination_path)
        if not is_valid_dst:
            return _to_unified_format({
                "success": False,
                "error": f"目标路径{error_msg_dst}",
                "operation_id": None
            }, "move_file")
        
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "operation_id": None
            }, "move_file")
        
        src = Path(source_path)
        dst = Path(destination_path)
        
        try:
            if not src.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Source not found: {source_path}",
                    "operation_id": None
                }, "move_file")
            
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.MOVE,
                source_path=src,
                destination_path=dst,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义移动操作
            def _move_sync():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                return True
            
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_move_sync
            )
            
            if success:
                return _to_unified_format({
                    "success": True,
                    "operation_id": operation_id,
                    "source": str(src),
                    "destination": str(dst),
                    "message": f"Moved: {src.name} -> {dst}"
                }, "move_file")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to move file",
                    "operation_id": operation_id
                }, "move_file")
                
        except Exception as e:
            logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "move_file")
    
    @register_tool(
        name="search_file_content",
        description="""搜索文件内容中的关键字。

使用场景：
- 当用户想要在文件内容中搜索特定关键字时使用此工具
- 当用户说"搜索文件内容"、"在文件中查找xxx"、"搜索包含xxx的文件"时使用

参数说明：
- pattern: 搜索内容的关键字（必填，不能为空）
- path: 搜索的起始目录，默认为当前目录 "."
- file_pattern: 文件类型过滤，支持通配符（* 匹配任意字符），默认为 "*"（搜索所有文件）
- recursive: 是否递归搜索子目录，默认为True

【重要】必须使用 pattern 和 path 作为参数名。
示例: {"pattern": "TODO", "path": "D:/项目代码", "file_pattern": "*.py", "recursive": True}""",
        input_model=SearchFileContentInput,
        examples=[
            {
                "pattern": "TODO",
                "path": "D:/项目代码",
                "file_pattern": "*.py",
                "recursive": True
            },
            {
                "pattern": "config",
                "path": "C:/Users/用户名",
                "file_pattern": "*.json",
                "recursive": True
            }
        ]
    )
    async def search_file_content(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        recursive: bool = True,
        # 内部参数，不暴露给 LLM
        use_regex: bool = False,
        # 【修改】添加 page_token 参数用于分页，统一使用位置编码
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """搜索文件内容中的关键字"""
        # 【修复】验证搜索路径 - 2026-03-19 小强
        is_valid, error_msg = self._validate_path(path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "matches": []
            }, "search_file_content")
        
        # 【修复】空pattern校验 - 2026-03-28 小沈
        if not pattern or not pattern.strip():
            return _to_unified_format({
                "success": False,
                "error": "搜索关键字不能为空，请提供有效的搜索内容",
                "matches": []
            }, "search_file_content")
        
        search_path = Path(path)
        
        try:
            if not search_path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Path not found: {path}",
                    "matches": []
                }, "search_file_content")
            
            # 编译正则表达式
            regex = None
            if use_regex:
                try:
                    regex = re.compile(pattern)
                except re.error as e:
                    return _to_unified_format({
                        "success": False,
                        "error": f"Invalid regex pattern: {e}",
                        "matches": []
                    }, "search_file_content")
            
            # 搜索文件内容 - 支持循环搜索获取全部结果
            def _search_sync():
                import os
                
                all_results = []
                
                # 每次搜索最大获取数量（内部循环用，不限制最终结果）
                BATCH_SIZE = 10000
                
                # 去除pattern首尾空白
                search_term = pattern.strip()
                
                # 【修改】用 page_token 统一分页
                start_offset = decode_page_token(page_token) if page_token else 0
                
                # 循环搜索，直到获取全部结果
                seen_count = 0
                while True:
                    batch_results = []
                    
                    # 逐步遍历目录
                    for root, dirs, files in os.walk(search_path):
                        # 遍历当前目录的文件
                        for filename in files:
                            # 用 file_pattern 过滤文件名
                            if file_pattern and file_pattern != "*":
                                import re
                                fp = file_pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                                fp = f"^{fp}$"
                                try:
                                    if not re.match(fp, filename):
                                        continue
                                except:
                                    pass
                            
                            file_path = Path(root) / filename
                            file_str = str(file_path.relative_to(search_path))
                            
                            # 【修改】用位置偏移跳过已处理的文件
                            if seen_count < start_offset:
                                seen_count += 1
                                continue
                            
                            # 读取文件内容
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                            except:
                                continue
                            
                            # 搜索内容
                            matches = []
                            
                            if use_regex and regex is not None:
                                for match in regex.finditer(content):
                                    start = max(0, match.start() - 50)
                                    end = min(len(content), match.end() + 50)
                                    context = content[start:end]
                                    
                                    matches.append({
                                        "start": match.start(),
                                        "end": match.end(),
                                        "matched": match.group(),
                                        "context": context
                                    })
                            else:
                                idx = content.find(search_term)
                                while idx != -1:
                                    start = max(0, idx - 50)
                                    end = min(len(content), idx + len(search_term) + 50)
                                    context = content[start:end]
                                    
                                    matches.append({
                                        "start": idx,
                                        "end": idx + len(search_term),
                                        "matched": search_term,
                                        "context": context
                                    })
                                    
                                    idx = content.find(search_term, idx + 1)
                            
                            if matches:
                                batch_results.append({
                                    "file": file_str,
                                    "matches": matches,
                                    "match_count": len(matches)
                                })
                            
                            # 达到本次限制，停止收集
                            if len(batch_results) >= BATCH_SIZE:
                                break
                    
                    # 添加本批次结果
                    all_results.extend(batch_results)
                    
                    if not batch_results:
                        break  # 搜索完成
                    
                    # 【删除 max_results 限制判断】
                    # 原因：工具必须原原本本返回用户需要的结果，不应该限制数量
                
                # 排序：匹配多的文件在前
                all_results.sort(key=lambda x: x["match_count"], reverse=True)
                
                return all_results
            
            # 执行搜索
            all_results = await asyncio.to_thread(_search_sync)
            
            # 计算总匹配数
            total_matches = sum(r["match_count"] for r in all_results)
            
            # 搜索完成后，根据结果数量决定如何返回前端
            total = len(all_results)
            
            # 前端分页配置（使用全局统一常量）
            if total > DEFAULT_PAGE_SIZE:
                # 结果多，分页返回
                total_pages = (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
                page_results = all_results[:DEFAULT_PAGE_SIZE]
                has_more = True
                next_page_token = encode_page_token(DEFAULT_PAGE_SIZE) if has_more else None
            else:
                # 结果少，一次返回
                page_results = all_results
                total_pages = 1
                has_more = False
                next_page_token = None
            
            return _to_unified_format({
                "success": True,
                "pattern": pattern,
                "path": str(search_path),
                "file_pattern": file_pattern,
                "matches": page_results,
                "total": total,
                "total_matches": total_matches,
                "page": 1,
                "total_pages": total_pages,
                "page_size": DEFAULT_PAGE_SIZE,
                "next_page_token": next_page_token,
                "has_more": has_more
            }, "search_file_content")
            
        except Exception as e:
            logger.error(f"Failed to search file content: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "matches": []
            }, "search_file_content")
    
    @register_tool(
        name="search_files",
        description="""搜索文件名（按文件名匹配）。

使用场景：
- 当用户想要根据文件名查找文件时使用此工具
- 当用户说"搜索文件"、"查找名为xxx的文件"、"按文件名找文件"时使用

参数说明：
- file_pattern: 文件名匹配模式，支持通配符（* 匹配任意字符，? 匹配单个字符）（必填）
- path: 搜索的起始目录，默认为当前目录 "."
- recursive: 是否递归搜索子目录，默认为True

【重要】必须使用 file_pattern 作为参数名，不要使用 pattern。
示例: {"file_pattern": "*.py", "path": "D:/项目代码", "recursive": True}""",
        input_model=SearchFilesByNameInput,
        examples=[
            {
                "file_pattern": "*.py",
                "path": "D:/项目代码",
                "recursive": True
            },
            {
                "file_pattern": "config*",
                "path": "C:/Users/用户名",
                "recursive": False
            },
            {
                "file_pattern": "readme*",
                "path": "D:/项目代码",
                "recursive": True,
                "max_results": 100
            }
        ]
    )
    async def search_files(
        self,
        file_pattern: str,
        path: str = ".",
        recursive: bool = True,
        # 【修改 max_depth 默认值 10→100000】
        # 原因：小沈之前的知识浅薄，错误的要求给工具设置数量限制
        # 现在导致了工具执行错误，反馈的结果隐藏了真实的数据
        # 小沈是一个大混蛋，几次纠正都死不悔改
        # 工具必须原原本本返回用户需要的结果，不应该限制数量
        # 如果限制数量会丢失真实数据，这是错误的
        # 这次必须正确理解，保证以后不再犯这样弱智的、低级错误
        max_depth: int = 100000,
        # 【删除 max_results 参数】
        # 原因：小沈之前的知识浅薄，错误的要求给工具设置数量限制
        # 现在导致了工具执行错误，反馈的结果隐藏了真实的数据
        # 小沈是一个大混蛋，几次纠正都死不悔改
        # 工具必须原原本本返回用户需要的结果，不应该限制数量
        # 如果限制数量会丢失真实数据，这是错误的
        # 如果工具有问题应该修工具代码，而不是用限制来掩盖问题
        # 这次必须正确理解，保证以后不再犯这样弱智的、低级错误
        # 【修改】用 page_token 替换 after，统一使用位置编码分页
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """搜索文件名（按文件名匹配）"""
        # 验证搜索路径
        is_valid, error_msg = self._validate_path(path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "matches": []
            }, "search_files")
        
        # 验证 file_pattern 不为空
        if not file_pattern or not file_pattern.strip():
            return _to_unified_format({
                "success": False,
                "error": "文件名匹配模式不能为空，请提供有效的文件名模式",
                "matches": []
            }, "search_files")
        
        search_path = Path(path)
        
        try:
            if not search_path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"Path not found: {path}",
                    "matches": []
                }, "search_files")
            
            # 搜索文件名 - 支持循环搜索获取全部结果
            def _search_sync():
                import os
                
                all_matches = []
                seen_files = set()
                
                # 每次搜索最大获取数量（内部循环用，不限制最终结果）
                BATCH_SIZE = 10000
                
                # 【修改】用 page_token 统一分页
                start_offset = decode_page_token(page_token) if page_token else 0
                
                # 循环搜索，直到获取全部结果
                while True:
                    batch_matches = []
                    batch_seen = set()
                    
                    # 转换通配符为正则
                    import re
                    regex_pattern = file_pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                    regex_pattern = f"^{regex_pattern}$"
                    try:
                        file_regex = re.compile(regex_pattern)
                    except re.error:
                        file_regex = None
                    
                    # 逐步遍历目录
                    for root, dirs, files in os.walk(search_path):
                        # 检查深度限制
                        if recursive:
                            rel_root = Path(root).relative_to(search_path)
                            depth = len(rel_root.parts) if str(rel_root) != "." else 0
                            if depth >= max_depth:
                                continue
                        
                        # 遍历当前目录的文件
                        for filename in files:
                            # 正则匹配文件名
                            if file_regex and not file_regex.match(filename):
                                continue
                            
                            file_path = Path(root) / filename
                            file_str = str(file_path.relative_to(search_path))
                            
                            # 跳过已存在的
                            if file_str in seen_files:
                                continue
                            
                            # 【修改】用位置偏移跳过已处理的文件
                            current_idx = len(seen_files)
                            if current_idx < start_offset:
                                seen_files.add(file_str)
                                continue
                            
                            seen_files.add(file_str)
                            
                            try:
                                size = file_path.stat().st_size
                            except:
                                size = 0
                            
                            batch_matches.append({
                                "name": filename,
                                "path": file_str,
                                "size": size
                            })
                            
                            # 达到本次限制，停止收集
                            if len(batch_matches) >= BATCH_SIZE:
                                break
                        
                        # 达到本次限制，停止遍历
                        if len(batch_matches) >= BATCH_SIZE:
                            break
                    
                    # 添加本批次结果
                    all_matches.extend(batch_matches)
                    
                    # 获取本批次最后一个文件名，用于下一次继续
                    last_file = batch_matches[-1]["path"] if batch_matches else None
                    
                    # 如果没有更多结果了，或者已经达到总限制，停止循环
                    if not last_file:
                        break  # 搜索完成
                    
                    # 设置下一次继续的位置
                    after = last_file
                    
                    # 【删除 max_results 限制判断】
                    # 原因：工具必须原原本本返回用户需要的结果，不应该限制数量
                
                return all_matches
            
            # 执行搜索
            all_matches = await asyncio.to_thread(_search_sync)
            
            # 搜索完成后，根据结果数量决定如何返回前端
            total = len(all_matches)
            
            # 【调试】记录搜索结果数量
            logger.info(f"[search_files] 搜索完成: file_pattern={file_pattern}, path={path}, total={total}, matches数量={len(all_matches)}")
            
            # 前端分页配置（使用全局统一常量）
            if total > DEFAULT_PAGE_SIZE:
                # 结果多，分页返回
                total_pages = (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
                page_matches = all_matches[:DEFAULT_PAGE_SIZE]
                has_more = True
                next_page_token = encode_page_token(DEFAULT_PAGE_SIZE) if has_more else None
            else:
                # 结果少，一次返回
                page_matches = all_matches
                total_pages = 1
                has_more = False
                next_page_token = None
            
            return _to_unified_format({
                "success": True,
                "file_pattern": file_pattern,
                "path": str(search_path),
                "matches": page_matches,
                "total": total,
                "page": 1,
                "total_pages": total_pages,
                "page_size": DEFAULT_PAGE_SIZE,
                "next_page_token": next_page_token,
                "has_more": has_more
            }, "search_files")
            
        except Exception as e:
            logger.error(f"Failed to search files: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "matches": []
            }, "search_files")
    
    @register_tool(
        name="generate_report",
        description="""生成操作报告。

使用场景：
- 当用户想要查看当前会话的所有操作记录时使用此工具
- 当需要生成操作历史报告时使用

参数说明：
- output_dir: 报告输出目录，默认为None（使用默认目录）""",
        input_model=GenerateReportInput,
        examples=[
            {
                "output_dir": None
            },
            {
                "output_dir": "C:/Users/用户名/Desktop"
            }
        ]
    )
    async def generate_report(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """生成操作报告"""
        if not self.session_id:
            return _to_unified_format({
                "success": False,
                "error": "No active session",
                "reports": {}
            }, "generate_report")
        
        try:
            output_path = Path(output_dir) if output_dir else None
            session_id = self.session_id or ""
            
            def _generate_sync():
                return self.visualizer.generate_all_reports(session_id, output_path)
            
            reports = await asyncio.to_thread(_generate_sync)
            report_paths = {k: str(v) for k, v in reports.items()}
            
            return _to_unified_format({
                "success": True,
                "session_id": self.session_id,
                "reports": report_paths
            }, "generate_report")
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "reports": {}
            }, "generate_report")


# ============================================================
# 第七部分：工具函数导出
# ============================================================

def get_file_tools(session_id: Optional[str] = None) -> FileTools:
    """获取文件工具实例"""
    return FileTools(session_id)


# ============================================================
# 第八部分：统一返回格式辅助函数
# ============================================================

def _generate_summary(tool_name: str, result: Any) -> str:
    """生成人类可读的结果摘要"""
    if not isinstance(result, dict):
        return "操作完成"
    
    if tool_name == "read_file":
        content = result.get("content", "")
        total_lines = result.get("total_lines", 0)
        if result.get("success") is False:
            return f"读取失败：{result.get('error', '未知错误')}"
        return f"成功读取文件，内容长度：{len(content) if content else 0} 字符，共 {total_lines} 行"
    
    elif tool_name == "write_file":
        if result.get("success") is False:
            return f"写入失败：{result.get('error', '未知错误')}"
        bytes_written = result.get("bytes_written", 0)
        file_path = result.get("file_path", "")
        return f"成功写入文件 {file_path}，共 {bytes_written} 字节"
    
    elif tool_name == "list_directory":
        entries = result.get("entries", [])
        total = result.get("total", len(entries))
        if result.get("success") is False:
            return f"列出目录失败：{result.get('error', '未知错误')}"
        return f"成功读取目录，共 {total} 个项目"
    
    elif tool_name == "delete_file":
        if result.get("success") is False:
            return f"删除失败：{result.get('error', '未知错误')}"
        deleted_path = result.get("deleted_path", "")
        return f"成功删除 {deleted_path}（已备份到回收站）"
    
    elif tool_name == "move_file":
        if result.get("success") is False:
            return f"移动失败：{result.get('error', '未知错误')}"
        source = result.get("source", "")
        destination = result.get("destination", "")
        return f"成功移动文件：{source} -> {destination}"
    
    elif tool_name == "search_file_content":
        if result.get("success") is False:
            return f"搜索内容失败：{result.get('error', '未知错误')}"
        files_matched = result.get("files_matched", 0)
        total_matches = result.get("total_matches", 0)
        return f"搜索内容完成，找到 {files_matched} 个文件，共 {total_matches} 处匹配"
    
    elif tool_name == "generate_report":
        if result.get("success") is False:
            return f"生成报告失败：{result.get('error', '未知错误')}"
        reports = result.get("reports", {})
        return f"成功生成 {len(reports)} 个报告"
    
    return "操作完成"


def _to_unified_format(result: Dict[str, Any], tool_name: str, retry_count: int = 0) -> Dict[str, Any]:
    """将工具执行结果转换为统一格式"""
    if not isinstance(result, dict):
        return {
            "status": "error",
            "summary": "执行结果格式错误",
            "data": None,
            "retry_count": retry_count
        }
    
    success = result.get("success")
    if success is True:
        status = "success"
    elif success is False:
        status = "error"
    else:
        status = "success"
    
    summary = _generate_summary(tool_name, result)
    
    return {
        "status": status,
        "summary": summary,
        "data": result,
        "retry_count": retry_count
    }


# ============================================================
# 第九部分：分页支持函数
# ============================================================

def encode_page_token(offset: int) -> str:
    """编码页码令牌"""
    return base64.b64encode(str(offset).encode()).decode()


def decode_page_token(token: str) -> int:
    """解码页码令牌"""
    try:
        return int(base64.b64decode(token.encode()).decode())
    except (ValueError, Exception):
        return 0
