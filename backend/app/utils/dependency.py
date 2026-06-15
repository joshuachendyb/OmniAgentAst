# -*- coding: utf-8 -*-
"""
依赖自动安装工具 — 统一处理运行时Python依赖

【公用函数规范】
本文件是公共utility模块，所有依赖安装公共函数必须在此定义。
禁止在业务代码中重复实现依赖安装逻辑。

【小欧 2026-06-16】新增：DRY原则从gui_tools.py send_notification抽取
"""

import subprocess
import sys
from typing import Optional


def ensure_dependency(
    import_name: str,
    pip_package: Optional[str] = None,
    pre_install: Optional[list] = None,
) -> bool:
    """确保Python依赖可用，缺失则自动pip安装

    Args:
        import_name: import时的模块名（如 'win10toast'）
        pip_package: pip包名，默认等于import_name
        pre_install: 前置依赖列表（如 ['setuptools<70']），这些包先于主包安装

    Returns:
        bool: True=依赖已可用，False=安装失败

    Usage:
        if not ensure_dependency("win10toast", pre_install=["setuptools<70"]):
            return build_error(...)
    """
    if pip_package is None:
        pip_package = import_name

    if pre_install:
        for pkg in pre_install:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

    try:
        __import__(import_name)
        return True
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_package, "-q"])
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False
