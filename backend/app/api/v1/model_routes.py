
# -*- coding: utf-8 -*-
"""
model_routes - copy from ai_config/, only changed import paths
小欧 2026-07-10
"""
import yaml
import os
import subprocess
from fastapi import APIRouter, HTTPException
from app.api.v1.model_schemas import (
    ConfigFixResponse,
    ConfigPathResponse,
    ConfigResponse,
    ConfigUpdate,
    ConfigValidateRequest,
    ConfigValidateResponse,
    FullConfigResponse,
    ModelAddRequest,
    ModelInfo,
    ModelListResponse,
    ProviderAddRequest,
    ProviderInfo,
    ProviderUpdate,
    SecurityConfig,
)
from app.config import _make_safe_loader, get_config as get_config_instance
from app.safety.operation_backup import clear_backup_paths
from app.services.model.resolver import get_ai_config_resolver
from app.services.model.persistence import (
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
from app.logger import logger
from app.utils.response_utils import api_success, api_failure


router = APIRouter()

@router.get("/config", response_model=ConfigResponse)
@handle_config_errors("获取配置")
async def get_system_config():
    config = get_config_instance()
    final_provider, final_model = get_ai_config_resolver().resolve_provider_model()
    ai_config = config.get('ai', {})
    provider_config = ai_config.get(final_provider, {})
    api_key = provider_config.get('api_key', '')
    api_key_configured = bool(api_key and api_key.strip() != '')
    theme = config.get('app.theme', 'light')
    language = config.get('app.language', 'zh-CN')
    security_config = config.get('security', {})
    if not security_config:
        security_config = SecurityConfig(
            contentFilterEnabled=True,
            contentFilterLevel="medium",
            whitelistEnabled=False,
            commandWhitelist="",
            commandBlacklist="",
            confirmDangerousOps=True,
            maxFileSize=100
        )
    else:
        security_config = SecurityConfig(**security_config)
    logger.info(f"获取配置成功: provider={final_provider}, model={final_model}")
    return ConfigResponse(
        ai_provider=final_provider,
        ai_model=final_model,
        api_key_configured=api_key_configured,
        theme=theme,
        language=language,
        security=security_config,
        max_steps=config.get_max_steps(),
        project_root=config.get_project_root()
    )


@router.put("/config")
async def update_config(config_update: ConfigUpdate):
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


@router.put("/config/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest):
    try:
        resolver = get_ai_config_resolver()
        try:
            provider_config = resolver.get_service_config(request.provider, request.model)
        except ValueError as e:
            return ConfigValidateResponse(
                valid=False,
                message=str(e),
                model=None
            )
        final_provider, final_model = resolver.resolve_provider_model()
        logger.info(f"配置已保存: provider={final_provider}, model={final_model}")
        return ConfigValidateResponse(
            valid=True,
            message=f"配置已保存,将在首次使用时验证 {final_provider} ({final_model})",
            model=final_model
        )
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return ConfigValidateResponse(
            valid=False,
            message=f"验证过程出错: {str(e)}",
            model=None
        )


@router.get("/config/models", response_model=ModelListResponse)
async def get_model_list():
    try:
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        final_provider, final_model = resolver.resolve_provider_model()
        models = []
        model_id = 1
        for provider_name in ai_config.keys():
            if is_provider_metadata_field(provider_name):
                continue
            provider_data = ai_config.get(provider_name, {})
            if not isinstance(provider_data, dict):
                continue
            provider_models = provider_data.get('models', [])
            if isinstance(provider_models, list) and provider_models:
                for model_name in provider_models:
                    display_name = f"{provider_name} ({model_name})"
                    is_current = (final_provider == provider_name and final_model == model_name)
                    models.append(ModelInfo(
                        id=model_id,
                        provider=provider_name,
                        model=model_name,
                        display_name=display_name,
                        current_model=is_current
                    ))
                    model_id += 1
        logger.info(f"获取模型列表成功: {len(models)}个模型")
        return ModelListResponse(
            models=models,
            default_provider=final_provider
        )
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return ModelListResponse(
            models=[],
            default_provider=''
        )


@router.get("/config/full", response_model=FullConfigResponse)
@handle_config_errors("获取完整配置")
async def get_full_config():
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    final_provider, final_model = resolver.resolve_provider_model()
    providers = {}
    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if not isinstance(provider_data, dict):
            continue
        api_key = provider_data.get('api_key', '')
        providers[provider_name] = ProviderInfo(
            name=provider_name,
            api_base=provider_data.get('api_base', ''),
            api_key=api_key,
            model='',
            models=provider_data.get('models', []),
            timeout=provider_data.get('timeout', 60),
            max_retries=provider_data.get('max_retries', 3)
        )
    return FullConfigResponse(
        providers=providers,
        current_provider=final_provider,
        current_model=final_model
    )


@router.delete("/config/provider/{provider_name}")
@handle_config_errors("删除Provider")
async def delete_provider(provider_name: str):
    config_path, config = load_config()
    ensure_provider_exists(config, provider_name)
    provider_keys = [k for k in config.get('ai', {}).keys() if k != 'provider']
    if len(provider_keys) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个Provider")
    del config['ai'][provider_name]
    if config['ai'].get('provider') == provider_name:
        remaining = [k for k in config['ai'].keys() if k != 'provider']
        if remaining:
            config['ai']['provider'] = remaining[0]
    save_config(str(config_path), config)
    return api_success(f"Provider {provider_name} 已删除")


@router.delete("/config/provider/{provider_name}/model/{model_name}")
@handle_config_errors("删除模型")
async def delete_model(provider_name: str, model_name: str):
    config_path, config = load_config()
    ensure_provider_exists(config, provider_name)
    ensure_model_exists(config, provider_name, model_name)
    models = config['ai'][provider_name].get('models', [])
    if len(models) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个模型")
    models.remove(model_name)
    config['ai'][provider_name]['models'] = models
    save_config(str(config_path), config)
    return api_success(f"模型 {model_name} 已删除")


@router.put("/config/provider/{provider_name}/model/{old_model_name}")
@handle_config_errors("更新模型")
async def update_model(provider_name: str, old_model_name: str, data: ModelAddRequest):
    config_path, config = load_config()
    ensure_provider_exists(config, provider_name)
    models = config['ai'][provider_name].get('models', [])
    new_model_name = ' '.join(data.model.split())
    if old_model_name not in models:
        raise HTTPException(status_code=404, detail=f"模型 {old_model_name} 不存在")
    if new_model_name == old_model_name:
        return api_success("模型名称未改变")
    if new_model_name in models:
        raise HTTPException(status_code=400, detail=f"模型 {new_model_name} 已存在")
    index = models.index(old_model_name)
    models[index] = new_model_name
    config['ai'][provider_name]['models'] = models
    save_config(str(config_path), config)
    return api_success(f"模型已从 {old_model_name} 更新为 {new_model_name}")


@router.put("/config/provider/{provider_name}")
@handle_config_errors("更新Provider")
async def update_provider(provider_name: str, data: ProviderUpdate):
    config_path, config = load_config()
    backup_path = _backup_config(config_path)
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
    save_config(str(config_path), config)
    return api_success(f"Provider {provider_name} 已更新", warnings=warnings, backup_path=str(backup_path))


@router.post("/config/provider")
@handle_config_errors("添加Provider")
async def add_provider(data: ProviderAddRequest):
    config_path, config = load_config()
    backup_path = _backup_config(config_path)
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
    save_config(str(config_path), config)
    return api_success(f"Provider {data.name} 已添加", warnings=warnings)


@router.post("/config/provider/{provider_name}/model")
@handle_config_errors("添加模型")
async def add_model(provider_name: str, data: ModelAddRequest):
    config_path, config = load_config()
    ensure_provider_exists(config, provider_name)
    model_name = ' '.join(data.model.split())
    ensure_model_not_duplicate(config, provider_name, model_name)
    models = config['ai'][provider_name].get('models', [])
    models.append(model_name)
    config['ai'][provider_name]['models'] = models
    if not config['ai'].get('model'):
        config['ai']['model'] = model_name
    save_config(str(config_path), config)
    return api_success(f"模型 {data.model} 已添加")


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
    config = get_config_instance()
    config.reload()
    logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
    return ConfigFixResponse(
        success=True,
        fixed_issues=fixed_issues,
        warnings=warnings,
        backup_path=str(backup_path)
    )


@router.get("/config/path", response_model=ConfigPathResponse)
@handle_config_errors("获取配置路径")
async def get_config_path_endpoint():
    config_path = get_config_path()
    return ConfigPathResponse(
        config_path=str(config_path),
        config_dir=str(config_path.parent),
        exists=config_path.exists(),
    )

@router.get("/config/read")
@handle_config_errors("读取配置文件")
async def read_config_file():
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"config_content": content}

@router.post("/config/open-folder")
@handle_config_errors("打开配置目录")
async def open_config_folder():
    config_path = get_config_path()
    config_dir = str(config_path.parent)
    if not os.path.exists(config_dir):
        raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
    subprocess.Popen(
        ["explorer", "/e,", config_dir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"已打开配置目录: {config_dir}")
    return api_success(path=config_dir)

