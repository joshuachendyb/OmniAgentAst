# 配置管理API路由
# 编程人：小沈
# 创建时间：2026-02-17
# 更新时间：2026-02-26 02:09:53

"""
配置管理API路由
提供系统配置的获取、更新、验证功能
支持从YAML文件持久化配置

================================================================================
【重要！统一Fallback逻辑 - 所有代码编写人员必须遵守！】

逻辑规则：
1. 只有当 ai.provider 存在 且 ai.model 存在 且 ai.model 在 ai.provider 的 models 列表中
   时，才使用 ai.provider + ai.model
2. 否则（任何一个条件不满足：ai.provider不存在/ai.model不存在/ai.model不在列表中）
   统一fallback到：模型列表的第一个 模型provider+model
3. 禁止有"当前provider"的概念和理解，容易引起逻辑错误
4. 所有相关代码必须按照此逻辑实现，不能再次犯错误！

正确示例：
ai_config = config.get('ai', {})
fallback_provider = ''
fallback_model = ''
for provider_name in ai_config.keys():
    if provider_name == 'provider' or provider_name == 'model':
        continue
    provider_data = ai_config.get(provider_name, {})
    if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
        fallback_provider = provider_name
        fallback_model = provider_data['models'][0]
        break

selected_provider = ai_config.get('provider', '')
selected_model = ai_config.get('model', '')

if (selected_provider and selected_provider in ai_config and 
    'models' in ai_config[selected_provider] and 
    selected_model and selected_model in ai_config[selected_provider]['models']):
    final_provider = selected_provider
    final_model = selected_model
else:
    final_provider = fallback_provider
    final_model = fallback_model
================================================================================

================================================================================
【绝对禁止！硬编码Provider名称 - 所有代码编写人员必须遵守！】

禁止事项：
1. 绝对禁止在代码中硬编码具体的provider名称（如"zhipuai"、"opencode"、"longcat"等）
2. 所有provider必须从配置文件中动态遍历，不能写死
3. 配置文件里有什么provider，代码就处理什么provider
4. 这是通用程序，不是只给这几个provider用的！

正确做法：
ai_config = config.get('ai', {})
for provider_name in ai_config.keys():
    if provider_name == 'provider' or provider_name == 'model':
        continue
    provider_data = ai_config.get(provider_name, {})
    # 处理这个provider
================================================================================

================================================================================
【变量命名规范 - 所有代码编写人员必须遵守！】

禁止事项：
1. 禁止使用单独的"provider"变量名来表示模型信息
2. 模型信息 = provider + model，两者缺一不可
3. 单独的"provider"容易引起误解，让人以为只是处理provider
4. 涉及模型的变量名必须明确表示是模型信息

正确命名：
- final_provider, final_model  - 分别表示provider和model
- fallback_provider, fallback_model  - 分别表示fallback的provider和model
- current_provider, current_model  - 分别表示当前的provider和model

错误命名（禁止）：
- current_provider  - 单独用，容易误解为只是provider
- fallback_provider  - 单独用，容易误解
================================================================================
"""

import os
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger

router = APIRouter()


# ============================================
# 安全配置模型
# ============================================
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


class ConfigResponse(BaseModel):
    """配置响应"""
    ai_provider: str = Field(..., description="当前AI提供商")
    ai_model: str = Field(..., description="当前AI模型")
    api_key_configured: bool = Field(..., description="API Key是否已配置")
    theme: str = Field(..., description="当前主题")
    language: str = Field(..., description="当前语言")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")


class ConfigValidateRequest(BaseModel):
    """配置验证请求"""
    provider: str = Field(..., description="AI提供商")
    api_key: str = Field(..., description="API密钥")


class ConfigValidateResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="配置是否有效")
    message: str = Field(..., description="验证消息")
    model: Optional[str] = Field(None, description="模型名称")


def _get_config_path() -> Path:
    """获取配置文件路径"""
    base_dir = Path(__file__).parent.parent.parent.parent.parent
    return base_dir / "config" / "config.yaml"


@router.get("/config", response_model=ConfigResponse)
async def get_system_config():
    """
    获取当前系统配置
    
    返回脱敏后的配置信息（不返回真实API Key）
    
    Returns:
        ConfigResponse: 当前配置
    """
    try:
        config = get_config_instance()
        ai_config = config.get('ai', {})
        
        # ====================================================================
        # 【统一Fallback逻辑 - 必须遵守！】
        # 1. 找第一个有models的provider作为fallback（动态遍历，不是硬编码！）
        fallback_provider = ''
        fallback_model = ''
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
                fallback_provider = provider_name
                fallback_model = provider_data['models'][0]
                break
        
        # 如果没有找到任何provider，用空值
        # 注意：配置文件应该至少有一个provider配置
        if not fallback_provider:
            fallback_provider = ''
            fallback_model = ''
        
        # 2. 检查 ai.provider 和 ai.model 是否有效
        selected_provider = ai_config.get('provider', '')
        selected_model = ai_config.get('model', '')
        
        is_valid = (
            selected_provider and 
            selected_provider in ai_config and 
            'models' in ai_config[selected_provider] and 
            selected_model and 
            selected_model in ai_config[selected_provider]['models']
        )
        
        # 3. 使用有效配置或fallback
        if is_valid:
            final_provider = selected_provider
            final_model = selected_model
        else:
            final_provider = fallback_provider
            final_model = fallback_model
        # ====================================================================
        
        # 获取当前provider的配置，读取其api_key
        provider_config = ai_config.get(final_provider, {})
        api_key = provider_config.get('api_key', '')
        api_key_configured = bool(api_key and api_key.strip() != '')
        
        # 获取主题和语言配置（如果没有则使用默认值）
        theme = config.get('app.theme', 'light')
        language = config.get('app.language', 'zh-CN')
        
        # 获取安全配置（如果没有则使用默认值）
        security_config = config.get('security', {})
        if not security_config:
            # 使用默认值 - 所有字段都有默认值
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
            security=security_config
        )
        
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config")
async def update_config(config_update: ConfigUpdate):
    """
    更新系统配置
    
    将配置持久化到config.yaml文件
    
    Args:
        config_update: 配置更新请求
        
    Returns:
        dict: 更新结果
    """
    try:
        config_path = _get_config_path()
        
        # 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        # 更新AI配置
        if config_update.ai_provider:
            # 验证提供商 - 检查是否在配置文件中（通用方式，不硬编码）
            ai_config = config_data.get('ai', {})
            if config_update.ai_provider not in ai_config:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商: {config_update.ai_provider}"
                )
            config_data['ai']['provider'] = config_update.ai_provider
                
            # 切换AI服务提供商
            try:
                AIServiceFactory.switch_provider(config_update.ai_provider)
                logger.info(f"切换AI提供商成功: {config_update.ai_provider}")
            except Exception as e:
                logger.error(f"切换AI提供商失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"切换AI提供商失败: {str(e)}"
                )
        
        # 【修正】更新AI模型 - 只更新顶层ai.model
        # 如果只传了ai_model没传ai_provider，使用当前配置的provider
        if config_update.ai_model:
            provider = config_update.ai_provider or config_data.get('ai', {}).get('provider', 'zhipuai')
            if provider in config_data['ai']:
                # 【修正】只更新顶层 ai.model
                config_data['ai']['model'] = config_update.ai_model
                logger.info(f"切换AI模型成功: provider={provider}, model={config_update.ai_model}")
                # 【修复】清空AIServiceFactory缓存，强制重新读取配置
                AIServiceFactory._instance = None
                logger.info(f"已清空AIServiceFactory缓存")
        
        # 更新API Key - 通用方式（不硬编码）
        if config_update.provider_api_keys:
            for provider_name, api_key in config_update.provider_api_keys.items():
                if provider_name in config_data.get('ai', {}):
                    config_data['ai'][provider_name]['api_key'] = api_key
                    logger.info(f"更新Provider API Key成功: {provider_name}")
        
        # 确保app配置节存在
        if 'app' not in config_data:
            config_data['app'] = {}
        
        # 更新主题
        if config_update.theme:
            config_data['app']['theme'] = config_update.theme
        
        # 更新语言
        if config_update.language:
            config_data['app']['language'] = config_update.language
        
        # 更新安全配置
        if config_update.security:
            # 手动转换为字典 - 避免Pydantic版本兼容问题
            security_dict = {
                "contentFilterEnabled": config_update.security.contentFilterEnabled,
                "contentFilterLevel": config_update.security.contentFilterLevel,
                "whitelistEnabled": config_update.security.whitelistEnabled,
                "commandWhitelist": config_update.security.commandWhitelist,
                "commandBlacklist": config_update.security.commandBlacklist,
                "confirmDangerousOps": config_update.security.confirmDangerousOps,
                "maxFileSize": config_update.security.maxFileSize
            }
            config_data['security'] = security_dict
            logger.info(f"更新安全配置成功")
        
        # 写回配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config = get_config_instance()
        config.reload()
        
        logger.info(f"配置更新成功: {config_update.dict(exclude_none=True)}")
        
        return {
            "success": True,
            "message": "配置更新成功",
            "updated_fields": config_update.dict(exclude_none=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/config/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest):
    """
    验证配置是否有效
    
    使用通用BaseAIService测试API Key是否可用
    
    Args:
        request: 验证请求，包含provider和api_key
        
    Returns:
        ConfigValidateResponse: 验证结果
    """
    try:
        # 获取配置
        config = get_config_instance()
        
        # 获取provider配置
        provider_config = config.get(f'ai.{request.provider}', {})
        if not provider_config:
            return ConfigValidateResponse(
                valid=False,
                message=f"Provider '{request.provider}' 配置不存在",
                model=None
            )
        
        # 使用通用BaseAIService验证
        from app.services.base import BaseAIService
        
        # 【修复】优先用用户指定的provider，只有当指定provider无效时才fallback
        ai_config = config.get('ai', {})
        current_model_provider = request.provider
        
        # 检查用户指定的provider是否有有效配置
        provider_has_models = (
            current_model_provider in ai_config and 
            'models' in ai_config[current_model_provider] and 
            ai_config[current_model_provider]['models']
        )
        
        # 如果用户指定的provider无效，fallback到第一个有效的provider（动态遍历，不是硬编码！）
        if not provider_has_models:
            for provider_name in ai_config.keys():
                if provider_name == 'provider' or provider_name == 'model':
                    continue
                provider_data = ai_config.get(provider_name, {})
                if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
                    current_model_provider = provider_name
                    break
        
        # model优先用配置的，如果没有就用当前模型的第一个model
        model_name = ai_config.get('model', '')
        if not model_name:
            current_model_models = ai_config.get(current_model_provider, {}).get('models', [])
            if current_model_models and len(current_model_models) > 0:
                model_name = current_model_models[0]
        
        provider_config = ai_config.get(current_model_provider, {})
        api_base = provider_config.get('api_base', 'https://api.openai.com/v1')
        
        temp_service = BaseAIService(
            api_key=request.api_key,
            model=model_name,
            api_base=api_base,
            timeout=30
        )
        
        try:
            # 验证服务
            is_valid = await temp_service.validate()
            
            if is_valid:
                logger.info(f"配置验证成功: provider={request.provider}")
                return ConfigValidateResponse(
                    valid=True,
                    message=f"API Key验证成功，当前使用 {request.provider}",
                    model=model_name
                )
            else:
                logger.warning(f"配置验证失败: provider={request.provider}")
                return ConfigValidateResponse(
                    valid=False,
                    message=f"API Key无效，请检查是否正确",
                    model=None
                )
        finally:
            # 确保客户端关闭（异常时也会执行）
            await temp_service.close()
            
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return ConfigValidateResponse(
            valid=False,
            message=f"验证过程出错: {str(e)}",
            model=None
        )


# ============================================
# 模型列表相关
# ============================================

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


@router.get("/config/models", response_model=ModelListResponse)
async def get_model_list():
    """
    获取可用的AI模型列表
    
    支持新的models列表格式，每个provider可以有多个模型
    
    Returns:
        ModelListResponse: 可用模型列表
    """
    try:
        # 每次请求时重新加载配置文件，确保获取最新配置
        config = get_config_instance()
        config.reload()
        
        ai_config = config.get('ai', {})
        
        # ====================================================================
        # 【统一Fallback逻辑 - 必须遵守！】
        # 1. 找第一个有models的provider作为fallback
        fallback_provider = ''
        fallback_model = ''
        # 动态遍历所有provider（不是硬编码！）
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
                fallback_provider = provider_name
                fallback_model = provider_data['models'][0]
                break
        
        # 如果没有找到任何provider，用空值
        # 注意：配置文件应该至少有一个provider配置
        if not fallback_provider:
            fallback_provider = ''
            fallback_model = ''
        
        # 2. 检查 ai.provider 和 ai.model 是否有效
        selected_provider = ai_config.get('provider', '')
        selected_model = ai_config.get('model', '')
        
        is_valid = (
            selected_provider and 
            selected_provider in ai_config and 
            'models' in ai_config[selected_provider] and 
            selected_model and 
            selected_model in ai_config[selected_provider]['models']
        )
        
        # 3. 使用有效配置或fallback
        if is_valid:
            final_provider = selected_provider
            final_model = selected_model
        else:
            final_provider = fallback_provider
            final_model = fallback_model
        # ====================================================================
        
        # 构建模型列表 - 动态遍历配置文件中的所有provider
        models = []
        model_id = 1  # 从1开始的序号
        
        # 动态遍历所有provider（不是硬编码！）
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
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
        # 返回空列表，不返回硬编码默认值
        return ModelListResponse(
            models=[],
            default_provider=''
        )


# ============================================
# 完整配置管理API（新增）
# ============================================

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


@router.get("/config/full", response_model=FullConfigResponse)
async def get_full_config():
    """
    获取完整配置信息
    
    Returns:
        FullConfigResponse: 包含所有provider和model的完整配置
    """
    try:
        # 每次请求时重新加载配置文件，确保获取最新配置
        config = get_config_instance()
        config.reload()
        ai_config = config.get('ai', {})
        
        # ====================================================================
        # 【统一Fallback逻辑 - 必须遵守！】
        # 1. 找第一个有models的provider作为fallback（动态遍历，不是硬编码！）
        fallback_provider = ''
        fallback_model = ''
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
                fallback_provider = provider_name
                fallback_model = provider_data['models'][0]
                break
        
        # 如果没有找到任何provider，用空值
        # 注意：配置文件应该至少有一个provider配置
        if not fallback_provider:
            fallback_provider = ''
            fallback_model = ''
        
        # 2. 检查 ai.provider 和 ai.model 是否有效
        selected_provider = ai_config.get('provider', '')
        selected_model = ai_config.get('model', '')
        
        is_valid = (
            selected_provider and 
            selected_provider in ai_config and 
            'models' in ai_config[selected_provider] and 
            selected_model and 
            selected_model in ai_config[selected_provider]['models']
        )
        
        # 3. 使用有效配置或fallback
        if is_valid:
            final_provider = selected_provider
            final_model = selected_model
        else:
            final_provider = fallback_provider
            final_model = fallback_model
        # ====================================================================
        
        providers = {}
        # 动态遍历所有provider（不是硬编码！）
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if not isinstance(provider_data, dict):
                continue
            # 个人系统，返回明文API Key
            api_key = provider_data.get('api_key', '')
            
            providers[provider_name] = ProviderInfo(
                name=provider_name,
                api_base=provider_data.get('api_base', ''),
                api_key=api_key,  # 返回明文Key
                model='',  # provider下已无model字段，统一在顶层ai.model
                models=provider_data.get('models', []),
                timeout=provider_data.get('timeout', 60),
                max_retries=provider_data.get('max_retries', 3)
            )
        
        return FullConfigResponse(
            providers=providers,
            current_provider=final_provider,
            current_model=final_model
        )
    except Exception as e:
        logger.error(f"获取完整配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/provider/{provider_name}")
async def delete_provider(provider_name: str):
    """
    删除Provider
    
    Args:
        provider_name: Provider名称
    """
    try:
        config_path = _get_config_path()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        # 统计实际的provider数量（排除provider字段）
        provider_keys = [k for k in config.get('ai', {}).keys() if k != 'provider']
        if len(provider_keys) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个Provider")
        
        # 删除provider
        del config['ai'][provider_name]
        
        # 如果删除的是当前provider，切换到第一个
        if config['ai'].get('provider') == provider_name:
            remaining = [k for k in config['ai'].keys() if k != 'provider']
            if remaining:
                config['ai']['provider'] = remaining[0]
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"Provider {provider_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/provider/{provider_name}/model/{model_name}")
async def delete_model(provider_name: str, model_name: str):
    """
    删除Provider下的模型
    
    Args:
        provider_name: Provider名称
        model_name: 模型名称
    """
    try:
        config_path = _get_config_path()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        provider_config = config.get('ai', {}).get(provider_name, {})
        if not provider_config:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        models = provider_config.get('models', [])
        if model_name not in models:
            raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
        
        # 不能删除最后一个模型
        if len(models) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个模型")
        
        # 删除模型
        models.remove(model_name)
        config['ai'][provider_name]['models'] = models
        
        # 如果删除的是当前模型，更新顶层 ai.model 为新列表的第一个
        ai_config = config.get('ai', {})
        current_model = ai_config.get('model', '')
        if current_model == model_name and models:
            config['ai']['model'] = models[0]
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"模型 {model_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/provider/{provider_name}")
async def update_provider(provider_name: str, data: ProviderUpdate):
    """
    更新Provider配置
    
    Args:
        provider_name: Provider名称
        data: 更新数据
    """
    try:
        config_path = _get_config_path()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        # 更新配置
        if data.api_base is not None:
            config['ai'][provider_name]['api_base'] = data.api_base
        if data.api_key is not None:
            config['ai'][provider_name]['api_key'] = data.api_key
        if data.model is not None:
            # 【修正】更新顶层 ai.model，而不是 provider 下的 model
            config['ai']['model'] = data.model
        if data.timeout is not None:
            config['ai'][provider_name]['timeout'] = data.timeout
        if data.max_retries is not None:
            config['ai'][provider_name]['max_retries'] = data.max_retries
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"Provider {provider_name} 已更新"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/provider/{provider_name}/model")
async def add_model(provider_name: str, data: ModelAddRequest):
    """
    添加模型到Provider
    
    Args:
        provider_name: Provider名称
        data: 模型名称
    """
    try:
        config_path = _get_config_path()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        models = config['ai'][provider_name].get('models', [])
        if data.model in models:
            raise HTTPException(status_code=400, detail=f"模型 {data.model} 已存在")
        
        # 添加模型
        models.append(data.model)
        config['ai'][provider_name]['models'] = models
        
        # 如果，设为新增的顶层没有ai.model模型
        if not config['ai'].get('model'):
            config['ai']['model'] = data.model
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"模型 {data.model} 已添加"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/provider")
async def add_provider(data: ProviderAddRequest):
    """
    添加新Provider
    
    Args:
        data: Provider配置
    """
    try:
        config_path = _get_config_path()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if data.name in config.get('ai', {}):
            raise HTTPException(status_code=400, detail=f"Provider {data.name} 已存在")
        
        # 添加Provider
        config['ai'][data.name] = {
            'api_base': data.api_base,
            'api_key': data.api_key,
            'models': data.models if data.models else [data.model],
            'timeout': data.timeout,
            'max_retries': data.max_retries
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"Provider {data.name} 已添加"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 完整配置验证API
# ============================================

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


def _backup_config_file(config_path: Path) -> Path:
    """
    自动备份配置文件
    
    返回备份文件路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config_path.parent / f"config.yaml.backup.{timestamp}"
    
    shutil.copy2(config_path, backup_path)
    logger.info(f"配置文件已备份: {backup_path}")
    
    return backup_path


def _validate_config_integrity(config_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    完整验证配置文件完整性
    
    返回: (是否通过, 错误列表, 警告列表)
    """
    errors = []
    warnings = []
    
    ai_config = config_data.get('ai', {})
    
    # 1. 检查 ai.provider 和 ai.model 是否存在
    if 'provider' not in ai_config:
        errors.append("缺少 ai.provider 字段")
    if 'model' not in ai_config:
        errors.append("缺少 ai.model 字段")
    
    if errors:
        return False, errors, warnings
    
    selected_provider = ai_config['provider']
    selected_model = ai_config['model']
    
    # 2. 检查 provider 是否存在
    if selected_provider not in ai_config:
        errors.append(f"provider '{selected_provider}' 不存在")
        return False, errors, warnings
    
    provider_config = ai_config[selected_provider]
    
    # 3. 检查 provider 下必须有 api_base 和 api_key
    if 'api_base' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_base 字段")
    if 'api_key' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_key 字段")
    
    if errors:
        return False, errors, warnings
    
    # 4. 检查 provider 下是否有 models 列表
    if 'models' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 models 列表")
        return False, errors, warnings
    
    models_list = provider_config['models']
    
    # 5. 检查 model 是否在 models 列表中
    if selected_model not in models_list:
        errors.append(f"model '{selected_model}' 不在 provider '{selected_provider}' 的 models 列表中")
        return False, errors, warnings
    
    # 6. 检查并警告：provider 下是否有废弃的 model 字段
    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            warnings.append(f"provider '{provider_name}' 下有废弃的 model 字段，建议删除")
    
    return True, errors, warnings


def _fix_config_common_issues(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    自动修复常见的配置问题
    
    修复内容：
    1. 删除所有 provider 下废弃的 model 字段
    """
    ai_config = config_data.get('ai', {})
    
    # 清理所有 provider 下废弃的 model 字段
    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            del provider_data['model']
            logger.info(f"已删除 provider '{provider_name}' 下废弃的 model 字段")
    
    return config_data


@router.post("/config/fix", response_model=ConfigFixResponse)
async def fix_config():
    """
    修复配置文件常见问题
    
    修复内容：
    1. 删除所有 provider 下废弃的 model 字段
    2. 验证配置完整性
    """
    try:
        config_path = _get_config_path()
        
        # 1. 备份
        backup_path = _backup_config_file(config_path)
        
        # 2. 读取配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        fixed_issues = []
        
        # 3. 自动修复
        ai_config = config_data.get('ai', {})
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'model' in provider_data:
                del provider_data['model']
                fixed_issues.append(f"删除 provider '{provider_name}' 下废弃的 model 字段")
        
        # 4. 验证修复后的配置
        is_valid, errors, warnings = _validate_config_integrity(config_data)
        
        if not is_valid:
            return ConfigFixResponse(
                success=False,
                fixed_issues=fixed_issues,
                warnings=warnings + errors,
                backup_path=str(backup_path)
            )
        
        # 5. 写入修复后的配置
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        # 6. 重新加载
        config = get_config_instance()
        config.reload()
        
        logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
        
        return ConfigFixResponse(
            success=True,
            fixed_issues=fixed_issues,
            warnings=warnings,
            backup_path=str(backup_path)
        )
        
    except Exception as e:
        logger.error(f"配置修复失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置修复失败: {str(e)}")


@router.get("/config/validate-full", response_model=FullConfigValidationResponse)
async def validate_full_config():
    """
    完整配置验证
    
    验证项：
    1. 配置文件是否存在
    2. ai 配置块是否存在
    3. provider 字段是否存在
    4. provider 配置是否存在
    5. api_key 是否存在
    6. model 是否存在
    7. api_base 是否存在
    
    Returns:
        FullConfigValidationResponse: 包含错误列表和警告列表的完整验证结果
    """
    try:
        # 使用AIServiceFactory的验证方法
        validation_result = AIServiceFactory.validate_config()
        
        logger.info(f"完整配置验证: success={validation_result.success}, errors={len(validation_result.errors)}, warnings={len(validation_result.warnings)}")
        
        return FullConfigValidationResponse(
            success=validation_result.success,
            provider=validation_result.provider,
            model=validation_result.model,
            message=validation_result.message,
            errors=validation_result.errors,
            warnings=validation_result.warnings
        )
        
    except Exception as e:
        logger.error(f"完整配置验证异常: {e}")
        return FullConfigValidationResponse(
            success=False,
            provider="unknown",
            model="",
            message=f"验证过程出错: {str(e)}",
            errors=[str(e)],
            warnings=[]
        )
