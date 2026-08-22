
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 从 ai_config/ 复制, 仅改 import 路径
# 2026-08-12 - 小欧 - A1越层前置: safety 提升为顶层 app.safety, clear_backup_paths 的 import 由 app.services.safety.operation_backup 改 app.safety.operation_backup(配合 api 禁 tools 守护规则)
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤3): update_config 业务编排迁入 services/model/config_service.py; 删除
#   from app.safety.operation_backup import clear_backup_paths 越层 import(随 update_config 迁出, API→safety 越层消除,
#   守护测试 api 规则可启用)。本文件保留其余 config 路由与 DTO。
# 2026-08-13 - 小欧 - 三堂会审修复#6/#7/#8: #6 validate_config 谎报"配置已保存"改"配置校验通过(未保存)"
#   (该端点仅校验不落盘, 原文案误导); #7 GET /config/full 返回明文 api_key 改 _mask_api_key 掩码
#   (保留前3后2, 安全不泄露密钥); #8 update_provider 删除对全局 config['ai']['model'] 的改写
#   (更新provider信息时不再悄悄切换当前全局模型, 防模型被意外替换)
# 2026-08-13 - 小沈 - P3 CRUD全量下沉: 12个CRUD业务逻辑迁入 services/model/config_service.py,
#   本文件降为纯薄壳(路由+DTO+调service+返回), 与 sessions.py/messages.py 薄壳模式一致。
#   DTO边界: API层负责DTO解包/构造响应, config_service 不 import api/v1/model_schemas。
# 2026-08-13 - 小沈 - 三堂会审修复: ① validate_config 改传 request.provider(ConfigValidateRequest 无 model 字段,
#   原传 request.model 在 service try 之外抛 AttributeError→500, 行为退化); ② ModelInfo/get_config_path 两处
#   函数内局部 import 移顶部, 与其它 DTO/依赖并列(风格一致性)。
# 2026-08-14 - 小欧 - 改名名实相符: model_routes.py → config_routes.py(实为配置API路由薄壳, /config/* /provider/*)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.6 方案B: GET /config 落 DTO 改 ai_model_ref=data["ai_model_ref"]、
#   GET /config/full 改 current_model_ref=result["current_model_ref"](后端 DTO 字段变更, 前端 api.ts 契约已同步改)
"""
config_routes — 配置API路由薄壳 (P3 后路由+DTO 调 config_service)

小欧 2026-07-10
"""
from fastapi import APIRouter

from app.api.v1.config_schemas import (
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
from app.services.model.config_service import (
    add_model as svc_add_model,
    add_provider as svc_add_provider,
    delete_model as svc_delete_model,
    delete_provider as svc_delete_provider,
    fix_config as svc_fix_config,
    get_full_config as svc_get_full_config,
    get_model_list as svc_get_model_list,
    get_system_config_data,
    open_config_folder as svc_open_config_folder,
    read_config_file as svc_read_config_file,
    update_config as update_config_service,
    update_model as svc_update_model,
    update_provider as svc_update_provider,
    validate_config as svc_validate_config,
)
from app.services.model.config_helpers import get_config_path, handle_config_errors


router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
@handle_config_errors("获取配置")
async def get_system_config():
    data = get_system_config_data()
    security_config = data["security"]
    if isinstance(security_config, dict):
        security_config = SecurityConfig(**security_config)
    # 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): ai_provider/ai_model → ai_model_ref: ModelRef
    return ConfigResponse(
        ai_model_ref=data["ai_model_ref"],
        api_key_configured=data["api_key_configured"],
        theme=data["theme"],
        language=data["language"],
        security=security_config,
        max_steps=data["max_steps"],
        project_root=data["project_root"]
    )


@router.put("/config")
def update_config(config_update: ConfigUpdate):
    return update_config_service(config_update)


@router.put("/config/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest):
    result = svc_validate_config(request.provider)
    return ConfigValidateResponse(
        valid=result["valid"],
        message=result["message"],
        model=result["model"]
    )


@router.get("/config/models", response_model=ModelListResponse)
async def get_model_list():
    result = svc_get_model_list()
    models = [ModelInfo(**m) for m in result["models"]]
    return ModelListResponse(
        models=models,
        default_provider=result["default_provider"]
    )


@router.get("/config/full", response_model=FullConfigResponse)
@handle_config_errors("获取完整配置")
async def get_full_config():
    result = svc_get_full_config()
    providers = {}
    for name, p in result["providers"].items():
        providers[name] = ProviderInfo(**p)
    # 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): current_provider/current_model → current_model_ref
    return FullConfigResponse(
        providers=providers,
        current_model_ref=result["current_model_ref"]
    )


@router.delete("/config/provider/{provider_name}")
@handle_config_errors("删除Provider")
async def delete_provider(provider_name: str):
    return svc_delete_provider(provider_name)


@router.delete("/config/provider/{provider_name}/model/{model_name}")
@handle_config_errors("删除模型")
async def delete_model(provider_name: str, model_name: str):
    return svc_delete_model(provider_name, model_name)


@router.put("/config/provider/{provider_name}/model/{old_model_name}")
@handle_config_errors("更新模型")
async def update_model(provider_name: str, old_model_name: str, data: ModelAddRequest):
    return svc_update_model(provider_name, old_model_name, data)


@router.put("/config/provider/{provider_name}")
@handle_config_errors("更新Provider")
async def update_provider(provider_name: str, data: ProviderUpdate):
    return svc_update_provider(provider_name, data)


@router.post("/config/provider")
@handle_config_errors("添加Provider")
async def add_provider(data: ProviderAddRequest):
    return svc_add_provider(data)


@router.post("/config/provider/{provider_name}/model")
@handle_config_errors("添加模型")
async def add_model(provider_name: str, data: ModelAddRequest):
    return svc_add_model(provider_name, data)


@router.post("/config/fix", response_model=ConfigFixResponse)
@handle_config_errors("配置修复")
async def fix_config():
    result = svc_fix_config()
    return ConfigFixResponse(**result)


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
    return svc_read_config_file()


@router.post("/config/open-folder")
@handle_config_errors("打开配置目录")
async def open_config_folder():
    return svc_open_config_folder()
