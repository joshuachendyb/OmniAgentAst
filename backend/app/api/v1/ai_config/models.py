"""Pydantic模型定义"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.constants import DEFAULT_MAX_STEPS


class SecurityConfig(BaseModel):
    """安全配置"""
    contentFilterEnabled: bool = Field(True, description="是否启用内容安全过滤")
    contentFilterLevel: str = Field("medium", description="敏感词过滤级别: low | medium | high")
    whitelistEnabled: bool = Field(False, description="是否启用命令白名单")
    commandWhitelist: str = Field("", description="命令白名单，每行一个命令")
    commandBlacklist: str = Field("", description="命令黑名单，每行一个命令")
    confirmDangerousOps: bool = Field(True, description="危险操作是否需要二次确认")
    maxFileSize: int = Field(100, description="最大文件操作大小(MB)")


class ConfigUpdate(BaseModel):
    """配置更新请求"""
    ai_provider: Optional[str] = Field(None, description="AI提供商")
    ai_model: Optional[str] = Field(None, description="AI模型名称")
    provider_api_keys: Optional[Dict[str, str]] = Field(None, description="Provider API Key字典: {provider_name: api_key}")
    theme: Optional[str] = Field("light", description="主题: light | dark")
    language: Optional[str] = Field("zh-CN", description="语言: zh-CN | en-US")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")
    max_steps: Optional[int] = Field(None, description="Agent最大迭代次数")


class ConfigResponse(BaseModel):
    """配置响应"""
    ai_provider: str = Field(..., description="当前AI提供商")
    ai_model: str = Field(..., description="当前AI模型")
    api_key_configured: bool = Field(..., description="API Key是否已配置")
    theme: str = Field(..., description="当前主题")
    language: str = Field(..., description="当前语言")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")
    max_steps: int = Field(DEFAULT_MAX_STEPS, description="Agent最大迭代次数")


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
    display_name: str = Field(..., description="显示名称，格式: Provider (model)")
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
    """完整配置响应"""
    providers: dict[str, ProviderInfo] = Field(..., description="所有Provider配置")
    current_provider: str = Field(..., description="当前使用的Provider")
    current_model: str = Field(..., description="当前使用的模型")


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


class FullConfigValidationResponse(BaseModel):
    """完整配置验证响应"""
    success: bool = Field(..., description="验证是否成功")
    provider: str = Field(..., description="当前Provider")
    model: str = Field(..., description="当前Model")
    message: str = Field(..., description="验证消息")
    errors: list[str] = Field(default_factory=list, description="错误列表")
    warnings: list[str] = Field(default_factory=list, description="警告列表")


class ConfigPathResponse(BaseModel):
    """配置文件路径响应"""
    config_path: str = Field(..., description="配置文件完整路径")
    config_dir: str = Field(..., description="配置文件所在目录")
    exists: bool = Field(..., description="配置文件是否存在")
