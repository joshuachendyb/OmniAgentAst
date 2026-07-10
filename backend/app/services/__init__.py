# -*- coding: utf-8 -*-
"""
services — 共享服务模块

小欧 2026-07-10 factory/ → lifecycle/ + backup_paths → safety/operation_backup
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
    reset,
)

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
]
