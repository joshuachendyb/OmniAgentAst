# -*- coding: utf-8 -*-
"""
文件类型检查器 - 共享函数 - 小健 2026-06-24

职责：
1. 检查文件类型是否符合工具要求
2. 返回检查结果、错误信息、建议工具
3. 提供清晰的LLM引导信息

本文件（validate层）依赖关系：
  - 调用 validate/file_path_checker.py（路径检查）
  - 调用 validate/file_safety_checker.py -> check_tool_module（模块安装检查）
  - check_office_file 编排：路径检查→类型检查→模块安全检查三位一体

Safety层（services/safety/tool_safety_checker.py + path_safe_check.py）独立运行、互不调用：
  - 路径黑名单/白名单/穿越拒绝/写入大小保护/二元确认/已知风险检测

使用规范：
- 所有tool必须调用此模块进行检查
- 返回值：(is_valid: bool, error_detail: str, suggested_tool: str)
- 主函数根据返回值决定是否继续执行

北京老陈 2026-07-09 补充交叉引用

更新历史：
2026-07-09 北京老陈 3个wrapper编排路径检查+类型检查+安全检查; 增加UNSUPPORTED分支
"""
from pathlib import Path
from typing import Tuple, Optional, Literal

from app.tools.tool_constants import BINARY_EXTENSIONS
from app.tools.validate.file_path_checker import validate_path, OpCategory


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
    if isinstance(file_path, Path):
        file_path = str(file_path)
    
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


_DOC_TOOL_MAP = {
    # 文档扩展名→工具建议（读+写），用于文件类型检查错误提示 — 小欧 2026-07-09
    '.docx': 'read_docx或write_docx',
    '.pptx': 'read_pptx或write_pptx',
    '.xlsx': 'read_xlsx或write_xlsx',
    '.pdf': 'read_pdf或write_pdf',
}


def _suggest_doc_tool(suffix: str) -> str:
    """根据文档扩展名返回具体的工具建议 — 小欧 2026-06-24 — 小欧 2026-06-24 清理死代码(.doc/.xls/.ppt) — 小欧 2026-07-09 8种：读+写"""
    tool_hint = _DOC_TOOL_MAP.get(suffix)
    if tool_hint:
        return f"建议使用{tool_hint}工具"
    return "请根据文件类型选择对应的文档读取工具"


def check_office_file(
    file_name: str,
    allow_create: bool = False,
    tool_name: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """检查office文档文件 — 路径检查 + 类型检查 + 模块安全检查
    专供 write_docx/write_pptx/write_xlsx/write_pdf 使用
    tool_name: 传 "write_docx"/"write_pptx"/"write_xlsx"/"write_pdf"
    北京老陈 2026-07-09"""
    # 1. 路径检查(file_path_checker)
    is_valid, err, _ = validate_path(OpCategory.WRITE, file_name)
    if not is_valid:
        return False, err, None

    # 2. 类型检查(本文件，直接调check_file_type跳开check_for_document_tool防重复validate)
    is_valid, error_detail, _ = check_file_type(
        file_name, "document", check_content=False, allow_create=allow_create
    )
    if not is_valid:
        suffix = Path(file_name).suffix.lower()
        _hint = (
            f"文件扩展名不正确,请使用{suffix}格式"
            if suffix in DOCUMENT_EXTENSIONS
            else "请使用正确的文档格式(.docx/.pptx/.xlsx/.pdf)"
        )
        return False, error_detail, _hint

    # 3. 模块安全检查(file_safety_checker)
    if tool_name:
        from app.tools.validate.file_safety_checker import check_tool_module
        is_valid, err, hint = check_tool_module(tool_name)
        if not is_valid:
            return False, err, hint

    return True, "", None


def _check_text_file(path: Path, suffix: str, check_content: bool, allow_create: bool = False) -> Tuple[bool, str, Optional[str]]:
    """检查是否为文本文件 — 小欧 2026-06-24 修正错误信息格式：先说工具选择错误，再给建议"""
    # 检查扩展名
    if suffix in BINARY_EXTENSIONS:
        if suffix in MEDIA_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是媒体文件，不能用文本工具操作。建议使用readmedia工具", "readmedia"
        elif suffix in DOCUMENT_EXTENSIONS:
            doc_tool_hint = _DOC_TOOL_MAP.get(suffix, "read_docx")
            return False, f"工具选择错误：'{suffix}'是文档文件，不能用文本工具操作。建议使用{doc_tool_hint}工具", doc_tool_hint
        elif suffix in UNSUPPORTED_EXTENSIONS:
            hint = UNSUPPORTED_FORMAT_HINTS.get(suffix, "不支持的格式")
            return False, f"工具选择错误：'{suffix}'是不支持的格式。{hint}", None
        elif suffix in ARCHIVE_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是压缩文件，不能用文本工具操作。请先用解压工具解压后再读取", "extract_archive"
        else:
            return False, f"工具选择错误：'{suffix}'是二进制文件，不能用文本工具操作。请确认文件类型后选择合适的工具", None
    
    # 检查内容（如果启用且文件存在）
    if check_content and not allow_create and path.exists():
        is_binary, reason = _detect_binary_content(path)
        if is_binary:
            return False, f"工具选择错误：{reason}，不能用文本工具操作。建议使用readmedia工具", "readmedia"
    
    return True, "", None


def _check_media_file(path: Path, suffix: str) -> Tuple[bool, str, Optional[str]]:
    """检查是否为媒体文件 — 小欧 2026-06-24 修正错误信息格式"""
    if suffix not in MEDIA_EXTENSIONS:
        if suffix in TEXT_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是文本文件，不能用媒体工具操作。建议使用readtext工具", "readtext"
        elif suffix in DOCUMENT_EXTENSIONS:
            doc_tool = _suggest_doc_tool(suffix)
            return False, f"工具选择错误：'{suffix}'是文档文件，不能用媒体工具操作。{doc_tool}", None
        elif suffix in UNSUPPORTED_EXTENSIONS:
            hint = UNSUPPORTED_FORMAT_HINTS.get(suffix, "不支持的格式")
            return False, f"工具选择错误：'{suffix}'是不支持的格式。{hint}", None
        else:
            return False, f"工具选择错误：'{suffix}'不是支持的媒体格式。建议使用readtext或对应的文档工具", None
    
    return True, "", None


def _check_document_file(path: Path, suffix: str) -> Tuple[bool, str, Optional[str]]:
    """检查是否为文档文件 — 小健 2026-06-24 更新：引用UNSUPPORTED_FORMAT_HINTS"""
    if suffix in UNSUPPORTED_FORMAT_HINTS:
        hint = UNSUPPORTED_FORMAT_HINTS[suffix]
        return False, f"工具选择错误：'{suffix}'是不支持的文档格式。{hint}。支持的格式: {', '.join(sorted(DOCUMENT_EXTENSIONS))}", None
    if suffix not in DOCUMENT_EXTENSIONS:
        if suffix in TEXT_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是文本文件，不能用文档工具操作。建议使用readtext工具", "readtext"
        elif suffix in MEDIA_EXTENSIONS:
            return False, f"工具选择错误：'{suffix}'是媒体文件，不能用文档工具操作。建议使用readmedia工具", "readmedia"
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
            return False, f"工具选择错误：'{suffix}'是文本文件，不是压缩文件。建议使用readtext工具", "readtext"
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

def check_for_text_tool(
    file_path: str,
    check_content: bool = True,
    allow_create: bool = False,
    op_category: OpCategory = OpCategory.READ_FILE,
) -> Tuple[bool, str, Optional[str]]:
    """供readtext/writetext/edittext调用 — 路径检查+类型检查
    北京老陈 2026-07-09"""
    is_valid, err, _ = validate_path(op_category, file_path)
    if not is_valid:
        return False, err, ""
    return check_file_type(file_path, "text", check_content, allow_create)


def check_for_media_tool(
    file_path: str,
    op_category: OpCategory = OpCategory.READ_FILE,
) -> Tuple[bool, str, Optional[str]]:
    """供readmedia调用 — 路径检查+类型检查
    北京老陈 2026-07-09"""
    is_valid, err, _ = validate_path(op_category, file_path)
    if not is_valid:
        return False, err, ""
    return check_file_type(file_path, "media", check_content=False)




def check_for_archive_tool(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """供extract_archive调用"""
    return check_file_type(file_path, "archive", check_content=False)


def check_for_document_tool(
    file_path: str,
    allow_create: bool = False,
    op_category: OpCategory = OpCategory.READ_FILE,
) -> Tuple[bool, str, Optional[str]]:
    """供read_docx/read_pptx/read_xlsx/read_pdf调用 — 路径检查+类型检查
    北京老陈 2026-07-09"""
    is_valid, err, _ = validate_path(op_category, file_path)
    if not is_valid:
        return False, err, ""
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
    "check_office_file",
    "get_file_category",
    "is_text_file",
    "is_binary_file",
    "TEXT_EXTENSIONS",
    "MEDIA_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "ARCHIVE_EXTENSIONS",
    "UNSUPPORTED_EXTENSIONS",
    "UNSUPPORTED_FORMAT_HINTS",
    "OpCategory",
]
