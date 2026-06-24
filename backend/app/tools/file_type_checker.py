# -*- coding: utf-8 -*-
"""
文件类型检查器 - 共享函数 - 小健 2026-06-24

职责：
1. 检查文件类型是否符合工具要求
2. 返回检查结果、错误信息、建议工具
3. 提供清晰的LLM引导信息

使用规范：
- 所有tool必须调用此模块进行检查
- 返回值：(is_valid: bool, error_detail: str, suggested_tool: str)
- 主函数根据返回值决定是否继续执行
"""
from pathlib import Path
from typing import Tuple, Optional, Literal

from app.tools.tool_constants import BINARY_EXTENSIONS


# ============================================================
# 文件类型分类定义
# ============================================================

# 文本文件扩展名
TEXT_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.c', '.cpp', '.h',
    '.rs', '.rb', '.swift', '.kt', '.scala', '.php', '.pl', '.sh', '.bat', '.ps1', '.cmd',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.xml', '.properties',
    '.csv', '.tsv', '.html', '.htm', '.css', '.scss', '.less', '.sql', '.log', '.env',
    '.gitignore', '.dockerignore', '.editorconfig', '.prettierrc', '.eslintrc',
    '.makefile', '.cmake', '.gradle', '.maven',
}

# 媒体文件扩展名 — 小健 2026-06-24 更新：图片12+音频9+视频6=27种，移除.flv，新增.mid/.midi
MEDIA_EXTENSIONS = {
    # 图片（12种）
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.svg', '.tiff', '.tif', '.ico', '.heic', '.heif',
    # 音频（9种）
    '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac',
    '.wma', '.mid', '.midi',
    # 视频（6种）
    '.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv',
}

# 文档文件扩展名 — 小健 2026-06-24 更新：仅保留实际支持的4种格式
# 不支持的文档格式：.doc .xls .ppt .odt .ods .odp .rtf
DOCUMENT_EXTENSIONS = {
    '.pdf', '.docx', '.xlsx', '.pptx',
}

# 配置文件扩展名 — 已删除config工具，配置文件由text工具处理 — 小欧 2026-06-24

# 压缩文件扩展名
# 用途：compress_files/extract_archive工具的类型检查
# 说明：仅包含实际支持的格式，用于引导LLM选择正确的工具
# 小欧 2026-06-24 修正：只保留实际支持的4种格式
ARCHIVE_EXTENSIONS = {
    '.zip', '.tar', '.tar.gz', '.tar.bz2',
}

# 不支持的文件格式 — 小健 2026-06-24 新增
# 用途：当用户操作这些格式时，给出明确的"不支持"提示和转换建议
UNSUPPORTED_EXTENSIONS = {
    # 不支持的文档格式（7种）— 旧版Office + 开源办公格式
    '.doc', '.xls', '.ppt', '.odt', '.ods', '.odp', '.rtf',
    # 不支持的压缩格式（2种）
    '.rar', '.7z',
}

# 不支持格式的转换建议映射 — 小健 2026-06-24
UNSUPPORTED_FORMAT_HINTS = {
    '.doc': '请转换为.docx格式',
    '.xls': '请转换为.xlsx格式',
    '.ppt': '请转换为.pptx格式',
    '.odt': '请转换为.docx格式',
    '.ods': '请转换为.xlsx格式',
    '.odp': '请转换为.pptx格式',
    '.rtf': '请转换为.docx格式',
    '.rar': '请使用.zip格式压缩',
    '.7z': '请使用.zip格式压缩',
}


# ============================================================
# 核心检查函数
# ============================================================

def check_file_type(
    file_path: str,
    expected_type: Literal["text", "media", "document", "config", "archive", "not_binary"],
    check_content: bool = True,
    allow_create: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """
    检查文件类型是否符合预期
    
    参数：
        file_path: 文件路径
        expected_type: 期望的文件类型
            - "text": 文本文件
            - "media": 媒体文件（图片/音频/视频）
            - "document": 文档文件（PDF/Word/Excel/PPT）
            - "config": 配置文件（JSON/YAML/TOML等）
            - "archive": 压缩文件
            - "not_binary": 非二进制文件
        check_content: 是否检查文件内容（默认True）
        allow_create: 是否允许创建新文件（默认False，用于write操作）
    
    返回：
        (is_valid, error_detail, suggested_tool)
        - is_valid: 是否符合预期
        - error_detail: 错误详情（is_valid=False时有值）
        - suggested_tool: 建议使用的工具（is_valid=False时有值）
    
    示例：
        >>> is_valid, error, tool = check_file_type("test.png", "text")
        >>> if not is_valid:
        >>>     return build_error(error_detail=error, hint=f"请使用{tool}工具")
    """
    if not file_path or not file_path.strip():
        return False, "文件路径不能为空", None
    
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    # 检查文件是否存在（allow_create=True时允许不存在）
    if not allow_create:
        if not path.exists():
            return False, f"文件不存在: {file_path}", None
        if not path.is_file():
            return False, f"路径不是文件: {file_path}", None
    else:
        # allow_create=True时，如果文件存在且是目录，报错
        if path.exists() and path.is_dir():
            return False, f"路径是目录而非文件: {file_path}", None
    
    # 根据期望类型进行检查
    if expected_type == "text":
        return _check_text_file(path, suffix, check_content, allow_create)
    elif expected_type == "media":
        return _check_media_file(path, suffix)
    elif expected_type == "document":
        return _check_document_file(path, suffix)
    elif expected_type == "archive":
        return _check_archive_file(path, suffix)
    elif expected_type == "not_binary":
        return _check_not_binary(path, suffix, check_content, allow_create)
    else:
        return False, f"未知的期望类型: {expected_type}", None


def _suggest_doc_tool(suffix: str) -> str:
    """根据文档扩展名返回具体的工具建议 — 小欧 2026-06-24"""
    doc_tool_map = {
        '.docx': 'read_docx', '.doc': 'read_docx',
        '.pptx': 'read_pptx', '.ppt': 'read_pptx',
        '.xlsx': 'read_xlsx', '.xls': 'read_xlsx',
        '.pdf': 'read_pdf',
    }
    tool = doc_tool_map.get(suffix)
    if tool:
        return f"建议使用{tool}工具"
    return "请根据文件类型选择对应的文档读取工具"


def _check_text_file(path: Path, suffix: str, check_content: bool, allow_create: bool = False) -> Tuple[bool, str, Optional[str]]:
    """检查是否为文本文件 — 小欧 2026-06-24 修正错误信息格式：先说工具选择错误，再给建议"""
    # 检查扩展名
    if suffix in BINARY_EXTENSIONS:
        if suffix in MEDIA_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是媒体文件，不能用文本工具操作。建议使用read_media_file工具", "read_media_file"
        elif suffix in DOCUMENT_EXTENSIONS:
            doc_tool = _suggest_doc_tool(suffix)
            return False, f"工具选择错误：'{suffix}'是文档文件，不能用文本工具操作。{doc_tool}", None
        elif suffix in ARCHIVE_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是压缩文件，不能用文本工具操作。请先用解压工具解压后再读取", None
        else:
            return False, f"工具选择错误：'{suffix}'是二进制文件，不能用文本工具操作。请确认文件类型后选择合适的工具", None
    
    # 检查内容（如果启用且文件存在）
    if check_content and not allow_create and path.exists():
        is_binary, reason = _detect_binary_content(path)
        if is_binary:
            return False, f"工具选择错误：{reason}，不能用文本工具操作。建议使用read_media_file工具", "read_media_file"
    
    return True, "", None


def _check_media_file(path: Path, suffix: str) -> Tuple[bool, str, Optional[str]]:
    """检查是否为媒体文件 — 小欧 2026-06-24 修正错误信息格式"""
    if suffix not in MEDIA_EXTENSIONS:
        if suffix in TEXT_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是文本文件，不能用媒体工具操作。建议使用read_text_file工具", "read_text_file"
        elif suffix in DOCUMENT_EXTENSIONS:
            doc_tool = _suggest_doc_tool(suffix)
            return False, f"工具选择错误：'{suffix}'是文档文件，不能用媒体工具操作。{doc_tool}", None
        else:
            return False, f"工具选择错误：'{suffix}'不是支持的媒体格式。建议使用read_text_file或对应的文档工具", None
    
    return True, "", None


def _check_document_file(path: Path, suffix: str) -> Tuple[bool, str, Optional[str]]:
    """检查是否为文档文件 — 小健 2026-06-24 更新：引用UNSUPPORTED_FORMAT_HINTS"""
    if suffix in UNSUPPORTED_FORMAT_HINTS:
        hint = UNSUPPORTED_FORMAT_HINTS[suffix]
        return False, f"工具选择错误：'{suffix}'是不支持的文档格式。{hint}。支持的格式: {', '.join(sorted(DOCUMENT_EXTENSIONS))}", None
    if suffix not in DOCUMENT_EXTENSIONS:
        if suffix in TEXT_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是文本文件，不能用文档工具操作。建议使用read_text_file工具", "read_text_file"
        elif suffix in MEDIA_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是媒体文件，不能用文档工具操作。建议使用read_media_file工具", "read_media_file"
        else:
            return False, f"工具选择错误：'{suffix}'不是支持的文档格式。支持的格式: {', '.join(sorted(DOCUMENT_EXTENSIONS))}", None
    
    return True, "", None


def _check_archive_file(path: Path, suffix: str) -> Tuple[bool, str, Optional[str]]:
    """检查是否为压缩文件 — 小健 2026-06-24 更新：引用UNSUPPORTED_FORMAT_HINTS"""
    if suffix in UNSUPPORTED_FORMAT_HINTS and suffix in ('.rar', '.7z'):
        hint = UNSUPPORTED_FORMAT_HINTS[suffix]
        return False, f"工具选择错误：'{suffix}'是不支持的压缩格式。{hint}。支持的格式: {', '.join(sorted(ARCHIVE_EXTENSIONS))}", None
    if suffix not in ARCHIVE_EXTENSIONS:
        if suffix in TEXT_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是文本文件，不是压缩文件。建议使用read_text_file工具", "read_text_file"
        else:
            return False, f"工具选择错误：'{suffix}'不是支持的压缩格式。支持的格式: {', '.join(sorted(ARCHIVE_EXTENSIONS))}", None
    
    return True, "", None


def _check_not_binary(path: Path, suffix: str, check_content: bool, allow_create: bool = False) -> Tuple[bool, str, Optional[str]]:
    """检查是否非二进制文件 — 小欧 2026-06-24 修正错误信息格式"""
    # 检查扩展名
    if suffix in BINARY_EXTENSIONS:
        return False, f"工具选择错误：'{suffix}'是二进制文件类型，不能用文本工具操作。请确认文件类型后选择合适的工具", None
    
    # 检查内容（如果启用且文件存在）
    if check_content and not allow_create and path.exists():
        is_binary, reason = _detect_binary_content(path)
        if is_binary:
            return False, reason, None
    
    return True, "", None


def _detect_binary_content(path: Path) -> Tuple[bool, str]:
    """
    检测文件内容是否为二进制
    
    返回：
        (is_binary, reason)
    """
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
        
        # 检查空字节
        if b'\x00' in chunk:
            return True, "文件包含空字节(0x00)，疑似二进制文件"
        
        # 检查BOM标记
        null_count = chunk.count(b'\xff\xfe') + chunk.count(b'\xfe\xff')
        if null_count > 0 and len(chunk) < 100:
            return True, "文件包含BOM标记但内容过短，疑似二进制文件"
        
        return False, ""
    except Exception:
        return False, ""


# ============================================================
# 便捷检查函数（供各个tool直接调用）
# ============================================================

def check_for_text_tool(file_path: str, check_content: bool = True, allow_create: bool = False) -> Tuple[bool, str, Optional[str]]:
    """
    供read_text_file/write_text_file/edit_text_file调用
    
    参数：
        file_path: 文件路径
        check_content: 是否检查文件内容
        allow_create: 是否允许创建新文件（用于write操作）
    
    示例：
        is_valid, error, tool = check_for_text_tool(file_path)
        if not is_valid:
            return build_error(error_detail=error, hint=f"请使用{tool}工具")
    """
    return check_file_type(file_path, "text", check_content, allow_create)


def check_for_media_tool(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """供read_media_file调用"""
    return check_file_type(file_path, "media", check_content=False)




def check_for_archive_tool(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """供extract_archive调用"""
    return check_file_type(file_path, "archive", check_content=False)


def check_for_document_tool(file_path: str, allow_create: bool = False) -> Tuple[bool, str, Optional[str]]:
    """供read_docx/read_pptx/read_xlsx/read_pdf/write_docx/write_pptx/write_xlsx调用 — 小欧 2026-06-24"""
    return check_file_type(file_path, "document", check_content=False, allow_create=allow_create)


# ============================================================
# 扩展名查询函数
# ============================================================

def get_file_category(file_path: str) -> Optional[str]:
    """
    获取文件类别
    
    返回：
        "text" / "media" / "document" / "config" / "archive" / "binary" / "unknown"
    """
    if not file_path:
        return None
    
    suffix = Path(file_path).suffix.lower()
    
    if suffix in TEXT_EXTENSIONS:
        return "text"
    elif suffix in MEDIA_EXTENSIONS:
        return "media"
    elif suffix in DOCUMENT_EXTENSIONS:
        return "document"
    elif suffix in ARCHIVE_EXTENSIONS:
        return "archive"
    elif suffix in BINARY_EXTENSIONS:
        return "binary"
    else:
        return "unknown"


def is_text_file(file_path: str) -> bool:
    """判断是否为文本文件"""
    category = get_file_category(file_path)
    return category == "text"


def is_binary_file(file_path: str) -> bool:
    """判断是否为二进制文件"""
    category = get_file_category(file_path)
    return category in ("binary", "media", "document", "archive")


__all__ = [
    "check_file_type",
    "check_for_text_tool",
    "check_for_media_tool",
    "check_for_archive_tool",
    "check_for_document_tool",
    "get_file_category",
    "is_text_file",
    "is_binary_file",
    "TEXT_EXTENSIONS",
    "MEDIA_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "ARCHIVE_EXTENSIONS",
    "UNSUPPORTED_EXTENSIONS",
    "UNSUPPORTED_FORMAT_HINTS",
]