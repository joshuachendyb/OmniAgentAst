"""
系统信息适配器 — 生成系统自适应的 Prompt 内容

【功能】根据服务器 OS 生成路径格式提示
【重构】2026-06-14 小沈 — COMMANDS移至shell_register.execute_shell_command描述

Author: 小沈 - 2026-06-14
"""
import os
import platform
import shutil
import subprocess
from typing import Optional

from app.utils.logger import logger

PATH_FORMATS = {
    "Windows": "C:\\Users\\xxx\\file.txt 或 C:/Users/xxx/file.txt",
    "Linux": "/home/xxx/file.txt",
}


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
    """获取环境信息（项目根目录/Git 状态/日期时间）— 小沈 2026-06-11
    【2026-06-23 北京老陈】工作目录改为项目根目录,避免显示backend子目录
    """
    from app.utils.time_utils import now_str
    from app.config import get_config as get_config_instance

    config = get_config_instance()
    root = config.get_project_root()
    now = now_str()
    is_git = _check_is_git_repo(root)
    git_status = "是" if is_git else "否"
    return f"""
【环境信息】
- 项目根目录: {root}
- Git仓库: {git_status}
- 当前时间: {now}
"""


_ALWAYS_RULES = """【路径规则】
- 禁止用 ~ 表示家目录
- ❌ 中文路径禁止翻译或转换!

"""


_POWERSHELL_VERSION: Optional[str] = None
_PWSH_VERSION: Optional[str] = None


def get_powershell_version() -> str:
    """检测 Windows PowerShell 5.1 版本号（带缓存）— 小沈 2026-07-01"""
    global _POWERSHELL_VERSION
    if _POWERSHELL_VERSION is not None:
        return _POWERSHELL_VERSION
    try:
        r = subprocess.run(
            ['powershell.exe', '-NoLogo', '-Command', '$PSVersionTable.PSVersion.ToString()'],
            capture_output=True, text=True, timeout=5
        )
        _POWERSHELL_VERSION = r.stdout.strip() or "5.1"
    except Exception:
        _POWERSHELL_VERSION = "5.1"
    return _POWERSHELL_VERSION


def get_pwsh_version() -> str:
    """检测 pwsh.exe (PS 7+) 版本号（带缓存）— 小沈 2026-07-01"""
    global _PWSH_VERSION
    if _PWSH_VERSION is not None:
        return _PWSH_VERSION
    pwsh = shutil.which("pwsh.exe")
    if not pwsh:
        _PWSH_VERSION = ""
        return _PWSH_VERSION
    try:
        r = subprocess.run(
            [pwsh, '-NoLogo', '-Command', '$PSVersionTable.PSVersion.ToString()'],
            capture_output=True, text=True, timeout=5
        )
        _PWSH_VERSION = r.stdout.strip()
    except Exception:
        _PWSH_VERSION = ""
    return _PWSH_VERSION


def get_system_prompt() -> str:
    """获取系统 Prompt 字符串（带缓存）"""
    system = platform.system()
    path_format = PATH_FORMATS.get(system, "/home/xxx/file.txt")
    env_info = _get_environment_info()

    logger.debug("[system_adapter] OS=%s", system)

    return "\n\n".join([
        env_info,
        f"【当前系统】{system}",
        f"【路径格式】{path_format}",
        _ALWAYS_RULES,
    ])
