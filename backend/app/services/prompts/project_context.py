"""项目上下文注入 — 读取项目规则文档注入Prompt — 小沈 2026-06-11

借鉴 OpenCode 的 getContextFromPaths():
- 读取 README.md 等文件拼接到 system prompt 末尾
- 使用 lru_cache 进程内缓存

Author: 小沈 - 2026-06-11
"""
import os
from functools import lru_cache

# 查找路径列表（相对于工作目录）
CONTEXT_PATHS = [
    "README.md",
    "AGENTS.md",
]

MAX_FILES = 2
MAX_CHARS_PER_FILE = 3000
MAX_TOTAL_CHARS = 5000


@lru_cache(maxsize=1)
def load_project_context(workdir: str = None) -> str:
    """加载项目上下文文件内容 — 小沈 2026-06-11

    Args:
        workdir: 项目根目录,默认自动探测(从cwd向上找README.md)

    Returns:
        格式化的上下文文本,如果没有找到则返回空字符串
    """
    if workdir is None:
        workdir = _detect_project_root()

    contents = []
    total_chars = 0

    for filename in CONTEXT_PATHS:
        if len(contents) >= MAX_FILES:
            break
        if total_chars >= MAX_TOTAL_CHARS:
            break

        filepath = os.path.join(workdir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(MAX_CHARS_PER_FILE)
        except (FileNotFoundError, PermissionError, IOError):
            continue

        if content:
            trimmed = content if len(content) < MAX_CHARS_PER_FILE else content[:MAX_CHARS_PER_FILE] + "\n...(截断)"
            block = f"## 项目文档: {filename}\n{trimmed}"
            contents.append(block)
            total_chars += len(block)

    if not contents:
        return ""

    return "\n\n".join(contents)


def _detect_project_root() -> str:
    """从当前工作目录向上搜索,找到包含 README.md 的目录 — 小沈 2026-06-11"""
    cwd = os.getcwd()
    # 向上搜索3层
    for _ in range(3):
        if os.path.isfile(os.path.join(cwd, "README.md")):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return os.getcwd()


def clear_project_context_cache():
    """清理缓存(供测试使用)"""
    load_project_context.cache_clear()
