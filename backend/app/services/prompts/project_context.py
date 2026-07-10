"""项目上下文注入 — 读取 OmniAgent.md 注入Prompt — 小沈 2026-06-11 — 小欧 2026-07-08 改用config.get_project_root()

只读取 OmniAgent.md 文件，不读取其他文件。

Author: 小沈 - 2026-06-11
"""
import os
from collections import OrderedDict

from app.config import get_config as get_config_instance
from app.utils.logger import logger

CONTEXT_FILE = "OmniAgent.md"
MAX_CHARS = 8000
_CACHE_MAX_SIZE = 64

# 【修复P1-3】手动缓存替代lru_cache，按workdir隔离 — 北京老陈 2026-06-13
# M-13: OrderedDict + 上限 64，淘汰最旧 — 小欧 2026-07-10
_context_cache: OrderedDict = OrderedDict()


def load_project_context(workdir: str = None) -> str:
    """加载 OmniAgent.md 文件内容 — 小沈 2026-06-11 — 小欧 2026-07-08 改用config.get_project_root()

    Args:
        workdir: 项目根目录,默认从配置读取(get_project_root)

    Returns:
        文件内容,如果没有找到则返回空字符串
    """
    if workdir is None:
        workdir = get_config_instance().get_project_root()

    if workdir in _context_cache:
        _context_cache.move_to_end(workdir)
        return _context_cache[workdir]

    filepath = os.path.join(workdir, CONTEXT_FILE)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(MAX_CHARS)
    except (FileNotFoundError, PermissionError, IOError):
        _context_cache[workdir] = ""
        if len(_context_cache) > _CACHE_MAX_SIZE:
            _context_cache.popitem(last=False)
        return ""

    if not content:
        _context_cache[workdir] = ""
        if len(_context_cache) > _CACHE_MAX_SIZE:
            _context_cache.popitem(last=False)
        return ""

    if len(content) >= MAX_CHARS:
        logger.warning(f"[project_context] OmniAgent.md超过{MAX_CHARS}字符, 已截断")
        content = content[:MAX_CHARS] + "\n...(截断)"

    _context_cache[workdir] = content
    if len(_context_cache) > _CACHE_MAX_SIZE:
        _context_cache.popitem(last=False)
    return content

