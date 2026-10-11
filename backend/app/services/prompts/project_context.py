# 编辑历史:
# 2026-07-14 - 小欧 - 明确注释说明 OmniAgent.md 为项目规则文件，替换模糊的"项目上下文"表述
# 2026-07-15 - 小欧 - 常量归一化治理: 项目规则文件注入字符上限改引用 constants.PROJECT_CONTEXT_MAX_CHARS(原 MAX_CHARS=8000→10000, 系统级), 功能零退化
# 2026-09-22 小欧 - constants.py 配置化迁移：import PROJECT_CONTEXT_MAX_CHARS 改别名 + 使用点改读 tuning 配置
# 2026-10-11 小欧 - 规则文件定位基准由"项目根(workspace.project_root)"改为"代码根(get_code_root)": 与 version.txt/config/logs 统一同源; workdir 参数保留可覆盖
"""项目规则文件注入 — 读取代码根目录下的项目规则文件(OmniAgent.md)并注入Prompt — 小沈 2026-06-11 — 小欧 2026-07-08 改用config.get_project_root() — 小欧 2026-10-11 改用get_code_root()

只读取代码根目录下的 OmniAgent.md（项目规则文件），不读取其他文件。

Author: 小沈 - 2026-06-11
"""
import os
from collections import OrderedDict

from app.config import get_code_root
from app.logger import logger
from app.constants import PROJECT_CONTEXT_MAX_CHARS as _D_CONTEXT_CHARS
from app.config import get_config

CONTEXT_FILE = "OmniAgent.md"  # 项目规则文件名(基准名, 大小写不敏感解析) 置于代码根目录(与 version.txt/config/logs 同源)
# MAX_CHARS 已归一化为系统级 PROJECT_CONTEXT_MAX_CHARS (app/constants.py, 2026-07-15 治理: 8000→10000)
_CACHE_MAX_SIZE = 64

# 【修复】手动缓存替代lru_cache，按workdir隔离 — 北京老陈 2026-06-13
# OrderedDict + 上限 64，淘汰最旧 — 小欧 2026-07-10
_context_cache: OrderedDict = OrderedDict()


def resolve_context_path(workdir: str, create_missing: bool = False) -> str:
    """解析项目规则文件实际路径 — 小欧 2026-10-11

    文件名大小写不敏感: 先直接拼基准名命中, 未命中则列目录按小写比对,
    避免 OmniAgent.md / omnniagent.md / OMNIAGENT.MD 因大小写差异读不到(静默降级为空)。
    未命中且 create_missing=True 时创建空文件, 保证规则文件始终有落点。

    Args:
        workdir: 规则文件所在目录
        create_missing: 未找到时是否创建空文件

    Returns:
        实际存在的文件路径; 未找到且未创建则返回按基准名拼出的路径(交由调用方按缺失处理)
    """
    filepath = os.path.join(workdir, CONTEXT_FILE)
    if os.path.isfile(filepath):
        return filepath
    try:
        for name in os.listdir(workdir):
            if name.lower() == CONTEXT_FILE.lower() and os.path.isfile(os.path.join(workdir, name)):
                return os.path.join(workdir, name)
        if create_missing:
            with open(filepath, 'w', encoding='utf-8'):
                pass  # 建空文件即占位, 用户自行填写规则
            logger.info(f"[project_context] 代码根未找到规则文件, 已创建空文件: {filepath}")
    except OSError as e:
        logger.warning(f"[project_context] 规则文件缺失且创建失败: {filepath} — {e}")
    return filepath


def load_project_context(workdir: str = None) -> str:
    """加载项目规则文件(OmniAgent.md)内容 — 小沈 2026-06-11 — 小欧 2026-07-08 改用config.get_project_root()
    — 小欧 2026-10-11 基准由项目根(workspace.project_root)改为代码根(get_code_root), 与 version.txt/config/logs 同源

    Args:
        workdir: 规则文件所在目录,默认代码根目录(get_code_root)

    Returns:
        文件内容,如果没有找到则返回空字符串
    """
    if workdir is None:
        workdir = get_code_root()

    if workdir in _context_cache:
        _context_cache.move_to_end(workdir)
        return _context_cache[workdir]

    filepath = resolve_context_path(workdir, create_missing=True)
    _max_chars = get_config().get("tuning.content.project_context_max_chars", _D_CONTEXT_CHARS)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(_max_chars)
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

    if len(content) >= _max_chars:
        logger.warning(f"[project_context] OmniAgent.md超过{_max_chars}字符, 已截断")
        content = content[:_max_chars] + "\n...(截断)"

    _context_cache[workdir] = content
    if len(_context_cache) > _CACHE_MAX_SIZE:
        _context_cache.popitem(last=False)
    return content

