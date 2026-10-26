# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-26 小沈: 新建。从 fetch_webpage._save_to_file 抽取 save_text_to_file,
#   调 write 工具走完整安全链路(路径校验/文件类型/内容安全/编码/语法/mtime/仲裁/操作记录),
#   基准 project_root, 供网络工具等"调 write 落盘"场景复用(复用优先, 禁止重复实现)。
"""
toolhelper/tool_utils.py — 工具通用辅助函数(跨工具复用的非业务逻辑辅助)

Author: 小沈 2026-10-26
"""
from typing import Tuple

from app.utils.path_utils import absolutize_path, has_path_traversal

__all__ = [
    "save_text_to_file",
]


async def save_text_to_file(path: str, content: str) -> Tuple[str, str]:
    """调 write 工具保存文本到文件(完整安全链路)。

    路径绝对化: 绝对路径原样, 相对路径相对于项目根目录(project_root)。
    走 write 工具完整安全链路: 路径校验/文件类型/内容安全/编码/语法/mtime/仲裁/操作记录。

    Returns:
        (注记字符串, 保存路径绝对路径); 路径为空=失败。

    小沈 2026-10-26
    """
    from app.tools.file.write_text_file import write as _write_tool
    from app.config import get_config
    from app.logger import logger

    # BUG-5修复: content=None 拒绝
    if content is None:
        return "落盘失败:内容为None", ""

    # BUG-4修复: 空content拒绝
    if len(content) == 0:
        return "落盘失败:内容为空", ""

    # BUG-7修复: 路径穿越检查(复用公用函数 has_path_traversal)
    if has_path_traversal(path):
        return "落盘失败:路径穿越禁止(../)", ""

    _abs_path = absolutize_path(path, get_config().get_project_root())
    try:
        _wr = await _write_tool(path=_abs_path, content=content)
    except Exception as e:
        logger.warning(f"[save_text_to_file] 落盘异常: {type(e).__name__}: {e}")
        return f"落盘失败:{type(e).__name__}:{e}", ""

    # BUG-6修复: write返回None优雅处理
    if _wr is None:
        return "落盘失败:write工具返回None", ""

    _wl = _wr.get("llm_data", {})
    _status = _wl.get("status", {})
    _code = _status.get("exec_code", "error")
    if _code in ("success", "warning"):
        _saved = _wl.get("action", {}).get("params", {}).get("path", _abs_path)
        return f"已保存至{_saved}({len(content)}字符)", str(_saved)
    return f"落盘失败:{_status.get('detail', '写入失败')}", ""
