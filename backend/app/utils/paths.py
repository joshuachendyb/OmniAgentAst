# -*- coding: utf-8 -*-
"""
路径辅助函数 — 统一配置文件路径计算

【3.21修复 北京老陈 2026-05-31】消除"config/config.yaml"路径片段重复，
所有模块统一调用 get_config_path() 获取配置路径。
"""

from pathlib import Path
from typing import Optional

# 项目根目录缓存（基于当前文件位置推算）
_PROJECT_ROOT: Optional[Path] = None


def _get_project_root() -> Path:
    """唯一项目根目录计算入口——基于当前文件位置推算
    
    路径推算: utils/paths.py → utils/ → app/ → backend/ → 项目根目录
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    return _PROJECT_ROOT


def get_config_path(filename: str = "config.yaml") -> str:
    """统一配置路径获取
    
    Args:
        filename: 配置文件名，默认"config.yaml"
    
    Returns:
        配置文件的完整路径字符串
    """
    return str(_get_project_root() / "config" / filename)


# 配置文件名常量
DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_TOOLS_CONFIG_FILENAME = "tools.yaml"
