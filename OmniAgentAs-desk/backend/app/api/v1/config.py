# 配置管理API路由
# 编程人：小沈
# 创建时间：2026-02-17

"""
配置管理API路由
提供系统配置的获取、更新、验证功能
支持从YAML文件持久化配置
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
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
    ai_provider: Optional[str] = Field(None, description="AI提供商: zhipuai | opencode | longcat")
    ai_model: Optional[str] = Field(None, description="AI模型名称")
    zhipu_api_key: Optional[str] = Field(None, description="智谱AI API密钥")
    opencode_api_key: Optional[str] = Field(None, description="OpenCode API密钥")
    longcat_api_key: Optional[str] = Field(None, description="LongCat API密钥")
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
        
        # 获取当前AI配置
        provider = config.get('ai.provider', 'zhipuai')
        ai_config = config.get_ai_config(provider)
        
        # 检查API Key是否已配置（脱敏）
        api_key = ai_config.get('api_key', '')
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
        
        logger.info(f"获取配置成功: provider={provider}")
        
        return ConfigResponse(
            ai_provider=provider,
            ai_model=ai_config.get('model', ''),
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
            # 验证提供商
            if config_update.ai_provider not in ["zhipuai", "opencode", "longcat"]:
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
        
        # 更新AI模型 - 更新对应provider下的model字段
        # 如果只传了ai_model没传ai_provider，使用当前配置的provider
        if config_update.ai_model:
            provider = config_update.ai_provider or config_data.get('ai', {}).get('provider', 'zhipuai')
            if provider in config_data['ai']:
                config_data['ai'][provider]['model'] = config_update.ai_model
                logger.info(f"切换AI模型成功: provider={provider}, model={config_update.ai_model}")
                # 【修复】清空AIServiceFactory缓存，强制重新读取配置
                AIServiceFactory._instance = None
                logger.info(f"已清空AIServiceFactory缓存")
        
        # 更新API Key - 根据provider更新对应的API Key
        if config_update.zhipu_api_key:
            config_data['ai']['zhipuai']['api_key'] = config_update.zhipu_api_key
            logger.info(f"更新智谱AI API Key成功")
        
        if config_update.opencode_api_key:
            config_data['ai']['opencode']['api_key'] = config_update.opencode_api_key
            logger.info(f"更新OpenCode API Key成功")
        
        if config_update.longcat_api_key:
            config_data['ai']['longcat']['api_key'] = config_update.longcat_api_key
            logger.info(f"更新LongCat API Key成功")
        
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
        
        model_name = provider_config.get('model', '')
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
    id: str = Field(..., description="模型ID")
    name: str = Field(..., description="模型显示名称")
    provider: str = Field(..., description="所属提供商")


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
        
        # 从配置中读取模型信息
        zhipuai_config = config.get('ai.zhipuai', {})
        opencode_config = config.get('ai.opencode', {})
        longcat_config = config.get('ai.longcat', {})
        
        default_provider = config.get('ai.provider', 'zhipuai')
        
        # 构建模型列表 - 按照配置文件中provider的实际顺序
        # 配置文件顺序: longcat -> opencode -> zhipuai
        models = []
        
        # LongCat模型（配置文件中第一个provider）
        longcat_config = config.get('ai.longcat', {})
        longcat_models = longcat_config.get('models', [])
        if isinstance(longcat_models, list) and longcat_models:
            for model_name in longcat_models:
                models.append(ModelInfo(
                    id=f"longcat-{model_name}",
                    name=f"LongCat ({model_name})",
                    provider="longcat"
                ))
        
        # OpenCode模型（配置文件中第二个provider）
        opencode_config = config.get('ai.opencode', {})
        opencode_models = opencode_config.get('models', [])
        if isinstance(opencode_models, list) and opencode_models:
            for model_name in opencode_models:
                models.append(ModelInfo(
                    id=f"opencode-{model_name}",
                    name=f"OpenCode ({model_name})",
                    provider="opencode"
                ))
        
        # 智谱模型（配置文件中第三个provider）
        zhipuai_config = config.get('ai.zhipuai', {})
        zhipuai_models = zhipuai_config.get('models', [])
        if isinstance(zhipuai_models, list) and zhipuai_models:
            for model_name in zhipuai_models:
                models.append(ModelInfo(
                    id=f"zhipuai-{model_name}",
                    name=f"智谱GLM ({model_name})",
                    provider="zhipuai"
                ))
        
        logger.info(f"获取模型列表成功: {len(models)}个模型")
        
        return ModelListResponse(
            models=models,
            default_provider=default_provider
        )
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        # 返回空列表，不返回硬编码默认值
        return ModelListResponse(
            models=[],
            default_provider="zhipuai"
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
        current_provider = ai_config.get('provider', 'zhipuai')
        current_model = ai_config.get(current_provider, {}).get('model', '')
        
        providers = {}
        for provider_name in ['opencode', 'zhipuai', 'longcat']:
            provider_data = ai_config.get(provider_name, {})
            if provider_data:
                # 个人系统，返回明文API Key
                api_key = provider_data.get('api_key', '')
                
                providers[provider_name] = ProviderInfo(
                    name=provider_name,
                    api_base=provider_data.get('api_base', ''),
                    api_key=api_key,  # 返回明文Key
                    model=provider_data.get('model', ''),
                    models=provider_data.get('models', []),
                    timeout=provider_data.get('timeout', 60),
                    max_retries=provider_data.get('max_retries', 3)
                )
        
        return FullConfigResponse(
            providers=providers,
            current_provider=current_provider,
            current_model=current_model
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
        
        # 如果删除的是当前模型，更新为第一个
        if provider_config.get('model') == model_name and models:
            config['ai'][provider_name]['model'] = models[0]
        
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
            config['ai'][provider_name]['model'] = data.model
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
        
        # 如果没有当前模型，设为新增的模型
        if not config['ai'][provider_name].get('model'):
            config['ai'][provider_name]['model'] = data.model
        
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
            'model': data.model,
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

class FullConfigValidationResponse(BaseModel):
    """完整配置验证响应"""
    success: bool = Field(..., description="验证是否成功")
    provider: str = Field(..., description="当前Provider")
    model: str = Field(..., description="当前Model")
    message: str = Field(..., description="验证消息")
    errors: list[str] = Field(default_factory=list, description="错误列表")
    warnings: list[str] = Field(default_factory=list, description="警告列表")


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