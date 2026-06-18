from . import router
from .models import ConfigFixResponse
from ._helpers import get_config_path, read_yaml_config, write_yaml_config
from ._helpers import handle_config_errors, _backup_config, _validate_config_integrity, _fix_config_common_issues
from app.utils.logger import logger


@router.post("/config/fix", response_model=ConfigFixResponse)
@handle_config_errors("配置修复")
async def fix_config():
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config_data = read_yaml_config(config_path)

    config_data = _fix_config_common_issues(config_data)
    fixed_issues = [f"删除 provider 下废弃的 model 字段"]

    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        return ConfigFixResponse(
            success=False,
            fixed_issues=fixed_issues,
            warnings=warnings + errors,
            backup_path=str(backup_path)
        )

    write_yaml_config(str(config_path), config_data)
    from app.config import get_config as get_config_instance
    config = get_config_instance()
    config.reload()
    logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
    return ConfigFixResponse(
        success=True,
        fixed_issues=fixed_issues,
        warnings=warnings,
        backup_path=str(backup_path)
    )
