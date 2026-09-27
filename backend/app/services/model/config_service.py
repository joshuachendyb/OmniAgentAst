# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 小欧 - 新建: 配置业务服务，从 model_routes 迁入 CRUD 编排。DTO 边界: 本服务不 import
#   api/v1 的 schema，接收 API 层传入对象(鸭子类型)，YAML 底层 I/O 归 config_helpers。
# 2026-08-14 小欧 - 改名名实相符: model_routes→config_routes，persistence→config_helpers。
# 2026-08-22 小欧 - 模型结构归一: 拆包 resolve_provider_model → resolve_model_ref，响应统一 current_model_ref。
# 2026-09-21 小欧 - 修 None 陷阱: .get('k','') 在键存在值为 None 时返回 None → Pydantic 校验 500。
#   全文件 .get() 统一加 or 兜底。另: 新增 _provider_conf(非 dict provider 归空守卫)、
#   DEFAULT_SECURITY(默认块提模块级)、BOM 剥离、超 512KB 拒读、models dict 老格式归一。
# 2026-09-22 小欧 - update_config 加 filelock(与 merge 写链路同锁)，根治并发丢更新与文件占用 500。
# 2026-09-24 小欧 - 删 6 个死函数(delete_provider 等，前端零调用)。
# 2026-09-26 小欧 - 删死契约 _mask_api_key，/config/full 的 api_key 改用唯一权威 mask_secret_value
#   (形状为对象)；update_config 收敛为只切模型，FIELD_HANDLERS/备份恢复逻辑仍被它使用。
# 2026-09-27 小欧 - 修 B1/B2/B4: models 多形态归一抽成 _model_names() 供两处共用；
#   theme/language/security 出口加兜底；provider 值为 None 的守卫补齐。
# 2026-09-27 小欧 - security 出口改按白名单挑选(见 get_system_config_data 内注释)；max_steps 归一
#   下沉到 config.get_max_steps。
# 2026-09-27 小欧 - 修本轮引入的退化：timeout/max_retries 曾被改成 `or 60/3`，把 0 吞成默认值
#   （`max_retries: 0` = 不重试，是合法配置；2026-09-21 已明文修过一次此坑，勿再改回 `or`）。
#   改用 app.utils.type_utils.to_int_or：仅 None 回落，0 保留、脏值也回落。同轮精简冗长注释。
#
# ⚠️ 两个"别再删"的坑:
#   1. `api_success` import 必须保留 —— open_config_folder 在用。曾因"全仓零引用"删掉导致该端点
#      NameError→500(已实跑复现)。核实引用前先看本文件。
#   2. `FIELD_HANDLERS` 收敛后已无消费方，但章节设计要求保留该结构，故未删。
#      是否进一步删除待北京老陈裁定，勿自行处置。
"""
config_service — 配置业务服务(services/model)

职责: 配置CRUD业务编排。YAML底层I/O归属config_helpers.py, 本服务只做编排。
A7(小欧 2026-08-13): update_config 业务编排。
修复(小沈 2026-08-13): 全量CRUD下沉, model_routes 降为纯薄壳。
"""
import os
import subprocess
import copy
from pathlib import Path

from fastapi import HTTPException

from app.logger import logger
from app.utils.response_utils import api_success   # open_config_folder 在用，别删（见文件头"别再删的坑"）
from app.utils.type_utils import to_int_or
from app.config import get_config as get_config_instance
from app.services.model.resolver import get_ai_config_resolver
from app.services.model.config_helpers import (
    _update_model_ref,  # 唯一保留的 handler（直调，不经 FIELD_HANDLERS 中转）
    _auto_fix_and_validate,
    _backup_config,
    _fix_config_common_issues,
    _restore_backup_if_needed,  # 收敛后 update_config 的 except 分支仍需回滚备份
    _validate_config_integrity,
    get_config_path,
    is_provider_metadata_field,
    mask_secret_value,
    read_yaml_config,
    reload_ai_config,
    write_yaml_config,
)


def update_config(config_update):
    """配置更新业务编排 — **只切模型**。
    原实现（已删）经 FIELD_HANDLERS 派发 7 个 handler：ai_model_ref / provider_api_keys / theme /
    language / max_steps / security / project_root。本次整改后本函数**只保留 ai_model_ref 一条能力**：
      - provider_api_keys：能空串擦除密钥（认定第二个入口），字段已从 ConfigUpdate 删除，漏洞消失
      - theme/language/max_steps/security/project_root：功能已迁移至 PUT /settings 对应 registry 项，
        旧字段与旧 handler 一并删除，不留第二条写路径（避免同一配置两个写入口产生分叉）
    保留原因：configApi.switchCurrentModel（AppContext.tsx:266，顶栏与设置页「切换全局模型」唯一写链）
    仍调 PUT /config；删端点会导致该功能 404 失效（功能退化，违反"只能增强不能退化"红线）。
    事务语义不变：整段读-改-写包 filelock(config.yaml.lock)，异常路径回滚备份。
    """
    import filelock  # 局部 import：filelock 为可选依赖，抑制启动失败面（与 merge_region_patch 同策略）
    config_path = get_config_path()
    with filelock.SoftFileLock(str(config_path) + ".lock", timeout=10):
        config_data = read_yaml_config(Path(config_path)) or {}
        original_config_data = copy.deepcopy(config_data)
        restored = [False]
        backup_path = _backup_config(config_path)
        try:
            # 直调 _update_model_ref，不经 FIELD_HANDLERS 中转（表只剩这一项，查表+间接调用已成死抽象）
            _update_model_ref(config_data, config_update)
            is_valid, errors, warnings, fail_result = _auto_fix_and_validate(
                config_data, config_path, backup_path, original_config_data)
            if not is_valid:
                return fail_result

            write_yaml_config(str(config_path), config_data)
            reload_ai_config()

            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                    logger.info(f"[update_config] 验证成功, 已删除备份文件: {backup_path}")
                except Exception as e:
                    # 不静默 pass：残留副本内含明文 api_key，堆积要留痕
                    logger.warning(f"[update_config] 删除备份文件失败（可能残留含明文密钥的副本）: {e}")
            return {
                "success": True,                 "message": "配置更新成功，已校验并生效",
                # 只输出本次真正写入的非空项，避免 jsonable_encoder 把 null/模型对象混进 JSON
                "updated_fields": {
                    "ai_model_ref": {
                        k: v
                        for k, v in (
                            getattr(config_update, "ai_model_ref", None) or {}
                        ).model_dump(exclude_none=True).items()
                        if v is not None
                    }
                },
                "warnings": warnings,
                "backup_path": str(backup_path) if backup_path else None,
                "current_model_ref": {
                    "provider": (config_data.get('ai', {}).get('model_ref') or {}).get('provider') or '',
                    "model": (config_data.get('ai', {}).get('model_ref') or {}).get('model') or '',
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
            logger.error(f"配置更新失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="配置更新失败，请稍后重试")


DEFAULT_SECURITY = {
    "enabled": False,
    "confirmDangerousOps": True,
    "auto_confirm_delay": 10,
    "hitl_timeout": 120,
}


def _provider_conf(ai_config: dict, provider: str) -> dict:
    """取 provider 配置；非 dict 一律归空 — 2026-09-21 小欧 统一守卫
    （畸形 YAML 写 provider 为 str/list 时避免 .get 崩溃；get_system_config_data/get_model_list/get_full_config 复用）"""
    p = ai_config.get(provider)
    return p if isinstance(p, dict) else {}


def _model_names(provider_data: dict) -> list:
    """取 provider 的模型名列表，把 yaml 的多种写法归一成 list[str]。

    2026-09-27 小欧 - 抽成函数（修 B1）：原先只有 get_model_list 内联做归一，get_full_config 没做，
    把 dict 原样塞进 ProviderInfo.models（声明 list[str]）→ ValidationError → /config/full 500。
    同日补 list[dict] 形态：只做 dict→keys 时 `models: [{name: gpt-4}]` 仍会 500（与修前同一症状）。
    口径与 `model_service._models_of` 的"非 str 取 name"保持一致，不另立一套。
    """
    models = provider_data.get('models') or []
    if isinstance(models, dict):
        models = list(models.keys())        # 老式映射写法 {name: {...}}
    return [
        (m if isinstance(m, str) else str((m.get("name") or "")))
        if isinstance(m, (str, dict)) else str(m)
        for m in models
    ]


def get_system_config_data() -> dict:
    """获取系统配置数据 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: ai_provider/ai_model → ai_model_ref: ModelRef 结构"""
    config = get_config_instance()
    resolved_model = get_ai_config_resolver().resolve_model_ref()
    ai_config = config.get('ai', {})
    provider_config = _provider_conf(ai_config, resolved_model.provider)
    api_key = str(provider_config.get('api_key') or '')
    api_key_configured = bool(api_key.strip() != '')
    # or 兜底：config.get 只在键不存在时给 default，键存在但为空（yaml `app.theme:`）会返回 None，
    # 而 ConfigResponse 三项是必填 str/int → 500。出口归一，不放宽 DTO。
    theme = config.get('app.theme') or 'light'
    language = config.get('app.language') or 'zh-CN'
    security_config = config.get('security', {})
    if not isinstance(security_config, dict) or not security_config:
        security_config = dict(DEFAULT_SECURITY)
    # security 段按白名单挑选（不整体透传）：env 注入的明文 api_token 在此挡掉。
    # 靠 SecurityConfig 少声明字段被动丢弃是巧合不是契约。
    logger.info(f"获取配置成功: provider={resolved_model.provider}, model={resolved_model.model}")
    return {
        "ai_model_ref": resolved_model,
        "api_key_configured": api_key_configured,
        "theme": theme,
        "language": language,
        "security": {
            "confirmDangerousOps": bool(security_config.get("confirmDangerousOps", True)),
        },
        # 归一已下沉到 config.get_max_steps（源头一处处理），此处不再重复兜底
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
            provider_data = _provider_conf(ai_config, provider_name)
            if not provider_data:
                continue
            provider_models = _model_names(provider_data)
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
        provider_data = _provider_conf(ai_config, provider_name)
        if not provider_data:
            continue
        api_key = str(provider_data.get('api_key') or '')
        providers[provider_name] = {
            "name": provider_name,
            "api_base": provider_data.get('api_base') or '',
            # api_key 用唯一权威 mask_secret_value，形状为 {configured, masked}（非字符串）
            "api_key": mask_secret_value(api_key),
            "model": '',
            "models": _model_names(provider_data),
            # 归一走 to_int_or：0 是合法值（max_retries: 0 = 不重试）不能被 `or` 吞掉，
            # 带引号的 "60" 能正常转换，脏值 "abc" 回落默认而不是穿透成 500。
            "timeout": to_int_or(provider_data.get('timeout'), 60),
            "max_retries": to_int_or(provider_data.get('max_retries'), 3),
        }
    return {
        "providers": providers,
        "current_model_ref": resolved_model
    }


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


_MAX_READ_FILE_BYTES = 512 * 1024


def read_config_file() -> dict:
    """读取配置文件 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-09-21 小欧 扩展：返回体扩 path/size/lines/mtime
    2026-09-21 小欧 修复：BOM 剥离 + 大小上限"""
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    size = config_path.stat().st_size
    if size > _MAX_READ_FILE_BYTES:
        raise HTTPException(status_code=400, detail=f"配置文件过大({size} 字节)，拒绝读取")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read().lstrip("\ufeff")
    stat = config_path.stat()
    return {
        "config_content": content,
        "path": str(config_path),
        "size": stat.st_size,
        "lines": content.count('\n') + 1,
        "mtime": int(stat.st_mtime),
    }


def read_version_file() -> dict:
    """读取 version.txt 全文 — 2026-09-21 小欧 关于页"查看版本文件全文"。
    路径与 main.get_version / settings_service.app_version 一致（get_code_root()/version.txt，DRY）。
    2026-09-21 小欧 扩展：返回体扩 path/size/lines/mtime
    2026-09-21 小欧 修复：BOM 剥离 + 大小上限"""
    from app.config import get_code_root  # 局部 import：避免顶层循环依赖
    version_path = Path(get_code_root()) / "version.txt"
    if not version_path.exists():
        raise HTTPException(status_code=404, detail=f"version 文件不存在: {version_path}")
    size = version_path.stat().st_size
    if size > _MAX_READ_FILE_BYTES:
        raise HTTPException(status_code=400, detail=f"version 文件过大({size} 字节)，拒绝读取")
    with open(version_path, "r", encoding="utf-8") as f:
        content = f.read().lstrip("\ufeff")
    stat = version_path.stat()
    return {
        "version_content": content,
        "path": str(version_path),
        "size": stat.st_size,
        "lines": content.count('\n') + 1,
        "mtime": int(stat.st_mtime),
    }


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