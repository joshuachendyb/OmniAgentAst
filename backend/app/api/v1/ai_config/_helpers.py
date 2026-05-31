"""ai_config 包内部公用函数 — 配置路径 / YAML 读写 / 通用字段更新

【小健 2026-05-31】新建：从各 endpoint 文件中提取公共模式
"""

from pathlib import Path
from typing import Any, Optional

import yaml

from app.services import AIServiceFactory
from app.utils.logger import logger
from ._write_yaml_with_order import _write_yaml_with_order


def get_config_path() -> Path:
    """获取配置文件路径（缓存式调用）"""
    return Path(AIServiceFactory.get_config_path())


def read_yaml_config(config_path: Path) -> dict:
    """读取 YAML 配置文件，文件不存在时返回空 dict"""
    if not config_path.exists():
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def write_yaml_config(config_path: str, data: dict) -> None:
    """使用有序 Key 写入 YAML 配置文件"""
    _write_yaml_with_order(config_path, data)


def reload_ai_config() -> None:
    """重新加载 AI 配置并重置缓存"""
    from app.config import get_config as get_config_instance
    config_obj = get_config_instance()
    config_obj._load_config()
    AIServiceFactory.reset()


def _set_app_field(config_data: dict, field_name: str, value: Any, display_name: str = "") -> None:
    """设置 app 下单一字段，替换 _update_theme / _update_language"""
    config_data.setdefault('app', {})[field_name] = value
    logger.info(f"更新{display_name or field_name}: {value}")
