
"""
系统信息适配器 — 生成系统自适应的 Prompt 内容

【功能】根据服务器 OS 生成路径格式提示
【重构】2026-06-14 小沈 — COMMANDS移至shell_register.execute_shell_command描述
【2026-07-28 小欧】压缩系统提示文字: 删路径格式(LLM已知)、合并环境信息、压缩路径规则
【2026-07-28 小欧】新增 get_default_shell_code(): 返回内部 shell 编码(ps7/ps5/bash),供 system_prompts 动态切换
【2026-08-10 小欧】_get_environment_info 扩展: 环境行追加授权目录(allowed_dirs, 分号分隔), 与项目根一并告知LLM; 未配置时保持原样 — 北京老陈驱动
【2026-08-10 小欧】git 状态判定固化: 只基于项目根(get_project_root), 严禁从代码库根推算 — 北京老陈裁定
【2026-08-11 小欧】三堂会审复核落地(P2-8): 删除env行授权目录段(DRY) — 授权目录结构化块已由system_prompts._get_project_root_info()注入,
    env行分号格式重复注入属DRY违反; 同步删allowed无消费变量

Author: 小沈 - 2026-06-14
"""
import os
import platform
import shutil
import subprocess
from typing import Optional

from app.logger import logger
from app.utils.time_utils import now_str
from app.config import get_config as get_config_instance

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
    """获取环境信息（项目根目录/授权目录/Git 状态/日期时间）— 小沈 2026-06-11
    【2026-06-23 北京老陈】工作目录改为项目根目录,避免显示backend子目录
    【2026-08-10 小欧】追加授权目录, 与项目根一并告知LLM
    """

    config = get_config_instance()
    # git 状态只基于项目根(tool工作区), 严禁从代码库根推算 — 北京老陈 2026-08-10 裁定
    root = config.get_project_root()
    now = now_str()
    is_git = _check_is_git_repo(root)
    git_status = "是" if is_git else "否"
    # 2026-08-11 小欧(P2-8): 授权目录不再注入env行(DRY) — 结构化块已由 system_prompts._get_project_root_info() 注入,
    #   多行列表对LLM更友好且 build_full_system_prompt 总是append, env行分号格式重复注入属冗余
    env = f"【环境】任务根目录={root}, Git={git_status}, 时间={now}"
    return env


_ALWAYS_RULES = """【路径】
- 勿用~; 中文路径禁翻译/转换

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


def get_default_shell_name() -> str:
    """返回实际默认 Shell 名称（匹配 shell_engine.py 的启动优先级）— 北京老陈 2026-07-09"""
    pwsh_ver = get_pwsh_version()
    if pwsh_ver:
        return f"PowerShell {pwsh_ver}"
    ps_ver = get_powershell_version()
    return f"Windows PowerShell {ps_ver}"


def get_default_shell_code() -> str:
    """返回默认 shell 的内部编码 (ps7/ps5/bash) — 小欧 2026-07-28"""
    system = platform.system()
    if system != "Windows":
        return "bash"
    pwsh_ver = get_pwsh_version()
    if pwsh_ver:
        return "ps7"
    return "ps5"


def get_system_prompt() -> str:
    """获取系统 Prompt 字符串（带缓存）"""
    system = platform.system()
    env_info = _get_environment_info()

    logger.debug("[system_adapter] OS=%s", system)

    return "\n\n".join([
        env_info,
        f"【系统】{system}",
        _ALWAYS_RULES,
    ])

