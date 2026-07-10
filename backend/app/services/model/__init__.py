# -*- coding: utf-8 -*-
"""
config — 配置管理模块

小欧 2026-07-10 从 services/ 根迁入，消除两个flat文件的重叠感

- resolver.py: AI配置只读解析（resolve_provider_model, get_service_config）
- persistence.py: YAML I/O、配置修复、备份、验证
"""

from app.services.model.resolver import AIConfigResolver, get_ai_config_resolver
from app.services.model.persistence import (
    FIELD_HANDLERS,
    _auto_fix_and_validate,
    _backup_config,
    _fix_config_common_issues,
    _restore_backup_if_needed,
    _validate_config_integrity,
    ensure_model_exists,
    ensure_model_not_duplicate,
    ensure_provider_exists,
    ensure_provider_not_duplicate,
    get_config_path,
    handle_config_errors,
    is_provider_metadata_field,
    load_config,
    read_yaml_config,
    save_config,
    write_yaml_config,
)

__all__ = [
    "AIConfigResolver", "get_ai_config_resolver",
    "FIELD_HANDLERS",
    "_auto_fix_and_validate", "_backup_config",
    "_fix_config_common_issues", "_restore_backup_if_needed",
    "_validate_config_integrity",
    "ensure_model_exists", "ensure_model_not_duplicate",
    "ensure_provider_exists", "ensure_provider_not_duplicate",
    "get_config_path", "handle_config_errors",
    "is_provider_metadata_field", "load_config",
    "read_yaml_config", "save_config", "write_yaml_config",
]
