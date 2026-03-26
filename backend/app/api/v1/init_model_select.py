"""
模型初始化和切换接口

用于前端顶部模型选择器，与配置页面接口分离
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services import AIServiceFactory
from app.utils.logger import logger

router = APIRouter()


class ValidateResponse(BaseModel):
    """验证响应"""
    success: bool = Field(..., description="验证是否通过")
    provider: str = Field(..., description="当前使用的提供商")
    model: str = Field(default="", description="当前使用的模型")
    message: str = Field(default="", description="验证消息")


# ============================================================
# 备份管理辅助函数 - 小欧新增
# ============================================================

async def _delete_backup_by_path(backup_path: str):
    """
    删除指定备份文件（验证成功后调用）
    
    ⭐ 修复：接收明确的 backup_path 参数，避免竞态条件
    
    调用时机：
    - validate_ai_service 验证成功后
    
    功能：
    1. 验证备份文件是否存在
    2. 验证备份文件命名格式
    3. 验证备份文件时间（10 分钟内）
    4. 删除备份文件
    
    设计原因：
    - 验证成功说明新配置可用
    - 删除备份避免文件累积
    - 显式传递路径避免误操作
    
    作者：小欧
    时间：2026-03-01
    """
    try:
        from pathlib import Path
        backup = Path(backup_path)
        
        # 验证备份文件是否存在
        if not backup.exists():
            logger.warning(f"备份文件不存在：{backup_path}")
            return
        
        # 验证备份文件命名格式
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        
        # 验证备份文件时间（必须是 10 分钟内的）
        import time
        file_mtime = backup.stat().st_mtime
        if time.time() - file_mtime > 600:  # 10 分钟
            logger.warning(f"备份文件过期，跳过删除：{backup_path}")
            return
        
        backup.unlink()
        logger.info(f"验证成功，已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"删除备份失败：{e}")


async def _restore_backup_and_delete_by_path(backup_path: str, config_path: str):
    """
    恢复指定备份文件并删除备份（验证失败后调用）
    
    ⭐ 修复：接收明确的 backup_path 和 config_path 参数
    
    调用时机：
    - validate_ai_service 验证失败后
    
    功能：
    1. 验证备份文件是否存在
    2. 验证备份文件命名格式
    3. 恢复备份到配置文件
    4. 删除备份文件
    
    设计原因：
    - 验证失败说明新配置不可用
    - 恢复到旧配置保证系统可用
    - 显式传递路径避免误操作
    
    作者：小欧
    时间：2026-03-01
    """
    try:
        from pathlib import Path
        backup = Path(backup_path)
        config = Path(config_path)
        
        # 验证备份文件是否存在
        if not backup.exists():
            logger.warning(f"备份文件不存在，无法恢复：{backup_path}")
            return
        
        # 验证备份文件命名格式
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        
        # 恢复备份
        import shutil
        shutil.copy2(str(backup), str(config))
        logger.info(f"验证失败，已恢复备份：{backup_path}")
        
        # 删除备份
        backup.unlink()
        logger.info(f"已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"恢复备份失败：{e}")


@router.get("/chat/validate", response_model=ValidateResponse)
async def validate_ai_service():
    """
    验证 AI 服务配置是否正确
    
    用于测试 API 密钥是否有效
    
    ⭐ 重要：验证成功后删除备份，验证失败时恢复备份
    ⭐ 修复：从全局状态获取 backup_path
    
    日志记录：
    - 开始时间、provider、model
    - 结束时间、结果、耗时
    """
    from datetime import datetime
    start_time = datetime.now()
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"[检查服务] 开始验证 - 时间: {start_str}")
    
    try:
        # 获取当前服务（同时会加载当前配置）
        ai_service = AIServiceFactory.get_service()
        
        # 获取当前提供商（从工厂的内部状态）
        provider = AIServiceFactory.get_current_provider()
        
        # 获取当前模型名称
        current_model = ai_service.model
        
        logger.info(f"[检查服务] 加载配置完成 - provider: {provider}, model: {current_model}")
        
        # ⭐ 从全局状态获取 backup_path（由 update_config 设置）
        backup_path, config_path = AIServiceFactory.get_backup_paths()
        
        # 检查 API Key 是否为空
        if not ai_service.api_key or ai_service.api_key.strip() == "":
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"AI 服务未配置：{provider} ({current_model}) 的 API Key 为空"
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(API Key为空), 消息: {error_msg}")
            
            return ValidateResponse(
                success=False,
                provider=provider,
                model=current_model,
                message=error_msg + "。请在 config/config.yaml 中配置。（配置已恢复到更新前的状态）"  # ⭐ 添加说明
            )
        
        # 验证服务
        logger.info(f"[检查服务] 开始调用 API 验证...")
        is_valid = await ai_service.validate()
        
        if is_valid:
            # ⭐ 验证成功：删除备份
            if backup_path:
                await _delete_backup_by_path(backup_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            success_msg = f"AI 服务验证成功，当前使用 {provider} ({current_model})"
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 成功, 消息: {success_msg}")
            
            return ValidateResponse(
                success=True,
                provider=provider,
                model=current_model,
                message=success_msg
            )
        else:
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(验证返回False), provider: {provider}, model: {current_model}")
            # 验证失败，尝试获取详细错误信息，并明确说明配置已恢复
            # 通过发送一个实际请求来获取错误详情
            import httpx
            test_response = None
            try:
                # 使用 ai_service 的 timeout 配置（从 config.yaml 读取）
                timeout = ai_service.timeout if hasattr(ai_service, 'timeout') else 30
                async with httpx.AsyncClient(timeout=timeout) as client:
                    test_response = await client.post(
                        f"{ai_service.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {ai_service.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": ai_service.model,
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    )
            except httpx.TimeoutException:
                # 超时也返回通用错误
                logger.warning(f"API validation timeout for {provider}")
            except httpx.RequestError as e:
                logger.warning(f"API validation request error: {e}")
            except Exception as e:
                logger.warning(f"API validation error: {e}")
            
            # 根据状态码返回不同的错误信息
            if test_response:
                if test_response.status_code == 401:
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"API Key无效：{provider} ({current_model}) 的API Key认证失败"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP 401), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请检查Key是否正确"
                    )
                elif test_response.status_code == 429:
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"速率限制：{provider} ({current_model}) API请求太频繁"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP 429), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请等待几分钟后重试"
                    )
                else:
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"API错误：{provider} ({current_model}) 返回HTTP {test_response.status_code}"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP {test_response.status_code}), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请检查配置"
                    )
            else:
                end_time = datetime.now()
                elapsed = (end_time - start_time).total_seconds()
                end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                error_msg = f"连接失败：无法连接到 {provider} ({current_model}) API"
                logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(连接失败), 消息: {error_msg}")
                
                return ValidateResponse(
                    success=False,
                    provider=provider,
                    model=current_model,
                    message=error_msg + "，请检查网络或API地址配置"
                )
            
    except Exception as e:
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(异常), 错误: {str(e)}")
        
        return ValidateResponse(
            success=False,
            provider="unknown",
            message=f"验证过程出错: {str(e)}"
        )


# 【隐藏】冗余接口，已被 /config PUT 替代，仅保留以防后续需要
@router.post("/chat/switch/{provider}", response_model=ValidateResponse, include_in_schema=False)
async def switch_ai_provider(provider: str):
    """
    切换AI提供商
    
    - **provider**: 提供商名称 (从配置中动态支持)
    
    用于切换AI提供商
    """
    try:
        # 验证提供商名称（从配置中动态验证）
        from app.config import get_config as get_config_instance
        
        config = get_config_instance()
        ai_config = config.get('ai', {})
        
        # 获取所有可用的provider（排除provider和model这两个配置项）
        available_providers = []
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict):
                available_providers.append(provider_name)
        
        if provider not in available_providers:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商: {provider}，支持的选项: {', '.join(available_providers)}"
            )
        
        # 切换提供商
        ai_service = AIServiceFactory.switch_provider(provider)
        
        # 获取新模型名称
        new_model = ai_service.model
        
        # 验证新服务
        is_valid = await ai_service.validate()
        
        if is_valid:
            return ValidateResponse(
                success=True,
                provider=provider,
                model=new_model,
                message=f"成功切换到 {provider} ({new_model})"
            )
        else:
            return ValidateResponse(
                success=False,
                provider=provider,
                model=new_model,
                message=f"已切换到 {provider} ({new_model})，但验证失败，请检查API密钥"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"切换提供商失败: {str(e)}"
        )
