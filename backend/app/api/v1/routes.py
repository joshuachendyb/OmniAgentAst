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
import shutil
import subprocess
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from collections import OrderedDict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger
from app.services.agent.base_react import DEFAULT_MAX_STEPS
from app.services.ai_config_resolver import get_ai_config_resolver

router = APIRouter()


def ordered_dict(data: dict) -> OrderedDict:
    """
    将字典转换为OrderedDict，保持特定顺序
    ai节点下：provider和model在最前面，其他provider按字母顺序
    """
    if not isinstance(data, dict):
        return data
    
    result = OrderedDict()
    
    # ai节点的特定顺序
    if 'ai' in data:
        ai_data = data['ai']
        ai_ordered = OrderedDict()
        
        # 首先添加provider和model（如果存在）
        if 'provider' in ai_data:
            ai_ordered['provider'] = ai_data['provider']
        if 'model' in ai_data:
            ai_ordered['model'] = ai_data['model']
        
        # 然后添加其他key，按字母顺序
        for key in sorted(ai_data.keys()):
            if key not in ('provider', 'model'):
                value = ai_data[key]
                if isinstance(value, dict):
                    ai_ordered[key] = ordered_dict(value)
                else:
                    ai_ordered[key] = value
        
        result['ai'] = ai_ordered
    
    # 处理其他节点，按字母顺序
    for key in sorted(data.keys()):
        if key != 'ai':
            value = data[key]
            if isinstance(value, dict):
                result[key] = ordered_dict(value)
            else:
                result[key] = value
    
    return result


def write_yaml_with_order(file_path: str, data: dict):
    """使用OrderedDict写入YAML，保持特定顺序"""
    ordered_data = ordered_dict(data)
    
    # 自定义representer，让OrderedDict按普通dict输出
    def represent_ordereddict(dumper, data):
        return dumper.represent_dict(data.items())
    
    yaml.add_representer(OrderedDict, represent_ordereddict)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(ordered_data, f, allow_unicode=True, default_flow_style=False)


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
        
        # 【重构 2026-05-28 小健】直接调用AIConfigResolver，绕过config中间层
        from app.services.ai_config_resolver import resolve_provider_model
        final_provider, final_model = resolve_provider_model()
        
        # 获取当前provider的配置，读取其api_key
        ai_config = config.get('ai', {})
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
            security=security_config,
            max_steps=config.get_max_steps(DEFAULT_MAX_STEPS)  # 使用统一方法
        )
        
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config")
async def update_config(config_update: ConfigUpdate):
    """更新系统配置（带备份恢复机制）- 小欧 2026-03-01, 重构 小健 2026-05-25"""
    backup_path: Optional[Path] = None
    config_path: Optional[Path] = None
    restored = [False]

    try:
        config_path = Path(AIServiceFactory.get_config_path())
        backup_path = _backup_config(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            original_config_data = yaml.safe_load(f) or {}
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

        write_yaml_with_order(str(config_path), config_data)
        with open(config_path, 'r', encoding='utf-8') as f:
            verify_data = yaml.safe_load(f)
            logger.info(f"[update_config] 验证写入: provider={verify_data['ai'].get('provider')}, model={verify_data['ai'].get('model')}")
        get_config_instance().reload()

        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
                logger.info(f"验证成功，已删除备份文件：{backup_path}")
            except Exception as e:
                logger.warning(f"删除备份文件失败：{e}")
        AIServiceFactory.clear_backup_paths()

        current_provider = config_data.get('ai', {}).get('provider', '')
        current_model = config_data.get('ai', {}).get('model', '')
        return {
            "success": True, "message": "配置更新成功，请验证服务可用性",
            "updated_fields": config_update.dict(exclude_none=True), "warnings": warnings,
            "backup_path": str(backup_path), "current_provider": current_provider, "current_model": current_model,
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
        logger.error(f"更新配置失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新配置失败，请稍后重试")


@router.put("/config/validate", response_model=ConfigValidateResponse)
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
        # 使用统一的AIConfigResolver进行验证
        resolver = get_ai_config_resolver()
        
        # 验证指定的provider和model
        try:
            provider_config = resolver.get_service_config(request.provider, request.model)
        except ValueError as e:
            return ConfigValidateResponse(
                valid=False,
                message=str(e),
                model=None
            )
        
        # 获取最终的provider和model（含fallback）
        final_provider, final_model = resolver.resolve_provider_model()
        
        # 配置已保存，FC能力在首次LLM调用时由 llm_adapter.detect_strategy 自动探测
        logger.info(f"配置已保存: provider={final_provider}, model={final_model}")
        return ConfigValidateResponse(
            valid=True,
            message=f"配置已保存，将在首次使用时验证 {final_provider} ({final_model})",
            model=final_model
        )
            
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
        # 使用缓存，自动检测变更
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        
        final_provider, final_model = resolver.resolve_provider_model()
        
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
        # 使用缓存，自动检测变更
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        final_provider, final_model = resolver.resolve_provider_model()
        
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
        config_path = Path(AIServiceFactory.get_config_path())
        
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
        
        write_yaml_with_order(str(config_path), config)
        
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
        config_path = Path(AIServiceFactory.get_config_path())
        
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
        
        write_yaml_with_order(str(config_path), config)
        
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


@router.put("/config/provider/{provider_name}/model/{old_model_name}")
async def update_model(provider_name: str, old_model_name: str, data: ModelAddRequest):
    """
    更新Provider下的模型名称
    
    Args:
        provider_name: Provider名称
        old_model_name: 原模型名称
        data: 新模型名称
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        models = config['ai'][provider_name].get('models', [])
        
        # 清理新模型名称
        new_model_name = ' '.join(data.model.split())
        
        if old_model_name not in models:
            raise HTTPException(status_code=404, detail=f"模型 {old_model_name} 不存在")
        
        if new_model_name == old_model_name:
            return {"success": True, "message": "模型名称未改变"}
        
        if new_model_name in models:
            raise HTTPException(status_code=400, detail=f"模型 {new_model_name} 已存在")
        
        # 更新模型名称
        index = models.index(old_model_name)
        models[index] = new_model_name
        config['ai'][provider_name]['models'] = models
        

        
        write_yaml_with_order(str(config_path), config)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {"success": True, "message": f"模型已从 {old_model_name} 更新为 {new_model_name}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/provider/{provider_name}")
async def update_provider(provider_name: str, data: ProviderUpdate):
    """
    更新Provider配置（新版本：带验证和备份）
    
    Args:
        provider_name: Provider名称
        data: 更新数据
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        
        # 1. 自动备份
        backup_path = _backup_config(config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        # 2. 更新配置
        if data.api_base is not None:
            config['ai'][provider_name]['api_base'] = data.api_base
        if data.api_key is not None:
            config['ai'][provider_name]['api_key'] = data.api_key.strip()  # trim 空格
        if data.model is not None:
            # 【修正】更新顶层 ai.model，而不是 provider 下的 model
            config['ai']['model'] = data.model.strip()  # trim 空格
        if data.timeout is not None:
            config['ai'][provider_name]['timeout'] = data.timeout
        if data.max_retries is not None:
            config['ai'][provider_name]['max_retries'] = data.max_retries
        
        # 3. 自动修复常见问题
        config = _fix_config_common_issues(config)
        
        # 4. 验证配置完整性
        is_valid, errors, warnings = _validate_config_integrity(config)
        
        if not is_valid:
            return {
                "success": False,
                "message": "配置验证失败",
                "errors": errors,
                "warnings": warnings,
                "backup_path": str(backup_path)
            }
        
        write_yaml_with_order(str(config_path), config)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {
            "success": True,
            "message": f"Provider {provider_name} 已更新",
            "warnings": warnings,
            "backup_path": str(backup_path)
        }
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
        config_path = Path(AIServiceFactory.get_config_path())
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        # 清理模型名称：移除首尾空白和内部多余空格
        model_name = ' '.join(data.model.split())
        
        models = config['ai'][provider_name].get('models', [])
        if model_name in models:
            raise HTTPException(status_code=400, detail=f"模型 {model_name} 已存在")
        
        # 添加模型
        models.append(model_name)
        config['ai'][provider_name]['models'] = models
        
        # 如果，设为新增的顶层没有ai.model模型
        if not config['ai'].get('model'):
            config['ai']['model'] = model_name
        
        write_yaml_with_order(str(config_path), config)
        
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
    添加新Provider（新版本：不写废弃的model字段）
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        
        # 1. 自动备份
        backup_path = _backup_config(config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if data.name in config.get('ai', {}):
            raise HTTPException(status_code=400, detail=f"Provider {data.name} 已存在")
        
        # 2. 【修正】不写 provider 下的 model 字段
        config['ai'][data.name] = {
            'api_base': data.api_base.strip(),  # trim 空格
            'api_key': data.api_key.strip() if data.api_key else "",  # trim 空格
            'models': [m.strip() for m in (data.models if data.models else ([data.model] if data.model else []))],  # trim 空格
            'timeout': data.timeout,
            'max_retries': data.max_retries
        }
        
        # 3. 验证配置
        is_valid, errors, warnings = _validate_config_integrity(config)
        
        if not is_valid:
            return {
                "success": False,
                "message": "配置验证失败",
                "errors": errors,
                "backup_path": str(backup_path)
            }
        
        write_yaml_with_order(str(config_path), config)
        
        # 重新加载配置
        config_obj = get_config_instance()
        config_obj._load_config()
        
        # 清空AIServiceFactory缓存
        AIServiceFactory.reset()
        
        return {
            "success": True,
            "message": f"Provider {data.name} 已添加",
            "warnings": warnings
        }
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


class ConfigPathResponse(BaseModel):
    """配置文件路径响应"""
    config_path: str = Field(..., description="配置文件完整路径")
    config_dir: str = Field(..., description="配置文件所在目录")
    exists: bool = Field(..., description="配置文件是否存在")


def _invalidate_ai_service_cache(provider: Optional[str] = None) -> None:
    """清理AIServiceFactory缓存，强制下次重新读取配置 - 小健 2026-05-25"""
    AIServiceFactory._instance = None
    AIServiceFactory._config = None
    if provider:
        AIServiceFactory._current_provider = provider
    logger.info("已清空AIServiceFactory缓存，下次调用将重新加载配置")


def _backup_config(config_path: Path) -> Path:
    """备份配置文件，复用file_helpers.backup_file - 小健 2026-05-25"""
    from app.services.tools.toolhelper.file_helpers import backup_file
    result = backup_file(str(config_path), suffix=".backup")
    if result.get("code") != "SUCCESS":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.parent / f"config.yaml.backup.{timestamp}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"配置文件已备份(fallback): {backup_path}")
        return backup_path
    bp = Path(result["data"]["backup_path"])
    logger.info(f"配置文件已备份: {bp}")
    return bp


def _update_provider(config_data: dict, update: "ConfigUpdate") -> None:
    ai_config = config_data.get('ai', {})
    if update.ai_provider not in ai_config:
        raise HTTPException(status_code=400, detail=f"不支持的提供商: {update.ai_provider}")
    config_data['ai']['provider'] = update.ai_provider
    _invalidate_ai_service_cache(update.ai_provider)
    logger.info(f"更新AI Provider: {update.ai_provider}")


def _update_model(config_data: dict, update: "ConfigUpdate") -> None:
    _ai_cfg = config_data.get('ai', {})
    provider = update.ai_provider or _ai_cfg.get('provider')
    if not provider:
        for _k, _v in _ai_cfg.items():
            if isinstance(_v, dict) and _v.get('models'):
                provider = _k
                break
    if provider in config_data.get('ai', {}):
        config_data['ai']['model'] = update.ai_model
        logger.info(f"更新AI Model: {update.ai_model} (provider={provider})")
        _invalidate_ai_service_cache(provider)


def _update_api_keys(config_data: dict, update: "ConfigUpdate") -> None:
    for provider_name, api_key in (update.provider_api_keys or {}).items():
        if provider_name in config_data.get('ai', {}):
            config_data['ai'][provider_name]['api_key'] = api_key.strip()
            logger.info(f"更新Provider API Key成功: {provider_name}")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的Provider: {provider_name}")


def _update_theme(config_data: dict, update: "ConfigUpdate") -> None:
    config_data.setdefault('app', {})['theme'] = update.theme
    logger.info(f"更新主题: {update.theme}")


def _update_language(config_data: dict, update: "ConfigUpdate") -> None:
    config_data.setdefault('app', {})['language'] = update.language
    logger.info(f"更新语言: {update.language}")


def _update_max_steps(config_data: dict, update: "ConfigUpdate") -> None:
    if update.max_steps < 1:
        raise HTTPException(status_code=400, detail="max_steps 必须大于等于 1")
    if update.max_steps > 1000:
        raise HTTPException(status_code=400, detail="max_steps 不能超过 1000")
    config_data.setdefault('app', {})['max_steps'] = update.max_steps
    logger.info(f"更新max_steps: {update.max_steps}")


def _update_security(config_data: dict, update: "ConfigUpdate") -> None:
    if not update.security:
        return
    config_data['security'] = {
        "contentFilterEnabled": update.security.contentFilterEnabled,
        "contentFilterLevel": update.security.contentFilterLevel,
        "whitelistEnabled": update.security.whitelistEnabled,
        "commandWhitelist": update.security.commandWhitelist,
        "commandBlacklist": update.security.commandBlacklist,
        "confirmDangerousOps": update.security.confirmDangerousOps,
        "maxFileSize": update.security.maxFileSize,
    }
    logger.info("更新安全配置成功")


FIELD_HANDLERS: Dict[str, Any] = {
    "ai_provider": _update_provider,
    "ai_model": _update_model,
    "provider_api_keys": _update_api_keys,
    "theme": _update_theme,
    "language": _update_language,
    "max_steps": _update_max_steps,
    "security": _update_security,
}


def _restore_backup_if_needed(
    backup_path: Optional[Path], config_path: Optional[Path],
    restored_flag: List[bool],
) -> bool:
    """恢复备份配置（仅一次）- 小健 2026-05-25"""
    if restored_flag[0]:
        return False
    if not backup_path or not config_path or not backup_path.exists():
        return False
    try:
        shutil.copy2(str(backup_path), str(config_path))
        restored_flag[0] = True
        logger.warning(f"已从备份恢复配置: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"备份恢复失败: {e}")
        return False


def _auto_fix_and_validate(
    config_data: dict, config_path: Path, backup_path: Optional[Path],
    original_config_data: dict,
) -> Tuple[bool, List[str], List[str], Optional[Dict[str, Any]]]:
    """自动修复+验证，失败则恢复备份 - 小健 2026-05-25"""
    config_data = _fix_config_common_issues(config_data)
    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        _restore_backup_if_needed(backup_path, config_path, [False])
        get_config_instance().reload()
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        original_ai = original_config_data.get('ai', {})
        fail_result = {
            "success": False, "message": "配置验证失败", "errors": errors, "warnings": warnings,
            "backup_path": str(backup_path) if backup_path else None,
            "current_provider": original_ai.get('provider', 'unknown'),
            "current_model": original_ai.get('model', 'unknown'),
        }
        return False, errors, warnings, fail_result
    return True, [], warnings, None


# ================================================================================
# 防御性备份清理函数（暂时不启用，等待后续调试完成后再启用）
# ================================================================================
# 
# 【背景】
# 备份机制设计：
#   1. 用户切换模型 → update_config → 创建备份文件
#   2. 调用 validateService 验证
#   3. 验证成功 → 删除备份
#   4. 验证失败 → 恢复备份
# 
# 正常情况下：
#   - 备份文件会在验证成功后立即删除
#   - 不会出现多个备份文件遗留
# 
# 异常情况（需要清理）：
#   1. 用户切换模型后直接关闭应用（没调用validateService）
#   2. 应用异常崩溃
#   3. 验证过程中网络中断
#   → 以上情况会导致备份文件遗留
# 
# 启动时清理策略：
#   1. 扫描 config 目录下的所有 config.yaml.backup.* 文件
#   2. 删除所有遗留的备份文件
#   3. 原因：当前配置文件已经是最新状态（成功时被删除，失败时被恢复）
# 
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
        config_path = Path(AIServiceFactory.get_config_path())
        
        # 1. 备份
        backup_path = _backup_config(config_path)
        
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
            write_yaml_with_order(str(config_path), config_data)
        
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


@router.get("/config/path", response_model=ConfigPathResponse)
async def get_config_path():
    """
    获取配置文件路径
    
    Returns:
        ConfigPathResponse: 配置文件路径信息
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        return ConfigPathResponse(
            config_path=str(config_path),
            config_dir=str(config_path.parent),
            exists=config_path.exists()
        )
    except Exception as e:
        logger.error(f"获取配置路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置路径失败: {str(e)}")


@router.post("/config/open-folder")
async def open_config_folder():
    """
    打开配置文件所在目录（调用系统资源管理器）
    
    在Windows上使用explorer.exe打开文件夹
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        config_dir = str(config_path.parent)
        
        if not os.path.exists(config_dir):
            raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
        
        # 使用Windows资源管理器打开文件夹
        # explorer /select,"file" 会打开文件夹并选中文件
        # explorer /e,"folder" 会打开文件夹
        subprocess.Popen(['explorer', '/e,', config_dir], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
        logger.info(f"已打开配置目录: {config_dir}")
        return {"success": True, "path": config_dir}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"打开配置目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"打开配置目录失败: {str(e)}")


@router.get("/config/read")
async def read_config_file():
    """
    读取配置文件原文内容
    
    Returns:
        config_content: 配置文件YAML原文
    """
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"config_content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}")

