# -*- coding: utf-8 -*-
"""
config — 配置管理模块

小欧 2026-07-10 从 services/ 根迁入，消除两个flat文件的重叠感

- resolver.py: AI配置只读解析（resolve_model_ref, get_service_config）
- config_helpers.py: YAML I/O、配置修复、备份、验证
"""
# 编辑历史:
# 2026-08-14 - 小欧 - 改名名实相符: persistence.py → config_helpers.py(包内re-export同步)
# 2026-08-23 - 小欧 - 三轮三堂会审修复: docstring resolve_provider_model → resolve_model_ref(改名后名实同步)
# 2026-09-26 - 小欧 - 包级导出 FIELD_HANDLERS 随 config_helpers 同步收敛为
#   只含 "ai_model_ref" 一项（六个旧 handler 已删，PUT /config 只写切全局模型）。本文件仅同步包级 re-export，
#   导出集合与名值零变化（仍是同一批符号，只是 FIELD_HANDLERS 字典内容变窄），
#   故不改 __all__、不改下游 import 写法（禁止 backward：不为"看起来一致"而制造无谓改动）— 小欧 2026-09-26

from app.services.model.resolver import AIConfigResolver, get_ai_config_resolver
from app.services.model.config_helpers import (
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
    # 2026-09-26 小欧 - FIELD_HANDLERS 导出保留（已收敛为只含 ai_model_ref 一项）
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
