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
from app.services.factory.close_instance import close_instance
from app.services.factory.close_instance_sync import close_instance_sync
from app.utils.paths import get_config_path
from app.services.factory.make_validation_error import make_validation_error
from app.services.factory.validate_credentials import validate_credentials
from app.services.factory.validate_config import validate_config
from app.services.factory.get_service import get_service
from app.services.factory.reset import reset
from app.services.factory.get_service_for_model import get_service_for_model
from app.services.factory.backup_paths import set_backup_paths, get_backup_paths, clear_backup_paths

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
    "set_backup_paths", "get_backup_paths", "clear_backup_paths",
]
