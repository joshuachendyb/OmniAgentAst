from . import router
from .models import ConfigFixResponse
from ._helpers import get_config_path, read_yaml_config, write_yaml_config
from ._decorators import handle_config_errors
from ._backup_config import _backup_config
from ._validate_config_integrity import _validate_config_integrity
from app.utils.logger import logger


@router.post("/config/fix", response_model=ConfigFixResponse)
@handle_config_errors("配置修复")
async def fix_config():
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config_data = read_yaml_config(config_path)

    fixed_issues = []
    ai_config = config_data.get('ai', {})
    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            del provider_data['model']
            fixed_issues.append(f"删除 provider '{provider_name}' 下废弃的 model 字段")

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
