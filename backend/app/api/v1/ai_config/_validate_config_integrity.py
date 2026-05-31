from typing import Dict, Any, Tuple, List


def _validate_config_integrity(config_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    完整验证配置文件完整性

    返回: (是否通过, 错误列表, 警告列表)
    """
    errors = []
    warnings = []
    ai_config = config_data.get('ai', {})

    if 'provider' not in ai_config:
        errors.append("缺少 ai.provider 字段")
    if 'model' not in ai_config:
        errors.append("缺少 ai.model 字段")
    if errors:
        return False, errors, warnings

    selected_provider = ai_config['provider']
    selected_model = ai_config['model']

    if selected_provider not in ai_config:
        errors.append(f"provider '{selected_provider}' 不存在")
        return False, errors, warnings

    provider_config = ai_config[selected_provider]

    if 'api_base' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_base 字段")
    if 'api_key' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_key 字段")
    if errors:
        return False, errors, warnings

    if 'models' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 models 列表")
        return False, errors, warnings

    models_list = provider_config['models']

    if selected_model not in models_list:
        errors.append(f"model '{selected_model}' 不在 provider '{selected_provider}' 的 models 列表中")
        return False, errors, warnings

    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            warnings.append(f"provider '{provider_name}' 下有废弃的 model 字段，建议删除")

    return True, errors, warnings
