# -*- coding: utf-8 -*-
"""
factory — 从 factory.py 拆出的职责

- ConfigValidationResult: 模型
- close_instance/close_instance_sync: 服务生命周期
- get_config_path: 配置路径
- make_validation_error/validate_credentials/validate_config: 配置验证
- get_service/get_service_for_model/reset: 服务创建
- set_backup_paths/get_backup_paths/clear_backup_paths: 备份路径
"""

from app.services.factory.models import ConfigValidationResult
from app.services.factory.close_instance import close_instance
from app.services.factory.close_instance_sync import close_instance_sync
from app.services.factory.get_config_path import get_config_path
from app.services.factory.make_validation_error import make_validation_error
from app.services.factory.validate_credentials import validate_credentials
from app.services.factory.validate_config import validate_config
from app.services.factory.get_service import get_service
from app.services.factory.reset import reset
from app.services.factory.get_service_for_model import get_service_for_model
from app.services.factory.set_backup_paths import set_backup_paths
from app.services.factory.get_backup_paths import get_backup_paths
from app.services.factory.clear_backup_paths import clear_backup_paths
from app.services.factory.ai_service_factory import AIServiceFactory

__all__ = [
    "AIServiceFactory",
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "reset",
    "set_backup_paths", "get_backup_paths", "clear_backup_paths",
]
