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


class ConfigUpdate(BaseModel):
    """配置更新请求"""
    ai_provider: Optional[str] = Field(None, description="AI提供商: zhipuai | opencode")
    api_key: Optional[str] = Field(None, description="API密钥")
    theme: Optional[str] = Field("light", description="主题: light | dark")
    language: Optional[str] = Field("zh-CN", description="语言: zh-CN | en-US")


class ConfigResponse(BaseModel):
    """配置响应"""
    ai_provider: str = Field(..., description="当前AI提供商")
    ai_model: str = Field(..., description="当前AI模型")
    api_key_configured: bool = Field(..., description="API Key是否已配置")
    theme: str = Field(..., description="当前主题")
    language: str = Field(..., description="当前语言")


class ConfigValidateRequest(BaseModel):
    """配置验证请求"""
    provider: str = Field(..., description="AI提供商")
    api_key: str = Field(..., description="API密钥")


class ConfigValidateResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="配置是否有效")
    message: str = Field(..., description="验证消息")


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
        
        logger.info(f"获取配置成功: provider={provider}")
        
        return ConfigResponse(
            ai_provider=provider,
            ai_model=ai_config.get('model', ''),
            api_key_configured=api_key_configured,
            theme=theme,
            language=language
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
            if config_update.ai_provider not in ["zhipuai", "opencode"]:
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
        
        # 更新API Key
        if config_update.api_key:
            provider = config_update.ai_provider or config_data['ai']['provider']
            config_data['ai'][provider]['api_key'] = config_update.api_key
            logger.info(f"更新API Key成功: provider={provider}")
        
        # 确保app配置节存在
        if 'app' not in config_data:
            config_data['app'] = {}
        
        # 更新主题
        if config_update.theme:
            config_data['app']['theme'] = config_update.theme
        
        # 更新语言
        if config_update.language:
            config_data['app']['language'] = config_update.language
        
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
    
    测试API Key是否可用
    
    Args:
        request: 验证请求，包含provider和api_key
        
    Returns:
        ConfigValidateResponse: 验证结果
    """
    try:
        # 验证提供商
        if request.provider not in ["zhipuai", "opencode"]:
            return ConfigValidateResponse(
                valid=False,
                message=f"不支持的提供商: {request.provider}"
            )
        
        # 获取配置
        config = get_config_instance()
        
        # 创建临时服务实例进行验证
        if request.provider == "zhipuai":
            from app.services.zhipuai import ZhipuAIService
            temp_service = ZhipuAIService(
                api_key=request.api_key,
                model=config.get('ai.zhipuai.model', 'glm-4.7-flash'),
                api_base=config.get('ai.zhipuai.api_base', 'https://open.bigmodel.cn/api/paas/v4'),
                timeout=30
            )
        else:
            from app.services.opencode import OpenCodeService
            temp_service = OpenCodeService(
                api_key=request.api_key,
                model=config.get('ai.opencode.model', 'minimax-m2.5-free'),
                api_base=config.get('ai.opencode.api_base', 'https://opencode.ai/zen/v1'),
                timeout=30
            )
        
        # 验证服务
        is_valid = await temp_service.validate()
        
        if is_valid:
            logger.info(f"配置验证成功: provider={request.provider}")
            return ConfigValidateResponse(
                valid=True,
                message=f"API Key验证成功，当前使用 {request.provider}"
            )
        else:
            logger.warning(f"配置验证失败: provider={request.provider}")
            return ConfigValidateResponse(
                valid=False,
                message=f"API Key无效，请检查是否正确"
            )
            
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return ConfigValidateResponse(
            valid=False,
            message=f"验证过程出错: {str(e)}"
        )
