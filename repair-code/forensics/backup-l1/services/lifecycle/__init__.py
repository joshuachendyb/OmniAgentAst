# -*- coding: utf-8 -*-
"""
service_manager — 服务管理模块

小欧 2026-07-10 从 factory/ 改名迁入

- ConfigValidationResult: 模型
- close_instance/close_instance_sync: 服务生命周期
- get_config_path: 配置路径(来自app.utils.paths)
- make_validation_error/validate_credentials/validate_config: 配置验证
- get_service/get_service_for_model/reset: 服务创建
"""

from app.services.lifecycle.validation import ConfigValidationResult
from app.services.lifecycle.lifecycle import close_instance, close_instance_sync, reset
from app.config import get_config_path
from app.services.lifecycle.validation import make_validation_error, validate_credentials, validate_config
from app.services.lifecycle.service import get_service, get_service_for_model

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
]
