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
from collections import OrderedDict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger

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


def _ensure_ai_provider_model_first(config_data: dict) -> dict:
    """
    确保 ai.provider 和 ai.model 在 ai 字典的最前面
    解决写入配置文件时顺序错乱的问题
    """
    if 'ai' not in config_data:
        return config_data
    
    ai_data = config_data['ai']
    if not isinstance(ai_data, dict):
        return config_data
    
    # 构建新的有序字典，provider 和 model 在最前面
    new_ai = OrderedDict()
    
    # 先添加 provider 和 model
    if 'provider' in ai_data:
        new_ai['provider'] = ai_data['provider']
    if 'model' in ai_data:
        new_ai['model'] = ai_data['model']
    
    # 再添加其他 key，按字母顺序
    for key in sorted(ai_data.keys()):
        if key not in ('provider', 'model'):
            new_ai[key] = ai_data[key]
    
    config_data['ai'] = new_ai
    return config_data


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
    max_steps: int = Field(100, description="Agent最大迭代次数")


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
            security=security_config,
            max_steps=config.get('app', {}).get('max_steps', 100)
        )
        
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config")
async def update_config(config_update: ConfigUpdate):
    """
    更新系统配置（带备份恢复机制）
    
    备份策略：
    1. 更新前备份配置文件
    2. 验证配置完整性
    3. 保留备份文件（不立即删除）
    4. 返回 backup_path 供 validate_ai_service 使用
    
    备份删除/恢复逻辑：
    - 由 validate_ai_service 决定
    - 验证成功 → 删除备份 ✅
    - 验证失败 → 恢复备份 ❌
    
    设计原因：
    - 配置更新后立即验证服务可用性
    - 避免无效配置导致系统不可用
    - 保证配置可回滚
    
    完整流程：
    1. 用户切换模型 → updateConfig
    2. 后端备份 → 更新配置 → 返回成功
    3. 前端调用 → validateService
    4. 验证成功 → 删除备份
    5. 验证失败 → 恢复备份
    
    Args:
        config_update: 配置更新请求
        
    Returns:
        dict: 更新结果（包含 backup_path）
    
    作者：小欧
    时间：2026-03-01
    """
    backup_path = None  # ⭐ 初始化备份路径
    config_path = None  # ⭐ 初始化配置路径
    backup_restored = False  # ⭐ 标记备份是否已恢复，避免重复
    
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        
        # 1. 【新增】自动备份
        backup_path = _backup_config_file(config_path)
        logger.info(f"配置文件已备份：{backup_path}")
        
        # 2. 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            original_config_data = yaml.safe_load(f) or {}
        
        # 复制一份用于修改
        config_data = original_config_data.copy()
        
        # 3. 应用更新（保持原有逻辑）
        if config_update.ai_provider:
            # 验证提供商 - 检查是否在配置文件中（通用方式，不硬编码）
            ai_config = config_data.get('ai', {})
            if config_update.ai_provider not in ai_config:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商: {config_update.ai_provider}"
                )
            config_data['ai']['provider'] = config_update.ai_provider
            logger.info(f"[update_config] 写入 provider={config_update.ai_provider}")
            
            # 【修复】不再调用switch_provider，直接清空缓存让get_service重新加载
            # 统一由updateConfig处理provider和model的更新
            AIServiceFactory._instance = None
            AIServiceFactory._current_provider = config_update.ai_provider
            logger.info(f"切换AI提供商成功: {config_update.ai_provider}")
        
        # 【修正】更新AI模型 - 只更新顶层ai.model
        # 如果只传了ai_model没传ai_provider，使用当前配置的provider
        if config_update.ai_model:
            provider = config_update.ai_provider or config_data.get('ai', {}).get('provider', 'zhipuai')
            if provider in config_data['ai']:
                # 【修正】只更新顶层 ai.model
                config_data['ai']['model'] = config_update.ai_model
                logger.info(f"[update_config] 写入 model={config_update.ai_model} (provider={provider})")
                # 【修复】清空AIServiceFactory缓存，强制重新读取配置
                AIServiceFactory._instance = None
                AIServiceFactory._config = None
                logger.info(f"已清空AIServiceFactory缓存")
        
        # 更新API Key - 通用方式（不硬编码）
        if config_update.provider_api_keys:
            for provider_name, api_key in config_update.provider_api_keys.items():
                # ⭐ 用户要求：不验证 API Key 格式（2026-03-01）
                
                # 检查Provider是否存在
                if provider_name in config_data.get('ai', {}):
                    config_data['ai'][provider_name]['api_key'] = api_key.strip()
                    logger.info(f"更新Provider API Key成功: {provider_name}")
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"不支持的Provider: {provider_name}"
                    )
        
        # 确保app配置节存在
        if 'app' not in config_data:
            config_data['app'] = {}
        
        # 更新主题
        if config_update.theme:
            config_data['app']['theme'] = config_update.theme
        
        # 更新语言
        if config_update.language:
            config_data['app']['language'] = config_update.language
        
        # 更新 max_steps
        if config_update.max_steps is not None:
            if config_update.max_steps < 1:
                raise HTTPException(status_code=400, detail="max_steps 必须大于等于 1")
            if config_update.max_steps > 1000:
                raise HTTPException(status_code=400, detail="max_steps 不能超过 1000")
            config_data['app']['max_steps'] = config_update.max_steps
            logger.info(f"更新 max_steps 成功: {config_update.max_steps}")
        
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
        
        # 4. 【新增】自动修复常见问题
        config_data = _fix_config_common_issues(config_data)
        
        # 5. 【新增】验证配置完整性
        is_valid, errors, warnings = _validate_config_integrity(config_data)
        
        if not is_valid:
            # ⭐ 验证失败：恢复备份
            if not backup_restored and backup_path and backup_path.exists():
                logger.warning(f"配置验证失败，恢复备份：{backup_path}")
                shutil.copy2(str(backup_path), str(config_path))  # type: ignore
                backup_restored = True  # ⭐ 标记已恢复
            
            # 恢复后重新加载，获取回滚后的真正模型
            config = get_config_instance()
            config.reload()
            original_ai = original_config_data.get('ai', {})
            current_provider = original_ai.get('provider', 'unknown')
            current_model = original_ai.get('model', 'unknown')
            
            # 删除备份文件
            backup_path.unlink(missing_ok=True)
            return {
                "success": False,
                "message": "配置验证失败",
                "errors": errors,
                "warnings": warnings,
                "backup_path": str(backup_path),
                "current_provider": current_provider,
                "current_model": current_model
            }
        
        # 6. 【修复】确保 ai.provider 和 ai.model 在最前面
        config_data = _ensure_ai_provider_model_first(config_data)
        
        # 7. 写回配置文件
        logger.info(f"[update_config] 准备写入配置文件...")
        with open(config_path, 'w', encoding='utf-8') as f:
            write_yaml_with_order(str(config_path), config_data)
        logger.info(f"[update_config] 配置文件已写入")
        
        # 验证写入结果
        with open(config_path, 'r', encoding='utf-8') as f:
            verify_data = yaml.safe_load(f)
            logger.info(f"[update_config] 验证写入: provider={verify_data['ai'].get('provider')}, model={verify_data['ai'].get('model')}")
        
        # 7. 重新加载
        config = get_config_instance()
        config.reload()
        
        # ============================================================
        # 【小强修复 2026-04-07】
        # 修改说明：
        # 之前：验证成功后保留备份，等待 validate_ai_service 实际调用AI API后再删除
        # 现在：验证成功后立即删除备份（使用 _validate_config_integrity 结果）
        #
        # 原因：用户要求切换模型时不再调用外部AI API做验证，
        #       直接用配置文件完整性检查（_validate_config_integrity）的结果来决定
        #       1）前端是否打* 2）后端是否删除/恢复备份
        # ============================================================
        
        # 6. 【新增】验证成功，立即删除备份文件
        #    不再等待 validate_ai_service 调用AI API验证
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
                logger.info(f"验证成功，已删除备份文件：{backup_path}")
            except Exception as e:
                logger.warning(f"删除备份文件失败：{e}")
        
        # 清理全局备份路径（不再需要，供 validate_ai_service 使用）
        AIServiceFactory.clear_backup_paths()
        
        logger.info(f"配置更新成功：{config_update.dict(exclude_none=True)}")
        
        # ============================================================
        # 【旧逻辑 - 已注释】
        # 之前是保留备份文件，等待 validate_ai_service 处理：
        # 1. 设置全局备份路径，供 validate_ai_service 使用
        # AIServiceFactory.set_backup_paths(str(backup_path), str(config_path))
        # 2. 保留备份（不删除），等待 validate_ai_service 处理
        # logger.info(f"配置更新成功，备份文件保留：{backup_path}，等待服务验证")
        # ============================================================
        
        # 返回当前配置模型，供前端更新下拉框
        current_provider = config_data.get('ai', {}).get('provider', '')
        current_model = config_data.get('ai', {}).get('model', '')
        
        return {
            "success": True,
            "message": "配置更新成功，请验证服务可用性",
            "updated_fields": config_update.dict(exclude_none=True),
            "warnings": warnings,
            "backup_path": str(backup_path),
            "current_provider": current_provider,
            "current_model": current_model
        }
        
    except HTTPException:
        # ⭐ HTTP 异常：恢复备份
        if not backup_restored and backup_path is not None and config_path is not None and backup_path.exists():
            try:
                logger.warning(f"发生 HTTP 异常，恢复备份：{backup_path}")
                shutil.copy2(str(backup_path), str(config_path))  # type: ignore
                backup_restored = True  # ⭐ 标记已恢复
            except:
                pass
        # 清理备份文件
        if backup_path:
            backup_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        # ⭐ 其他异常：恢复备份
        if not backup_restored and backup_path is not None and config_path is not None and backup_path.exists():
            try:
                logger.error(f"更新配置失败，恢复备份：{backup_path}, 错误：{e}")
                shutil.copy2(str(backup_path), str(config_path))  # type: ignore
                backup_restored = True  # ⭐ 标记已恢复
            except:
                pass
        # 清理备份文件
        if backup_path:
            backup_path.unlink(missing_ok=True)
        # 【修复 P2-007】记录详细日志但返回通用错误信息
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
        
        # 【小沈-2026-03-27修复】直接在接口中验证，添加30秒超时
        import httpx
        is_valid = False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {request.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "test"}]
                    }
                )
                is_valid = response.status_code == 200
        except Exception as e:
            logger.warning(f"配置验证请求失败: {e}")
            
            if is_valid:
                logger.info(f"配置验证成功: provider={request.provider}, model={model_name}")
                return ConfigValidateResponse(
                    valid=True,
                    message=f"API Key验证成功，当前使用 {request.provider} ({model_name})",
                    model=model_name
                )
            else:
                logger.warning(f"配置验证失败: provider={request.provider}, model={model_name}")
                return ConfigValidateResponse(
                    valid=False,
                    message=f"API Key无效，请检查是否正确",
                    model=None
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
        config = get_config_instance()
        
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
        # 使用缓存，自动检测变更
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
        backup_path = _backup_config_file(config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        
        # 2. 更新配置
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
        
        models = config['ai'][provider_name].get('models', [])
        if data.model in models:
            raise HTTPException(status_code=400, detail=f"模型 {data.model} 已存在")
        
        # 添加模型
        models.append(data.model)
        config['ai'][provider_name]['models'] = models
        
        # 如果，设为新增的顶层没有ai.model模型
        if not config['ai'].get('model'):
            config['ai']['model'] = data.model
        
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
        backup_path = _backup_config_file(config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if data.name in config.get('ai', {}):
            raise HTTPException(status_code=400, detail=f"Provider {data.name} 已存在")
        
        # 2. 【修正】不写 provider 下的 model 字段
        config['ai'][data.name] = {
            'api_base': data.api_base,
            'api_key': data.api_key,
            'models': data.models if data.models else ([data.model] if data.model else []),
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
# 【何时启用】
#   当前阶段暂时不启用，因为：
#   1. 备份逻辑还在调试中
#   2. 需要确保正常流程备份文件都能正确删除
#   3. 调试完成后，再在后端启动时调用此函数
# 
# 【启用方式】
#   在 backend/app/main.py 的启动流程中，首次调用API前调用此函数：
#   
#   from app.api.v1.config import cleanup_all_backups
#   cleanup_all_backups(Path("D:/2bktest/MDview/OmniAgentAs-desk/config/config.yaml"))
# 
# ================================================================================
def cleanup_all_backups(config_path: Path) -> int:
    """
    清理所有遗留的配置文件备份文件（防御性函数）
    
    【使用场景】
    - 后端启动时调用
    - 清理上次异常退出时遗留的备份文件
    
    【清理策略】
    - 删除所有 config.yaml.backup.* 文件
    - 原因：当前配置文件已经是正确状态
#     - 成功时会删除最新备份，失败时会恢复备份
    
    【参数】
    - config_path: 配置文件路径
    
    【返回值】
    - 清理的备份文件数量
    """
    backup_files = list(config_path.parent.glob("config.yaml.backup.*"))
    count = 0
    for backup_file in backup_files:
        backup_file.unlink(missing_ok=True)
        logger.info(f"已清理遗留备份: {backup_file}")
        count += 1
    
    if count > 0:
        logger.info(f"启动时清理了 {count} 个遗留备份文件")
    
    return count


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
        import subprocess
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

