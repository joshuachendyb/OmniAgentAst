# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-09 - 北京老陈 - 创建文件(validate层 内容安全+模块安装检查; 架构分层说明注释)
# 2026-08-04 - 小欧 - DRY收敛: _check_text_content 手写json.dumps → 复用公共safe_json_dumps(行为不变, dict/list自动转JSON供写入); 头部补编辑历史区对齐同目录规范 — 北京老陈驱动
"""
工具级安全检查（validate层） — 内容安全 + 模块安装检查

本文件（validate层，工具内嵌执行）：
  - check_content_safety: 内容安全检查（None/空/null字节/类型/append冲突）
  - check_tool_module:    依赖库安装检查

file_type_checker.py 的 check_office_file 编排调用本文件的 check_tool_module

Safety层（services/safety/tool_safety_checker.py + path_safe_check.py）独立运行、互不调用：
  - 路径黑名单/白名单/穿越拒绝
  - 写入大小保护
  - 二元安全确认(needs_confirmation)
  - 已知风险检测(路径越权/写入污染/代码注入)

架构层级（从实到虚）：
  validate层（本文件+file_path_checker+file_type_checker）→ tool内嵌，执行前必检
  Safety层（tool_safety_checker+path_safe_check）→ agent调度时执行，独立运行
  两层检查覆盖不同维度，互不依赖、互不调用

北京老陈 2026-07-09
"""
from typing import Any, Optional, Tuple

from app.tools.tool_fc_helper import _check_module
from app.utils.json_utils import safe_json_dumps
from app.logger import logger

_OFFICE_WRITE_MODULES = {
    "write_docx": "docx",
    "write_pptx": "pptx",
    "write_xlsx": "openpyxl",
    "write_pdf": "reportlab",
}


def check_tool_module(tool_name: str) -> Tuple[bool, str, str]:
    """检查文档写工具对应的模块是否安装。
    供 check_office_file 编排调用
    返回: (is_valid, error_detail, hint)
    """
    module = _OFFICE_WRITE_MODULES.get(tool_name)
    if not module:
        return True, "", ""
    if not _check_module(module):
        return False, f"{module}库未安装", f"请安装{module}库"
    return True, "", ""


def check_content_safety(
    content: Any,
    tool_type: str,
    param_name: str = "content",
    **options: Any,
) -> Tuple[Optional[str], Any]:
    """统一内容安全检查 — 所有写工具共用
    设计原则：SRP(单一检查职责)、DRY(避免重复)、KISS-DIRECT(简单直接)

    第1层 None检查（ALL）
    第2层 空检查（ALL）
    第3层 null字节检查（字符串内容，ALL）
    第4层 类型特定检查

    Args:
        content:   待检查的内容
        tool_type: 工具类型 ("text"/"docx"/"pptx"/"xlsx"/"pdf")
        param_name: 参数名，用于错误消息（默认"content"）
        options:   额外选项
            - append: bool (text专用)
            - encoding: str (text专用)

    Returns:
        (error, safe_content) — error=None表示通过，safe_content为处理后内容
    北京老陈 2026-07-09
    """
    # 第1层：None检查（ALL）
    if content is None:
        return f"{param_name}不能为None", content

    # 第2层：空检查（ALL）
    if isinstance(content, (str, list, dict)):
        if len(content) == 0:
            return f"{param_name}不能为空", content

    # 第3层：null字节检查（字符串内容）
    if isinstance(content, str) and '\x00' in content:
        return f"{param_name}包含null字符(0x00)", content

    # 第4层：类型特定检查
    if tool_type == "text":
        return _check_text_content(content, options, param_name)

    if tool_type in ("docx", "pdf"):
        if not isinstance(content, str):
            return f"{param_name}类型错误: 期望str，实际{type(content).__name__}", content
        return None, content

    if tool_type == "pptx":
        if not isinstance(content, list):
            return f"{param_name}类型错误: 期望list[dict]，实际{type(content).__name__}", content
        return None, content

    if tool_type == "xlsx":
        if not isinstance(content, list):
            return f"{param_name}类型错误: 期望list[dict]，实际{type(content).__name__}", content
        return None, content

    return None, content


def _check_text_content(content: Any, options: dict, param_name: str) -> Tuple[Optional[str], Any]:
    """文本内容特殊检查 — dict/list自动转JSON + append冲突
    2026-08-04 小欧: 手写json.dumps → 复用公共safe_json_dumps(DRY复用先查库)"""
    if isinstance(content, (dict, list)):
        try:
            content = safe_json_dumps(content, ensure_ascii=False, indent=2)
            logger.info(f"[check_content_safety] {param_name}参数为{type(content).__name__}，已自动转为JSON字符串")
        except Exception as e:
            return f"{param_name}序列化失败: {e}", content
    if not isinstance(content, str):
        return f"{param_name}类型错误: 期望str/dict/list，实际{type(content).__name__}", content
    if options.get("append") and options.get("encoding"):
        return "append模式不允许指定encoding。追加时会自动检测原文件编码并使用相同编码写入。如需转换编码请先读取全文、转换后覆盖写入。", content
    return None, content


__all__ = [
    "check_tool_module",
    "check_content_safety",
]
