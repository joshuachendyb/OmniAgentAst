"""
MCP文件操作工具集 - 重写版本

【重构日期】2026-03-19 小强
【参考】FastMCP、MarcusJellinghaus、LangChain、Claude官方Tool Use规范

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

改进点：
1. 使用Pydantic模型定义参数Schema
2. 动态白名单（自动添加存在的盘符）
3. 自动生成JSON Schema
4. 添加input_examples示例
5. 修复search_file_content空pattern安全漏洞

统一返回格式：{status, summary, data, retry_count}

【分页方案更新】2026-04-03 小沈
- read_file: 默认读取500行（READ_FILE_DEFAULT_LIMIT = 500）
- 其他工具: 分页返回（DEFAULT_PAGE_SIZE = 200）
"""

import asyncio
import base64
import inspect
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, get_type_hints

from app.services.context_vars import _current_task_id

from app.services.tools._response import build_success, build_error, build_warning

# 【修改】移除分页限制，2026-04-03 小沈
# 原因：后端必须返回全部真实数据，前端自己控制显示方式（分页/滚动）
# 前端不再依赖 next-page 接口，后端不再做分页处理

# read_file 特殊处理：默认限制500行（因为大文件不能一次性读取到内存）
READ_FILE_DEFAULT_LIMIT = 500

# 其他工具返回全部数据
DEFAULT_PAGE_SIZE = 200  # 每页返回数量，防止LLM上下文爆满 小沈-2026-05-15

from pydantic import BaseModel, Field

from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteTextFileInput,
    ListDirectoryInput,
    SearchFilesInput,
    ReadMediaFileInput,
    GrepFileContentInput,
    EditFileInput,
    FileOperationInput,
    ArchiveToolInput,
    RenameFileInput,
    DataFileFormatInput,
)

from app.services.safety.file.file_safety import OperationType
from app.utils.visualization import get_visualizer
from app.utils.logger import logger
from app.services.tools.tool_meta import get_timeout
from app.services.tools.tool_result_utils import format_file_content_llm, format_output_for_llm, build_next_actions, truncate_data_for_frontend, truncate_text, make_json_safe, DEFAULT_MAX_FILE_CHARS  # 小沈-2026-05-15, 2026-05-20增加截断安全, 2026-05-21小健修复make_json_safe缺失

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
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.tif',
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
        from app.services.agent import get_file_safety_service, get_session_service
        from app.services.agent.mixins.task_tracker import get_task_tracker
        from app.utils.visualization.file_visualization import get_visualizer
        
        self.safety = get_file_safety_service()
        self.task_tracker = get_task_tracker()
        self.visualizer = get_visualizer()
        self.task_id = task_id or _current_task_id.get(None)
        self._sequence = 0
        self._sequence_lock = threading.Lock()
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
    
    async def _read_text_file(
        self,
        file_path: str,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """读取文本文件的完整内容，支持指定行数 - 小沈 2026-05-02 增加 offset/limit 参数
        
        参数组合说明：
        - 无参数：读取全部内容
        - head=N：读取前N行
        - tail=N：读取后N行
        - offset=N, limit=M：从第N行开始读取M行（分页读取）
        """
        try:
            # 【新增 2026-05-02 小沈】二进制文件保护
            is_binary, binary_reason = _is_binary_file(file_path)
            if is_binary:
                return build_error("ERR_FILE_READ_BINARY_FILE", f"{binary_reason}。请使用 read_media_file 工具读取媒体文件（图片/音频/视频）。")
            
            # 【修复 2026-05-01 小沈】参数校验（4合1压缩）
            for _name, _val in [("head", head), ("tail", tail), ("offset", offset), ("limit", limit)]:
                if _val is not None and _val < 1:
                    return build_error("ERR_PARAM_INVALID", f"{_name}必须>=1，当前值: {_val}")

            # 验证参数不能同时使用
            if head is not None and tail is not None:
                return build_error("ERR_PARAM_CONFLICT", "head 和 tail 参数不能同时使用，请只使用其中一个")

            if (head is not None or tail is not None) and (offset is not None or limit is not None):
                return build_error("ERR_PARAM_CONFLICT", "head/tail 与 offset/limit 不能同时使用。head/tail用于快捷读取首尾，offset/limit用于分页读取")

            # 验证路径合法性
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return build_error("ERR_PATH_INVALID", error_msg)

            path = Path(file_path)
            if not path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"文件不存在: {file_path}")

            if not path.is_file():
                return build_error("ERR_PATH_NOT_FILE", f"路径不是文件: {file_path}")

            # 尝试编码读取
            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]
            file_size = path.stat().st_size

            # 【修复 2026-05-01 小沈】OOM防护：预检文件大小
            if file_size > MAX_READ_SIZE:
                return build_error("ERR_FILE_READ_TOO_LARGE", f"文件过大({file_size}字节)，超过读取上限{MAX_READ_SIZE}字节({MAX_READ_SIZE//1024//1024}MB)。请使用head/tail参数分段读取。")

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
                    # 【修复 小沈 2026-05-19】自动检测模式下utf-8因errors='replace'不会抛异常，
                    # 但会产生\uFFFD替换字符。检测到替换字符时继续尝试下一个编码。
                    if encoding is None and '\ufffd' in content:
                        content = None
                        continue
                    used_encoding = enc
                    break
                except Exception:
                    continue

            if content is None:
                return build_error("ERR_FILE_READ_FAILED", f"无法读取文件: {file_path}，已尝试编码: {encodings_to_try}")

            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            # 处理不同的参数组合
            if head is not None:
                # head: 读取前N行
                selected_lines = lines[:min(head, total_lines)]
            elif tail is not None:
                # tail: 读取后N行
                start = max(0, total_lines - tail)
                selected_lines = lines[start:]
            elif offset is not None:
                # offset/limit: 分页读取（从第offset行开始读取limit行）
                start_idx = max(0, offset - 1)
                effective_limit = limit if limit else READ_FILE_DEFAULT_LIMIT
                end_idx = start_idx + effective_limit
                selected_lines = lines[start_idx:end_idx]
            else:
                # 无参数：读取全部
                selected_lines = lines

            result_content = "".join(selected_lines)
            line_count = len(selected_lines)

            # 构造成功返回数据
            _data = {
                "content": result_content,
                "total_lines": total_lines,
                "line_count": line_count,
                "encoding": used_encoding,
                "file_size": file_size,
            }

            if head is not None:
                _data["head"] = head
            elif tail is not None:
                _data["tail"] = tail
            elif offset is not None:
                _data["offset"] = offset
                _data["limit"] = limit
                _data["start_line"] = offset
                _data["end_line"] = offset + line_count - 1

            # 【优化 小沈 2026-05-15】llm_data提供精简内容+行数，避免LLM上下文浪费
            _llm = format_file_content_llm(result_content) if result_content else None


            return build_success(
                _data,
                f"读取文件成功: {file_path} ({line_count}/{total_lines}行, {file_size}字节, 编码:{used_encoding})",
                llm_data=_llm,
                next_actions=build_next_actions([
                    ("edit_file", "编辑文件", "需要修改内容时"),
                    ("grep_file_content", "搜索文件内容", "需要查找特定内容时"),
                ])
            )

        except Exception as e:
            logger.error(f"read_text_file failed: {file_path}: {e}")
            return build_error("ERR_FILE_READ_FAILED", str(e))
    
    async def write_text_file(
        self,
        file_path: str,
        text: str,
        encoding: Optional[str] = None,
        append: bool = False,
        create_parents: bool = True,
        unescape: bool = True
    ) -> Dict[str, Any]:
        """写入文本文件 - 小健 2026-05-03 增加编码自动检测+OOM保护"""
        # 【新增 2026-05-02 小沈】二进制文件保护（最关键，防止破坏二进制文件）
        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            return build_error("ERR_FILE_READ_BINARY_FILE", f"{binary_reason}。write_text_file 仅支持文本文件，禁止写入二进制文件。")
        
        # 【小健 2026-05-03】OOM保护：写入内容超过10MB时拒绝
        content = text
        if content and len(content.encode(encoding or 'utf-8')) > MAX_READ_SIZE:
            return build_error("ERR_FILE_READ_TOO_LARGE", f"内容过大({len(content.encode(encoding or 'utf-8'))}字节)，超过写入上限{MAX_READ_SIZE//1024//1024}MB。请分批写入或使用其他方式处理大文件。")

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
                logger.info(f"write_text_file: 自动将全角标点替换为半角标点({file_path})，如需保留全角请在中文注释中使用")

        if content:
            from app.services.tools.toolhelper.content_quality import check_content_quality
            quality_result = check_content_quality(content=content, file_path=file_path)
            if quality_result.get("is_thought_leak"):
                return build_error("ERR_FILE_CONTENT_BLOCKED", f"内容保护：{quality_result['warning']}")
        if unescape:
            content = content.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", "\"")
        
        validation_error = self._validate_content_format(file_path, content)
        if validation_error:
            return build_error("ERR_FILE_CONTENT_INVALID", validation_error)
        
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return build_error("ERR_PATH_INVALID", error_msg)
        
        path = Path(file_path)
        
        # 【小健 2026-05-03】编码自动检测：encoding=None时自动检测
        if encoding is None:
            if append and path.exists() and path.is_file():
                # 追加模式：检测已有文件的编码
                for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
                    try:
                        with open(path, 'r', encoding=enc) as f:
                            f.read(1024)
                        encoding = enc
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                if encoding is None:
                    encoding = "utf-8"
            else:
                encoding = "utf-8"
        
        if not append and path.exists() and path.is_file():
            old_size = path.stat().st_size
            new_size = len(content.encode(encoding))
            # 【修正 2026-05-19 小健】数据保护：缩小80%以上且非空内容才拦截
            # 原阈值95%过严，重构代码等合法场景经常缩小80%+
            # 豁免条件：新内容为空（有意清空）或缩小比例<80%
            if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
                return build_error("ERR_FILE_DATA_PROTECTION", f"数据保护：新内容({new_size}字节)远小于原始内容({old_size}字节，缩小{100-int(new_size/max(old_size,1)*100)}%)，可能覆盖数据。如确认覆盖，请使用precise_replace_in_file或在text中传入完整内容。")
        
        if not self.task_id:
            self.task_id = _current_task_id.get(None)
        if not self.task_id:
            return build_error("ERR_META_NO_ACTIVE_TASK", "当前没有活跃任务ID，请先创建一个任务")
        
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
                return build_success(
                    {"operation_id": operation_id, "file_path": str(path), "bytes_written": len(content.encode(encoding))},
                    f"写入文件成功: {path} ({len(content.encode(encoding))}字节)",
                    next_actions=build_next_actions([
                        ("read_file", "验证写入结果", "需要确认内容时"),
                    ])
                )
            else:
                return build_error("ERR_FILE_WRITE_FAILED", "写入文件失败，safety拦截")

        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return build_error("ERR_FILE_WRITE_FAILED", str(e))

    async def _write_file(self, file_path: str, text: str, encoding: str = "utf-8",
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
        format: str = "list",
        recursive: bool = False,
        max_depth: int = 10,
        page_token: Optional[str] = None,
        sortBy: str = "name",
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """列出目录内容 — 小沈 2026-05-19 精简参数(8→7)
        P11统一入口：list/tree/statistics三合一
        【FIX 2026-05-20 小健】exclude_patterns已从参数中删除（schema已精简）
        """
        # P17 format校验
        if format not in ("list", "tree"):
            return build_error("ERR_PARAM_INVALID", f"format只支持'list'或'tree'，当前值: '{format}'")

        if max_depth < 1:
            return build_error("ERR_PARAM_INVALID", f"max_depth必须>=1，当前值: {max_depth}")
        if sortBy not in ("name", "size", "mtime"):
            return build_error("ERR_PARAM_INVALID", f"sortBy只支持'name'/'size'/'mtime'，当前值: '{sortBy}'")
        
        # format="tree" 分支：委托 get_directory_tree 逻辑 — 小沈 2026-05-18
        if format == "tree":
            tree_result = await self._get_directory_tree(
                dir_path=dir_path,
                max_depth=max_depth,
            )
            # 小健 2026-05-19: tree模式补充statistics统计信息
            if tree_result.get("code") == "SUCCESS" and "data" in tree_result:
                tree_data = tree_result["data"]
                if isinstance(tree_data, dict) and "tree" in tree_data:
                    tree_obj = tree_data["tree"]
                    def _count_tree(node: dict) -> tuple:
                        files = dirs = total_size = 0
                        if node.get("type") == "file":
                            files = 1
                            total_size = node.get("size", 0)
                        elif node.get("type") == "directory":
                            dirs = 1
                        for child in node.get("children", []):
                            cf, cd, cs = _count_tree(child)
                            files += cf; dirs += cd; total_size += cs
                        return files, dirs, total_size
                    f, d, s = _count_tree(tree_obj)
                    tree_data["statistics"] = {"file_count": f, "dir_count": d, "total_size": s}
            return tree_result

        # 验证路径合法性
        is_valid, error_msg = self._validate_path(dir_path)
        if not is_valid:
            return build_error("ERR_PATH_INVALID", error_msg)

        path = Path(dir_path)

        # 解码page_token
        start_offset = 0
        if page_token:
            try:
                start_offset = decode_page_token(page_token)
            except Exception as e:
                return build_error("ERR_PARAM_INVALID", f"Invalid page token: {e}")

        try:
            if not path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"Directory not found: {dir_path}")

            if not path.is_dir():
                return build_error("ERR_FILE_PATH_NOT_DIR", f"Not a directory: {dir_path}")

            # 异步执行目录遍历
            # 【修复 2026-05-10 小健】超时自检：递归遍历大目录时主动退出
            _list_deadline = time.monotonic() + get_timeout("list_directory") - 2
            _list_timed_out = False

            def _list_sync():
                nonlocal _list_timed_out
                import fnmatch
                _exclude = []  # exclude_patterns已从参数中移除 - 小健 2026-05-20
                entries = []
                stats = {"total_size": 0, "dir_count": 0, "file_count": 0}
                ext_counter: Dict[str, int] = {}
                size_bins = {"<1KB": 0, "1KB-10KB": 0, "10KB-100KB": 0, "100KB-1MB": 0, ">1MB": 0}

                if recursive:
                    def _scan_recursive(current_path: Path, current_depth: int):
                        nonlocal _list_timed_out
                        if current_depth > max_depth:
                            return
                        if time.monotonic() > _list_deadline:
                            _list_timed_out = True
                            logger.warning(f"[list_directory] 超时自检触发，已收集{len(entries)}条，提前返回")
                            return
                        try:
                            for item in current_path.iterdir():
                                if _list_timed_out:
                                    return
                                try:
                                    if not include_hidden and item.name.startswith('.'):
                                        continue
                                    if any(fnmatch.fnmatch(item.name, p) for p in _exclude):
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
                                        if _list_timed_out:
                                            return
                                    else:
                                        stats["total_size"] += st.st_size
                                        stats["file_count"] += 1
                                        ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                                        ext_counter[ext] = ext_counter.get(ext, 0) + 1
                                        sz = st.st_size
                                        if sz < 1024:
                                            size_bins["<1KB"] += 1
                                        elif sz < 10240:
                                            size_bins["1KB-10KB"] += 1
                                        elif sz < 102400:
                                            size_bins["10KB-100KB"] += 1
                                        elif sz < 1048576:
                                            size_bins["100KB-1MB"] += 1
                                        else:
                                            size_bins[">1MB"] += 1
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
                            if any(fnmatch.fnmatch(item.name, p) for p in _exclude):
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
                                ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                                ext_counter[ext] = ext_counter.get(ext, 0) + 1
                                sz = st.st_size
                                if sz < 1024:
                                    size_bins["<1KB"] += 1
                                elif sz < 10240:
                                    size_bins["1KB-10KB"] += 1
                                elif sz < 102400:
                                    size_bins["10KB-100KB"] += 1
                                elif sz < 1048576:
                                    size_bins["100KB-1MB"] += 1
                                else:
                                    size_bins[">1MB"] += 1
                        except (PermissionError, OSError):
                            continue

                return entries, stats["total_size"], stats["dir_count"], stats["file_count"], ext_counter, size_bins

            all_entries, total_size, dir_count, file_count, file_types, size_distribution = await asyncio.to_thread(_list_sync)

            # 排序：目录优先，然后按sortBy
            if sortBy == "size":
                all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
            elif sortBy == "mtime":
                all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("mtime", 0)), reverse=True)
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
                "file_types": file_types, "size_distribution": size_distribution,
            }

            if total > MAX_DISPLAY_ENTRIES:
                display_entries = all_entries[start_offset:start_offset + MAX_DISPLAY_ENTRIES]

                logger.warning(
                    f"[list_directory] Large directory truncated: path={path}, "
                    f"total={total}, dir_count={dir_count}, file_count={file_count}, "
                    f"displayed={MAX_DISPLAY_ENTRIES}"
                )

                return build_success(
                    {
                        "entries": display_entries, "total": total, "directory": str(path),
                        "truncated": True, "dir_count": dir_count, "file_count": file_count,
                        "statistics": statistics,
                        "next_page_token": encode_page_token(start_offset + MAX_DISPLAY_ENTRIES) if start_offset + MAX_DISPLAY_ENTRIES < total else None
                    },
                    f"列出目录成功: {path} ({total}项，已截断显示前{MAX_DISPLAY_ENTRIES}项)",
                    llm_data={
                        "目录": str(path), "总数": total, "目录数": dir_count, "文件数": file_count,
                        "条目预览": [e.get("name","") for e in display_entries[:30]],
                        "截断": True
                    },
                    next_actions=build_next_actions([
                        ("search_files", "搜索文件", "需要查找特定文件时"),
                        ("read_file", "读取文件", "需要查看文件内容时"),
                    ])
                )

            return build_success(
                {
                    "entries": all_entries, "total": total, "directory": str(path),
                    "statistics": statistics, "next_page_token": None
                },
                f"列出目录成功: {path} ({total}项)",
                llm_data={
                    "目录": str(path), "总数": total,
                    "条目预览": [e.get("name","") for e in all_entries[:30]]
                },
                next_actions=build_next_actions([
                    ("search_files", "搜索文件", "需要查找特定文件时"),
                    ("read_file", "读取文件", "需要查看文件内容时"),
                ])
            )

        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return build_error("ERR_FILE_LIST_DIR_FAILED", str(e))
    
    async def _delete_file(
        self,
        file_path: str,
        recursive: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """删除文件或目录 - 小健 2026-05-03 默认放入回收站，force=True永久删除"""
        # 验证路径合法性
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return build_error("ERR_PATH_INVALID", error_msg)
        
        path = Path(file_path)
        
        try:
            if not path.exists():
                return build_success(None, f"文件不存在，无需删除(P16幂等): {file_path}")
            
            if not self.task_id:
                self.task_id = _current_task_id.get(None)
            if not self.task_id:
                return build_error("ERR_META_NO_ACTIVE_TASK", "当前没有活跃任务ID，请先创建一个任务")

            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.DELETE,
                source_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义删除操作 - 小沈 2026-05-19 追踪删除方式
            deletion_info = {}  # 可变容器追踪删除方式: "send2trash" 或 "permanent"
            def _delete_sync():
                if force:
                    # force=True: 永久删除（不放入回收站）
                    if path.is_dir():
                        if recursive:
                            shutil.rmtree(str(path), onerror=_remove_readonly)
                        else:
                            path.rmdir()
                    else:
                        if path.exists() and not os.access(str(path), os.W_OK):
                            path.chmod(path.stat().st_mode | 0o200)
                        path.unlink()
                    return True
                else:
                    # force=False: 放入回收站（默认，更安全）
                    try:
                        import send2trash
                        send2trash.send2trash(str(path))
                        deletion_info["method"] = "send2trash"
                        return True
                    except ImportError:
                        # send2trash未安装时回退到永久删除
                        logger.warning("send2trash未安装，回退到永久删除")
                        if path.is_dir():
                            if recursive:
                                shutil.rmtree(str(path), onerror=_remove_readonly)
                            else:
                                path.rmdir()
                        else:
                            path.unlink()
                        deletion_info["method"] = "permanent"
                        return True
                    except Exception as e:
                        # send2trash失败时回退到永久删除
                        logger.warning(f"send2trash失败: {e}，回退到永久删除")
                        if path.is_dir():
                            if recursive:
                                shutil.rmtree(str(path), onerror=_remove_readonly)
                            else:
                                path.rmdir()
                        else:
                            path.unlink()
                        deletion_info["method"] = "permanent"
                        return True
            
            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_delete_sync
            )
            
            if success:
                delete_mode = "永久删除" if force else "放入回收站"
                data = {
                    "operation_id": operation_id,
                    "deleted_path": str(path),
                }
                caps = []
                if not force:
                    method = deletion_info.get("method", "send2trash")
                    if method == "send2trash":
                        caps = ["send2trash"]
                    else:
                        caps = ["os.remove"]
                return build_success(data, f"文件已{delete_mode}: {file_path}")
            else:
                return build_error("ERR_FILE_DELETE_FAILED", "删除文件失败，safety拦截")

        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return build_error("ERR_FILE_DELETE_FAILED", str(e))
    
    async def _move_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """移动或重命名文件 - 小健 2026-05-02 增加overwrite"""
        # 验证源路径
        is_valid_src, error_msg_src = self._validate_path(source_path)
        if not is_valid_src:
            return build_error("ERR_PATH_INVALID", f"源路径{error_msg_src}")

        # 验证目标路径
        is_valid_dst, error_msg_dst = self._validate_path(destination_path)
        if not is_valid_dst:
            return build_error("ERR_PATH_INVALID", f"目标路径{error_msg_dst}")
        
        src = Path(source_path)
        dst = Path(destination_path)
        
        try:
            if not src.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"源文件不存在: {source_path}")
            
            if not self.task_id:
                self.task_id = _current_task_id.get(None)
            if not self.task_id:
                return build_error("ERR_META_NO_ACTIVE_TASK", "当前没有活跃任务ID，请先创建一个任务")

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
                return build_success(
                    {"operation_id": operation_id, "source": str(src), "destination": str(dst)},
                    f"已移动: {src.name} -> {dst}"
                )
            return build_error("ERR_FILE_MOVE_FAILED", "移动文件失败")

        except Exception as e:
            logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
            return build_error("ERR_FILE_MOVE_FAILED", str(e))
    
    async def search_files(
        self,
        pattern: str,
        search_dir: str,
        recursive: bool = True,
        max_depth: int = 50,
        ignore_case: bool = True,
        type: Optional[Literal["file", "directory"]] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """搜索文件名 — 小沈 2026-05-19 精简参数(9→7)
        【FIX 2026-05-20 小健】exclude_patterns已从参数中删除（schema已精简）
        【FIX 2026-05-21 小健】sortBy未定义bug修复（schema精简时遗漏了内部引用）
        """
        sortBy = "name"
        is_valid, error_msg = self._validate_path(search_dir)
        if not is_valid:
            return build_error("ERR_PATH_INVALID", error_msg)

        if not pattern or not pattern.strip():
            return build_error("ERR_PARAM_INVALID", "文件名匹配模式不能为空，请提供有效的文件名模式")

        search_path = Path(os.path.expanduser(search_dir))

        try:
            if not search_path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"搜索目录不存在: {search_dir}")

            _deadline = time.monotonic() + get_timeout("search_files") - 2

            _pagination_info = {}
            excludePatterns = None
            def _search_sync():
                all_matches = []
                seen_files = set()
                start_offset = decode_page_token(page_token) if page_token else 0
                seen_count = 0

                import fnmatch

                for root, dirs, files in os.walk(search_path):
                    if time.monotonic() > _deadline:
                        logger.warning(f"[search_files] 超时自检触发，已遍历{seen_count}条，提前返回{len(all_matches)}个匹配")
                        break
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
                        matched = fnmatch.fnmatch(dirname, pattern) if ignore_case else fnmatch.fnmatchcase(dirname, pattern)
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
                        if any(fnmatch.fnmatch(filename, pat) for pat in excludePatterns or []):
                            continue
                        matched = fnmatch.fnmatch(filename, pattern) if ignore_case else fnmatch.fnmatchcase(filename, pattern)
                        if not matched:
                            continue

                        file_path = Path(root) / filename
                        file_str = str(file_path.relative_to(search_path))

                        if file_str in seen_files:
                            continue

                        seen_count += 1

                        if seen_count <= start_offset:
                            seen_files.add(file_str)
                            continue
                        seen_files.add(file_str)

                        try:
                            st = file_path.stat()
                            size = st.st_size
                        except (PermissionError, OSError):
                            st = None
                            size = 0

                        all_matches.append({
                            "name": filename,
                            "path": file_str,
                            "size": size,
                            "type": "file",
                            "mtime": st.st_mtime if st is not None and sortBy == "mtime" else None
                        })

                _pagination_info['start_offset'] = start_offset
                return all_matches

            all_matches = await asyncio.to_thread(_search_sync)
            start_offset = _pagination_info.get('start_offset', 0)

            if sortBy == "mtime":
                all_matches.sort(key=lambda x: x.get("mtime", 0) or 0, reverse=True)
            elif sortBy == "name":
                all_matches.sort(key=lambda x: x.get("name", ""))
            elif sortBy == "size":
                all_matches.sort(key=lambda x: x.get("size", 0) or 0, reverse=True)

            total = len(all_matches)

            logger.info(f"[search_files] 搜索完成: pattern={pattern}, search_dir={search_dir}, total={total}, matches数量={len(all_matches)}")

            if total > DEFAULT_PAGE_SIZE:
                total_pages = (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE
                page_matches = all_matches[:DEFAULT_PAGE_SIZE]
                has_more = True
                next_offset = start_offset + DEFAULT_PAGE_SIZE
                next_page_token = encode_page_token(next_offset) if has_more else None
            else:
                page_matches = all_matches
                total_pages = 1
                has_more = False
                next_page_token = None

            return build_success(
                {
                    "pattern": pattern,
                    "search_dir": str(search_path),
                    "matches": page_matches,
                    "total": total,
                    "page": 1,
                    "total_pages": total_pages,
                    "page_size": DEFAULT_PAGE_SIZE,
                    "next_page_token": next_page_token,
                    "has_more": has_more,
                },
                f"搜索完成，共{total}个匹配",
                llm_data={
                    "模式": pattern, "搜索目录": str(search_path), "匹配数": total,
                    "文件预览": [m.get("path","") if isinstance(m,dict) else str(m) for m in page_matches[:20]],
                    "has_more": has_more,
                },
                next_actions=build_next_actions([("read_file", "读取找到的文件", "需要查看内容时")]),
            )

        except Exception as e:
            logger.error(f"Failed to search files: {e}")
            return build_error("ERR_FILE_SEARCH_FAILED", str(e))
    
    async def _copy_file(
        self,
        source_path: str,
        destination_path: str,
        recursive: bool = False,
        overwrite: bool = False,
        preserve_metadata: bool = True,
    ) -> Dict[str, Any]:
        """复制文件或目录 - 小健 2026-05-02 增加preserve_metadata"""
        from app.services.tools.toolhelper.file_helpers import copy_file_impl
        
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
            get_next_sequence_func=self._get_next_sequence,
        )

    async def _get_file_info(
        self,
        file_path: str,
        follow_symlinks: bool = True,
    ) -> Dict[str, Any]:
        """获取文件信息 - 小健 2026-05-02 增加follow_symlinks"""
        from app.services.tools.toolhelper.file_helpers import get_file_info_impl
        
        return await get_file_info_impl(
            file_path=file_path,
            validate_path_func=self._validate_path,
            follow_symlinks=follow_symlinks,
        )

    async def _batch_rename(
        self,
        directory: str,
        pattern: str,
        replacement: str,
        recursive: bool = False,
        preview: bool = False,
        conflict_strategy: Literal["skip", "overwrite", "append_number"] = "skip",
    ) -> Dict[str, Any]:
        """批量重命名文件"""
        from app.services.tools.toolhelper.file_helpers import batch_rename_impl
        
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
            get_next_sequence_func=self._get_next_sequence,
        )

    async def _compress_files(
        self,
        source_path: str,
        output_path: str,
        format: str = "zip",
        exclude_patterns: Optional[List[str]] = None,
        compression_level: int = 6,
        overwrite: bool = False,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """压缩文件或目录"""
        from app.services.tools.toolhelper.file_helpers import compress_files_impl
        
        return await compress_files_impl(
            source_path=source_path,
            output_path=output_path,
            format=format,
            exclude_patterns=exclude_patterns,
            compression_level=compression_level,
            overwrite=overwrite,
            password=password,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
            get_next_sequence_func=self._get_next_sequence,
        )

    async def _extract_archive(
        self,
        archive_path: str,
        output_dir: Optional[str] = None,
        overwrite: bool = False,
        password: Optional[str] = None,
        preserve_permissions: bool = True,
    ) -> Dict[str, Any]:
        """解压压缩文件"""
        from app.services.tools.toolhelper.file_helpers import extract_archive as _extract_archive
        
        return _extract_archive(
            archive_path=archive_path,
            output_dir=output_dir,
            overwrite=overwrite,
            password=password,
            preserve_permissions=preserve_permissions,
        )

    async def _get_file_hash(
        self,
        file_path: str,
        algorithm: str = "sha256",
        verify_against: Optional[str] = None,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """计算文件哈希值"""
        from app.services.tools.toolhelper.file_helpers import get_file_hash as _get_file_hash
        
        return _get_file_hash(
            file_path=file_path,
            algorithm=algorithm,
            verify_against=verify_against,
            timeout=timeout,
        )

    async def _file_statistics(
        self,
        directory: str,
        recursive: bool = True,
        max_depth: int = 100000,
        filters: Optional[Dict[str, Any]] = None,
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """统计文件系统信息"""
        from app.services.tools.toolhelper.file_helpers import file_statistics_impl
        
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
            get_next_sequence_func=self._get_next_sequence,
        )

    async def _file_checksum(
        self,
        file_path: str,
        algorithm: str = "sha256",
        verify_hash: Optional[str] = None,
        chunk_size: int = 65536,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """计算文件校验和"""
        from app.services.tools.toolhelper.file_helpers import file_checksum_impl
        
        return await file_checksum_impl(
            file_path=file_path,
            algorithm=algorithm,
            verify_hash=verify_hash,
            chunk_size=chunk_size,
            timeout=timeout,
            validate_path_func=self._validate_path,
            safety_service=self.safety,
            task_id=self.task_id,
            record_operation_func=self.safety.record_operation,
            execute_with_safety_func=self.safety.execute_with_safety,
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
                return build_error("ERR_PATH_INVALID", error_msg)

            path = Path(file_path)
            if not path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"文件不存在: {file_path}")
            if not path.is_file():
                return build_error("ERR_PATH_NOT_FILE", f"路径不是文件: {file_path}")

            file_size = path.stat().st_size
            if file_size > MAX_MEDIA_READ_SIZE:
                return build_error("ERR_FILE_READ_TOO_LARGE", f"媒体文件过大({file_size}字节)，超过读取上限{MAX_MEDIA_READ_SIZE//1024//1024}MB")

            suffix = path.suffix.lower()
            if suffix == '.pdf':
                return build_error("ERR_DOC_FORMAT_NOT_SUPPORTED", "PDF文件请使用 read_document 工具读取，read_media_file 不支持PDF")

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
            }
            mime_type = mime_map.get(suffix, "application/octet-stream")

            def _read_sync():
                with open(path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')

            b64_data = await asyncio.to_thread(_read_sync)
            return build_success(
                {"file_name": path.name, "mime_type": mime_type, "file_size": path.stat().st_size, "base64_data": b64_data},
                f"已读取媒体文件: {path.name}",
                llm_data={"文件名": path.name, "类型": mime_type, "大小": f"{path.stat().st_size:,}字节"},
            )
        except Exception as e:
            logger.error(f"read_media_file failed: {file_path}: {e}")
            return build_error("ERR_FILE_READ_FAILED", str(e))

    async def _read_batch_file(
        self,
        file_paths: List[str],
    ) -> Dict[str, Any]:
        """同时读取多个文本文件 - 小沈 2026-05-01"""
        if not file_paths:
            return build_error("ERR_PARAM_INVALID", "文件路径列表为空")

        # 【修复 2026-05-01 小沈】OOM防护：批量文件数上限
        if len(file_paths) > MAX_BATCH_FILE_COUNT:
            return build_error("ERR_PARAM_INVALID", f"批量读取文件数({len(file_paths)})超过上限{MAX_BATCH_FILE_COUNT}，请分批读取")

        # 【修复 2026-05-01 小沈】B1: 添加Semaphore并发限制，防止大量文件并发读取耗尽文件句柄
        semaphore = asyncio.Semaphore(20)

        async def _read_single(fp: str) -> Dict[str, Any]:
            async with semaphore:
                # 【新增 2026-05-02 小沈】二进制文件保护
                is_binary, binary_reason = _is_binary_file(fp)
                if is_binary:
                    return build_error("ERR_FILE_READ", f"{binary_reason}。已跳过该文件。: {fp}", data={"file_path": fp})
                
                is_valid, error_msg = self._validate_path(fp)
                if not is_valid:
                    return build_error("ERR_FILE_READ", f"{error_msg}: {fp}", data={"file_path": fp})
                path = Path(fp)
                if not path.exists():
                    return build_error("ERR_FILE_NOT_FOUND", f"文件不存在: {fp}", data={"file_path": fp})
                
                # 【修复 2026-05-01 小沈】OOM防护：单文件大小预检
                try:
                    if path.stat().st_size > MAX_READ_SIZE:
                        return build_error("ERR_FILE_READ_TOO_LARGE", f"文件过大({path.stat().st_size}字节)，超过读取上限{MAX_READ_SIZE//1024//1024}MB: {fp}", data={"file_path": fp})
                except OSError as e:
                    return build_error("ERR_FILE_READ", f"{e}: {fp}", data={"file_path": fp})
                
                try:
                    for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
                        try:
                            # 【修复 2026-04-30 小沈】用with语句读取，避免文件句柄泄漏
                            def _read_with(e=enc):
                                with open(path, 'r', encoding=e, errors='replace') as f:
                                    return f.read()
                            content = await asyncio.to_thread(_read_with)
                            # 【修复 小沈 2026-05-19】同_read_text_file：errors='replace'导致utf-8不抛异常
                            if '\ufffd' in content:
                                continue
                            return build_success({"file_path": fp, "content": content, "encoding": enc, "file_size": path.stat().st_size}, f"读取成功: {fp}")
                        except Exception:
                            continue
                    return build_error("ERR_FILE_READ_FAILED", f"无法解码文件: {fp}", data={"file_path": fp})
                except Exception as e:
                    return build_error("ERR_FILE_READ", f"{e}: {fp}", data={"file_path": fp})

        results = await asyncio.gather(*[_read_single(fp) for fp in file_paths])
        success_count = sum(1 for r in results if r.get("code") == "SUCCESS")
        # 【修复 小健 2026-05-16】llm_data包含每个文件内容，≤5K全给，>5K给前800字符预览
        _llm_files = []
        for r in results:
            _rd = r.get("data", {})
            if r.get("code") == "SUCCESS":
                content = _rd.get("content", "")
                if len(content) <= 5000:
                    _llm_files.append({"路径": _rd.get("file_path", ""), "内容": content})
                else:
                    _llm_files.append({"路径": _rd.get("file_path", ""), "内容预览": content[:800], "总长度": f"{len(content)}字符"})
            else:
                _llm_files.append({"路径": _rd.get("file_path", ""), "失败": r.get("message", "未知错误")})
        _llm = {
            "总数": f"{len(results)}个文件",
            "成功": f"{success_count}个",
            "失败": f"{len(results) - success_count}个",
            "文件详情": _llm_files,
        }
        return build_success(
            {"results": results, "total": len(results), "success_count": success_count, "failed_count": len(results) - success_count},
            f"批量读取完成: 成功{success_count}个, 失败{len(results) - success_count}个",
            llm_data=_llm,
        )

    async def _precise_replace_in_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        ignore_case: bool = False,
        dry_run: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """精确替换文件中的字符串 — 小健 2026-05-19 增加dry_run支持"""
        # 【修复 2026-04-30 小沈】空old_string拒绝：content.replace("", x)会在每个字符间插入，导致内容爆炸
        if not old_string:
            return build_error("ERR_PARAM_INVALID", "old_string不能为空，空字符串替换会导致内容爆炸")

        if not self.task_id:
            self.task_id = _current_task_id.get(None)
        if not self.task_id:
            return build_error("ERR_META_NO_ACTIVE_TASK", "当前没有活跃任务ID，请先创建一个任务")

        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            return build_error("ERR_FILE_READ_BINARY_FILE", f"{binary_reason}。请使用对应的专业工具操作二进制文件。")

        try:
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return build_error("ERR_PATH_INVALID", error_msg)

            path = Path(file_path)
            if not path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"文件不存在: {file_path}")

            if path.stat().st_size > MAX_READ_SIZE:
                return build_error("ERR_FILE_READ_TOO_LARGE", f"文件过大({path.stat().st_size}字节)，超过替换上限{MAX_READ_SIZE//1024//1024}MB")

            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.MODIFY,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )

            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]

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

                replace_result['count'] = count
                replace_result['used_enc'] = used_enc
                replace_result['name'] = path.name

                if dry_run:
                    replace_result['preview'] = True
                    replace_result['diff_info'] = f"将替换 {count} 处匹配: '{old_string[:50]}' -> '{new_string[:50]}'"
                    return True

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
                data = {
                    "replaced_count": replace_result['count'],
                    "encoding": replace_result['used_enc'],
                    "file_path": str(path),
                    "file_name": replace_result['name'],
                    "operation_id": operation_id,
                }
                if replace_result.get('preview'):
                    data["preview"] = True
                    data["diff_info"] = replace_result.get('diff_info', '')
                return build_success(
                    data,
                    f"已替换 {replace_result['count']} 处匹配",
                    next_actions=build_next_actions([("read_file", "验证修改结果", "需要确认修改时")]),
                )
            return build_error("ERR_FILE_REPLACE_FAILED", "文件替换失败，safety拦截")

        except Exception as e:
            logger.error(f"precise_replace_in_file failed: {file_path}: {e}")
            return build_error("ERR_FILE_REPLACE_FAILED", str(e))

    async def _apply_edits(
        self,
        file_path: str,
        edits: List[Dict[str, str]],
        dry_run: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """高级编辑文件，支持多处编辑和预览（内部方法） - 小沈 2026-05-01, 小健 2026-05-19 参数名dryRun→dry_run"""
        try:
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return build_error("ERR_PATH_INVALID", error_msg)

            if not self.task_id:
                self.task_id = _current_task_id.get(None)
            if not self.task_id:
                return build_error("ERR_META_NO_ACTIVE_TASK", "当前没有活跃任务ID，请先创建一个任务")

            is_binary, binary_reason = _is_binary_file(file_path)
            if is_binary:
                return build_error("ERR_FILE_READ_BINARY_FILE", f"{binary_reason}。请使用对应的专业工具操作二进制文件。")

            path = Path(file_path)
            if not path.exists():
                return build_error("ERR_FILE_NOT_FOUND", f"文件不存在: {file_path}")

            if path.stat().st_size > MAX_READ_SIZE:
                return build_error("ERR_FILE_READ_TOO_LARGE", f"文件过大({path.stat().st_size}字节)，超过编辑上限{MAX_READ_SIZE//1024//1024}MB")

            operation_id = self.safety.record_operation(
                task_id=self.task_id,
                operation_type=OperationType.MODIFY,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )

            encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "utf-8-sig"] if encoding else ["utf-8", "gbk", "gb2312", "utf-8-sig"]

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
                        results.append({"index": i, "ok": False, "reason": "oldText 为空"})
                        continue
                    idx = modified.find(old_text)
                    if idx == -1:
                        results.append({"index": i, "ok": False, "reason": f"未找到匹配文本: {old_text[:50]}"})
                        continue
                    modified = modified[:idx] + new_text + modified[idx + len(old_text):]
                    results.append({"index": i, "ok": True, "old_text": old_text[:50], "new_text": new_text[:50]})

                applied = sum(1 for r in results if r["ok"])
                if not dry_run and applied > 0:
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
                edit_result['preview'] = modified if dry_run else None
                edit_result['dry_run'] = dry_run
                edit_result['used_enc'] = used_enc
                return True

            success = await asyncio.to_thread(
                self.safety.execute_with_safety,
                operation_id=operation_id,
                operation_func=_edit_sync
            )
            if success:
                return build_success(
                    {
                        "applied_edits": edit_result['applied_edits'],
                        "total_edits": edit_result['total_edits'],
                        "results": edit_result['results'],
                        "preview": edit_result['preview'],
                        "dry_run": edit_result['dry_run'],
                        "encoding": edit_result['used_enc'],
                        "operation_id": operation_id,
                    },
                    f"已应用 {edit_result['applied_edits']}/{edit_result['total_edits']} 处编辑"
                )
            return build_error("ERR_FILE_EDIT_FAILED", "文件编辑失败，safety拦截")
        except Exception as e:
            logger.error(f"edit_file failed: {file_path}: {e}")
            return build_error("ERR_FILE_EDIT_FAILED", str(e))

    async def grep_file_content(
        self,
        pattern: str,
        search_dir: Optional[str] = None,
        output_mode: Optional[Literal["content", "files_with_matches", "count"]] = None,
        glob: Optional[str] = None,
        context: Optional[Dict[str, int]] = None,
        ignore_case: bool = True,
        multiline: bool = False,
        head_limit: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """基于正则的内容搜索 — 小沈 2026-05-19 精简参数(13→9)"""
        # 从context对象解构上下文行数 — 小沈 2026-05-19
        after_lines = None
        before_lines = None
        context_lines = None
        if context:
            after_lines = context.get("after")
            before_lines = context.get("before")
            context_lines = context.get("around")
        show_line_no = True  # 小沈 2026-05-19: 永远显示行号
        type = None  # ⚠️ 警告: 已从Schema移除，用glob替代，后续视需求决定是否恢复
        try:
            search_path = Path(search_dir).resolve() if search_dir else Path.cwd().resolve()
            is_valid, error_msg = self._validate_path(str(search_path))
            if not is_valid:
                return build_error("ERR_PATH_INVALID", error_msg)

            if not pattern:
                return build_error("ERR_PARAM_INVALID", "搜索模式不能为空")

            type_ext_map = {
                "js": "*.js", "ts": "*.ts", "tsx": "*.tsx", "jsx": "*.jsx",
                "py": "*.py", "rs": "*.rs", "go": "*.go", "java": "*.java",
                "html": "*.html", "css": "*.css", "json": "*.json", "yaml": "*.yaml",
                "md": "*.md", "xml": "*.xml", "c": "*.c", "cpp": "*.cpp",
                "h": "*.h", "rust": "*.rs",
            }
            file_glob = glob
            if not file_glob and type:
                file_glob = type_ext_map.get(type)
                if file_glob is None:
                    return build_error("ERR_PARAM_INVALID", f"不支持的语言类型: '{type}'，可用: {', '.join(sorted(type_ext_map.keys()))}")

            # 【修复 2026-05-10 小健】超时自检：os.walk循环中检查耗时，超时提前返回已有结果
            _grep_deadline = time.monotonic() + get_timeout("grep_file_content") - 2

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
                    # 【修复 2026-05-10 小健】超时自检：接近deadline时提前返回
                    if time.monotonic() > _grep_deadline:
                        logger.warning(f"[grep_file_content] 超时自检触发，已匹配{match_count}条，提前返回{len(results)}个文件结果")
                        break
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
                            # 小健 2026-05-19: 多编码尝试，支持gbk等中文编码文件
                            lines = None
                            for _enc in ('utf-8', 'gbk', 'gb2312', 'utf-8-sig'):
                                try:
                                    with open(file_path, 'r', encoding=_enc, errors='strict') as f:
                                        lines = f.readlines()
                                    break
                                except (UnicodeDecodeError, UnicodeError):
                                    continue
                            if lines is None:
                                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                    lines = f.readlines()
                        except Exception:
                            continue

                        file_matches = []
                        if multiline:
                            content = ''.join(lines)
                            for m in regex.finditer(content):
                                match_count += 1
                                line_no = content[:m.start()].count('\n') + 1
                                file_matches.append({
                                    "line": line_no if show_line_no else None,
                                    "content": m.group(),
                                })
                                if head_limit is not None and match_count >= head_limit:
                                    break
                        else:
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

            return build_success(
                {
                    "matches": page_results,
                    "total_files": total,
                    "total_matches": total_matches,
                    "pattern": pattern,
                    "search_dir": str(search_path),
                    "output_mode": output_mode or "content",
                    "has_more": has_more,
                    "next_page_token": next_page_token,
                },
                f"搜索完成，匹配{total_matches}行，涉及{total}个文件",
                llm_data={
                    "模式": pattern, "搜索目录": str(search_path),
                    "匹配文件数": total, "匹配行数": total_matches,
                    "预览": make_json_safe(page_results[:10], max_str_len=200),
                    "has_more": has_more,
                },
                next_actions=build_next_actions([
                    ("read_file", "读取匹配行上下文", "需要查看完整内容时"),
                    ("edit_file", "编辑匹配内容", "需要修改时"),
                ]),
            )
        except Exception as e:

            return build_error("ERR_FILE_CONTENT_SEARCH_FAILED", str(e))

    async def get_directory_tree(self, dir_path: str) -> Dict[str, Any]:
        """获取目录树（委托给 _get_directory_tree 实现）
        
        规范：§11.10 浏览器禁止执行write、chmod等shell操作
        通过 path_utils.validate_and_normalize 实现安全路径检查
        """
        return await self._get_directory_tree(dir_path)

    async def _get_directory_tree(
        self,
        dir_path: str,
        excludePatterns: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取目录的递归JSON树结构 - 小沈 2026-05-01"""
        try:
            is_valid, error_msg = self._validate_path(dir_path)
            if not is_valid:
                return build_error("ERR_PATH_INVALID", error_msg)

            path = Path(dir_path)
            if not path.exists():
                return build_error("ERR_FILE_DIRECTORY_NOT_FOUND", f"目录不存在: {dir_path}")
            if not path.is_dir():
                return build_error("ERR_FILE_PATH_NOT_DIR", f"不是目录: {dir_path}")

            # 【修复 2026-05-01 小沈】默认max_depth防止无限递归
            effective_max_depth = max_depth if max_depth is not None else 10
            excludes = excludePatterns or []
            import fnmatch
            entry_count = [0]
            # 【修复 2026-05-10 小健】超时自检
            _tree_deadline = time.monotonic() + get_timeout("get_directory_tree") - 2
            _tree_timed_out = False

            def _build_tree(current_path: Path, depth: int = 0) -> Optional[Dict[str, Any]]:
                nonlocal _tree_timed_out
                if _tree_timed_out:
                    return None
                if depth > effective_max_depth:
                    return None
                # 【修复 2026-05-01 小沈】条目数上限防护
                if entry_count[0] >= MAX_PAGE_SIZE:
                    return None
                # 【修复 2026-05-01 小沈】符号链接循环防护：跳过符号链接目录
                if current_path.is_dir() and current_path.is_symlink():
                    return None
                if time.monotonic() > _tree_deadline:
                    _tree_timed_out = True
                    logger.warning(f"[get_directory_tree] 超时自检触发，已收集{entry_count[0]}条，提前返回")
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
            return build_success(
                {"tree": tree, "root": str(path)},
                f"已获取目录树: {dir_path}",
                llm_data={"目录": str(path), "树形结构根节点": tree.get("name",""), "子项数": len(tree.get("children",[]))},
                next_actions=build_next_actions([
                    ("search_files", "搜索文件", "需要查找特定文件时"),
                    ("read_file", "读取文件", "需要查看文件内容时"),
                ])
            )
        except Exception as e:
            logger.error(f"get_directory_tree failed: {dir_path}: {e}")
            return build_error("ERR_FILE_LIST_DIR_FAILED", str(e))
    
    # ============================================================
    # 第九部分：精简合并工具（v2.0）— 小沈 2026-05-18
    # ============================================================
    
    async def read_file(
        self,
        file_paths: List[str],
        head: Optional[int] = None,
        tail: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        读取文本文件（统一入口）— 小沈 2026-05-18
        【小沈 2026-05-19】合并file_path+file_paths→file_paths
        
        P11统一入口：合并 read_text_file + read_batch_file
        - 传1个路径：单文件模式，支持 head/tail/offset/limit 分页
        - 传多个路径：批量模式，每个文件返回完整内容
        
        P15返回值全面化：单文件返回content/encoding/file_size/total_lines；批量返回results列表
        """
        if not file_paths:
            return build_error("ERR_PARAM_INVALID", "file_paths不能为空，至少提供1个文件路径")
        
        # 单文件模式
        if len(file_paths) == 1:
            return await self._read_text_file(
                file_path=file_paths[0],
                head=head,
                tail=tail,
                offset=offset,
                limit=limit,
                encoding=encoding
            )
        
        # 批量模式：忽略行控制参数
        return await self._read_batch_file(file_paths=file_paths)
    
    async def edit_file(
        self,
        file_path: str,
        old_string: Optional[str] = None,
        new_string: Optional[str] = None,
        edits: Optional[List[Dict]] = None,
        replace_all: bool = False,
        dry_run: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        编辑文本文件 — 小沈 2026-05-19 精简参数(8→7)
        P17互斥：old_string和edits不能同时传入
        """
        ignore_case = False  # ⚠️ 警告: 已从Schema移除，硬编码默认False，后续视需求决定是否恢复
        # P17互斥校验
        if old_string and edits:
            return build_error("ERR_PARAM_INVALID", "old_string和edits不能同时使用（P17互斥校验）")

        if not old_string and not edits:
            return build_error("ERR_PARAM_INVALID", "old_string或edits至少填一个")
        
        # 单处替换模式：调用precise_replace_in_file逻辑
        if old_string:
            return await self._precise_replace_in_file(
                file_path=file_path,
                old_string=old_string,
                new_string=new_string or "",
                replace_all=replace_all,
                ignore_case=ignore_case,
                dry_run=dry_run,
                encoding=encoding
            )
        
        # 多处编辑模式：调用edit_text_file逻辑
        else:
            return await self._apply_edits(
                file_path=file_path,
                edits=edits,
                dry_run=dry_run,
                encoding=encoding
            )
    
    async def rename_file(
        self,
        mode: Literal["single", "batch"] = "single",
        file_path: Optional[str] = None,
        new_name: Optional[str] = None,
        directory: Optional[str] = None,
        pattern: Optional[str] = None,
        replacement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """重命名文件 — 小沈 2026-05-19 精简参数(9→6)，小健 2026-05-19 补充batch模式缺失参数"""
        recursive = False
        preview = False
        conflict_strategy: Literal["skip", "overwrite", "append_number"] = "skip"
        # mode分发
        if mode == "batch":
            if not directory:
                return build_error("ERR_PARAM_INVALID", "批量模式(mode=batch)需要提供directory参数")
            if not pattern:
                return build_error("ERR_PARAM_INVALID", "批量模式(mode=batch)需要提供pattern参数")
            if not replacement:
                return build_error("ERR_PARAM_INVALID", "批量模式(mode=batch)需要提供replacement参数")

            return await self._batch_rename(
                directory=directory,
                pattern=pattern,
                replacement=replacement,
                recursive=recursive,
                preview=preview,
                conflict_strategy=conflict_strategy
            )

        # mode="single" (默认)
        if not file_path:
            return build_error("ERR_PARAM_INVALID", "单文件模式(mode=single)需要提供file_path参数")

        if not new_name:
            return build_error("ERR_PARAM_INVALID", "单文件模式(mode=single)需要提供new_name参数")

        # 小健 2026-05-19: Windows非法字符校验
        _illegal_chars = set('<>:"|?*')
        if os.name == 'nt' and any(c in _illegal_chars for c in new_name):
            return build_error("ERR_PARAM_INVALID", f"新名称包含Windows非法字符: {set(c for c in new_name if c in _illegal_chars)}")

        # 计算新路径（同目录改名）
        src = Path(file_path)

        if src.name == new_name:
            return build_success({"new_path": str(src), "old_path": str(src)}, "新名称与原名相同(P16幂等)")

        if "/" in new_name or "\\" in new_name:
            return build_error("ERR_PARAM_INVALID", "新名称不能包含路径分隔符（rename_file仅支持同目录改名）。如需跨目录移动请使用move_file。")

        dst = src.parent / new_name

        # 调用move_file实现
        return await self._move_file(
            source_path=file_path,
            destination_path=str(dst),
            overwrite=False
        )
    
    async def archive_tool(
        self,
        action: Literal["compress", "extract"],
        source: Optional[str] = None,
        destination: Optional[str] = None,
        format: str = "zip",
        compression_level: int = 6,
        password: Optional[str] = None,
        overwrite: bool = False,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        压缩/解压工具 — 小沈 2026-05-19 精简参数(11→8)
        - action="compress": source=源路径, destination=输出压缩包路径
        - action="extract": source=压缩包路径, destination=解压目标目录(可选)
        """
        if action not in ("compress", "extract"):
            return build_error("ERR_PARAM_INVALID", f"不支持的action: {action}，可选: compress/extract")

        if action == "compress":
            if not source:
                return build_error("ERR_PARAM_INVALID", "compress模式需要提供source")
            if not destination:
                return build_error("ERR_PARAM_INVALID", "compress模式需要提供destination")

            return await self._compress_files(
                source_path=source,
                output_path=destination,
                format=format,
                exclude_patterns=exclude_patterns,
                compression_level=compression_level,
                overwrite=overwrite,
                password=password
            )

        elif action == "extract":
            if not source:
                return build_error("ERR_PARAM_INVALID", "extract模式需要提供source")

            result = await self._extract_archive(
                archive_path=source,
                output_dir=destination,
                overwrite=overwrite,
                password=password,
                preserve_permissions=True
            )
            if "data" not in result:
                return build_error("ERR_FILE_EXTRACT", result.get("message", "解压失败"))
            return result
    
    async def file_operation(
        self,
        action: Literal["move", "copy", "delete"],
        source: str,
        destination: Optional[str] = None,
        recursive: bool = False,
        overwrite: bool = False,
        force: bool = False,
        preserve_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        文件操作统一入口 — 小沈 2026-05-18
        
        P11统一入口：合并 move_file + copy_file + delete_file
        - action="move": 移动文件/目录（原子操作 shutil.move，同盘瞬间完成）
        - action="copy": 复制文件/目录（shutil.copy2，preserve_metadata=True保留时间戳/权限）
        - action="delete": 删除文件/目录（默认send2trash放入回收站，force=True永久删除）
        
        P17互斥校验：action只能是"move"/"copy"/"delete"
        P17必填参数校验：move/copy需要destination，delete不需要
        P16幂等性：
          - delete: 文件已不存在→返回SUCCESS
          - move: 源和目标相同→返回SUCCESS
          - copy: 源和目标相同且内容一致→返回SUCCESS
        P15返回值全面化：返回action/source/destination/deleted_path/bytes_transferred/checksum
        """
        # P17互斥校验
        if action not in ("move", "copy", "delete"):
            return build_error("ERR_PARAM_INVALID", f"不支持的action: {action}，可选: move/copy/delete")

        # P17按action校验必填参数
        if action in ("move", "copy"):
            if not destination:
                return build_error("ERR_PARAM_INVALID", f"{action}模式需要提供destination")

            if action == "move":
                if os.path.abspath(source) == os.path.abspath(destination):
                    return build_success({"action": "move", "source": source, "destination": destination}, "源和目标相同(P16幂等)", next_actions=build_next_actions([("read_file", "验证操作结果", "需要确认时")]))
                return await self._move_file(
                    source_path=source,
                    destination_path=destination,
                    overwrite=overwrite
                )
            else:  # copy
                if os.path.abspath(source) == os.path.abspath(destination):
                    return build_success({"action": "copy", "source": source, "destination": destination}, "源和目标相同(P16幂等)", next_actions=build_next_actions([("read_file", "验证操作结果", "需要确认时")]))
                return await self._copy_file(
                    source_path=source,
                    destination_path=destination,
                    recursive=recursive,
                    overwrite=overwrite,
                    preserve_metadata=preserve_metadata
                )

        elif action == "delete":
            src_path = Path(source)
            if not src_path.exists():
                return build_success({"action": "delete", "source": source}, "文件已不存在(P16幂等)", next_actions=build_next_actions([("read_file", "验证操作结果", "需要确认时")]))
            return await self._delete_file(
                file_path=source,
                recursive=recursive,
                force=force
            )
    
    async def data_file_format(
        self,
        file_path: str,
        action: Literal["read", "write"] = "read",
        format: Optional[Literal["json", "yaml", "toml", "ini", "xml", "properties"]] = None,
        data: Optional[Any] = None,
        encoding: str = "utf-8",
        indent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        结构化配置格式统一入口 — 小沈 2026-05-18
        
        归入File分类（不是data_format分类），与read_file/write_text_file同类。
        注意：CSV/Excel属于Document分类，不在本工具范围内。
        
        P11统一入口：合并 read_json/write_json/parse_yaml/write_yaml/parse_toml/write_toml/parse_ini/parse_xml/parse_properties
        - action="read": 读取配置文件
        - action="write": 写入配置文件
        
        P17互斥校验：action只能是"read"或"write"
        P17必填参数校验：write模式需要data参数
        """
        from app.services.tools.toolhelper import data_format_helper as df_tools
        
        # P17互斥校验
        if action not in ("read", "write"):
            return build_error("ERR_PARAM_INVALID", f"不支持的action: {action}，可选: read/write")

        if not file_path:
            return build_error("ERR_PARAM_INVALID", "file_path是必填参数")

        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return build_error("ERR_PATH_INVALID", error_msg)

        detected_format = format
        if not detected_format:
            ext = os.path.splitext(file_path)[1].lower()
            format_map = {
                ".json": "json",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".toml": "toml",
                ".ini": "ini",
                ".cfg": "ini",
                ".xml": "xml",
                ".properties": "properties",
            }
            detected_format = format_map.get(ext)
            if not detected_format:
                return build_error("ERR_DOC_FORMAT_NOT_DETECTED", f"无法识别文件格式: {file_path}，请通过format参数指定")

        # write模式前置校验（提取自各格式分支）
        if action == "write":
            if detected_format in ("ini", "xml", "properties"):
                return build_error("ERR_DOC_FORMAT_NOT_SUPPORTED", f"{detected_format.upper()}格式暂不支持写入")
            if data is None:
                return build_error("ERR_PARAM_INVALID", "write模式需要提供data参数")

        from app.services.tools.toolhelper import data_format_helper as df_tools

        # 调用对应格式工具
        try:
            if detected_format == "json":
                if action == "read":
                    result = df_tools.read_json(file_path=file_path, encoding=encoding)
                else:
                    result = df_tools.write_json(
                        file_path=file_path,
                        data=data,
                        encoding=encoding,
                        indent=indent or 2
                    )

            elif detected_format == "yaml":
                if action == "read":
                    result = df_tools.parse_yaml(file_path=file_path, encoding=encoding)
                else:
                    result = df_tools.write_yaml(
                        file_path=file_path,
                        data=data,
                        encoding=encoding,
                        indent=indent
                    )

            elif detected_format == "toml":
                if action == "read":
                    result = df_tools.parse_toml(file_path=file_path, encoding=encoding)
                else:
                    result = df_tools.write_toml(file_path=file_path, data=data, encoding=encoding)

            elif detected_format == "ini":
                result = df_tools.parse_ini(file_path=file_path, encoding=encoding)

            elif detected_format == "xml":
                result = df_tools.parse_xml(file_path=file_path, encoding=encoding)

            elif detected_format == "properties":
                result = df_tools.parse_properties(file_path=file_path, encoding=encoding)

            else:
                return build_error("ERR_PARAM_INVALID", f"不支持的格式: {detected_format}")

            # 统一返回格式转换
            helper_code = result.get("code", "")
            if helper_code.startswith("ERR_"):
                return build_error("ERR_DOC_DATA_FORMAT_FAILED", result.get("message", "未知错误"))

            bytes_written = None
            if action == "write":
                try:
                    bytes_written = os.path.getsize(file_path)
                except Exception:
                    pass

            result_data = result.get("data", result)
            _llm = None
            if action == "read":
                _llm = {"格式": detected_format, "文件": file_path, "动作": "read"}
                if isinstance(result_data, dict):
                    _llm["键"] = list(result_data.keys())[:30]
                    _llm["顶层项数"] = len(result_data)
                elif isinstance(result_data, list):
                    _llm["项数"] = len(result_data)
                    _llm["预览"] = make_json_safe(result_data[:5], max_str_len=200)

            return build_success(
                {"data": result_data, "format": detected_format, "file_path": file_path, "action": action, "bytes_written": bytes_written},
                f"已{action} {detected_format.upper()}格式文件: {file_path}",
                llm_data=_llm,
                next_actions=build_next_actions([("edit_file", "编辑格式化文件", "需要修改时")]),
            )

        except Exception as e:
            logger.error(f"[data_file_format] 执行失败: {e}")
            return build_error("ERR_DOC_DATA_FORMAT_FAILED", str(e))


# ============================================================
# 第七部分：工具函数导出
# ============================================================

def get_file_tools(task_id: Optional[str] = None) -> FileTools:
    """获取文件工具实例"""
    return FileTools(task_id)


# ============================================================
# 第八部分：分页支持函数（原第九部分）
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
