# -*- coding: utf-8 -*-
"""
依赖自动安装工具 — 统一处理运行时Python依赖

【公用函数规范】
本文件是公共utility模块，所有依赖安装公共函数必须在此定义。
禁止在业务代码中重复实现依赖安装逻辑。

【小欧 2026-06-16】新增：DRY原则从gui_tools.py send_notification抽取
【小健 2026-06-18】增强：支持版本控制和前置依赖，集成到工具注册系统

===============================================================================
                         依赖管理系统使用指南
===============================================================================

1. 核心函数：ensure_dependency()
   用于检查并自动安装Python依赖包，支持版本控制和前置依赖。

   参数：
   - import_name: import时的模块名（如 'win10toast'）
   - pip_package: pip包名，默认等于import_name
   - version: 版本号，如 '==0.26.0'，可选
   - pre_install: 前置依赖列表（如 ['setuptools<70']），先于主包安装

   返回值：bool - True=依赖已可用，False=安装失败

   示例：
   ```
   # 简单依赖
   ensure_dependency("pandas")
   
   # 带版本号
   ensure_dependency("httpx", version="==0.26.0")
   
   # 带前置依赖
   ensure_dependency("win10toast", pre_install=["setuptools<70"])
   
   # 完整参数
   ensure_dependency(
       import_name="matplotlib", 
       pip_package="matplotlib",
       version=">=3.5.0",
       pre_install=["numpy"]
   )
   ```

2. 工具注册集成
   在工具注册文件中定义 TOOL_DEPENDENCIES 常量，支持两种格式：

   格式1：简单字符串（无版本限制）
   ```
   TOOL_DEPENDENCIES = {
       "analyze_data": ["pandas"],
       "filter_data": ["pandas"],
   }
   ```

   格式2：带版本号字符串
   ```
   TOOL_DEPENDENCIES = {
       "http_request": ["httpx==0.26.0", "httpcore==1.0.1"],
   }
   ```

   格式3：字典格式（完整参数）
   ```
   TOOL_DEPENDENCIES = {
       "send_notification": [
           {"import_name": "win10toast", "pip_package": "win10toast", "pre_install": ["setuptools<70"]}
       ],
   }
   ```

3. 注册时自动检查
   工具注册时会自动检查并安装所有依赖：
   ```
   tool_registry.register(
       name=name,
       description=desc,
       category=ToolCategory.DATAANALYSIS,
       implementation=func,
       dependencies=TOOL_DEPENDENCIES.get(name, []),  # 自动依赖检查
   )
   ```

4. 注意事项
   - 依赖检查在工具注册时进行，不在运行时
   - 安装失败会记录警告，但不阻止工具注册
   - 工具函数内部仍需进行运行时检查（使用 _check_module）
   - 版本锁定示例：httpx必须使用0.26.0版本（AGENTS.md要求）
"""

import subprocess
import sys
from typing import Optional


def _pip_install(pkg: str, version: Optional[str] = None) -> bool:
    """尝试pip安装，先普通模式失败后自动降级为--user
    
    Args:
        pkg: 包名，如 'httpx'
        version: 版本号，如 '==0.26.0'，可选
    """
    install_cmd = [sys.executable, "-m", "pip", "install", "-q"]
    if version:
        pkg_with_version = f"{pkg}{version}"
    else:
        pkg_with_version = pkg
    
    try:
        subprocess.check_call(install_cmd + [pkg_with_version])
        return True
    except subprocess.CalledProcessError:
        try:
            subprocess.check_call(install_cmd + ["--user", pkg_with_version])
            return True
        except subprocess.CalledProcessError:
            return False


def ensure_dependency(
    import_name: str,
    pip_package: Optional[str] = None,
    version: Optional[str] = None,
    pre_install: Optional[list] = None,
) -> bool:
    """确保Python依赖可用，缺失则自动pip安装（普通→--user两级降级）

    Args:
        import_name: import时的模块名（如 'win10toast'）
        pip_package: pip包名，默认等于import_name
        version: 版本号，如 '==0.26.0'，可选
        pre_install: 前置依赖列表（如 ['setuptools<70']），先于主包安装

    Returns:
        bool: True=依赖已可用，False=安装失败
    """
    if pip_package is None:
        pip_package = import_name

    if pre_install:
        for pkg in pre_install:
            _pip_install(pkg)

    try:
        __import__(import_name)
        return True
    except ImportError:
        if not _pip_install(pip_package, version):
            return False
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False
