# -*- coding: utf-8 -*-
"""
services — 共享服务模块

小健 - 2026-06-08 清理:删除AIServiceFactory死代码
"""

from app.services.factory import (
    ConfigValidationResult,
    close_instance,
    close_instance_sync,
    get_config_path,
    make_validation_error,
    validate_credentials,
    validate_config,
    get_service,
    get_service_for_model,
    reset,
    set_backup_paths,
    get_backup_paths,
    clear_backup_paths,
)

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
    "set_backup_paths", "get_backup_paths", "clear_backup_paths",
]
