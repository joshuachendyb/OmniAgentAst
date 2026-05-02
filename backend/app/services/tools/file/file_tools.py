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
    SearchFilesInput,
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

from app.services.safety.file.file_safety import OperationType
from app.utils.visualization import get_visualizer
from app.utils.logger import logger

# 【重要】延迟导入，避免循环导入问题
# file_tools.py 在 tools 模块加载时被导入，此时 agent 还未初始化完成
# 将 agent 服务延迟到实际使用时再导入


# ============================================================
# 第一部分：分页配置常量
# ============================================================

PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# 【修复 2026-05-01 小沈】OOM防护常量
MAX_READ_SIZE = 10 * 1024 * 1024        # 文本文件读取上限：10MB
MAX_MEDIA_READ_SIZE = 50 * 1024 * 1024   # 媒体文件读取上限：50MB（base64后约67MB）
MAX_BATCH_FILE_COUNT = 100               # 批量读取文件数上限
MAX_SEARCH_FILE_SIZE = 10 * 1024 * 1024  # 搜索/单个文件读取上限：10MB

# 【新增 2026-05-02 小沈】二进制文件保护：禁止的后缀列表
BINARY_EXTENSIONS = {
    # 图片
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.svg', '.tiff', '.tif',
    # 音视频
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4a', '.ogg',
    # 压缩包
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
    # 可执行文件
    '.exe', '.dll', '.so', '.dylib', '.msi', '.app', '.deb', '.rpm',
    # 办公文档（二进制格式）
    '.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt', '.pdf',
    # 数据库
    '.db', '.sqlite', '.sqlite3',
    # 虚拟机/磁盘
    '.iso', '.vhd', '.vmdk',
}


def _is_binary_file(file_path: str) -> tuple[bool, str]:
    """
    检测文件是否为二进制文件 - 小沈 2026-05-02
    
    Args:
        file_path: 文件路径
        
    Returns:
        (is_binary, reason): 是否为二进制文件及原因说明
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix in BINARY_EXTENSIONS:
        return True, f"文件后缀 '{suffix}' 属于二进制文件类型，禁止使用text工具操作"
    
    return False, ""


def _remove_readonly(func, path, excinfo):
    """force删除时解除只读属性的回调 - 小健 2026-05-02"""
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


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
    
    BINARY_EXTENSIONS = {
        '.xlsx', '.xls', '.docx', '.doc', '.pptx', '.ppt',
        '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
        '.exe', '.dll', '.so', '.dylib',
        '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv',
        '.sqlite', '.db', '.pyc', '.pyd', '.class',
    }
    
    def __init__(self, task_id: Optional[str] = None):
        # 【重要】延迟导入 agent 服务，避免循环导入
        from app.services.agent import get_file_safety_service, get_session_service
        
        # 【重要】task_id 用于操作追踪和回退，【禁止】使用 session_id
        # session_id 专用于会话场景，操作追踪必须用 task_id
        self.safety = get_file_safety_service()
        self.session = get_session_service()
        self.visualizer = get_visualizer()
        self.task_id = task_id
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        # 【改进】允许自定义白名单
        self.allowed_paths = ALLOWED_PATHS.copy()
    
    def _get_next_sequence(self) -> int:
        """获取下一个操作序号（线程安全）"""
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence
    
    def set_task_id(self, task_id: str):
        # 【重要】task_id 用于操作追踪和回退，【禁止】使用 session_id
        # session_id 专用于会话场景，操作追踪必须用 task_id
        self.task_id = task_id
        self._sequence = 0
    
    def _validate_content_format(self, file_path: str, content: str) -> Optional[str]:
        """
        写入前按文件扩展名验证内容格式合法性
        
        【新增 2026-04-30 小沈】
        防止写入畸形格式的文件：
        - .json: 验证JSON合法性
        - .csv: 验证CSV基本格式
        - .xml/.html/.htm: 验证标记基本合法性
        - .py: 验证Python语法
        - .xlsx/.docx/.pdf/.png/.jpg等二进制格式: 拒绝通过write_file写入
        
        Args:
            file_path: 文件路径
            content: 要写入的内容
            
        Returns:
            None 表示验证通过，str 表示错误信息
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        # 二进制格式禁止通过write_file写入（会损坏文件）
        if suffix in self.BINARY_EXTENSIONS:
            return f"不支持通过write_file写入二进制格式文件(.{suffix[1:]})，请使用对应的专业工具操作"
        
        # .json: 验证JSON合法性
        if suffix == '.json':
            try:
                import json
                json.loads(content)
            except json.JSONDecodeError as e:
                return f"JSON格式验证失败: 第{e.lineno}行第{e.colno}列 - {e.msg}"
        
        # .csv: 验证CSV基本格式（检查行数和列数一致性）
        elif suffix == '.csv':
            try:
                import csv
                from io import StringIO
                reader = csv.reader(StringIO(content))
                row_lengths = []
                for i, row in enumerate(reader):
                    if i > 1000:  # 只检查前1000行
                        break
                    if row:  # 跳过空行
                        row_lengths.append(len(row))
                if row_lengths and len(set(row_lengths)) > 1:
                    return f"CSV格式警告: 列数不一致(发现{set(row_lengths)}种列数)，写入可能导致数据错位"
            except Exception as e:
                return f"CSV格式验证失败: {str(e)[:100]}"
        
        # .xml/.html/.htm: 验证标记基本合法性
        elif suffix in ('.xml', '.html', '.htm'):
            if suffix == '.xml':
                try:
                    import xml.etree.ElementTree as ET
                    ET.fromstring(content)
                except ET.ParseError as e:
                    return f"XML格式验证失败: {str(e)[:100]}"
            # html只做基本检查（< 和 > 配对）
            elif suffix in ('.html', '.htm'):
                open_tags = content.count('<')
                close_tags = content.count('>')
                if open_tags != close_tags:
                    return f"HTML标记验证警告: '<'({open_tags}个)与'>'({close_tags}个)数量不匹配"
        
        # .py: 验证Python语法
        elif suffix == '.py':
            try:
                compile(content, str(path), 'exec')
            except SyntaxError as e:
                # 【修复 2026-05-01 序号5】Python验证错误提示优化：给出具体修复建议
                error_msg = f"Python语法验证失败: 第{e.lineno}行 - {e.msg}"
                if "unterminated string literal" in e.msg:
                    error_msg += "；建议：转义字符串请使用raw string r'...'，如 r'\\\\' 代替 '\\\\'"
                elif "invalid character" in e.msg:
                    error_msg += "；建议：Python不支持全角标点，请使用半角括号()、逗号,、冒号:、分号;"
                elif "invalid escape sequence" in e.msg:
                    error_msg += "；建议：请在字符串前加r前缀使用raw string，或将转义字符双写如 \\\\d → r'\\d'"
                return error_msg
        
        return None

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
                            # 普通目录：允许子目录或相等路径
                            if len(real_parts) >= len(allowed_parts):
                                return True, None
                except (ValueError, OSError):
                    pass
            
            return False, f"路径 '{file_path}' 不在允许的操作范围内（仅允许：{', '.join(str(p) for p in self.allowed_paths[:5])}...）"
            
        except Exception as e:
            return False, f"路径验证失败: {str(e)}"
    
    async def read_file(
        self,
        file_path: str,
        offset: int = 1,
        limit: int = READ_FILE_DEFAULT_LIMIT,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """读取文件内容 - 小沈 2026-05-01"""
        # 【修复 2026-05-01 小沈】参数校验
        if offset < 1:
            return _to_unified_format({"success": False, "error": f"offset必须>=1，当前值: {offset}", "content": None}, "read_file")
        if limit < 1:
            return _to_unified_format({"success": False, "error": f"limit必须>=1，当前值: {limit}", "content": None}, "read_file")
        
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
            
            # 【修复 2026-05-01 小沈】OOM防护：预检文件大小
            file_size = path.stat().st_size
            if file_size > MAX_READ_SIZE:
                return _to_unified_format({
                    "success": False,
                    "error": f"文件过大({file_size}字节)，超过读取上限{MAX_READ_SIZE}字节({MAX_READ_SIZE//1024//1024}MB)。请使用offset/limit分段读取，或使用search_file_content搜索特定内容。",
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

    async def read_text_file(
        self,
        file_path: str,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """读取文本文件的完整内容，支持指定行数 - 小沈 2026-05-01"""
        try:
            # 【新增 2026-05-02 小沈】二进制文件保护
            is_binary, binary_reason = _is_binary_file(file_path)
            if is_binary:
                return _to_unified_format({
                    "success": False,
                    "error": f"{binary_reason}。请使用 read_media_file 工具读取媒体文件，或使用 read_file 工具读取任意类型文件。",
                    "content": None
                }, "read_text_file")
            
            # 【修复 2026-05-01 小沈】参数校验
            if head is not None and head < 1:
                return _to_unified_format({"success": False, "error": f"head必须>=1，当前值: {head}", "content": None}, "read_text_file")
            if tail is not None and tail < 1:
                return _to_unified_format({"success": False, "error": f"tail必须>=1，当前值: {tail}", "content": None}, "read_text_file")
            
            # 验证head和tail不能同时使用
            if head is not None and tail is not None:
                return _to_unified_format({
                    "success": False,
                    "error": "head 和 tail 参数不能同时使用，请只使用其中一个",
                    "content": None
                }, "read_text_file")

            # 验证路径合法性
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return _to_unified_format({
                    "success": False,
                    "error": error_msg,
                    "content": None
                }, "read_text_file")

            path = Path(file_path)
            if not path.exists():
                return _to_unified_format({
                    "success": False,
                    "error": f"文件不存在: {file_path}",
                    "content": None
                }, "read_text_file")

            if not path.is_file():
                return _to_unified_format({
                    "success": False,
                    "error": f"路径不是文件: {file_path}",
                    "content": None
                }, "read_text_file")

            # 尝试编码读取
            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]
            file_size = path.stat().st_size
            
            # 【修复 2026-05-01 小沈】OOM防护：预检文件大小
            if file_size > MAX_READ_SIZE:
                return _to_unified_format({
                    "success": False,
                    "error": f"文件过大({file_size}字节)，超过读取上限{MAX_READ_SIZE}字节({MAX_READ_SIZE//1024//1024}MB)。请使用head/tail参数分段读取。",
                    "content": None
                }, "read_text_file")
            
            content = None
            used_encoding = None

            for enc in encodings_to_try:
                if enc is None:
                    continue
                try:
                    def _read_sync(e=enc):
                        with open(path, 'r', encoding=e, errors='replace') as f:
                            return f.read()
                    content = await asyncio.to_thread(_read_sync)
                    used_encoding = enc
                    break
                except Exception:
                    continue

            if content is None:
                return _to_unified_format({
                    "success": False,
                    "error": f"无法读取文件: {file_path}，已尝试编码: {encodings_to_try}",
                    "content": None
                }, "read_text_file")

            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            # 处理head/tail
            if head is not None:
                selected_lines = lines[:min(head, total_lines)]
            elif tail is not None:
                start = max(0, total_lines - tail)
                selected_lines = lines[start:]
            else:
                selected_lines = lines

            result_content = "".join(selected_lines)
            line_count = len(selected_lines)

            return _to_unified_format({
                "success": True,
                "content": result_content,
                "total_lines": total_lines,
                "line_count": line_count,
                "head": head,
                "tail": tail,
                "encoding": used_encoding,
                "file_size": file_size,
            }, "read_text_file")

        except Exception as e:
            logger.error(f"read_text_file failed: {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "content": None
            }, "read_text_file")
    
    async def write_text_file(
        self,
        file_path: str,
        text: str,
        encoding: str = "utf-8",
        append: bool = False,
        create_parents: bool = True,
        unescape: bool = True
    ) -> Dict[str, Any]:
        """写入文本文件 - 小健 2026-05-02 增强: text参数+append+create_parents"""
        # 【新增 2026-05-02 小沈】二进制文件保护（最关键，防止破坏二进制文件）
        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            return _to_unified_format({
                "success": False,
                "error": f"{binary_reason}。write_text_file 仅支持文本文件，禁止写入二进制文件。",
                "content": None
            }, "write_text_file")
        
        content = text
        MAX_WRITE_SIZE = MAX_READ_SIZE
        if len(content.encode(encoding)) > MAX_WRITE_SIZE:
            return _to_unified_format({
                "success": False,
                "error": f"写入内容过大，超过上限{MAX_WRITE_SIZE//1024//1024}MB",
                "content": None
            }, "write_text_file")

        path_preview = Path(file_path)
        if path_preview.suffix.lower() == '.py' and content:
            fullwidth_map = {
                '（': '(', '）': ')', '，': ',', '：': ':', '；': ';',
                '！': '!', '？': '?', '＝': '=', '＋': '+', '－': '-',
                '＊': '*', '／': '/', '＜': '<', '＞': '>', '［': '[', '］': ']',
            }
            original_content = content
            for fw, hw in fullwidth_map.items():
                content = content.replace(fw, hw)
            if content != original_content:
                import logging
                logging.getLogger(__name__).info(f"write_text_file: 自动将全角标点替换为半角标点({file_path})")

        if content:
            from app.services.tools.content_quality import check_content_quality
            quality_result = check_content_quality(content=content, file_path=file_path)
            if quality_result.get("is_thought_leak"):
                return _to_unified_format({
                    "success": False,
                    "error": f"内容保护：{quality_result['warning']}",
                    "content": None
                }, "write_text_file")
        if unescape:
            content = content.replace("\\n", "\n").replace("\\\"", "\"").replace("\\\\", "\\")
        
        validation_error = self._validate_content_format(file_path, content)
        if validation_error:
            return _to_unified_format({
                "success": False,
                "error": validation_error,
                "content": None
            }, "write_text_file")
        
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "content": None
            }, "write_text_file")
        
        if not self.task_id:
            return _to_unified_format({
                "success": False,
                "error": "No active task",
                "operation_id": None
            }, "write_text_file")
        
        path = Path(file_path)
        
        if not append and path.exists() and path.is_file():
            old_size = path.stat().st_size
            new_size = len(content.encode(encoding))
            if old_size > 1024 and new_size < old_size * 0.1:
                return _to_unified_format({
                    "success": False,
                    "error": f"数据保护：新内容({new_size}字节)远小于原始内容({old_size}字节，缩小{100-int(new_size/max(old_size,1)*100)}%)，可能覆盖数据。如确认覆盖，请使用precise_replace_in_file或在text中传入完整内容。",
                    "content": None
                }, "write_text_file")
        
        try:
            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.CREATE,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            def _write_sync():
                import tempfile
                import os
                
                if create_parents:
                    path.parent.mkdir(parents=True, exist_ok=True)
                elif not path.parent.exists():
                    raise FileNotFoundError(f"父目录不存在: {path.parent}")
                
                if append and path.exists() and path.is_file():
                    with open(path, 'a', encoding=encoding) as f:
                        f.write(content)
                    return True
                
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
                }, "write_text_file")
            else:
                return _to_unified_format({
                    "success": False,
                    "error": "Failed to write file",
                    "operation_id": operation_id
                }, "write_text_file")
                
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "operation_id": None
            }, "write_text_file")

    async def write_file(self, file_path: str, text: str, encoding: str = "utf-8",
                         append: bool = False, create_parents: bool = True,
                         unescape: bool = True) -> Dict[str, Any]:
        """write_file兼容别名 - 小健 2026-05-02"""
        return await self.write_text_file(
            file_path=file_path, text=text, encoding=encoding,
            append=append, create_parents=create_parents, unescape=unescape
        )
    
    async def list_directory(
        self,
        dir_path: str,
        recursive: bool = False,
        max_depth: int = 10,
        page_token: Optional[str] = None,
        sortBy: str = "name",
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """列出目录内容（含大小/排序/统计） - 小沈 2026-05-01"""
        # 【修复 2026-05-01 小沈】参数校验
        if max_depth < 1:
            return _to_unified_format({"success": False, "error": f"max_depth必须>=1，当前值: {max_depth}", "entries": []}, "list_directory")
        if sortBy not in ("name", "size"):
            return _to_unified_format({"success": False, "error": f"sortBy只支持'name'或'size'，当前值: '{sortBy}'", "entries": []}, "list_directory")

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
                stats = {"total_size": 0, "dir_count": 0, "file_count": 0}

                if recursive:
                    def _scan_recursive(current_path: Path, current_depth: int):
                        if current_depth > max_depth:
                            return
                        try:
                            for item in current_path.iterdir():
                                try:
                                    if not include_hidden and item.name.startswith('.'):
                                        continue
                                    st = item.stat()
                                    is_dir = item.is_dir()
                                    entries.append({
                                        "name": item.name,
                                        "path": str(item.absolute()),
                                        "type": "directory" if is_dir else "file",
                                        "size": None if is_dir else st.st_size,
                                        "mtime": st.st_mtime,
                                    })
                                    if is_dir:
                                        stats["dir_count"] += 1
                                        _scan_recursive(item, current_depth + 1)
                                    else:
                                        stats["total_size"] += st.st_size
                                        stats["file_count"] += 1
                                except (PermissionError, OSError):
                                    continue
                        except (PermissionError, OSError):
                            return

                    _scan_recursive(path, 1)
                else:
                    for item in path.iterdir():
                        try:
                            if not include_hidden and item.name.startswith('.'):
                                continue
                            st = item.stat()
                            is_dir = item.is_dir()
                            entries.append({
                                "name": item.name,
                                "path": str(item.absolute()),
                                "type": "directory" if is_dir else "file",
                                "size": None if is_dir else st.st_size,
                                "mtime": st.st_mtime,
                            })
                            if is_dir:
                                stats["dir_count"] += 1
                            else:
                                stats["total_size"] += st.st_size
                                stats["file_count"] += 1
                        except (PermissionError, OSError):
                            continue

                return entries, stats["total_size"], stats["dir_count"], stats["file_count"]

            all_entries, total_size, dir_count, file_count = await asyncio.to_thread(_list_sync)

            # 排序：目录优先，然后按sortBy
            if sortBy == "size":
                all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
            else:
                all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

            total = len(all_entries)

            # 【优化 2026-04-16 小沈】大目录优化
            # 背景：E盘根目录有 492,335 个文件，entries JSON 大小达 90.58MB
            # 问题：导致 API 请求体过大，触发 429 错误
            # 解决：截断大目录，只返回前 200 项 + 统计摘要
            MAX_DISPLAY_ENTRIES = 200

            statistics = {
                "total_size": total_size, "dir_count": dir_count,
                "file_count": file_count, "sort_by": sortBy,
            }

            if total > MAX_DISPLAY_ENTRIES:
                display_entries = all_entries[start_offset:start_offset + MAX_DISPLAY_ENTRIES]

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
                    "truncated": True,
                    "dir_count": dir_count,
                    "file_count": file_count,
                    "statistics": statistics,
                    "next_page_token": encode_page_token(start_offset + MAX_DISPLAY_ENTRIES) if start_offset + MAX_DISPLAY_ENTRIES < total else None
                }, "list_directory")

            return _to_unified_format({
                "success": True,
                "entries": all_entries,
                "total": total,
                "directory": str(path),
                "statistics": statistics,
                "next_page_token": None
            }, "list_directory")

        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "entries": []
            }, "list_directory")
    
    async def delete_file(
        self,
        file_path: str,
        recursive: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """删除文件或目录 - 小健 2026-05-02 增加force"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return _to_unified_format({
                "success": False,
                "error": error_msg,
                "operation_id": None
            }, "delete_file")
        
        if not self.task_id:
            return _to_unified_format({
                "success": False,
                "error": "No active task",
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
                task_id=self.task_id,
                operation_type=OperationType.DELETE,
                source_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义删除操作
            def _delete_sync():
                if path.is_dir():
                    if recursive:
                        if force:
                            shutil.rmtree(str(path), onerror=_remove_readonly)
                        else:
                            shutil.rmtree(path)
                    else:
                        path.rmdir()
                else:
                    if force and path.exists() and not os.access(str(path), os.W_OK):
                        path.chmod(path.stat().st_mode | 0o200)
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
    
    async def move_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """移动或重命名文件 - 小健 2026-05-02 增加overwrite"""
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
        
        if not self.task_id:
            return _to_unified_format({
                "success": False,
                "error": "No active task",
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
                task_id=self.task_id,
                operation_type=OperationType.MOVE,
                source_path=src,
                destination_path=dst,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义移动操作
            def _move_sync():
                if dst.exists():
                    if not overwrite:
                        raise FileExistsError(f"目标路径已存在: {dst}，移动操作已取消。请设置overwrite=True或指定其他路径。")
                    if dst.is_dir():
                        shutil.rmtree(str(dst))
                    else:
                        dst.unlink()
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
        """【已废弃】请使用 grep_file_content 替代 - 小健 2026-05-02
        该工具已废弃，自动转发到 grep_file_content（功能更强、性能更好、支持正则+分页）。
        """
        logger.warning("[deprecated] search_file_content 已废弃，请使用 grep_file_content 替代")
        return await self.grep_file_content(
            pattern=pattern,
            search_dir=path,
            output_mode="content",
            glob=file_pattern if file_pattern != "*" else None,
            ignore_case=True,
            show_line_no=True,
            head_limit=200,
            page_token=page_token,
        )
    
    async def search_files(
        self,
        file_pattern: str,
        path: str = "~",
        recursive: bool = True,
        max_depth: int = 100000,
        excludePatterns: Optional[List[str]] = None,
        ignore_case: bool = True,
        type: Optional[str] = None,
        sortBy: Optional[str] = None,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """搜索文件名（按文件名匹配）- 小沈 2026-05-02 增加sortBy参数（覆盖glob_files功能）"""
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
                    if not recursive:
                        dirs.clear()
                    else:
                        rel_root = Path(root).relative_to(search_path)
                        depth = len(rel_root.parts) if str(rel_root) != "." else 0
                        if depth >= max_depth:
                            dirs.clear()
                            continue
                    
                    if excludePatterns:
                        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in excludePatterns)]
                    
                    for dirname in dirs:
                        if type == "file":
                            continue
                        matched = fnmatch.fnmatch(dirname, file_pattern) if ignore_case else fnmatch.fnmatchcase(dirname, file_pattern)
                        if not matched:
                            continue

                        dir_path = Path(root) / dirname
                        dir_str = str(dir_path.relative_to(search_path))

                        if dir_str in seen_files:
                            continue

                        seen_count += 1

                        if seen_count <= start_offset:
                            seen_files.add(dir_str)
                            continue
                        seen_files.add(dir_str)

                        all_matches.append({
                            "name": dirname,
                            "path": dir_str,
                            "type": "directory"
                        })

                    for filename in files:
                        if type == "directory":
                            continue
                        matched = fnmatch.fnmatch(filename, file_pattern) if ignore_case else fnmatch.fnmatchcase(filename, file_pattern)
                        if not matched:
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
                            "size": size,
                            "type": "file",
                            "mtime": file_path.stat().st_mtime if sortBy == "mtime" else None
                        })
                
                return all_matches
            
            # 执行搜索
            all_matches = await asyncio.to_thread(_search_sync)
            
            # 【新增 2026-05-02 小沈】排序支持（覆盖glob_files功能）
            if sortBy == "mtime":
                # 按修改时间降序（最新的在前）
                all_matches.sort(key=lambda x: x.get("mtime", 0) or 0, reverse=True)
            elif sortBy == "name":
                # 按名称升序
                all_matches.sort(key=lambda x: x.get("name", ""))
            elif sortBy == "size":
                # 按大小降序
                all_matches.sort(key=lambda x: x.get("size", 0) or 0, reverse=True)
            
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
        
        if not self.task_id:
            return _to_unified_format({
                "success": False,
                "error": "No active task",
                "reports": {}
            }, "generate_report")
        
        try:
            output_path = Path(output_dir) if output_dir else None
            task_id = self.task_id or ""
            
            def _generate_sync():
                return self.visualizer.generate_all_reports(task_id, output_path)
            
            reports = await asyncio.to_thread(_generate_sync)
            report_paths = {k: str(v) for k, v in reports.items()}
            
            return _to_unified_format({
                "success": True,
                "task_id": self.task_id,
                "reports": report_paths
            }, "generate_report")
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return _to_unified_format({
                "success": False,
                "error": str(e),
                "reports": {}
            }, "generate_report")

    async def copy_file(
        self,
        source_path: str,
        destination_path: str,
        recursive: bool = False,
        overwrite: bool = False,
        preserve_metadata: bool = True,
    ) -> Dict[str, Any]:
        """复制文件或目录 - 小健 2026-05-02 增加preserve_metadata"""
        from app.services.tools.file.copy_file import copy_file_impl
        
        return await copy_file_impl(
            source_path=source_path,
            destination_path=destination_path,
            recursive=recursive,
            overwrite=overwrite,
            preserve_metadata=preserve_metadata,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    async def get_file_info(
        self,
        file_path: str,
        follow_symlinks: bool = True,
    ) -> Dict[str, Any]:
        """获取文件信息 - 小健 2026-05-02 增加follow_symlinks"""
        from app.services.tools.file.get_file_info import get_file_info_impl
        
        return await get_file_info_impl(
            file_path=file_path,
            validate_path_func=self._validate_path,
            to_unified_format_func=_to_unified_format,
            follow_symlinks=follow_symlinks,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
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
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            to_unified_format_func=_to_unified_format,
            get_next_sequence_func=self._get_next_sequence,
        )

    async def read_media_file(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """读取媒体文件，返回Base64编码"""
        try:
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return _to_unified_format({
                    "success": False, "error": error_msg, "data": None, "mime_type": None
                }, "read_media_file")

            path = Path(file_path)
            if not path.exists():
                return _to_unified_format({
                    "success": False, "error": f"文件不存在: {file_path}", "data": None, "mime_type": None
                }, "read_media_file")
            if not path.is_file():
                return _to_unified_format({
                    "success": False, "error": f"路径不是文件: {file_path}", "data": None, "mime_type": None
                }, "read_media_file")

            # 【修复 2026-05-01 小沈】OOM防护：预检媒体文件大小（base64膨胀约33%）
            file_size = path.stat().st_size
            if file_size > MAX_MEDIA_READ_SIZE:
                return _to_unified_format({
                    "success": False, "error": f"媒体文件过大({file_size}字节)，超过读取上限{MAX_MEDIA_READ_SIZE//1024//1024}MB", "data": None, "mime_type": None
                }, "read_media_file")

            suffix = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
                ".svg": "image/svg+xml", ".tiff": "image/tiff", ".tif": "image/tiff",
                ".ico": "image/x-icon", ".heic": "image/heic", ".heif": "image/heif",
                ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
                ".m4a": "audio/mp4", ".flac": "audio/flac", ".aac": "audio/aac",
                ".wma": "audio/x-ms-wma", ".mid": "audio/midi", ".midi": "audio/midi",
                ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
                ".mkv": "video/x-matroska", ".webm": "video/webm", ".wmv": "video/x-ms-wmv",
                ".pdf": "application/pdf",
            }
            mime_type = mime_map.get(suffix, "application/octet-stream")

            def _read_sync():
                with open(path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')

            b64_data = await asyncio.to_thread(_read_sync)
            return _to_unified_format({
                "success": True, "data": b64_data, "mime_type": mime_type,
                "file_name": path.name, "file_size": path.stat().st_size,
            }, "read_media_file")
        except Exception as e:
            logger.error(f"read_media_file failed: {file_path}: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "data": None, "mime_type": None
            }, "read_media_file")

    async def read_batch_file(
        self,
        file_paths: List[str],
    ) -> Dict[str, Any]:
        """同时读取多个文本文件 - 小沈 2026-05-01"""
        if not file_paths:
            return _to_unified_format({
                "success": False, "error": "文件路径列表为空", "results": []
            }, "read_batch_file")

        # 【修复 2026-05-01 小沈】OOM防护：批量文件数上限
        if len(file_paths) > MAX_BATCH_FILE_COUNT:
            return _to_unified_format({
                "success": False, "error": f"批量读取文件数({len(file_paths)})超过上限{MAX_BATCH_FILE_COUNT}，请分批读取", "results": []
            }, "read_batch_file")

        # 【修复 2026-05-01 小沈】B1: 添加Semaphore并发限制，防止大量文件并发读取耗尽文件句柄
        semaphore = asyncio.Semaphore(20)

        async def _read_single(fp: str) -> Dict[str, Any]:
            async with semaphore:
                # 【新增 2026-05-02 小沈】二进制文件保护
                is_binary, binary_reason = _is_binary_file(fp)
                if is_binary:
                    return {"file_path": fp, "success": False, "error": f"{binary_reason}。已跳过该文件。", "content": None}
                
                is_valid, error_msg = self._validate_path(fp)
                if not is_valid:
                    return {"file_path": fp, "success": False, "error": error_msg, "content": None}
                path = Path(fp)
                if not path.exists():
                    return {"file_path": fp, "success": False, "error": f"文件不存在: {fp}", "content": None}
                
                # 【修复 2026-05-01 小沈】OOM防护：单文件大小预检
                try:
                    if path.stat().st_size > MAX_READ_SIZE:
                        return {"file_path": fp, "success": False, "error": f"文件过大({path.stat().st_size}字节)，超过读取上限{MAX_READ_SIZE//1024//1024}MB", "content": None}
                except OSError as e:
                    return {"file_path": fp, "success": False, "error": str(e), "content": None}
                
                try:
                    for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
                        try:
                            # 【修复 2026-04-30 小沈】用with语句读取，避免文件句柄泄漏
                            def _read_with(e=enc):
                                with open(path, 'r', encoding=e, errors='replace') as f:
                                    return f.read()
                            content = await asyncio.to_thread(_read_with)
                            return {"file_path": fp, "success": True, "content": content, "encoding": enc, "file_size": path.stat().st_size}
                        except Exception:
                            continue
                    return {"file_path": fp, "success": False, "error": f"无法解码文件: {fp}", "content": None}
                except Exception as e:
                    return {"file_path": fp, "success": False, "error": str(e), "content": None}

        results = await asyncio.gather(*[_read_single(fp) for fp in file_paths])
        success_count = sum(1 for r in results if r["success"])
        # 【修复 2026-04-30 小沈】success基于实际结果，不再硬编码True
        return _to_unified_format({
            "success": success_count > 0, "results": results, "total": len(results),
            "success_count": success_count, "failed_count": len(results) - success_count,
        }, "read_batch_file")

    async def precise_replace_in_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        ignore_case: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """精确替换文件中的字符串"""
        # 【修复 2026-04-30 小沈】空old_string拒绝：content.replace("", x)会在每个字符间插入，导致内容爆炸
        if not old_string:
            return _to_unified_format({
                "success": False, "error": "old_string不能为空，空字符串替换会导致内容爆炸", "replaced_count": 0
            }, "precise_replace_in_file")
        
        # 【修复 2026-04-30 小沈】添加task_id检查（与write_file对齐）
        if not self.task_id:
            return _to_unified_format({
                "success": False, "error": "No active task", "replaced_count": 0
            }, "precise_replace_in_file")
        
        # 【小健 2026-05-02】【修复 2026-05-02 小沈】二进制文件保护：仅支持文本文件编辑
        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            return _to_unified_format({
                "success": False, "error": f"{binary_reason}。请使用对应的专业工具操作二进制文件。", "replaced_count": 0
            }, "precise_replace_in_file")
        
        try:
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return _to_unified_format({
                    "success": False, "error": error_msg, "replaced_count": 0
                }, "precise_replace_in_file")

            path = Path(file_path)
            if not path.exists():
                return _to_unified_format({
                    "success": False, "error": f"文件不存在: {file_path}", "replaced_count": 0
                }, "precise_replace_in_file")

            # 【修复 2026-05-01 小沈】OOM防护：预检文件大小
            if path.stat().st_size > MAX_READ_SIZE:
                return _to_unified_format({
                    "success": False, "error": f"文件过大({path.stat().st_size}字节)，超过替换上限{MAX_READ_SIZE//1024//1024}MB", "replaced_count": 0
                }, "precise_replace_in_file")

            # 【修复 2026-04-30 小沈】添加safety记录（与write_file对齐）
            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.MODIFY,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )

            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]

            # 【修复 2026-05-01 小沈】闭包变量存结果，_replace_sync返回True给execute_with_safety
            replace_result = {}

            def _replace_sync() -> bool:
                content = None
                used_enc = None
                for enc in encodings_to_try:
                    if enc is None:
                        continue
                    try:
                        with open(path, 'r', encoding=enc, errors='replace') as f:
                            content = f.read()
                        used_enc = enc
                        break
                    except Exception:
                        continue
                if content is None:
                    raise ValueError(f"无法读取文件: {file_path}")

                if ignore_case:
                    import re as re_mod
                    if replace_all:
                        new_content = re_mod.sub(re_mod.escape(old_string), new_string, content, flags=re_mod.IGNORECASE)
                        count = len(re_mod.findall(re_mod.escape(old_string), content, flags=re_mod.IGNORECASE))
                    else:
                        new_content = re_mod.sub(re_mod.escape(old_string), new_string, content, count=1, flags=re_mod.IGNORECASE)
                        count = 1
                else:
                    if replace_all:
                        count = content.count(old_string)
                        new_content = content.replace(old_string, new_string)
                    else:
                        idx = content.find(old_string)
                        if idx == -1:
                            raise ValueError(f"文件中未找到匹配文本: {old_string[:50]}")
                        new_content = content[:idx] + new_string + content[idx + len(old_string):]
                        count = 1

                # 【修复 2026-04-30 小沈】原子写入：先写临时文件再重命名（与write_file对齐）
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(
                    mode='w', encoding=used_enc,
                    dir=path.parent, delete=False,
                    prefix=f".{path.name}.", suffix=""
                ) as f:
                    f.write(new_content)
                    temp_path = f.name
                try:
                    os.replace(temp_path, str(path))
                except Exception:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                    raise
                replace_result['count'] = count
                replace_result['used_enc'] = used_enc
                replace_result['name'] = path.name
                return True

            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_replace_sync
            )
            if success:
                return _to_unified_format({
                    "success": True, "replaced_count": replace_result['count'], "encoding": replace_result['used_enc'],
                    "file_path": str(path), "file_name": replace_result['name'],
                    "operation_id": operation_id,
                }, "precise_replace_in_file")
            else:
                return _to_unified_format({
                    "success": False, "error": "Failed to replace in file",
                    "replaced_count": 0, "operation_id": operation_id
                }, "precise_replace_in_file")
        except Exception as e:
            logger.error(f"precise_replace_in_file failed: {file_path}: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "replaced_count": 0
            }, "precise_replace_in_file")

    async def edit_file(
        self,
        file_path: str,
        edits: List[Dict[str, str]],
        dryRun: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """高级编辑文件，支持多处编辑和预览 - 小沈 2026-05-01"""
        try:
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return _to_unified_format({
                    "success": False, "error": error_msg, "applied_edits": 0, "preview": None
                }, "edit_file")

            # 【修复 2026-05-01 小沈】添加task_id检查（与write_file对齐）
            if not self.task_id:
                return _to_unified_format({
                    "success": False, "error": "No active task", "applied_edits": 0, "preview": None
                }, "edit_file")

            # 【小健 2026-05-02】【修复 2026-05-02 小沈】二进制文件保护：仅支持文本文件编辑
            is_binary, binary_reason = _is_binary_file(file_path)
            if is_binary:
                return _to_unified_format({
                    "success": False, "error": f"{binary_reason}。请使用对应的专业工具操作二进制文件。", "applied_edits": 0, "preview": None
                }, "edit_file")

            path = Path(file_path)
            if not path.exists():
                return _to_unified_format({
                    "success": False, "error": f"文件不存在: {file_path}", "applied_edits": 0, "preview": None
                }, "edit_file")

            # 【修复 2026-05-01 小沈】OOM防护：预检文件大小
            if path.stat().st_size > MAX_READ_SIZE:
                return _to_unified_format({
                    "success": False, "error": f"文件过大({path.stat().st_size}字节)，超过编辑上限{MAX_READ_SIZE//1024//1024}MB", "applied_edits": 0, "preview": None
                }, "edit_file")

            # 【修复 2026-05-01 小沈】添加safety记录（与precise_replace_in_file对齐）
            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.MODIFY,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )

            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]

            # 【修复 2026-05-01 小沈】闭包变量存结果，_edit_sync返回True给execute_with_safety
            edit_result = {}

            def _edit_sync() -> bool:
                content = None
                used_enc = None
                for enc in encodings_to_try:
                    if enc is None:
                        continue
                    try:
                        with open(path, 'r', encoding=enc, errors='replace') as f:
                            content = f.read()
                        used_enc = enc
                        break
                    except Exception:
                        continue
                if content is None:
                    raise ValueError(f"无法读取文件: {file_path}")

                results = []
                modified = content
                for i, edit in enumerate(edits):
                    old_text = edit.get("oldText", "")
                    new_text = edit.get("newText", "")
                    if not old_text:
                        results.append({"index": i, "success": False, "error": "oldText 为空"})
                        continue
                    idx = modified.find(old_text)
                    if idx == -1:
                        results.append({"index": i, "success": False, "error": f"未找到匹配文本: {old_text[:50]}"})
                        continue
                    modified = modified[:idx] + new_text + modified[idx + len(old_text):]
                    results.append({"index": i, "success": True, "old_text": old_text[:50], "new_text": new_text[:50]})

                applied = sum(1 for r in results if r["success"])
                if not dryRun and applied > 0:
                    # 【修复 2026-05-01 小沈】原子写入：先写临时文件再重命名（与write_file对齐）
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(
                        mode='w', encoding=used_enc,
                        dir=path.parent, delete=False,
                        prefix=f".{path.name}.", suffix=""
                    ) as f:
                        f.write(modified)
                        temp_path = f.name
                    try:
                        os.replace(temp_path, str(path))
                    except Exception:
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass
                        raise
                edit_result['applied_edits'] = applied
                edit_result['total_edits'] = len(edits)
                edit_result['results'] = results
                edit_result['preview'] = modified if dryRun else None
                edit_result['dry_run'] = dryRun
                edit_result['used_enc'] = used_enc
                return True

            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_edit_sync
            )
            if success:
                # 【修复 2026-05-01 小沈】applied_edits=0时success应为False（如oldText全为空）
                edit_success = edit_result['applied_edits'] > 0
                return _to_unified_format({
                    "success": edit_success, "applied_edits": edit_result['applied_edits'], "total_edits": edit_result['total_edits'],
                    "results": edit_result['results'], "preview": edit_result['preview'],
                    "dry_run": edit_result['dry_run'], "encoding": edit_result['used_enc'],
                    "operation_id": operation_id,
                }, "edit_file")
            else:
                return _to_unified_format({
                    "success": False, "error": "Failed to edit file",
                    "applied_edits": 0, "operation_id": operation_id
                }, "edit_file")
        except Exception as e:
            logger.error(f"edit_file failed: {file_path}: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "applied_edits": 0, "preview": None
            }, "edit_file")

    async def rename_file(
        self,
        file_path: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """重命名文件或目录（仅同目录改名）- 小沈 2026-05-02
        
        注意：内部通过 move_file 实现，但对外保持独立语义。
        - rename_file: 仅同目录改名（语义明确）
        - move_file: 跨目录移动+改名（功能更强）
        
        用户说"重命名"用此工具，说"移动"用 move_file。
        """
        # 计算新路径（同目录改名）
        src = Path(file_path)
        
        # 参数校验
        if "/" in new_name or "\\" in new_name:
            return _to_unified_format({
                "success": False, 
                "error": "新名称不能包含路径分隔符（rename_file仅支持同目录改名）。如需跨目录移动请使用move_file。", 
                "new_path": None
            }, "rename_file")
        
        dst = src.parent / new_name
        
        # 内部调用 move_file 实现
        result = await self.move_file(
            source_path=file_path,
            destination_path=str(dst),
            overwrite=False
        )
        
        # 转换返回格式（保持rename_file的语义）
        if result.get("success"):
            return _to_unified_format({
                "success": True,
                "new_path": str(dst),
                "old_path": str(src),
                "old_name": src.name,
                "new_name": new_name,
                "operation_id": result.get("operation_id"),
            }, "rename_file")
        else:
            return _to_unified_format({
                "success": False,
                "error": result.get("error"),
                "new_path": None
            }, "rename_file")

    async def grep_file_content(
        self,
        pattern: str,
        search_dir: Optional[str] = None,
        output_mode: Optional[str] = None,
        glob: Optional[str] = None,
        type: Optional[str] = None,
        after_lines: Optional[int] = None,
        before_lines: Optional[int] = None,
        context_lines: Optional[int] = None,
        ignore_case: bool = False,
        show_line_no: bool = False,
        multiline: bool = False,
        head_limit: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """基于正则的内容搜索，支持分页 - 小健 2026-05-02 添加page_token"""
        try:
            search_path = Path(search_dir).resolve() if search_dir else Path.cwd().resolve()
            is_valid, error_msg = self._validate_path(str(search_path))
            if not is_valid:
                return _to_unified_format({
                    "success": False, "error": error_msg, "matches": []
                }, "grep_file_content")

            if not pattern:
                return _to_unified_format({
                    "success": False, "error": "搜索模式不能为空", "matches": []
                }, "grep_file_content")

            type_ext_map = {
                "js": "*.js", "ts": "*.ts", "tsx": "*.tsx", "jsx": "*.jsx",
                "py": "*.py", "rs": "*.rs", "go": "*.go", "java": "*.java",
                "html": "*.html", "css": "*.css", "json": "*.json", "yaml": "*.yaml",
                "md": "*.md", "xml": "*.xml", "c": "*.c", "cpp": "*.cpp",
                "h": "*.h", "rust": "*.rs",
            }
            file_glob = glob or (type_ext_map.get(type) if type else None)

            def _grep_sync() -> List[Dict[str, Any]]:
                import fnmatch
                import re as re_mod

                flags = re_mod.IGNORECASE if ignore_case else 0
                if multiline:
                    flags |= re_mod.DOTALL
                try:
                    regex = re_mod.compile(pattern, flags)
                except re.error as e:
                    raise ValueError(f"正则表达式错误: {e}")

                results = []
                match_count = 0

                for root, dirs, files in os.walk(search_path):
                    filtered_files = []
                    for f in files:
                        if file_glob and not fnmatch.fnmatch(f, file_glob):
                            continue
                        filtered_files.append(f)
                    for filename in filtered_files:
                        if head_limit is not None and match_count >= head_limit:
                            break
                        file_path = Path(root) / filename
                        # 【修复 2026-05-01 小沈】OOM防护：跳过大文件
                        try:
                            if file_path.stat().st_size > MAX_SEARCH_FILE_SIZE:
                                continue
                        except OSError:
                            continue
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                lines = f.readlines()
                        except Exception:
                            continue

                        file_matches = []
                        for line_no, line in enumerate(lines, 1):
                            m = regex.search(line)
                            if m:
                                match_count += 1
                                entry = {
                                    "line": line_no if show_line_no else None,
                                    "content": line.rstrip('\n\r'),
                                }
                                if context_lines or after_lines:
                                    after = after_lines or context_lines or 0
                                    after_content = []
                                    for i in range(1, after + 1):
                                        if line_no - 1 + i < len(lines):
                                            after_content.append(lines[line_no - 1 + i].rstrip('\n\r'))
                                    entry["after"] = after_content if after_content else None
                                if context_lines or before_lines:
                                    before = before_lines or context_lines or 0
                                    before_content = []
                                    for i in range(1, before + 1):
                                        if line_no - 1 - i >= 0:
                                            before_content.insert(0, lines[line_no - 1 - i].rstrip('\n\r'))
                                    entry["before"] = before_content if before_content else None
                                file_matches.append(entry)
                                if head_limit is not None and match_count >= head_limit:
                                    break

                        if file_matches:
                            if output_mode == "count":
                                results.append({"file": str(file_path), "count": len(file_matches)})
                            elif output_mode == "files_with_matches":
                                results.append({"file": str(file_path)})
                            else:
                                results.append({"file": str(file_path), "matches": file_matches, "match_count": len(file_matches)})

                return results

            matches = await asyncio.to_thread(_grep_sync)
            total_matches = sum(m.get("match_count", 0) if "match_count" in m else (m.get("count", 1) if "count" in m else 1) for m in matches)

            # 【小健 2026-05-02】分页逻辑（从search_file_content迁移）
            total = len(matches)
            start_offset = decode_page_token(page_token) if page_token else 0
            if total > DEFAULT_PAGE_SIZE or start_offset > 0:
                end_offset = start_offset + DEFAULT_PAGE_SIZE
                page_results = matches[start_offset:end_offset]
                has_more = end_offset < total
                next_page_token = encode_page_token(end_offset) if has_more else None
            else:
                page_results = matches
                has_more = False
                next_page_token = None

            return _to_unified_format({
                "success": True, "matches": page_results, "total_files": total,
                "total_matches": total_matches, "pattern": pattern,
                "search_dir": str(search_path), "output_mode": output_mode or "content",
                "has_more": has_more, "next_page_token": next_page_token,
            }, "grep_file_content")
        except Exception as e:
            logger.error(f"grep_file_content failed: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "matches": []
            }, "grep_file_content")

    async def get_directory_tree(
        self,
        dir_path: str,
        excludePatterns: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取目录的递归JSON树结构 - 小沈 2026-05-01"""
        try:
            is_valid, error_msg = self._validate_path(dir_path)
            if not is_valid:
                return _to_unified_format({
                    "success": False, "error": error_msg, "tree": None
                }, "get_directory_tree")

            path = Path(dir_path)
            if not path.exists():
                return _to_unified_format({
                    "success": False, "error": f"目录不存在: {dir_path}", "tree": None
                }, "get_directory_tree")
            if not path.is_dir():
                return _to_unified_format({
                    "success": False, "error": f"不是目录: {dir_path}", "tree": None
                }, "get_directory_tree")

            # 【修复 2026-05-01 小沈】默认max_depth防止无限递归
            effective_max_depth = max_depth if max_depth is not None else 10
            excludes = excludePatterns or []
            import fnmatch
            entry_count = [0]

            def _build_tree(current_path: Path, depth: int = 0) -> Optional[Dict[str, Any]]:
                if depth > effective_max_depth:
                    return None
                # 【修复 2026-05-01 小沈】条目数上限防护
                if entry_count[0] >= MAX_PAGE_SIZE:
                    return None
                # 【修复 2026-05-01 小沈】符号链接循环防护：跳过符号链接目录
                if current_path.is_dir() and current_path.is_symlink():
                    return None
                name = current_path.name
                for pattern in excludes:
                    if fnmatch.fnmatch(name, pattern):
                        return None
                if current_path.is_file():
                    entry_count[0] += 1
                    return {"name": name, "type": "file"}
                try:
                    children = []
                    for item in sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                        child = _build_tree(item, depth + 1)
                        if child is not None:
                            children.append(child)
                    entry_count[0] += 1
                    return {"name": name, "type": "directory", "children": children}
                except (PermissionError, OSError):
                    return {"name": name, "type": "directory", "children": []}

            tree = await asyncio.to_thread(_build_tree, path)
            tree = tree or {"name": path.name, "type": "directory", "children": []}
            return _to_unified_format({
                "success": True, "tree": tree, "root": str(path),
            }, "get_directory_tree")
        except Exception as e:
            logger.error(f"get_directory_tree failed: {dir_path}: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "tree": None
            }, "get_directory_tree")

    async def list_allowed_directories(self) -> Dict[str, Any]:
        """列出允许访问的目录"""
        try:
            dirs = []
            for p in self.allowed_paths:
                p_obj = Path(p)
                try:
                    exists = p_obj.exists()
                    dirs.append({
                        "path": str(p_obj.resolve()),
                        "exists": exists,
                        "type": "directory" if exists and p_obj.is_dir() else "unknown",
                    })
                except Exception:
                    dirs.append({"path": str(p), "exists": False, "type": "unknown"})

            return _to_unified_format({
                "success": True, "directories": dirs, "total": len(dirs),
            }, "list_allowed_directories")
        except Exception as e:
            logger.error(f"list_allowed_directories failed: {e}")
            return _to_unified_format({
                "success": False, "error": str(e), "directories": []
            }, "list_allowed_directories")


# ============================================================
# 第七部分：工具函数导出
# ============================================================

def get_file_tools(task_id: Optional[str] = None) -> FileTools:
    """获取文件工具实例"""
    return FileTools(task_id)


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
        if result.get("success") is False:
            return f"列出目录失败：{result.get('error', '未知错误')}"
        stats = result.get("statistics", {})
        if stats:
            total_size = stats.get("total_size", 0)
            dir_count = stats.get("dir_count", 0)
            file_count = stats.get("file_count", 0)
            size_str = f"{total_size:,}" if total_size < 1073741824 else f"{total_size / 1073741824:.2f} GB"
            return f"列出目录：{dir_count} 个目录，{file_count} 个文件，总大小 {size_str} 字节"
        total = result.get("total", 0)
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
    
    elif tool_name == "grep_file_content":
        if result.get("success") is False:
            return f"搜索内容失败：{result.get('error', '未知错误')}"
        # 【修复 2026-05-01 小沈】B5: 字段名files_matched不存在，实际字段是total
        files_matched = result.get("total", result.get("files_matched", 0))
        total_matches = result.get("total_matches", 0)
        return f"搜索内容完成，找到 {files_matched} 个文件，共 {total_matches} 处匹配"
    
    # 【修复 2026-05-01 小沈】C1: search_files添加专属summary分支
    elif tool_name == "search_files":
        if result.get("success") is False:
            return f"搜索文件失败：{result.get('error', '未知错误')}"
        total = result.get("total", 0)
        return f"搜索完成，找到 {total} 个匹配文件"
    
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
    
    elif tool_name == "read_text_file":
        if result.get("success") is False:
            return f"读取失败：{result.get('error', '未知错误')}"
        line_count = result.get("line_count", 0)
        total_lines = result.get("total_lines", 0)
        return f"成功读取文件：{line_count}/{total_lines} 行"
    
    elif tool_name == "read_media_file":
        if result.get("success") is False:
            return f"读取失败：{result.get('error', '未知错误')}"
        mime = result.get("mime_type", "未知")
        size = result.get("file_size", 0)
        return f"成功读取媒体文件：{mime}，{size:,} 字节"
    
    elif tool_name == "read_batch_file":
        if result.get("success") is False:
            return f"批量读取失败：{result.get('error', '未知错误')}"
        success_count = result.get("success_count", 0)
        failed_count = result.get("failed_count", 0)
        return f"批量读取完成：成功 {success_count} 个，失败 {failed_count} 个"
    
    elif tool_name == "precise_replace_in_file":
        if result.get("success") is False:
            return f"替换失败：{result.get('error', '未知错误')}"
        count = result.get("replaced_count", 0)
        return f"成功替换 {count} 处文本"
    
    elif tool_name == "edit_file":
        if result.get("success") is False:
            return f"编辑失败：{result.get('error', '未知错误')}"
        applied = result.get("applied_edits", 0)
        total = result.get("total_edits", 0)
        dry = result.get("dry_run", False)
        if dry:
            return f"预览模式：{applied}/{total} 处编辑将生效"
        return f"成功应用 {applied}/{total} 处编辑"
    
    elif tool_name == "rename_file":
        if result.get("success") is False:
            return f"重命名失败：{result.get('error', '未知错误')}"
        old = result.get("old_name", "")
        new = result.get("new_name", "")
        return f"成功重命名：{old} -> {new}"
    
    elif tool_name == "glob_files":
        if result.get("success") is False:
            return f"匹配失败：{result.get('error', '未知错误')}"
        total = result.get("total", 0)
        return f"Glob匹配完成，共 {total} 个文件"
    
    elif tool_name == "grep_file_content":
        if result.get("success") is False:
            return f"搜索失败：{result.get('error', '未知错误')}"
        total_files = result.get("total_files", 0)
        total_matches = result.get("total_matches", 0)
        return f"搜索完成：{total_files} 个文件，{total_matches} 处匹配"

    elif tool_name == "get_directory_tree":
        if result.get("success") is False:
            return f"获取目录树失败：{result.get('error', '未知错误')}"
        return f"成功获取目录树结构"
    
    elif tool_name == "list_allowed_directories":
        if result.get("success") is False:
            return f"获取允许目录失败：{result.get('error', '未知错误')}"
        total = result.get("total", 0)
        return f"列出 {total} 个允许访问的目录"
    
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
    except Exception:  # 【修复C2 2026-05-01 小沈】移除冗余ValueError（Exception已包含）
        return 0


# 文件结束
