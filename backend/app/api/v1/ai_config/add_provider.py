from . import router
from .models import ProviderAddRequest
from ._helpers import get_config_path, read_yaml_config, write_yaml_config, reload_ai_config
from ._decorators import handle_config_errors
from ._backup_config import _backup_config
from ._validate_config_integrity import _validate_config_integrity
from ._validators import ensure_provider_not_duplicate
from app.utils.response_utils import api_success, api_failure


@router.post("/config/provider")
@handle_config_errors("添加Provider")
async def add_provider(data: ProviderAddRequest):
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config = read_yaml_config(config_path)

    ensure_provider_not_duplicate(config, data.name)

    config['ai'][data.name] = {
        'api_base': data.api_base.strip(),
        'api_key': data.api_key.strip() if data.api_key else "",
        'models': [m.strip() for m in (data.models if data.models else ([data.model] if data.model else []))],
        'timeout': data.timeout,
        'max_retries': data.max_retries
    }
    is_valid, errors, warnings = _validate_config_integrity(config)
    if not is_valid:
        return api_failure("配置验证失败", errors=errors, backup_path=str(backup_path))

    write_yaml_config(str(config_path), config)
    reload_ai_config()
    return api_success(f"Provider {data.name} 已添加", warnings=warnings)
