"""
系统信息适配器 — 生成系统自适应的 Prompt 内容

【功能】根据服务器 OS 生成路径格式提示
【重构】2026-06-14 小沈 — COMMANDS移至shell_register.execute_shell_command描述

Author: 小沈 - 2026-06-14
"""
import functools
import os
import platform

from app.utils.logger import logger

PATH_FORMATS = {
    "Windows": "C:\\Users\\xxx\\file.txt 或 C:/Users/xxx/file.txt",
    "Linux": "/home/xxx/file.txt",
}


def _detect_os() -> str:
    return platform.system()


def _check_is_git_repo(path: str) -> bool:
    current = os.path.abspath(path)
    for _ in range(5):
        if os.path.isdir(os.path.join(current, ".git")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return False


def _get_environment_info() -> str:
    """获取环境信息（工作目录/Git 状态/日期时间）— 小沈 2026-06-11"""
    from app.utils.time_utils import now_str

    cwd = os.getcwd()
    now = now_str()
    is_git = _check_is_git_repo(cwd)
    git_status = "是" if is_git else "否"
    return f"""【环境信息】
- 工作目录: {cwd}
- Git仓库: {git_status}
- 当前时间: {now}
"""


_ALWAYS_RULES = """【路径规则】
- 必须使用绝对路径(禁止相对路径如 ./file.txt)
- 禁止用 ~ 表示家目录
- ❌ 路径中的中文字符必须原样保留,禁止翻译或转换!用户说"E:\\下载\\科幻小说"就用"E:\\下载\\科幻小说",禁止改成"E:\\download\\sci-fi-novel"
"""


@functools.lru_cache(maxsize=1)
def get_system_prompt() -> str:
    """获取系统 Prompt 字符串（带缓存）"""
    system = _detect_os()
    path_format = PATH_FORMATS.get(system, "/home/xxx/file.txt")
    env_info = _get_environment_info()

    logger.debug("[system_adapter] OS=%s", system)

    return "\n\n".join([
        env_info,
        f"【当前系统】\n{system}",
        f"【路径格式】\n- 当前系统: {path_format}",
        _ALWAYS_RULES,
    ])
