# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: 文件工具纠正逻辑独立, 解耦 action_handler - 小健-2026-09-04
"""
file_tool_utils — 文件工具扩展名预检自动纠正

从 action_handler.py 提取:
- _EXT_TO_READ_TOOL: 读工具扩展名映射（三分类: 文本→readtext, 文档→专用工具, 多媒体→readmedia）
- _EXT_TO_WRITE_TOOL: 写工具扩展名映射
- _auto_correct_file_tool: 文件扩展名预检自动纠正tool_name

原则: 完整复制, 保留原始功能分支和逻辑, 禁止简化退化
"""
from app.tools.validate.file_type_checker import TEXT_EXTENSIONS, MEDIA_EXTENSIONS

# #4 自动纠正: 文件扩展名→tool_name 映射（三分类: 文本→readtext, 文档→专用工具, 多媒体→readmedia）
# P07修复: .csv 是双域(文本+表格), 从读取映射移除, 使 read_xlsx/readtext 均不被自动改写 — 小欧 2026-08-07
# 完整复制自 action_handler.py:242-256
_EXT_TO_READ_TOOL = {ext: "readtext" for ext in TEXT_EXTENSIONS if ext != ".csv"}
_EXT_TO_READ_TOOL.update({ext: "readmedia" for ext in MEDIA_EXTENSIONS})
_EXT_TO_READ_TOOL.update({
    ".docx": "read_docx",
    ".xlsx": "read_xlsx",
    ".pdf": "read_pdf",
    ".pptx": "read_pptx",
})
_EXT_TO_WRITE_TOOL = {ext: "writetext" for ext in TEXT_EXTENSIONS}
_EXT_TO_WRITE_TOOL.update({
    ".docx": "write_docx",
    ".xlsx": "write_xlsx",
    ".pdf": "write_pdf",
    ".pptx": "write_pptx",
})


# ════════════════════════════════════════════════════════════
# 文件扩展名自动纠正（复制自 action_handler.py:259-276）
# ════════════════════════════════════════════════════════════

def _auto_correct_file_tool(tool_name: str, tool_params: dict) -> tuple:
    """文件扩展名预检自动纠正tool_name — 返回 (纠正后名, 原始名或None)
    三分类映射: 文本→readtext, 文档→专用工具, 多媒体→readmedia — 小欧 2026-07-25
    完整复制自 action_handler.py:259-276
    """
    _path = tool_params.get("path", "") if isinstance(tool_params, dict) else ""
    if not _path or not isinstance(_path, str):
        return tool_name, None
    _ext = _path[_path.rfind("."):].lower() if "." in _path else ""
    if not _ext:
        return tool_name, None
    if tool_name.startswith("read"):
        _mapping = _EXT_TO_READ_TOOL
    elif tool_name.startswith("write"):
        _mapping = _EXT_TO_WRITE_TOOL
    else:
        return tool_name, None
    if _ext in _mapping and tool_name != _mapping[_ext]:
        return _mapping[_ext], tool_name
    return tool_name, None
