# -*- coding: utf-8 -*-
"""
factory — 从 factory.py 拆出的职责

小健 - 2026-06-08 清理:删除AIServiceFactory死代码
小沈 - 2026-06-09 修复:删除重复get_config_path,改用app.utils.paths

- ConfigValidationResult: 模型
- close_instance/close_instance_sync: 服务生命周期
- get_config_path: 配置路径(来自app.utils.paths)
- make_validation_error/validate_credentials/validate_config: 配置验证
- get_service/get_service_for_model/reset: 服务创建
- set_backup_paths/get_backup_paths/clear_backup_paths: 备份路径
"""

from app.services.factory.models import ConfigValidationResult
from app.services.factory.lifecycle import close_instance, close_instance_sync, reset
from app.utils.paths import get_config_path
from app.services.factory.validation import make_validation_error, validate_credentials, validate_config
from app.services.factory.service import get_service, get_service_for_model
from app.services.factory.backup_paths import set_backup_paths, get_backup_paths, clear_backup_paths

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
    "set_backup_paths", "get_backup_paths", "clear_backup_paths",
]
