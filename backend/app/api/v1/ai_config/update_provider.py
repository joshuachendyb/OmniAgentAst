from . import router
from .models import ProviderUpdate
from ._helpers import get_config_path, read_yaml_config, write_yaml_config, reload_ai_config
from ._decorators import handle_config_errors
from ._backup_config import _backup_config
from ._fix_config_common_issues import _fix_config_common_issues
from ._validate_config_integrity import _validate_config_integrity
from ._validators import ensure_provider_exists
from app.utils.response_utils import api_success, api_failure


@router.put("/config/provider/{provider_name}")
@handle_config_errors("更新Provider")
async def update_provider(provider_name: str, data: ProviderUpdate):
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config = read_yaml_config(config_path)

    ensure_provider_exists(config, provider_name)

    if data.api_base is not None:
        config['ai'][provider_name]['api_base'] = data.api_base
    if data.api_key is not None:
        config['ai'][provider_name]['api_key'] = data.api_key.strip()
    if data.model is not None:
        config['ai']['model'] = data.model.strip()
    if data.timeout is not None:
        config['ai'][provider_name]['timeout'] = data.timeout
    if data.max_retries is not None:
        config['ai'][provider_name]['max_retries'] = data.max_retries

    config = _fix_config_common_issues(config)
    is_valid, errors, warnings = _validate_config_integrity(config)
    if not is_valid:
        return api_failure("配置验证失败", errors=errors, warnings=warnings, backup_path=str(backup_path))

    write_yaml_config(str(config_path), config)
    reload_ai_config()
    return api_success(f"Provider {provider_name} 已更新", warnings=warnings, backup_path=str(backup_path))
