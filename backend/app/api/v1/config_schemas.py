# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-14 - 小欧 - 改名名实相符: model_schemas.py → config_schemas.py(实为配置DTO定义: ConfigUpdate/SecurityConfig/ProviderInfo等)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6 方案B(前端随后端修改): ConfigUpdate.ai_provider/ai_model、
#   ConfigResponse.ai_provider/ai_model、FullConfigResponse.current_provider/current_model 分离字段归一为
#   ai_model_ref/current_model_ref: ModelRef 封装字段(前端 api.ts 契约同步改); FullConfigValidationResponse
#   死DTO(全仓无引用)按 YAGNI 删除
"""配置DTO定义（Pydantic模型）"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.constants import DEFAULT_MAX_STEPS
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22


class SecurityConfig(BaseModel):
    """安全配置"""
    contentFilterEnabled: bool = Field(True, description="是否启用内容安全过滤")
    contentFilterLevel: str = Field("medium", description="敏感词过滤级别: low | medium | high")
    whitelistEnabled: bool = Field(False, description="是否启用命令白名单")
    commandWhitelist: str = Field("", description="命令白名单,每行一个命令")
    commandBlacklist: str = Field("", description="命令黑名单,每行一个命令")
    confirmDangerousOps: bool = Field(True, description="危险操作需要二次确认")
    maxFileSize: int = Field(100, description="最大文件操作大小(MB)")


class ConfigUpdate(BaseModel):
    """配置更新请求 — 归一: provider+model 成对语义由 ModelRef 单字段承载(原子切换)"""
    ai_model_ref: Optional[ModelRef] = Field(None, description="AI模型(provider+model 结构)")
    provider_api_keys: Optional[Dict[str, str]] = Field(None, description="Provider API Key字典: {provider_name: api_key}")
    theme: Optional[str] = Field("light", description="主题: light | dark")
    language: Optional[str] = Field("zh-CN", description="语言: zh-CN | en-US")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")
    max_steps: Optional[int] = Field(None, description="Agent最大迭代次数")
    project_root: Optional[str] = Field(None, description="项目根目录路径,空值则自动检测")


class ConfigResponse(BaseModel):
    """配置响应 — 归一: ai_provider/ai_model → ai_model_ref: ModelRef"""
    ai_model_ref: ModelRef = Field(..., description="当前AI模型(provider+model 结构)")
    api_key_configured: bool = Field(..., description="API Key是否已配置")
    theme: str = Field(..., description="当前主题")
    language: str = Field(..., description="当前语言")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")
    max_steps: int = Field(DEFAULT_MAX_STEPS, description="Agent最大迭代次数")
    project_root: str = Field("", description="项目根目录路径")


class ConfigValidateRequest(BaseModel):
    """配置验证请求"""
    provider: str = Field(..., description="AI提供商")
    api_key: str = Field(..., description="API密钥")


class ConfigValidateResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="配置是否有效")
    message: str = Field(..., description="验证消息")
    model: Optional[str] = Field(None, description="模型名称")


class ModelInfo(BaseModel):
    """模型信息"""
    id: int = Field(..., description="模型ID序号")
    provider: str = Field(..., description="提供商名称(小写)")
    model: str = Field(..., description="模型名称")
    display_name: str = Field(..., description="显示名称,格式: Provider (model)")
    current_model: bool = Field(default=False, description="是否为当前模型")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: list[ModelInfo] = Field(..., description="可用模型列表")
    default_provider: str = Field(..., description="默认提供商")


class ProviderInfo(BaseModel):
    """Provider信息"""
    name: str = Field(..., description="Provider名称")
    api_base: str = Field(..., description="API地址")
    api_key: str = Field("", description="API密钥")
    model: str = Field("", description="当前使用的模型")
    models: list[str] = Field(default_factory=list, description="模型列表")
    timeout: int = Field(60, description="超时时间")
    max_retries: int = Field(3, description="最大重试次数")


class FullConfigResponse(BaseModel):
    """完整配置响应 — 归一: current_provider/current_model → current_model_ref: ModelRef"""
    providers: dict[str, ProviderInfo] = Field(..., description="所有Provider配置")
    current_model_ref: ModelRef = Field(..., description="当前使用的模型(provider+model 结构)")


class ProviderUpdate(BaseModel):
    """Provider更新请求"""
    api_base: Optional[str] = Field(None, description="API地址")
    api_key: Optional[str] = Field(None, description="API密钥")
    model: Optional[str] = Field(None, description="当前使用的模型")
    timeout: Optional[int] = Field(None, description="超时时间")
    max_retries: Optional[int] = Field(None, description="最大重试次数")


class ModelAddRequest(BaseModel):
    """添加模型请求"""
    model: str = Field(..., description="模型名称")


class ProviderAddRequest(BaseModel):
    """添加Provider请求"""
    name: str = Field(..., description="Provider名称")
    api_base: str = Field(..., description="API地址")
    api_key: str = Field("", description="API密钥")
    model: str = Field("", description="默认模型")
    models: list[str] = Field(default_factory=list, description="模型列表")
    timeout: int = Field(60, description="超时时间")
    max_retries: int = Field(3, description="最大重试次数")


class ConfigFixResponse(BaseModel):
    """配置修复响应"""
    success: bool = Field(..., description="修复是否成功")
    fixed_issues: List[str] = Field(default_factory=list, description="修复的问题列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    backup_path: str = Field("", description="备份文件路径")


class ConfigPathResponse(BaseModel):
    """配置文件路径响应"""
    config_path: str = Field(..., description="配置文件完整路径")
    config_dir: str = Field(..., description="配置文件所在目录")
    exists: bool = Field(..., description="配置文件是否存在")
