# -*- coding: utf-8 -*-
"""
service_manager — 服务管理模块

小欧 2026-07-10 从 factory/ 改名迁入
小欧 2026-09-25 [70] ConnectionScope连接池统一所有者(3.7): 导出补 shutdown(停机收口)与 get_scope(唯一所有者门面), __all__ 同步 — 小欧 2026-09-25

- ConfigValidationResult: 模型
- close_instance/close_instance_sync/shutdown: 服务生命周期(含停机 drain)
- get_config_path: 配置路径(来自app.utils.paths)
- make_validation_error/validate_credentials/validate_config: 配置验证
- get_service/get_service_for_model/get_scope/reset: 服务创建与唯一所有者门面
"""

from app.services.lifecycle.validation import ConfigValidationResult
from app.services.lifecycle.lifecycle import close_instance, close_instance_sync, reset
from app.services.lifecycle.lifecycle import shutdown  # [70] 停机收口 — 小欧-2026-09-25
from app.config import get_config_path
from app.services.lifecycle.validation import make_validation_error, validate_credentials, validate_config
from app.services.lifecycle.service import get_service, get_service_for_model, get_scope  # [70] — 小欧-2026-09-25

__all__ = [
    "ConfigValidationResult",
    "close_instance", "close_instance_sync", "get_config_path",
    "make_validation_error", "validate_credentials", "validate_config",
    "get_service", "get_service_for_model", "get_scope", "reset", "shutdown",  # [70] +get_scope/shutdown — 小欧-2026-09-25
]
