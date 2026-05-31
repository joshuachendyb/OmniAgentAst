"""
AIServiceFactory — 类骨架

从 factory.py 拆出，遵循 SRP：
- 各功能函数独立文件
- 本文件保留 AIServiceFactory 类骨架

Author: 小沈
"""

from typing import Optional
import threading

from app.services.llm_core import BaseAIService
from app.services.factory.models import ConfigValidationResult
from app.services.factory.close_instance import close_instance
from app.services.factory.close_instance_sync import close_instance_sync
from app.services.factory.get_config_path import get_config_path as _get_config_path
from app.services.factory.make_validation_error import make_validation_error
from app.services.factory.validate_credentials import validate_credentials
from app.services.factory.validate_config import validate_config
from app.services.factory.get_service import get_service as _get_service
from app.services.factory.reset import reset as _reset
from app.services.factory.get_service_for_model import get_service_for_model as _get_service_for_model
from app.services.factory.set_backup_paths import set_backup_paths as _set_backup_paths
from app.services.factory.get_backup_paths import get_backup_paths as _get_backup_paths
from app.services.factory.clear_backup_paths import clear_backup_paths as _clear_backup_paths


class AIServiceFactory:
    """AI 服务工厂 — 类骨架"""

    _instance: Optional[BaseAIService] = None
    _current_provider: str = ""
    _lock: threading.Lock = threading.Lock()
    _backup_path: Optional[str] = None
    _config_path: Optional[str] = None
    _backup_lock: threading.Lock = threading.Lock()

    @staticmethod
    async def _close_instance(instance: Optional[BaseAIService]) -> None:
        return await close_instance(instance)

    @staticmethod
    def _close_instance_sync(instance: Optional[BaseAIService]) -> None:
        return close_instance_sync(instance)

    @classmethod
    def get_config_path(cls, config_path: Optional[str] = None) -> str:
        return _get_config_path(config_path)

    @staticmethod
    def _make_validation_error(message, field="", provider="", model="", errors=None, warnings=None):
        return make_validation_error(message, field, provider, model, errors, warnings)

    @staticmethod
    def _validate_credentials(ai_config, final_provider):
        return validate_credentials(ai_config, final_provider)

    @classmethod
    def validate_config(cls, config_path=None):
        return validate_config(config_path)

    @classmethod
    def get_service(cls, config_path=None):
        return _get_service(config_path)

    @classmethod
    def reset(cls):
        return _reset()

    @classmethod
    def get_service_for_model(cls, provider, model, config_path=None):
        return _get_service_for_model(provider, model, config_path)

    @classmethod
    def set_backup_paths(cls, backup_path, config_path):
        return _set_backup_paths(backup_path, config_path)

    @classmethod
    def get_backup_paths(cls):
        return _get_backup_paths()

    @classmethod
    def clear_backup_paths(cls):
        return _clear_backup_paths()
