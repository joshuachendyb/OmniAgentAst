# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-09 - 北京老陈 - 创建(原在 file_safety_checker.py)
# 2026-10-15 北京老陈裁定(拆分·SRP) - 本文件由 file_safety_checker.py 拆出, 只保留「依赖库是否安装」一件事(SRP):
#   原文件把 check_tool_module(依赖库) 与 check_content_safety(内容) 混放, 文件名与职责无对应关系 — 名不副实。
#   业务代码逐字复制自原 check_tool_module, 零改动; 原 _OFFICE_WRITE_MODULES 表随之迁入。
"""
工具依赖模块安装检查（validate层）

只做一件事: 写文档类工具的第三方库是否已安装。消费方仅 file_type_checker.check_office_file。

注意: 此处的「安装检查」是**依赖可用性**检查, 不是安全判定。
      路径权限在 Safety 层(工具层调不到), 内容安全见同目录 content_safety.py。

北京老陈 2026-07-09
"""
from typing import Tuple

from app.tools.tool_fc_helper import _check_module

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


__all__ = [
    "check_tool_module",
]