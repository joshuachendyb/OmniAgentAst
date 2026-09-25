# -*- coding: utf-8 -*-
"""
services — 共享服务模块

小欧 2026-07-10 factory/ → lifecycle/ + backup_paths → safety/operation_backup
小欧 2026-09-25 [70] ConnectionScope连接池统一所有者(3.8): 导出补 get_scope(orchestrator 唯一所有者入口), __all__ 同步 — 小欧 2026-09-25
"""

from app.services.lifecycle import (
    ConfigValidationResult,
    close_instance,
    close_instance_sync,
    get_config_path,
    make_validation_error,
    validate_credentials,
    validate_config,
    get_service,
    get_service_for_model,
    get_scope,
    reset,
)

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "get_scope", "reset",  # [70] +get_scope — 小欧-2026-09-25
]
