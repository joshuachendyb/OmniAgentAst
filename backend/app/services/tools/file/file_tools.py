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
    CopyFileInput,
    CreateDirectoryInput,
    GetFileInfoInput,
    CompareFilesInput,
    BatchRenameInput,
    CompressFilesInput,
    FileMonitorInput,
    FileStatisticsInput,
    FileChecksumInput,
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
                # 【修复P13】防止前缀绕过：必须验证是真正的子路径
                # 例如：C:/Users 允许 C:/Users/subdir，但不允许 C:/Usersbackdoor
                try:
                    real_parts = Path(real_path).parts
                    allowed_parts = Path(allowed_real).parts
                    
                    # 检查是否完全匹配开头
                    if len(real_parts) >= len(allowed_parts):
                        prefix_match = all(real_parts[i] == allowed_parts[i] for i in range(len(allowed_parts)))
                        if not prefix_match:
                            continue
                        
                        # 【关键修复】对于驱动器根路径(如C:\ = 1 part = ('C:\',))
                        # 必须完全相等，不允许 C:\Usersbackdoor 绕过 C:\
                        # 对于普通目录(如C:/Users = 2+ parts)，允许子目录
                        if len(allowed_parts) == 1 and (allowed_parts[0].endswith(':') or allowed_parts[0].endswith(':\\') or allowed_parts[0].endswith(':/')):
                            # 驱动器根路径：必须完全相等
                            if str(real_path) == str(allowed_real) or real_path.parts[0] == allowed_parts[0]:
                                return True, None
                        else:
                            # 普通目录：允许子目录
                            if len(real_parts) > len(allowed_parts):
                                return True, None
                except (ValueError, OSError):
                    pass
            
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
                with open(path, 'r', encoding=encoding, errors='replace') as f:
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
                import tempfile
                import os
                
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # 【修复P12】先写入临时文件，然后原子重命名
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding=encoding,
                    dir=path.parent,
                    delete=False,
                    prefix=f".{path.name}.",
                    suffix=""
                ) as f:
                    f.write(content)
                    temp_path = f.name
                
                try:
                    os.replace(temp_path, str(path))
                    return True
                except Exception:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                    raise
            
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
- page_token: 分页令牌（base64编码的位置偏移量），用于获取后续页面结果，默认为None（从第一页开始）

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
            },
            {
                "dir_path": "E:/工作文档",
                "recursive": False,
                "page_token": "MA=="  # 示例：base64编码的"0"，从第0条开始
            },
            {
                "dir_path": "E:/工作文档",
                "recursive": False,
                "page_token": "NTA="  # 示例：base64编码的"10"，从第10条开始
            }
        ]
    )
    async def list_directory(
        self,
        dir_path: str,
        recursive: bool = False,
        max_depth: int = 10,
        page_token: Optional[str] = None,
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
        
        # 解码page_token
        start_offset = 0
        if page_token:
            try:
                start_offset = decode_page_token(page_token)
            except Exception as e:
                return _to_unified_format({
                    "success": False,
                    "error": f"Invalid page token: {e}",
                    "entries": []
                }, "list_directory")
        
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
                                    # 【修复 2026-04-16】保留 path 字段，因为：
                                    # 1. 前端 ListDirectoryView 需要 path 构建树形结构
                                    # 2. 只在 base_react.py 生成 observation_text 时去掉 path
                                    entries.append({
                                        "name": item.name,
                                        "path": str(item.absolute()),
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
                    # 【修复 2026-04-16】保留 path 字段
                    for item in path.iterdir():
                        entries.append({
                            "name": item.name,
                            "path": str(item.absolute()),
                            "type": "directory" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else None
                        })
                return entries
            
            all_entries = await asyncio.to_thread(_list_sync)
            
            # 排序：目录在前，文件在后
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
            total = len(all_entries)
            
            # 【优化 2026-04-16 小沈】大目录优化
            # 背景：E盘根目录有 492,335 个文件，entries JSON 大小达 90.58MB
            # 问题：导致 API 请求体过大，触发 429 错误
            # 解决：截断大目录，只返回前 200 项 + 统计摘要
            MAX_DISPLAY_ENTRIES = 200  # 最多显示 200 项

            if total > MAX_DISPLAY_ENTRIES:
                # 大目录处理：计算目录/文件统计，返回截断后的数据
                dir_count = sum(1 for e in all_entries if e.get("type") == "directory")
                file_count = sum(1 for e in all_entries if e.get("type") == "file")
                
                # 只返回前 MAX_DISPLAY_ENTRIES 项（排序后目录在前、文件在后）
                display_entries = all_entries[start_offset:start_offset + MAX_DISPLAY_ENTRIES]
                
                # 记录截断日志，方便运维监控大目录场景
                logger.warning(
                    f"[list_directory] Large directory truncated: path={path}, "
                    f"total={total}, dir_count={dir_count}, file_count={file_count}, "
                    f"displayed={MAX_DISPLAY_ENTRIES}"
                )
                
                return _to_unified_format({
                    "success": True,
                    "entries": display_entries,
                    "total": total,
                    "directory": str(path),
                    "truncated": True,  # 标记为截断状态
                    "dir_count": dir_count,  # 目录总数
                    "file_count": file_count,  # 文件总数
                    "next_page_token": encode_page_token(start_offset + MAX_DISPLAY_ENTRIES) if start_offset + MAX_DISPLAY_ENTRIES < total else None  # 分页标记
                }, "list_directory")

            # 小目录（<=200项）：直接返回全部数据
            return _to_unified_format({
                "success": True,
                "entries": all_entries,
                "total": total,
                "directory": str(path),
                "next_page_token": None  # 没有更多数据
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
                # 【修复P9】检查目标文件是否已存在
                if dst.exists():
                    raise FileExistsError(f"目标路径已存在: {dst}，移动操作已取消。请先删除目标文件或指定其他路径。")
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
        path: str = "~",
        file_pattern: str = "*",
        recursive: bool = True,
        # 内部参数，不暴露给 LLM
        use_regex: bool = False,
        # 分页标记，用于继续之前的搜索
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
            
            # 搜索文件内容 - 单次遍历（P3修复：去掉while True循环）
            def _search_sync():
                import os
                import fnmatch
                
                all_results = []
                search_term = pattern.strip()
                start_offset = decode_page_token(page_token) if page_token else 0
                seen_count = 0
                
                # 单次遍历，不需要while循环
                for root, dirs, files in os.walk(search_path):
                    # 【修复P6】尊重recursive参数
                    if not recursive:
                        dirs.clear()  # 不递归：清空子目录列表，os.walk不会进入子目录
                    
                    # 遍历当前目录的文件
                    for filename in files:
                        # 【修复P10】用fnmatch替代手工正则
                        if file_pattern and file_pattern != "*":
                            if not fnmatch.fnmatch(filename, file_pattern):
                                continue
                        
                        file_path = Path(root) / filename
                        file_str = str(file_path.relative_to(search_path))
                        
                        # 【修改】用位置偏移跳过已处理的文件
                        if seen_count < start_offset:
                            seen_count += 1
                            continue
                        seen_count += 1
                        
                        # 【修复P11】errors='ignore' → errors='replace'
                        # 【修复P16】指定具体异常
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                        except (PermissionError, OSError):
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
                                all_results.append({
                                    "file": file_str,
                                    "matches": matches,
                                    "match_count": len(matches)
                                })
                
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
                "recursive": True
            }
        ]
    )
    async def search_files(
        self,
        file_pattern: str,
        path: str = "~",
        recursive: bool = True,
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
                start_offset = decode_page_token(page_token) if page_token else 0
                seen_count = 0
                
                # 单次遍历（P4修复：去掉while True循环）
                import fnmatch
                
                # 逐步遍历目录
                for root, dirs, files in os.walk(search_path):
                    # 【修复P15】尊重recursive参数
                    if not recursive:
                        dirs.clear()  # 不递归：清空子目录列表
                    else:
                        # 深度限制
                        rel_root = Path(root).relative_to(search_path)
                        depth = len(rel_root.parts) if str(rel_root) != "." else 0
                        if depth >= max_depth:
                            dirs.clear()  # 不再深入此目录的子目录
                            continue
                    
                    # 遍历当前目录的文件
                    for filename in files:
                        # 【修复P10】用fnmatch替代手工正则
                        if not fnmatch.fnmatch(filename, file_pattern):
                            continue
                        
                        file_path = Path(root) / filename
                        file_str = str(file_path.relative_to(search_path))
                        
                        # 跳过已存在的
                        if file_str in seen_files:
                            continue
                        
                        seen_count += 1
                        
                        # 位置偏移跳过
                        if seen_count <= start_offset:
                            seen_files.add(file_str)
                            continue
                        seen_files.add(file_str)
                        
                        # 【修复P16】指定具体异常
                        try:
                            size = file_path.stat().st_size
                        except (PermissionError, OSError):
                            size = 0
                        
                        all_matches.append({
                            "name": filename,
                            "path": file_str,
                            "size": size
                        })
                
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
        # 【修复P5】验证输出目录路径
        if output_dir:
            is_valid, error_msg = self._validate_path(output_dir)
            if not is_valid:
                return _to_unified_format({
                    "success": False,
                    "error": error_msg,
                    "reports": {}
                }, "generate_report")
        
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

    @register_tool(
        name="copy_file",
        description="""复制文件或目录到新位置。

使用场景：
- 当用户想要复制文件时使用此工具
- 当用户想要备份文件时使用
- 当用户说"复制文件"、"拷贝文件"、"备份文件"时使用

参数说明：
- source_path: 源文件或目录的完整路径（必须是绝对路径）
- destination_path: 目标路径（可以是新文件名或新目录位置）
- recursive: 是否递归复制目录，仅当源路径是目录时有效，默认为False
- overwrite: 是否覆盖已存在的目标文件，默认为False

【重要】必须使用 source_path 和 destination_path 作为参数名。
正确示例: {"source_path": "C:/Users/file.txt", "destination_path": "D:/backup/file.txt"}""",
        input_model=CopyFileInput,
        examples=[
            {
                "source_path": "C:/Users/用户名/Documents/file.txt",
                "destination_path": "D:/backup/file.txt"
            },
            {
                "source_path": "C:/Users/用户名/Documents/folder",
                "destination_path": "D:/backup/folder",
                "recursive": True
            }
        ]
    )
    async def copy_file(
        self,
        source_path: str,
        destination_path: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """复制文件或目录"""
        # 导入copy_file实现
        from app.services.tools.file.copy_file import copy_file_impl
        
        return await copy_file_impl(
            source_path=source_path,
            destination_path=destination_path,
            recursive=recursive,
            overwrite=overwrite,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="create_directory",
        description="""创建新目录。

使用场景：
- 当用户想要创建新文件夹时使用此工具
- 当用户说"创建目录"、"新建文件夹"、"mkdir"时使用

参数说明：
- dir_path: 要创建的目录的完整路径（必须是绝对路径）
- parents: 是否创建父目录，默认为True（如果父目录不存在则创建）
- exist_ok: 如果目录已存在是否报错，默认为True（不报错）

【重要】必须使用 dir_path 作为参数名。
正确示例: {"dir_path": "C:/Users/用户名/Documents/new_folder"}""",
        input_model=CreateDirectoryInput,
        examples=[
            {
                "dir_path": "C:/Users/用户名/Documents/new_folder"
            },
            {
                "dir_path": "D:/项目代码/src/components",
                "parents": True
            }
        ]
    )
    async def create_directory(
        self,
        dir_path: str,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> Dict[str, Any]:
        """创建目录"""
        from app.services.tools.file.create_directory import create_directory_impl
        
        return await create_directory_impl(
            dir_path=dir_path,
            parents=parents,
            exist_ok=exist_ok,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="get_file_info",
        description="""获取文件或目录的详细信息。

使用场景：
- 当用户想要查看文件属性时使用此工具
- 当用户说"文件信息"、"查看属性"、"文件详情"时使用

参数说明：
- file_path: 文件或目录的完整路径（必须是绝对路径）

【重要】必须使用 file_path 作为参数名。
正确示例: {"file_path": "C:/Users/用户名/Documents/file.txt"}""",
        input_model=GetFileInfoInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/file.txt"
            }
        ]
    )
    async def get_file_info(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """获取文件信息"""
        from app.services.tools.file.get_file_info import get_file_info_impl
        
        return await get_file_info_impl(
            file_path=file_path,
            validate_path_func=self._validate_path,
            to_unified_format_func=_to_unified_format,
        )

    @register_tool(
        name="compare_files",
        description="""比较两个文件的内容、大小或修改时间。

使用场景：
- 当用户需要比较两个文件是否相同时使用此工具
- 当用户需要验证文件完整性或检测文件变化时使用
- 当需要确认文件备份或同步是否成功时使用

参数说明：
- file_path1: 第一个文件的完整路径（必须是绝对路径）
- file_path2: 第二个文件的完整路径（必须是绝对路径）
- algorithm: 比较算法：content（内容比较）、size（大小比较）、mtime（修改时间比较），默认为content
- chunk_size: 分块大小（字节），用于大文件比较，默认8192字节

【重要】必须使用正确的参数名。
正确示例: {"file_path1": "C:/file1.txt", "file_path2": "C:/file2.txt", "algorithm": "content"}""",
        input_model=CompareFilesInput,
        examples=[
            {
                "file_path1": "C:/Users/用户名/Documents/file1.txt",
                "file_path2": "C:/Users/用户名/Documents/file2.txt",
                "algorithm": "content"
            },
            {
                "file_path1": "D:/项目代码/version1.py",
                "file_path2": "D:/项目代码/version2.py",
                "algorithm": "size"
            },
            {
                "file_path1": "E:/备份/data.db",
                "file_path2": "E:/恢复/data.db",
                "algorithm": "mtime",
                "chunk_size": 16384
            }
        ]
    )
    async def compare_files(
        self,
        file_path1: str,
        file_path2: str,
        algorithm: str = "content",
        chunk_size: int = 8192,
    ) -> Dict[str, Any]:
        """比较两个文件"""
        from app.services.tools.file.compare_files import compare_files_impl
        
        return await compare_files_impl(
            file_path1=file_path1,
            file_path2=file_path2,
            algorithm=algorithm,
            chunk_size=chunk_size,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="batch_rename",
        description="""批量重命名目录中的文件。

使用场景：
- 当用户需要批量修改文件名时使用此工具
- 当需要按照特定模式重命名文件时使用
- 当需要整理文件命名规范时使用

参数说明：
- directory: 目标目录的完整路径（必须是绝对路径）
- pattern: 匹配模式（支持正则表达式）
- replacement: 替换字符串
- recursive: 是否递归处理子目录，默认为False
- preview: 是否只预览不执行，默认为False
- conflict_strategy: 冲突处理策略：skip（跳过）、overwrite（覆盖）、rename（自动重命名），默认为skip

【重要】必须使用正确的参数名。
正确示例: {"directory": "C:/Users/用户名/Photos", "pattern": "IMG_\\d+\\.jpg", "replacement": "photo_$1.jpg", "preview": true}""",
        input_model=BatchRenameInput,
        examples=[
            {
                "directory": "C:/Users/用户名/Photos",
                "pattern": "IMG_\\d+\\.jpg",
                "replacement": "photo_$1.jpg",
                "preview": True
            },
            {
                "directory": "D:/项目代码/docs",
                "pattern": "(.+)\\.txt",
                "replacement": "$1.md",
                "recursive": True,
                "conflict_strategy": "rename"
            },
            {
                "directory": "E:/音乐",
                "pattern": "track_",
                "replacement": "song_",
                "conflict_strategy": "overwrite"
            }
        ]
    )
    async def batch_rename(
        self,
        directory: str,
        pattern: str,
        replacement: str,
        recursive: bool = False,
        preview: bool = False,
        conflict_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """批量重命名文件"""
        from app.services.tools.file.batch_rename import batch_rename_impl
        
        return await batch_rename_impl(
            directory=directory,
            pattern=pattern,
            replacement=replacement,
            recursive=recursive,
            preview=preview,
            conflict_strategy=conflict_strategy,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="compress_files",
        description="""压缩文件或目录。

使用场景：
- 当用户需要压缩文件以节省存储空间时使用此工具
- 当需要打包多个文件以便传输时使用
- 当需要创建备份压缩包时使用

参数说明：
- source_path: 源文件或目录的完整路径（必须是绝对路径）
- destination_path: 目标压缩文件路径（必须是绝对路径）
- format: 压缩格式：zip、tar.gz，默认为zip
- compression_level: 压缩级别（0-9，0不压缩，9最高压缩），默认为6
- password: 压缩密码（可选），用于加密压缩文件
- split_size: 分卷大小（字节），None表示不分卷

【重要】必须使用正确的参数名。
正确示例: {"source_path": "C:/Users/用户名/Documents", "destination_path": "C:/备份/docs.zip", "format": "zip", "compression_level": 9}""",
        input_model=CompressFilesInput,
        examples=[
            {
                "source_path": "C:/Users/用户名/Documents",
                "destination_path": "C:/备份/docs.zip",
                "format": "zip",
                "compression_level": 9
            },
            {
                "source_path": "D:/项目代码",
                "destination_path": "D:/备份/project.tar.gz",
                "format": "tar.gz",
                "compression_level": 6
            },
            {
                "source_path": "E:/敏感数据",
                "destination_path": "E:/加密备份/secure.zip",
                "format": "zip",
                "password": "mypassword123",
                "split_size": 104857600  # 100MB分卷
            }
        ]
    )
    async def compress_files(
        self,
        source_path: str,
        destination_path: str,
        format: str = "zip",
        compression_level: int = 6,
        password: Optional[str] = None,
        split_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """压缩文件或目录"""
        from app.services.tools.file.compress_files import compress_files_impl
        
        return await compress_files_impl(
            source_path=source_path,
            destination_path=destination_path,
            format=format,
            compression_level=compression_level,
            password=password,
            split_size=split_size,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="file_monitor",
        description="""监控文件系统变化。

使用场景：
- 当用户需要实时监控文件变化时使用此工具
- 当需要检测文件创建、修改、删除事件时使用
- 当需要监控目录变化并触发相应操作时使用

参数说明：
- directory: 监控目录的完整路径（必须是绝对路径）
- event_types: 监控事件类型列表，默认为["created", "modified", "deleted", "renamed"]
- recursive: 是否递归监控子目录，默认为True
- filters: 过滤条件字典，支持file_type、min_size、max_size、modified_after等字段
- duration: 监控持续时间（秒），None表示持续监控直到手动停止

【重要】必须使用正确的参数名。
正确示例: {"directory": "C:/Users/用户名/Downloads", "event_types": ["created", "modified"], "duration": 60}""",
        input_model=FileMonitorInput,
        examples=[
            {
                "directory": "C:/Users/用户名/Downloads",
                "event_types": ["created", "modified"],
                "duration": 60
            },
            {
                "directory": "D:/项目代码/logs",
                "recursive": False,
                "filters": {"file_type": ".log"}
            },
            {
                "directory": "E:/监控目录",
                "event_types": ["created", "deleted", "renamed"],
                "filters": {"min_size": 1024, "max_size": 1048576}
            }
        ]
    )
    async def file_monitor(
        self,
        directory: str,
        event_types: List[str] = None,
        recursive: bool = True,
        filters: Optional[Dict[str, Any]] = None,
        duration: Optional[int] = None,
    ) -> Dict[str, Any]:
        """监控文件系统变化"""
        from app.services.tools.file.file_monitor import file_monitor_impl
        
        if event_types is None:
            event_types = ["created", "modified", "deleted", "renamed"]
        
        return await file_monitor_impl(
            directory=directory,
            event_types=event_types,
            recursive=recursive,
            filters=filters,
            duration=duration,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="file_statistics",
        description="""统计文件系统信息。

使用场景：
- 当用户需要分析目录结构时使用此工具
- 当需要统计文件数量、大小分布时使用
- 当需要分析文件类型分布时使用

参数说明：
- directory: 统计目录的完整路径（必须是绝对路径）
- recursive: 是否递归统计子目录，默认为True
- max_depth: 最大递归深度，默认为100000
- filters: 过滤条件字典，支持file_type、min_size、max_size等字段
- output_format: 输出格式：json、csv、text，默认为json

【重要】必须使用正确的参数名。
正确示例: {"directory": "C:/Users/用户名/Documents", "recursive": true, "output_format": "json"}""",
        input_model=FileStatisticsInput,
        examples=[
            {
                "directory": "C:/Users/用户名/Documents",
                "recursive": True,
                "output_format": "json"
            },
            {
                "directory": "D:/项目代码",
                "filters": {"file_type": ".py"},
                "output_format": "csv"
            },
            {
                "directory": "E:/数据存储",
                "recursive": True,
                "max_depth": 3,
                "filters": {"min_size": 1024, "max_size": 10485760}
            }
        ]
    )
    async def file_statistics(
        self,
        directory: str,
        recursive: bool = True,
        max_depth: int = 100000,
        filters: Optional[Dict[str, Any]] = None,
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """统计文件系统信息"""
        from app.services.tools.file.file_statistics import file_statistics_impl
        
        return await file_statistics_impl(
            directory=directory,
            recursive=recursive,
            max_depth=max_depth,
            filters=filters,
            output_format=output_format,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    @register_tool(
        name="file_checksum",
        description="""计算文件的校验和（哈希值）。

使用场景：
- 当用户需要验证文件完整性时使用此工具
- 当需要检测文件是否被修改时使用
- 当需要生成文件的唯一标识符时使用

参数说明：
- file_path: 文件的完整路径（必须是绝对路径）
- algorithm: 哈希算法：md5、sha1、sha256、sha512，默认为md5
- verify_hash: 验证哈希值（如果提供则进行验证）
- chunk_size: 分块大小（字节），用于大文件哈希计算，默认65536字节

【重要】必须使用正确的参数名。
正确示例: {"file_path": "C:/Users/用户名/Documents/file.iso", "algorithm": "sha256"}""",
        input_model=FileChecksumInput,
        examples=[
            {
                "file_path": "C:/Users/用户名/Documents/file.iso",
                "algorithm": "sha256"
            },
            {
                "file_path": "D:/下载/软件安装包.exe",
                "algorithm": "md5",
                "verify_hash": "d41d8cd98f00b204e9800998ecf8427e"
            },
            {
                "file_path": "E:/备份/data.db",
                "algorithm": "sha512",
                "chunk_size": 131072
            }
        ]
    )
    async def file_checksum(
        self,
        file_path: str,
        algorithm: str = "md5",
        verify_hash: Optional[str] = None,
        chunk_size: int = 65536,
    ) -> Dict[str, Any]:
        """计算文件校验和"""
        from app.services.tools.file.file_checksum import file_checksum_impl
        
        return await file_checksum_impl(
            file_path=file_path,
            algorithm=algorithm,
            verify_hash=verify_hash,
            chunk_size=chunk_size,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            session_id=self.session_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )


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
    
    elif tool_name == "copy_file":
        if result.get("success") is False:
            return f"复制失败：{result.get('error', '未知错误')}"
        source = result.get("source", "")
        destination = result.get("destination", "")
        return f"成功复制文件：{source} -> {destination}"
    
    elif tool_name == "create_directory":
        if result.get("success") is False:
            return f"创建目录失败：{result.get('error', '未知错误')}"
        dir_path = result.get("dir_path", "")
        return f"成功创建目录：{dir_path}"
    
    elif tool_name == "get_file_info":
        if result.get("success") is False:
            return f"获取文件信息失败：{result.get('error', '未知错误')}"
        file_path = result.get("file_path", "")
        return f"成功获取文件信息：{file_path}"
    
    elif tool_name == "compare_files":
        if result.get("success") is False:
            return f"文件比较失败：{result.get('error', '未知错误')}"
        identical = result.get("identical", False)
        size_match = result.get("size_match", False)
        if identical:
            return "文件内容完全相同"
        elif size_match:
            return "文件大小相同但内容不同"
        else:
            return "文件大小不同"
    
    elif tool_name == "batch_rename":
        if result.get("success") is False:
            return f"批量重命名失败：{result.get('error', '未知错误')}"
        total_files = result.get("total_files", 0)
        renamed_files = result.get("renamed_files", 0)
        preview = result.get("preview_mode", False)
        if preview:
            return f"预览模式：计划重命名 {renamed_files}/{total_files} 个文件"
        else:
            return f"成功重命名 {renamed_files}/{total_files} 个文件"
    
    elif tool_name == "compress_files":
        if result.get("success") is False:
            return f"压缩失败：{result.get('error', '未知错误')}"
        source = result.get("source_path", "")
        destination = result.get("destination_path", "")
        compression_ratio = result.get("compression_ratio", 0)
        return f"成功压缩：{source} -> {destination}，压缩率：{compression_ratio:.2%}"
    
    elif tool_name == "file_monitor":
        if result.get("success") is False:
            return f"文件监控失败：{result.get('error', '未知错误')}"
        events_count = result.get("events_count", 0)
        duration = result.get("duration", 0)
        return f"监控完成：检测到 {events_count} 个事件，持续 {duration} 秒"
    
    elif tool_name == "file_statistics":
        if result.get("success") is False:
            return f"文件统计失败：{result.get('error', '未知错误')}"
        total_files = result.get("total_files", 0)
        total_size = result.get("total_size", 0)
        return f"统计完成：共 {total_files} 个文件，总大小 {total_size:,} 字节"
    
    elif tool_name == "file_checksum":
        if result.get("success") is False:
            return f"校验和计算失败：{result.get('error', '未知错误')}"
        algorithm = result.get("algorithm", "")
        checksum = result.get("checksum", "")
        verification = result.get("verification_result")
        if verification is not None:
            if verification:
                return f"{algorithm.upper()} 校验和验证通过：{checksum[:16]}..."
            else:
                return f"{algorithm.upper()} 校验和验证失败"
        else:
            return f"{algorithm.upper()} 校验和：{checksum[:16]}..."
    
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


# ============================================================
# 【M3关键】工具初始化注册
# 如果_TOOL_REGISTRY为空，手动注册所有工具
# ============================================================
def _ensure_tools_registered():
    """确保工具已注册到_TOOL_REGISTRY"""
    if _TOOL_REGISTRY:
        return  # 已有工具，跳过
    
    # 创建FileTools实例触发注册装饰器
    from app.services.tools.file import FileTools
    _ = FileTools()


# 立即执行注册（模块加载时）
_ensure_tools_registered()
