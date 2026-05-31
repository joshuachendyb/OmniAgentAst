from . import router
from .models import ConfigUpdate
from .field_handlers import FIELD_HANDLERS
from ._backup_config import _backup_config
from ._auto_fix_and_validate import _auto_fix_and_validate
from ._write_yaml_with_order import _write_yaml_with_order
from ._restore_backup_if_needed import _restore_backup_if_needed
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.put("/config")
async def update_config(config_update: ConfigUpdate):
    backup_path = None
    config_path = None
    restored = [False]

    try:
        config_path = Path(AIServiceFactory.get_config_path())
        backup_path = _backup_config(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            original_config_data = yaml.safe_load(f) or {}
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

        _write_yaml_with_order(str(config_path), config_data)
        with open(config_path, 'r', encoding='utf-8') as f:
            verify_data = yaml.safe_load(f)
            logger.info(f"[update_config] 验证写入: provider={verify_data['ai'].get('provider')}, model={verify_data['ai'].get('model')}")
        get_config_instance().reload()

        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
                logger.info(f"验证成功，已删除备份文件：{backup_path}")
            except Exception as e:
                logger.warning(f"删除备份文件失败：{e}")
        AIServiceFactory.clear_backup_paths()

        current_provider = config_data.get('ai', {}).get('provider', '')
        current_model = config_data.get('ai', {}).get('model', '')
        return {
            "success": True, "message": "配置更新成功，请验证服务可用性",
            "updated_fields": config_update.dict(exclude_none=True), "warnings": warnings,
            "backup_path": str(backup_path), "current_provider": current_provider, "current_model": current_model,
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
        logger.error(f"更新配置失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新配置失败，请稍后重试")
