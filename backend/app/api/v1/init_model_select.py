"""
模型初始化和切换接口

用于前端顶部模型选择器，与配置页面接口分离
"""

from datetime import datetime
from typing import Optional, Tuple

import httpx
from httpx import Limits
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services import AIServiceFactory
from app.config import get_config as get_config_instance
from app.utils.logger import logger

router = APIRouter()


class ValidateResponse(BaseModel):
    """验证响应"""
    success: bool = Field(..., description="验证是否通过")
    provider: str = Field(..., description="当前使用的提供商")
    model: str = Field(default="", description="当前使用的模型")
    message: str = Field(default="", description="验证消息")
    status: str = Field(default="success", description="详细状态: success/failed/warning")


_STATUS_MAP = {
    401: ("failed", "API Key无效：{p} ({m}) 的API Key认证失败，请检查Key是否正确"),
    429: ("warning", "速率限制：{p} ({m}) API请求太频繁，请稍后重试"),
    402: ("warning", "信用不足：{p} ({m}) 账户余额或信用不够，请检查账户"),
    403: ("warning", "信用不足：{p} ({m}) 账户余额或信用不够，请检查账户"),
}


def _log_validation(provider: str, model: str, result: str, message: str,
                    start_time: datetime, end_time: datetime) -> None:
    """记录验证结果日志 - 小健 2026-05-25"""
    elapsed = (end_time - start_time).total_seconds()
    logger.info(f"[检查服务] 结束 - 时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"耗时: {elapsed:.2f}秒, 结果: {result}, 消息: {message}")


async def _http_validate_call(ai_service) -> Optional[int]:
    """执行HTTP验证调用，返回status_code或None - 小健 2026-05-25"""
    try:
        async with httpx.AsyncClient(timeout=30.0, limits=Limits(max_connections=5, max_keepalive_connections=2)) as client:
            response = await client.post(
                f"{ai_service.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {ai_service.api_key}", "Content-Type": "application/json"},
                json={"model": ai_service.model, "messages": [{"role": "user", "content": "test"}]},
            )
            return response.status_code
    except Exception as e:
        logger.warning(f"[检查服务] API验证失败: {e}")
        return None


async def _restore_and_reload(backup_path: Optional[str], config_path: Optional[str]) -> Tuple[str, str]:
    """恢复备份+重新加载配置，返回回滚后的(provider, model) - 小健 2026-05-25"""
    if backup_path and config_path:
        await _restore_backup_and_delete_by_path(backup_path, config_path)
    config = get_config_instance()
    config.reload()
    ai_config = config.get('ai', {})
    provider = ai_config.get('provider', 'unknown')
    model = ai_config.get('model', 'unknown')
    logger.info(f"[检查服务] 验证失败已回滚，当前配置: provider={provider}, model={model}")
    return provider, model


async def _delete_backup_by_path(backup_path: str):
    """删除指定备份文件 - 小欧 2026-03-01"""
    try:
        from pathlib import Path
        import time
        backup = Path(backup_path)
        if not backup.exists():
            logger.warning(f"备份文件不存在：{backup_path}")
            return
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        file_mtime = backup.stat().st_mtime
        if time.time() - file_mtime > 600:
            logger.warning(f"备份文件过期，跳过删除：{backup_path}")
            return
        backup.unlink()
        logger.info(f"验证成功，已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"删除备份失败：{e}")


async def _restore_backup_and_delete_by_path(backup_path: str, config_path: str):
    """恢复指定备份文件并删除备份 - 小欧 2026-03-01"""
    try:
        from pathlib import Path
        import shutil
        backup = Path(backup_path)
        config = Path(config_path)
        if not backup.exists():
            logger.warning(f"备份文件不存在，无法恢复：{backup_path}")
            return
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        shutil.copy2(str(backup), str(config))
        logger.info(f"验证失败，已恢复备份：{backup_path}")
        backup.unlink()
        logger.info(f"已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"恢复备份失败：{e}")


@router.get("/chat/validate", response_model=ValidateResponse)
async def validate_ai_service():
    """验证AI服务配置是否正确 - 小欧 2026-03-01, 重构 小健 2026-05-25"""
    start_time = datetime.now()
    logger.info(f"[检查服务] 开始验证 - 时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        ai_service = AIServiceFactory.get_service()
        provider = AIServiceFactory.get_current_provider()
        current_model = ai_service.model
        logger.info(f"[检查服务] 加载配置完成 - provider={provider}, model={current_model}")
        backup_path, config_path = AIServiceFactory.get_backup_paths()

        if not ai_service.api_key or ai_service.api_key.strip() == "":
            provider, current_model = await _restore_and_reload(backup_path, config_path)
            end_time = datetime.now()
            error_msg = f"API Key为空：{provider} ({current_model}) 的 API Key 未配置"
            _log_validation(provider, current_model, "失败(API Key为空)", error_msg, start_time, end_time)
            return ValidateResponse(success=False, status="failed", provider=provider,
                                    model=current_model, message=error_msg + "。请在 config/config.yaml 中配置。（配置已恢复到更新前的状态）")

        logger.info(f"[检查服务] 开始调用 API 验证...")
        status_code = await _http_validate_call(ai_service)

        if status_code == 200:
            if backup_path:
                await _delete_backup_by_path(backup_path)
            AIServiceFactory.clear_backup_paths()
            end_time = datetime.now()
            success_msg = f"AI 服务验证成功，当前使用 {provider} ({current_model})"
            _log_validation(provider, current_model, "成功", success_msg, start_time, end_time)
            return ValidateResponse(success=True, status="success", provider=provider,
                                    model=current_model, message=success_msg)

        if status_code and status_code in _STATUS_MAP:
            status_val, msg_tpl = _STATUS_MAP[status_code]
            msg = msg_tpl.format(p=provider, m=current_model)
            if status_val == "failed":
                provider, current_model = await _restore_and_reload(backup_path, config_path)
                msg = msg_tpl.format(p=provider, m=current_model)
            end_time = datetime.now()
            _log_validation(provider, current_model, f"{status_val}(HTTP {status_code})", msg, start_time, end_time)
            return ValidateResponse(success=(status_val != "failed"), status=status_val,
                                    provider=provider, model=current_model, message=msg)

        if status_code:
            end_time = datetime.now()
            msg = f"API提示：{provider} ({current_model}) 返回HTTP {status_code}"
            _log_validation(provider, current_model, f"警告(HTTP {status_code})", msg, start_time, end_time)
            return ValidateResponse(success=True, status="warning", provider=provider,
                                    model=current_model, message=msg + "，请留意")

        provider, current_model = await _restore_and_reload(backup_path, config_path)
        end_time = datetime.now()
        error_msg = f"连接失败：无法连接到 {provider} ({current_model}) API"
        _log_validation(provider, current_model, "失败(连接失败)", error_msg, start_time, end_time)
        return ValidateResponse(success=False, status="failed", provider=provider,
                                model=current_model, message=error_msg + "，请检查网络或API地址配置")

    except Exception as e:
        try:
            provider = AIServiceFactory.get_current_provider()
            current_model = AIServiceFactory.get_service().model
        except Exception:
            provider, current_model = "unknown", "unknown"
        end_time = datetime.now()
        _log_validation(provider, current_model, "失败(异常)", str(e), start_time, end_time)
        return ValidateResponse(success=False, status="failed", provider=provider,
                                model=current_model, message=f"验证过程出错: {str(e)}")


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
        
        # 验证新服务 - 【小沈-2026-03-27修复】直接在接口中验证，添加30秒超时
        import httpx
        is_valid = False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
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
                is_valid = response.status_code == 200
        except Exception as e:
            logger.warning(f"[切换提供商] API验证失败: {e}")
        
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
