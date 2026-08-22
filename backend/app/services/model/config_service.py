# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 配置业务服务(方案4.7.3步骤3)。从 api/v1/model_routes.py 复制 update_config 业务编排,
#   复用 services/model/persistence.py 底层 I/O, 不重复迁移 read/write_yaml_config/save_config/_backup_config/
#   _auto_fix_and_validate(已在 persistence)。越层 app.safety.operation_backup.clear_backup_paths 依赖在业务服务层
#   调用(services→safety 合法方向), 消除 API→safety 越层(守护测试 api 规则可启用)。DTO 边界: 本服务不 import api/v1 DTO,
#   接收 API 层传入的 config_update 对象(鸭子类型访问字段/model_dump), 业务逻辑一字不改。
# 2026-08-13 - 小沈 - P3 CRUD全量下沉: 从 model_routes.py 复制12个CRUD业务逻辑迁入, 业务逻辑一字不改,
#   仅改归属与返回格式(返回plain dict, API层构造Pydantic响应模型)。model_routes 降为纯薄壳。
#   DTO边界: 本服务不import api/v1/model_schemas, 接收DTO对象(鸭子类型)或原始参数。
# 2026-08-13 - 小沈 - 三堂会审修复: validate_config 改只接收 provider。原签名接收(model) 但 API层
#   ConfigValidateRequest 无 model 字段, 迁移后 route 访问 request.model 在 service try 之外抛
#   AttributeError→500(原代码在 try 内被吞返回 valid=False)。get_service_config(provider, model) 的
#   model 参数实际未使用, 改传 "" 保持语义不变。校验接口第一次真正可用(原实现永远走假报错分支)。
# 2026-08-14 - 小欧 - 改名名实相符: model_routes.py→config_routes.py, persistence.py→config_helpers.py(import与docstring同步)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.6: 全文件 resolve_provider_model 拆包 → resolve_model_ref
#   (4处); get_system_config_data 返回 ai_model_ref=resolved_model、get_full_config 返回 current_model_ref=
#   resolved_model、update_config 返回 current_model_ref 结构(方案B 前端 api.ts 契约已同步改)
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P2): update_config 的 updated_fields 内嵌 ai_model_ref 的
#   api_base/display_name null 键剔除(模型转 dict 后过滤 None), 免前端/日志噪声
"""
config_service — 配置业务服务(services/model)

职责: 配置CRUD业务编排。YAML底层I/O归属config_helpers.py, 本服务只做编排。
A7(小欧 2026-08-13): update_config 业务编排。
P3(小沈 2026-08-13): 全量CRUD下沉, model_routes 降为纯薄壳。
"""
import os
import subprocess
import yaml

from fastapi import HTTPException

from app.config import _make_safe_loader, get_config as get_config_instance
from app.safety.operation_backup import clear_backup_paths
from app.services.model.resolver import get_ai_config_resolver
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
    is_provider_metadata_field,
    load_config,
    read_yaml_config,
    save_config,
    write_yaml_config,
)
from app.logger import logger
from app.utils.response_utils import api_success, api_failure


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

        # 归一(小欧 2026-08-22 报告v1.25 6.6): current_provider/current_model → current_model_ref 结构(PUT /config 直接返回前端, 方案B)
        # 三堂会审修复(P2): updated_fields 内嵌 ModelRef 的 api_base/display_name null 键剔除, 免前端噪声 — 小欧
        _updated_fields = config_update.model_dump(exclude_none=True)
        if isinstance(_updated_fields.get("ai_model_ref"), dict):
            _updated_fields["ai_model_ref"] = {
                k: v for k, v in _updated_fields["ai_model_ref"].items() if v is not None}
        return {
            "success": True, "message": "配置更新成功,请验证服务可用性",
            "updated_fields": _updated_fields,
            "warnings": warnings,
            "backup_path": str(backup_path) if backup_path else None,
            "current_model_ref": {
                "provider": config_data.get('ai', {}).get('provider', ''),
                "model": config_data.get('ai', {}).get('model', ''),
            },
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


def _mask_api_key(api_key: str) -> str:
    """掩码API Key: 非空时保留前3后2, 中间以*替换, 短于等于6位全掩码 — 小欧 2026-08-13 (#7)"""
    if not api_key:
        return ""
    if len(api_key) <= 6:
        return "*" * len(api_key)
    return api_key[:3] + "*" * (len(api_key) - 5) + api_key[-2:]


def get_system_config_data() -> dict:
    """获取系统配置数据 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: ai_provider/ai_model → ai_model_ref: ModelRef 结构"""
    config = get_config_instance()
    resolved_model = get_ai_config_resolver().resolve_model_ref()
    ai_config = config.get('ai', {})
    provider_config = ai_config.get(resolved_model.provider, {})
    api_key = provider_config.get('api_key', '')
    api_key_configured = bool(api_key and api_key.strip() != '')
    theme = config.get('app.theme', 'light')
    language = config.get('app.language', 'zh-CN')
    security_config = config.get('security', {})
    if not security_config:
        security_config = {
            "contentFilterEnabled": True,
            "contentFilterLevel": "medium",
            "whitelistEnabled": False,
            "commandWhitelist": "",
            "commandBlacklist": "",
            "confirmDangerousOps": True,
            "maxFileSize": 100
        }
    logger.info(f"获取配置成功: provider={resolved_model.provider}, model={resolved_model.model}")
    return {
        "ai_model_ref": resolved_model,
        "api_key_configured": api_key_configured,
        "theme": theme,
        "language": language,
        "security": security_config,
        "max_steps": config.get_max_steps(),
        "project_root": config.get_project_root()
    }


def validate_config(provider: str) -> dict:
    """配置校验 — 自 model_routes.py 迁入; 三堂会审修复: 只收provider(get_service_config的model参数未使用) — 小沈 2026-08-13
    2026-08-22 小欧 归一: resolve_provider_model 拆包 → resolve_model_ref"""
    try:
        resolver = get_ai_config_resolver()
        try:
            resolver.get_service_config(provider, "")
        except ValueError as e:
            return {"valid": False, "message": str(e), "model": None}
        resolved_model = resolver.resolve_model_ref()
        logger.info(f"配置校验通过: provider={resolved_model.provider}, model={resolved_model.model}")
        return {
            "valid": True,
            "message": f"配置校验通过(未保存),将在首次使用时验证 {resolved_model.provider} ({resolved_model.model})",
            "model": resolved_model.model
        }
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return {"valid": False, "message": f"验证过程出错: {str(e)}", "model": None}


def get_model_list() -> dict:
    """获取模型列表 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一: resolve_model_ref 属性访问"""
    try:
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        resolved_model = resolver.resolve_model_ref()
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
                    is_current = (resolved_model.provider == provider_name and resolved_model.model == model_name)
                    models.append({
                        "id": model_id,
                        "provider": provider_name,
                        "model": model_name,
                        "display_name": display_name,
                        "current_model": is_current
                    })
                    model_id += 1
        logger.info(f"获取模型列表成功: {len(models)}个模型")
        return {"models": models, "default_provider": resolved_model.provider}
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return {"models": [], "default_provider": ''}


def get_full_config() -> dict:
    """获取完整配置 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: current_provider/current_model → current_model_ref 结构"""
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    resolved_model = resolver.resolve_model_ref()
    providers = {}
    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if not isinstance(provider_data, dict):
            continue
        api_key = provider_data.get('api_key', '')
        providers[provider_name] = {
            "name": provider_name,
            "api_base": provider_data.get('api_base', ''),
            "api_key": _mask_api_key(api_key),
            "model": '',
            "models": provider_data.get('models', []),
            "timeout": provider_data.get('timeout', 60),
            "max_retries": provider_data.get('max_retries', 3)
        }
    return {
        "providers": providers,
        "current_model_ref": resolved_model
    }


def delete_provider(provider_name: str) -> dict:
    """删除Provider — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
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


def delete_model(provider_name: str, model_name: str) -> dict:
    """删除模型 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
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


def update_model(provider_name: str, old_model_name: str, data) -> dict:
    """更新模型 — 自 model_routes.py 迁入, data为ModelAddRequest DTO(鸭子类型) — 小沈 2026-08-13"""
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


def update_provider(provider_name: str, data) -> dict:
    """更新Provider — 自 model_routes.py 迁入, data为ProviderUpdate DTO(鸭子类型) — 小沈 2026-08-13"""
    config_path, config = load_config()
    backup_path = _backup_config(config_path)
    ensure_provider_exists(config, provider_name)
    if data.api_base is not None:
        config['ai'][provider_name]['api_base'] = data.api_base
    if data.api_key is not None:
        config['ai'][provider_name]['api_key'] = data.api_key.strip()
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


def add_provider(data) -> dict:
    """添加Provider — 自 model_routes.py 迁入, data为ProviderAddRequest DTO(鸭子类型) — 小沈 2026-08-13"""
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


def add_model(provider_name: str, data) -> dict:
    """添加模型 — 自 model_routes.py 迁入, data为ModelAddRequest DTO(鸭子类型) — 小沈 2026-08-13"""
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


def fix_config() -> dict:
    """配置修复 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config_data = read_yaml_config(config_path)
    config_data = _fix_config_common_issues(config_data)
    fixed_issues = [f"删除 provider 下废弃的 model 字段"]
    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        return {
            "success": False,
            "fixed_issues": fixed_issues,
            "warnings": warnings + errors,
            "backup_path": str(backup_path)
        }
    write_yaml_config(str(config_path), config_data)
    config = get_config_instance()
    config.reload()
    logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
    return {
        "success": True,
        "fixed_issues": fixed_issues,
        "warnings": warnings,
        "backup_path": str(backup_path)
    }


def read_config_file() -> dict:
    """读取配置文件 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"config_content": content}


def open_config_folder() -> dict:
    """打开配置目录 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
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