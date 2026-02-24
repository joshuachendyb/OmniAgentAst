"""
AI服务工厂
根据配置创建通用AI服务实例 - 支持无限provider

配置验证：
1. 配置文件是否存在
2. provider 配置是否存在
3. 必要字段是否存在（api_key, model, api_base）
4. 验证结果上报前端显示
"""

import os
import re
import asyncio
import threading
from dataclasses import dataclass
from typing import Optional

import yaml

from .base import BaseAIService


# 支持的provider列表（用于配置验证和提示）
SUPPORTED_PROVIDERS = [
    "zhipuai",      # 智谱GLM
    "opencode",     # OpenCode
    "deepseek",     # DeepSeek
    "moonshot",     # 月之暗面
    "qwen",         # 通义千问
    "baidu",        # 百度文心
    "ali",          # 阿里
    # 无限扩展... 配置即插即用
]


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
    """AI服务工厂 - 一个通用类支持所有OpenAI兼容API"""
    
    _instance: Optional[BaseAIService] = None
    _current_provider: str = "zhipuai"
    _config: Optional[dict] = None
    _lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get_config_path(cls, config_path: Optional[str] = None) -> str:
        """获取配置文件路径"""
        if config_path is not None:
            return config_path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(base_dir, "config", "config.yaml")
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> dict:
        """加载配置文件"""
        if cls._config is not None:
            return cls._config
            
        actual_path = cls.get_config_path(config_path)
        
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                config = loaded_config if loaded_config is not None else {}
        except Exception as e:
            print(f"[AIServiceFactory] 警告: 无法加载配置文件 {actual_path}: {e}")
            config = {
                "ai": {
                    "provider": cls._current_provider,
                    "zhipuai": {
                        "model": "glm-4-flash",
                        "api_key": "",
                        "api_base": "https://open.bigmodel.cn/api/paas/v4",
                        "timeout": 30
                    }
                }
            }
        
        return config
    
    @classmethod
    def validate_config(cls, config_path: Optional[str] = None) -> ConfigValidationResult:
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
            ConfigValidationResult: 包含成功状态、错误列表、警告列表
        """
        errors = []
        warnings = []
        provider = "unknown"
        model = ""
        
        # 1. 检查配置文件是否存在
        actual_path = cls.get_config_path(config_path)
        if not os.path.exists(actual_path):
            errors.append(f"配置文件不存在: {actual_path}")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="配置文件不存在",
                errors=errors,
                warnings=warnings
            )
        
        # 2. 加载配置
        try:
            config = cls.load_config(config_path)
        except Exception as e:
            errors.append(f"配置文件加载失败: {str(e)}")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="配置文件加载失败",
                errors=errors,
                warnings=warnings
            )
        
        # 3. 检查 ai 配置块
        ai_config = config.get("ai")
        if not ai_config:
            errors.append("配置文件缺少 'ai' 配置块")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="缺少 ai 配置块",
                errors=errors,
                warnings=warnings
            )
        
        if not isinstance(ai_config, dict):
            errors.append("'ai' 配置块格式错误，应为字典类型")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="ai 配置块格式错误",
                errors=errors,
                warnings=warnings
            )
        
        # 4. 检查 provider 字段
        provider = ai_config.get("provider")
        if not provider:
            errors.append("未指定 provider，请在 ai.provider 中配置")
            return ConfigValidationResult(
                success=False,
                provider="unknown",
                model=model,
                message="未指定 provider",
                errors=errors,
                warnings=warnings
            )
        
        # 5. 检查 provider 是否在支持列表中
        if provider not in SUPPORTED_PROVIDERS:
            warnings.append(f"provider '{provider}' 不在已知列表中，但仍会尝试使用")
        
        # 6. 检查 provider 配置是否存在
        provider_config = ai_config.get(provider)
        if not provider_config:
            errors.append(f"provider '{provider}' 的配置不存在，请在 ai.{provider} 中配置")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message=f"provider '{provider}' 配置不存在",
                errors=errors,
                warnings=warnings
            )
        
        if not isinstance(provider_config, dict):
            errors.append(f"provider '{provider}' 配置格式错误，应为字典类型")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message=f"provider '{provider}' 配置格式错误",
                errors=errors,
                warnings=warnings
            )
        
        # 7. 检查必要字段
        # api_key
        api_key = provider_config.get("api_key")
        if not api_key:
            errors.append(f"provider '{provider}' 缺少 api_key 配置")
        elif not isinstance(api_key, str) or api_key.strip() == "":
            errors.append(f"provider '{provider}' 的 api_key 为空")
        
        # model
        model = provider_config.get("model", "")
        if not model:
            errors.append(f"provider '{provider}' 缺少 model 配置")
        elif not isinstance(model, str) or model.strip() == "":
            errors.append(f"provider '{provider}' 的 model 为空")
        
        # api_base
        api_base = provider_config.get("api_base")
        if not api_base:
            warnings.append(f"provider '{provider}' 未配置 api_base，将使用默认值")
        
        # 8. 构建结果
        if errors:
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message=f"配置验证失败: {len(errors)} 个错误",
                errors=errors,
                warnings=warnings
            )
        
        message = f"配置验证通过: provider={provider}, model={model}"
        if warnings:
            message += f" ({len(warnings)} 个警告)"
        
        return ConfigValidationResult(
            success=True,
            provider=provider,
            model=model,
            message=message,
            errors=errors,
            warnings=warnings
        )
    
    @classmethod
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """获取AI服务实例 - 带完整配置验证"""
        cls._instance = None
        
        # 先进行配置验证
        validation = cls.validate_config(config_path)
        
        if not validation.success:
            print(f"[AIServiceFactory] 配置验证失败:")
            for error in validation.errors:
                print(f"  ❌ {error}")
            for warning in validation.warnings:
                print(f"  ⚠️ {warning}")
            # 仍然创建实例，但会记录错误
            cls._current_provider = validation.provider
        else:
            print(f"[AIServiceFactory] {validation.message}")
            for warning in validation.warnings:
                print(f"  ⚠️ {warning}")
        
        with cls._lock:
            config = cls.load_config(config_path)
            ai_config = config.get("ai", {})
            
            # 【修改】同时读取 provider 和 model
            provider = ai_config.get("provider", "zhipuai")
            model = ai_config.get("model", "")  # 新增：读取顶层ai.model
            
            cls._current_provider = provider
            
            print(f"[AIServiceFactory] 创建服务实例: provider={provider}, model={model}")
            
            provider_config = ai_config.get(provider, {})
            
            # 只有当provider配置完全不存在时才fallback
            if not provider_config:
                for key, val in ai_config.items():
                    if key != "provider" and isinstance(val, dict) and val.get("api_key"):
                        print(f"[AIServiceFactory] 警告: provider={provider} 配置不存在，使用 {key}")
                        provider = key
                        provider_config = val
                        break
            
            if not provider_config:
                print(f"[AIServiceFactory] 错误: 未找到任何有效的provider配置")
                provider_config = {}
            
            # 【修改】使用顶层ai.model，如果为空则用provider下的默认model
            final_model = model if model else provider_config.get("model", "")
            
            cls._instance = BaseAIService(
                api_key=provider_config.get("api_key", ""),
                model=final_model,
                api_base=provider_config.get("api_base", "https://api.openai.com/v1"),
                provider=provider,  # 新增：传递provider
                timeout=provider_config.get("timeout", 30)
            )
        
        return cls._instance
    
    @classmethod
    def switch_provider(cls, provider: str, config_path: Optional[str] = None):
        """切换AI提供商"""
        print(f"[AIServiceFactory] 切换提供商: {provider}")
        
        if provider not in SUPPORTED_PROVIDERS:
            print(f"[AIServiceFactory] 警告: 未知的provider={provider}，但仍会尝试创建")
        
        with cls._lock:
            old_provider = cls._current_provider
            
            if cls._instance is not None:
                try:
                    asyncio.create_task(cls._instance.close())
                except Exception as e:
                    print(f"[AIServiceFactory] 关闭旧实例出错: {e}")
            
            cls._instance = None
            cls._current_provider = provider
            
            actual_path = cls.get_config_path(config_path)
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pattern = r'(ai:\s*\n[^#]*provider:\s*["\']?)(\w+)(["\']?)'
                match = re.search(pattern, content)
                if match:
                    new_content = content[:match.start(2)] + provider + content[match.end(2):]
                else:
                    new_content = re.sub(r'(provider:\s*["\']?)(\w+)(["\']?)', rf'\g<1>{provider}\g<3>', content, count=1)
                
                with open(actual_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
            except Exception as e:
                print(f"[AIServiceFactory] 警告: 无法更新配置文件: {e}")
        
        try:
            new_service = cls.get_service(config_path)
            print(f"[AIServiceFactory] 新实例创建成功: {provider}")
            return new_service
        except Exception as e:
            print(f"[AIServiceFactory] 创建新实例失败，回滚到旧提供商: {old_provider}")
            with cls._lock:
                cls._current_provider = old_provider
                cls._instance = None
            raise e
    
    @classmethod
    def get_current_provider(cls) -> str:
        """获取当前使用的AI提供商"""
        if cls._current_provider:
            return cls._current_provider
        
        try:
            config = cls.load_config()
            return config.get("ai", {}).get("provider", "unknown")
        except:
            return "unknown"
    
    @classmethod
    def reset(cls):
        """重置工厂状态"""
        cls._instance = None
        cls._current_provider = "zhipuai"
        print("[AIServiceFactory] 工厂状态已重置")
