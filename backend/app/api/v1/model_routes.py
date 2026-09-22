# -*- coding: utf-8 -*-
"""模型管理路由薄壳。

编辑历史:
  2026-09-20 - 小沈 - 新建：/models /providers CRUD（5.2 模型管理接口）
  2026-09-21 - 小欧 - 对齐文档54 9.1.6：import 补 ModelAddRequest/ProviderInfo/ProviderUpdate（DTO 复用 config_schemas）
   2026-09-21 - 小欧 - 三堂会审第三轮 22 真实 bug 修复：①M13 add_provider 透传 req.models 列表与
     req.max_retries（旧实现丢弃，DTO 有字段借而不传，前端无法创建多模型 Provider/设置重试）；
     ②S7 ProviderConfigUpdate 补 label 字段并交由 update_provider_config 落盘（旧实现 provider
     label 创建后永不可改）
   2026-09-21 - 小欧 - 建议报告 P18: PUT/DELETE /models/{provider}/{model} 路由 model 参数改 :path 转换器——
     FastAPI 单段 path 参数对模型名含 '/'（真实 z-ai/glm-4.7, moonshotai/kimi-k2）先解码再分断必然 404，
     改贪婪吞余段后含斜杠模型名可更新/删除
   2026-09-22 - 小欧 - [62]P1/P2 param_options 读写链落地：P1 ModelCreateRequest/ModelUpdateRequest 各加
     param_options: Optional[Dict[str,List[str]]]=None（Pydantic 不声明即丢字段，老前端不送也不报错）；
     P2 POST /models 路由 add_model 调用透传 req.param_options（5 位置参→7 位置参，防 param_options 形参
     永远拿 None 静默丢）。PUT 路由无需改——model_dump(exclude_none=True) 自动含 param_options。
   2026-09-22 - 小欧 - [62]P6 4.3(3) ProviderConfigUpdate 补 max_retries: Optional[int]=None：
     前端 ProviderConfig.tsx 实际发送 max_retries 而 DTO 原只有 retry_times 别名，Pydantic v2
     extra='ignore' 丢弃未声明字段 → model_dump 不产 max_retries → 落不了盘；补声明后
     前端发的 max_retries 直连 key_map，不再依赖隐式绕过（BY-06 红条件验证）。
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.v1.config_schemas import (
    ModelAddRequest,
    ProviderAddRequest,
    ProviderInfo,
    ProviderUpdate,
)
from app.services.model.config_helpers import handle_config_errors
from app.services.model import model_service as svc


router = APIRouter()


class ModelCreateRequest(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    label: str = Field("")
    default_params: Dict[str, Any] = Field(default_factory=dict)
    range: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)
    param_options: Optional[Dict[str, List[str]]] = Field(default=None)


class ModelUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None)
    default_params: Optional[Dict[str, Any]] = Field(default=None)
    range: Optional[Dict[str, Any]] = Field(default=None)
    capabilities: Optional[List[str]] = Field(default=None)
    param_options: Optional[Dict[str, List[str]]] = Field(default=None)


class ProviderConfigUpdate(BaseModel):
    """Provider 配置更新 DTO — 2026-09-22 小欧 [62]P6 补 max_retries：
    前端 ProviderConfig.tsx 发送 max_retries，DTO 原只有 retry_times 别名——Pydantic v2
    默认 extra='ignore' 会丢弃未声明字段，补声明后 model_dump(exclude_none=True) 才落盘。"""
    label: Optional[str] = Field(default=None, description="Provider 显示名")
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    timeout: Optional[int] = Field(default=None)
    retry_times: Optional[int] = Field(default=None)
    max_retries: Optional[int] = Field(default=None)
    clear: Optional[bool] = Field(default=None, description="clear=true 显式清空 api_key")


@router.get("/models")
@handle_config_errors("获取模型列表")
async def get_models():
    return svc.get_models()


@router.post("/models")
@handle_config_errors("添加模型")
async def add_model(req: ModelCreateRequest):
    return svc.add_model(req.provider, req.model, req.label,
                         req.default_params, req.range, req.capabilities,
                         req.param_options)


@router.put("/models/{provider}/{model:path}")
@handle_config_errors("修改模型")
async def update_model(provider: str, model: str, req: ModelUpdateRequest):
    # 2026-09-21 小欧 修 P18：模型名可含 '/'（真实 z-ai/glm-4.7、moonshotai/kimi-k2），
    # FastAPI 单段 path 参数遇 '/' 先解码再分断必然 404，改 path 转换器贪婪吞余段。
    return svc.update_model(provider, model, req.model_dump(exclude_none=True))


@router.delete("/models/{provider}/{model:path}")
@handle_config_errors("删除模型")
async def delete_model(provider: str, model: str):
    # 2026-09-21 小欧 修 P18：同 update_model，path 转换器支持含 '/' 模型名删除。
    return svc.delete_model(provider, model)


@router.get("/providers")
@handle_config_errors("获取 Provider 列表")
async def get_providers():
    return svc.get_providers()


@router.post("/providers")
@handle_config_errors("添加 Provider")
async def add_provider(req: ProviderAddRequest):
    return svc.add_provider(req.name, req.label or req.name, req.api_base,
                            req.api_key, req.model, req.timeout,
                            models=req.models, max_retries=req.max_retries)


@router.put("/providers/{name}")
@handle_config_errors("修改 Provider 配置")
async def update_provider(name: str, req: ProviderConfigUpdate):
    return svc.update_provider_config(name, req.model_dump(exclude_none=True))


@router.delete("/providers/{name}")
@handle_config_errors("删除 Provider")
async def delete_provider(name: str):
    return svc.delete_provider(name)
