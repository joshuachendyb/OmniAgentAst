"""
AI配置解析器 - 统一Fallback逻辑入口

责任：统一所有AI配置相关的fallback逻辑，消除7份分散实现
设计原则：单一职责、单一入口、集中管理
"""

from typing import Dict, Any, Tuple, Optional
from app.config import Config, get_config


class AIConfigResolver:
    """单一职责：AI配置解析+Fallback，统一7份分散实现"""
    
    def __init__(self, config: Optional[Config] = None):
        """初始化配置解析器
        
        Args:
            config: 配置实例，如果为None则使用全局配置
        """
        self._config = config or get_config()
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置块 — 使用config.get()统一入口
        
        Returns:
            AI配置字典
        """
        return self._config.get("ai", {})
    
    def resolve_provider_model(self) -> Tuple[str, str]:
        """解析当前生效的provider和model，含完整fallback链
        
        核心逻辑：
        1. 获取配置的provider和model
        2. 验证配置是否有效
        3. 如果无效则使用fallback逻辑
        
        Returns:
            (provider, model) 元组
        """
        ai_config = self.get_ai_config()
        
        # 1. 获取配置的provider和model
        selected_provider = ai_config.get("provider", "")
        selected_model = ai_config.get("model", "")
        
        # 2. 验证配置是否有效
        if self._is_valid_provider_model(selected_provider, selected_model, ai_config):
            return selected_provider, selected_model
        
        # 3. 如果无效则使用fallback逻辑
        return self._fallback_provider_model(ai_config)
    
    def _is_valid_provider_model(self, provider: str, model: str, ai_config: Dict[str, Any]) -> bool:
        """验证provider和model是否有效
        
        Args:
            provider: 提供商名称
            model: 模型名称
            ai_config: AI配置字典
            
        Returns:
            是否有效
        """
        if not provider or not model:
            return False
        
        if provider not in ai_config:
            return False
        
        provider_config = ai_config[provider]
        if not isinstance(provider_config, dict):
            return False
        
        models = provider_config.get("models", [])
        if not isinstance(models, list):
            return False
        
        return model in models
    
    def _fallback_provider_model(self, ai_config: Dict[str, Any]) -> Tuple[str, str]:
        """Fallback逻辑：查找第一个有效的provider和model
        
        Args:
            ai_config: AI配置字典
            
        Returns:
            (fallback_provider, fallback_model) 元组
        """
        fallback_provider = ""
        fallback_model = ""
        
        for provider_name in ai_config.keys():
            # 跳过特殊字段
            if provider_name in ("provider", "model"):
                continue
            
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and "models" in provider_data:
                models = provider_data["models"]
                if models and isinstance(models, list) and len(models) > 0:
                    fallback_provider = provider_name
                    fallback_model = models[0]
                    break
        
        return fallback_provider, fallback_model
    
    def validate_config(self) -> Tuple[bool, str, str, list]:
        """验证AI配置并返回结果
        
        Returns:
            (is_valid, provider, model, error_messages) 元组
        """
        ai_config = self.get_ai_config()
        errors = []
        
        # 检查AI配置块是否存在
        if not ai_config:
            errors.append("配置文件缺少 'ai' 配置块")
            return False, "", "", errors
        
        # 检查AI配置块是否为字典
        if not isinstance(ai_config, dict):
            errors.append("'ai' 配置块格式错误，应为字典类型")
            return False, "", "", errors
        
        # 获取有效配置
        provider, model = self.resolve_provider_model()
        
        # 检查是否找到了有效配置
        if not provider:
            errors.append("未找到有效的AI provider配置")
        if not model:
            errors.append("未找到有效的AI model配置")
        
        return len(errors) == 0, provider, model, errors
    
    def get_service_config(self, provider: str, model: str) -> Dict[str, Any]:
        """获取指定provider和model的服务配置
        
        Args:
            provider: 提供商名称
            model: 模型名称
            
        Returns:
            服务配置字典
            
        Raises:
            ValueError: 如果provider或model无效
        """
        ai_config = self.get_ai_config()
        
        if not provider:
            raise ValueError("provider 不能为空")
        if not model:
            raise ValueError("model 不能为空")
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
        
        provider_config = ai_config[provider]
        if not isinstance(provider_config, dict):
            raise ValueError(f"provider {provider} 配置格式错误，应该是字典类型")
        
        if "models" not in provider_config:
            raise ValueError(f"provider {provider} 缺少 models 配置")
        
        models = provider_config["models"]
        if model not in models:
            raise ValueError(f"model {model} 不在 provider {provider} 的 models 列表中")
        
        return provider_config


# 单例实例
_global_resolver: Optional[AIConfigResolver] = None


def get_ai_config_resolver() -> AIConfigResolver:
    """获取全局AI配置解析器单例
    
    Returns:
        AIConfigResolver实例
    """
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = AIConfigResolver()
    return _global_resolver


def resolve_provider_model() -> Tuple[str, str]:
    """便捷函数：解析当前生效的provider和model
    
    Returns:
        (provider, model) 元组
    """
    return get_ai_config_resolver().resolve_provider_model()