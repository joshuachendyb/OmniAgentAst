"""项目上下文注入 — 读取 OmniAgent.md 注入Prompt — 小沈 2026-06-11

只读取 OmniAgent.md 文件，不读取其他文件。

Author: 小沈 - 2026-06-11
"""
import os
from functools import lru_cache

CONTEXT_FILE = "OmniAgent.md"
MAX_CHARS = 8000


@lru_cache(maxsize=1)
def load_project_context(workdir: str = None) -> str:
    """加载 OmniAgent.md 文件内容 — 小沈 2026-06-11

    Args:
        workdir: 项目根目录,默认自动探测(从cwd向上找OmniAgent.md)

    Returns:
        文件内容,如果没有找到则返回空字符串
    """
    if workdir is None:
        workdir = _detect_project_root()

    filepath = os.path.join(workdir, CONTEXT_FILE)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(MAX_CHARS)
    except (FileNotFoundError, PermissionError, IOError):
        return ""

    if not content:
        return ""

    if len(content) >= MAX_CHARS:
        content = content[:MAX_CHARS] + "\n...(截断)"

    return content


def _detect_project_root() -> str:
    """从当前工作目录向上搜索,找到包含 OmniAgent.md 的目录 — 小沈 2026-06-11"""
    cwd = os.getcwd()
    for _ in range(3):
        if os.path.isfile(os.path.join(cwd, CONTEXT_FILE)):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return os.getcwd()


def clear_project_context_cache():
    """清理缓存(供测试使用)"""
    load_project_context.cache_clear()
