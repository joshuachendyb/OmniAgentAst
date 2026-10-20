# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-09 - - 创建文件(validate层 内容安全+模块安装检查; 架构分层说明注释)
# 2026-08-04 - 小欧 - DRY收敛: _check_text_content 手写json.dumps → 复用公共safe_json_dumps(行为不变, dict/list自动转JSON供写入); 头部补编辑历史区对齐同目录规范 驱动
# 2026-10-15 (拆分·SRP) - 本文件由 file_safety_checker.py 拆出, 只保留「内容安全」一件事(SRP):
#   原文件把 check_content_safety(内容) 与 check_tool_module(依赖库安装) 两件互不相干的事塞在一起,
#   且文件名 file_safety_checker 与实际职责无任何关系 — 名不副实(命名即契约)。
#   本文件业务代码逐字复制自原 check_content_safety + _check_text_content, 零改动。
# 2026-10-20 05:27 小欧 - FIX _check_text_content: dict/list 转 JSON 的日志在 content 重新赋值之后
#   才取 type, 恒记成 "str" 失去诊断价值; 先留原始类型再转换, 日志记录真实原始类型
"""
内容安全检查（validate层） — 所有写工具共用的写入内容校验

只做一件事: 校验「待写入的内容」本身是否安全(空/None/null字节/类型/append冲突)。
不管路径权限、不管依赖库安装 — 后者见 tool_module_checker.py。

原 file_safety_checker.py 的 docstring 架构分层说明(validate层 与 Safety层 互不依赖)仍然成立, 见同目录 file_path_checker.py。

 2026-07-09
"""
from typing import Any, Optional, Tuple

from app.utils.json_utils import safe_json_dumps
from app.logger import logger


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
     2026-07-09
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
            # 2026-10-20 小欧 - FIX: 日志在 content 重新赋值之后才取 type, 恒记成 "str",
            #   失去"原始是什么类型"的诊断价值; 先留原类型再转换 — 小欧-2026-10-20
            _orig_type = type(content).__name__
            content = safe_json_dumps(content, ensure_ascii=False, indent=2)
            logger.info(f"[check_content_safety] {param_name}参数为{_orig_type}，已自动转为JSON字符串")
        except Exception as e:
            return f"{param_name}序列化失败: {e}", content
    if not isinstance(content, str):
        return f"{param_name}类型错误: 期望str/dict/list，实际{type(content).__name__}", content
    if options.get("append") and options.get("encoding"):
        return "append模式不允许指定encoding。追加时会自动检测原文件编码并使用相同编码写入。如需转换编码请先读取全文、转换后覆盖写入。", content
    return None, content


__all__ = [
    "check_content_safety",
]