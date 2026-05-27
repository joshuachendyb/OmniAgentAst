"""
AI服务工厂
根据配置创建通用AI服务实例 - 支持无限provider

配置验证：
1. 配置文件是否存在
2. provider 配置是否存在
3. 必要字段是否存在（api_key, model, api_base）
4. 验证结果上报前端显示

================================================================================
【重要！统一Fallback逻辑 - 所有代码编写人员必须遵守！】

逻辑规则：
1. 只有当 ai.provider 存在 且 ai.model 存在 且 ai.model 在 ai.provider 的 models 列表中
    时，才使用 ai.provider + ai.model
2. 否则（任何一个条件不满足：ai.provider不存在/ai.model不存在/ai.model不在列表中）
    统一fallback到：模型列表的第一个 模型provider+model
3. 禁止有"当前provider"的概念和理解，容易引起逻辑错误
4. 所有相关代码必须按照此逻辑实现，不能再次犯错误！
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
import asyncio
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

from app.utils.logger import setup_logger
from .llm_core import BaseAIService

# 创建logger
logger = setup_logger("OmniAgentAst.AIServiceFactory")


# 支持的provider列表（动态从配置文件读取，不硬编码）
# 不再硬编码provider列表，配置文件里有什么就支持什么


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    success: bool
    provider: str
    model: str
    message: str
    errors: list  # 错误列表，用于前端显示
    warnings: list  # 警告列表


class AIServiceFactory:
    """AI 服务工厂 - 一个通用类支持所有 OpenAI 兼容 API"""
    
    _instance: Optional[BaseAIService] = None
    _current_provider: str = ""
    _config: Optional[dict] = None
    _lock: threading.Lock = threading.Lock()
    
    # ⭐ 备份管理全局状态（带锁保护）
    _backup_path: Optional[str] = None
    _config_path: Optional[str] = None
    _backup_lock: threading.Lock = threading.Lock()  # ⭐ 新增：锁保护
    
    @classmethod
    def get_config_path(cls, config_path: Optional[str] = None) -> str:
        """获取配置文件路径"""
        if config_path is not None:
            return config_path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(base_dir, "config", "config.yaml")
    
    @staticmethod
    def _make_validation_error(message: str, field: str = "",
                               provider: str = "", model: str = "",
                               errors: Optional[list] = None,
                               warnings: Optional[list] = None) -> "ConfigValidationResult":
        """构造验证错误结果，消除9次ConfigValidationResult样板 - 小健 2026-05-25"""
        return ConfigValidationResult(
            success=False, provider=provider, model=model, message=message,
            errors=errors or ([{"field": field, "message": message}] if field else []),
            warnings=warnings or [])

    @staticmethod
    def _validate_credentials(ai_config: dict, final_provider: str) -> Tuple[list, list]:
        """验证凭据(api_key/api_base)，返回(errors, warnings) - 小健 2026-05-25"""
        errors = []
        warnings = []
        selected_provider_config = ai_config.get(final_provider, {})
        api_key = selected_provider_config.get("api_key")
        if not api_key:
            errors.append(f"provider '{final_provider}' 缺少 api_key 配置")
        elif not isinstance(api_key, str) or api_key.strip() == "":
            errors.append(f"provider '{final_provider}' 的 api_key 为空")
        api_base = selected_provider_config.get("api_base")
        if not api_base:
            warnings.append(f"provider '{final_provider}' 未配置 api_base，将使用默认值")
        return errors, warnings

    @classmethod
    def validate_config(cls, config_path: Optional[str] = None) -> ConfigValidationResult:
        """完整配置验证 - 小健 2026-05-25 重构为数据驱动步骤"""
        errors: list = []
        warnings: list = []
        provider = "unknown"
        model = ""

        actual_path = cls.get_config_path(config_path)
        if not os.path.exists(actual_path):
            return cls._make_validation_error("配置文件不存在", errors=[f"配置文件不存在: {actual_path}"])

        # 使用统一的AIConfigResolver进行验证
        from app.services.ai_config_resolver import get_ai_config_resolver
        resolver = get_ai_config_resolver()
        is_valid, final_provider, final_model, error_messages = resolver.validate_config()
        
        if not is_valid:
            return cls._make_validation_error(
                f"配置验证失败: {len(error_messages)} 个错误",
                provider=final_provider or "unknown",
                model=final_model or "",
                errors=error_messages,
                warnings=[]
            )

        cred_errors, cred_warnings = cls._validate_credentials(resolver.get_ai_config(), final_provider)
        errors.extend(cred_errors)
        warnings.extend(cred_warnings)

        if errors:
            return cls._make_validation_error(f"配置验证失败: {len(errors)} 个错误",
                                               provider=final_provider, model=final_model,
                                               errors=errors, warnings=warnings)

        message = f"配置验证通过: provider={final_provider}, model={final_model}"
        if warnings:
            message += f" ({len(warnings)} 个警告)"
        return ConfigValidationResult(success=True, provider=final_provider, model=final_model,
                                       message=message, errors=errors, warnings=warnings)
    
    @classmethod
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """获取AI服务实例 - 带缓存，仅配置变化时重建"""
        from app.services.ai_config_resolver import get_ai_config_resolver
        
        resolver = get_ai_config_resolver()
        final_provider, final_model = resolver.resolve_provider_model()
        ai_config = resolver.get_ai_config()
        
        # 验证配置的有效性
        if not final_provider:
            raise ValueError("未找到有效的AI provider配置")
        if not final_model:
            raise ValueError("未找到有效的AI model配置")
        
        # ⭐ 缓存检查：如果 provider/model 没变且实例存在，复用
        if cls._instance is not None and cls._current_provider == final_provider and cls._instance.model == final_model:
            return cls._instance
        
        cls._current_provider = final_provider
        
        from datetime import datetime
        log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
        logger.info(log_msg)
        
        provider_config = ai_config.get(final_provider, {})
        if not provider_config:
            raise ValueError(f"provider {final_provider} 的配置为空，请检查 config.yaml")
        
        cls._instance = BaseAIService(
            api_key=(provider_config.get("api_key") or "").strip(),
            model=final_model,
            api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
            provider=final_provider,
            timeout=provider_config.get("timeout", 30),
            # 【改进8 2026-05-01 小沈 小健】LLM调用参数
            max_tokens=provider_config.get("max_tokens", 4096),
            temperature=float(provider_config.get("temperature", 0.7)),
            seed=provider_config.get("seed", None),
        )

        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置工厂状态"""
        with cls._lock:
            cls._instance = None
            cls._current_provider = ""
            print("[AIServiceFactory] 工厂状态已重置")
    
    @classmethod
    def get_service_for_model(cls, provider: str, model: str, config_path: Optional[str] = None):
        """
        根据指定的 provider 和 model 获取服务实例
        
        使用统一Fallback逻辑验证 provider 和 model 是否有效，
        如果有效则使用指定值，否则使用 fallback 值。
        
        Args:
            provider: 提供商名称
            model: 模型名称
            config_path: 配置文件路径（可选）
            
        Returns:
            BaseAIService: AI服务实例
        """
        with cls._lock:
            from app.services.ai_config_resolver import get_ai_config_resolver
            resolver = get_ai_config_resolver()
            ai_config = resolver.get_ai_config()
            
            # 验证前端指定的 provider 和 model 是否有效
            try:
                provider_config = resolver.get_service_config(provider, model)
            except ValueError as e:
                raise ValueError(str(e))
            
            final_provider = provider
            final_model = model
            
            # 关闭旧实例
            if cls._instance is not None:
                try:
                    asyncio.create_task(cls._instance.close())
                except Exception as e:
                    print(f"[AIServiceFactory] 关闭旧实例出错: {e}")
            
            cls._instance = None
            cls._current_provider = final_provider
            
            from datetime import datetime
            log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
            logger.info(log_msg)
            
            if not provider_config:
                log_msg = f"[AIServiceFactory] 错误: 未找到任何有效的provider配置"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
                logger.error(log_msg)
                provider_config = {}
            
            cls._instance = BaseAIService(
                api_key=(provider_config.get("api_key") or "").strip(),  # trim 空格
                model=final_model,
                api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
                provider=final_provider,
                timeout=provider_config.get("timeout", 30),
                # 【改进8 2026-05-01 小沈 小健】LLM调用参数
                max_tokens=provider_config.get("max_tokens", 4096),
                temperature=float(provider_config.get("temperature", 0.7)),
                seed=provider_config.get("seed", None),
            )
            
            return cls._instance
    
    # ⭐ 新增：备份管理全局状态访问方法（带锁保护）
    @classmethod
    def set_backup_paths(cls, backup_path: str, config_path: str):
        """设置备份文件路径（由 update_config 调用）⭐ 带锁保护"""
        with cls._backup_lock:
            cls._backup_path = backup_path
            cls._config_path = config_path
    
    @classmethod
    def get_backup_paths(cls):
        """获取备份文件路径（由 validate_ai_service 调用）⭐ 带锁保护"""
        with cls._backup_lock:
            return cls._backup_path, cls._config_path
    
    @classmethod
    def clear_backup_paths(cls):
        """清除备份文件路径（验证完成后调用）⭐ 带锁保护"""
        with cls._backup_lock:
            cls._backup_path = None
            cls._config_path = None
