# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 配置业务服务(方案4.7.3步骤3)。从 api/v1/model_routes.py 复制 update_config 业务编排,
#   复用 services/model/persistence.py 底层 I/O, 不重复迁移 read/write_yaml_config/save_config/_backup_config/
#   _auto_fix_and_validate(已在 persistence)。越层 app.safety.operation_backup.clear_backup_paths 依赖在业务服务层
#   调用(services→safety 合法方向), 消除 API→safety 越层(守护测试 api 规则可启用)。DTO 边界: 本服务不 import api/v1 DTO,
#   接收 API 层传入的 config_update 对象(鸭子类型访问字段/model_dump), 业务逻辑一字不改。
"""
config_service — 配置业务服务(services/model)

职责(方案4.7.3, 小欧 2026-08-13): update_config 业务编排(备份→改字段→修复验证→写回→reload→删备份)。
YAML 底层 I/O 归属 persistence.py, 本服务只做编排。
"""
import yaml

from fastapi import HTTPException

from app.config import _make_safe_loader, get_config as get_config_instance
from app.safety.operation_backup import clear_backup_paths
from app.services.model.persistence import (
    FIELD_HANDLERS,
    _auto_fix_and_validate,
    _backup_config,
    _restore_backup_if_needed,
    get_config_path,
    read_yaml_config,
    write_yaml_config,
)
from app.logger import logger


def update_config(config_update):
    """配置更新业务编排 — 自 api/v1/model_routes.py 迁入, 复用 persistence.py 底层 I/O — 小欧 2026-08-13"""
    backup_path = None
    config_path = None
    restored = [False]

    try:
        config_path = get_config_path()
        backup_path = _backup_config(config_path)
        original_config_data = read_yaml_config(config_path)
        config_data = original_config_data.copy()
        config_data.setdefault('app', {})

        for field, handler in FIELD_HANDLERS.items():
            value = getattr(config_update, field, None)
            if value is not None:
                handler(config_data, config_update)

        is_valid, errors, warnings, fail_result = _auto_fix_and_validate(
            config_data, config_path, backup_path, original_config_data)
        if not is_valid:
            return fail_result

        write_yaml_config(str(config_path), config_data)
        with open(config_path, 'r', encoding='utf-8') as f:
            verify_data = yaml.load(f, Loader=_make_safe_loader())
            logger.info(f"[update_config] 验证写入: provider={verify_data['ai'].get('provider')}, model={verify_data['ai'].get('model')}")
        get_config_instance().reload()

        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
                logger.info(f"验证成功,已删除备份文件:{backup_path}")
            except Exception as e:
                logger.warning(f"删除备份文件失败:{e}")
        clear_backup_paths()

        current_provider = config_data.get('ai', {}).get('provider', '')
        current_model = config_data.get('ai', {}).get('model', '')
        return {
            "success": True, "message": "配置更新成功,请验证服务可用性",
            "updated_fields": config_update.model_dump(exclude_none=True), "warnings": warnings,
            "backup_path": str(backup_path) if backup_path else None, "current_provider": current_provider, "current_model": current_model,
        }

    except HTTPException:
        _restore_backup_if_needed(backup_path, config_path, restored)
        if backup_path:
            backup_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        _restore_backup_if_needed(backup_path, config_path, restored)
        if backup_path:
            backup_path.unlink(missing_ok=True)
        logger.error(f"更新配置失败:{e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新配置失败,请稍后重试")