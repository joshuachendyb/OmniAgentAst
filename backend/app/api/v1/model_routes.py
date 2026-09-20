# -*- coding: utf-8 -*-
"""模型管理路由薄壳。

编辑历史:
  2026-09-20 - 小沈 - 新建：/models /providers CRUD（5.2 模型管理接口）
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.model.config_helpers import handle_config_errors
from app.services.model import model_service as svc
from app.api.v1.config_schemas import ProviderAddRequest


router = APIRouter()


class ModelCreateRequest(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    label: str = Field("")
    default_params: Dict[str, Any] = Field(default_factory=dict)
    range: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)


class ModelUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None)
    default_params: Optional[Dict[str, Any]] = Field(default=None)
    range: Optional[Dict[str, Any]] = Field(default=None)
    capabilities: Optional[List[str]] = Field(default=None)


class ProviderConfigUpdate(BaseModel):
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    timeout: Optional[int] = Field(default=None)
    retry_times: Optional[int] = Field(default=None)
    clear: Optional[bool] = Field(default=None, description="clear=true 显式清空 api_key")


@router.get("/models")
@handle_config_errors("获取模型列表")
async def get_models():
    return svc.get_models()


@router.post("/models")
@handle_config_errors("添加模型")
async def add_model(req: ModelCreateRequest):
    return svc.add_model(req.provider, req.model, req.label,
                         req.default_params, req.range, req.capabilities)


@router.put("/models/{provider}/{model}")
@handle_config_errors("修改模型")
async def update_model(provider: str, model: str, req: ModelUpdateRequest):
    return svc.update_model(provider, model, req.model_dump(exclude_none=True))


@router.delete("/models/{provider}/{model}")
@handle_config_errors("删除模型")
async def delete_model(provider: str, model: str):
    return svc.delete_model(provider, model)


@router.get("/providers")
@handle_config_errors("获取 Provider 列表")
async def get_providers():
    return svc.get_providers()


@router.post("/providers")
@handle_config_errors("添加 Provider")
async def add_provider(req: ProviderAddRequest):
    return svc.add_provider(req.name, req.label or req.name, req.api_base,
                            req.api_key, req.model, req.timeout)


@router.put("/providers/{name}")
@handle_config_errors("修改 Provider 配置")
async def update_provider(name: str, req: ProviderConfigUpdate):
    return svc.update_provider_config(name, req.model_dump(exclude_none=True))


@router.delete("/providers/{name}")
@handle_config_errors("删除 Provider")
async def delete_provider(name: str):
    return svc.delete_provider(name)
