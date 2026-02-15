"""
AI服务工厂
根据配置创建对应的AI服务实例
"""

import yaml
import os
from typing import Optional
from .base import BaseAIService
from .zhipuai import ZhipuAIService
from .opencode import OpenCodeService

class AIServiceFactory:
    """AI服务工厂"""
    
    _instance: Optional[BaseAIService] = None
    _config: Optional[dict] = None
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> dict:
        """加载配置文件"""
        if cls._config is not None:
            return cls._config
        
        actual_path = config_path
        if actual_path is None:
            # 默认配置文件路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            actual_path = os.path.join(base_dir, "config", "config.yaml")
        
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                cls._config = loaded_config if loaded_config is not None else {}
            return cls._config
        except Exception as e:
            print(f"警告: 无法加载配置文件 {config_path}: {e}")
            # 返回默认配置
            return {
                "ai": {
                    "provider": "zhipuai",
                    "zhipuai": {
                        "model": "glm-4.7-flash",
                        "api_key": "",
                        "api_base": "https://open.bigmodel.cn/api/paas/v4",
                        "timeout": 30
                    }
                }
            }
    
    @classmethod
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """
        获取AI服务实例
        
        Returns:
            BaseAIService: AI服务实例
        """
        if cls._instance is not None:
            return cls._instance
        
        config = cls.load_config(config_path)
        ai_config = config.get("ai", {})
        provider = ai_config.get("provider", "zhipuai")
        
        if provider == "zhipuai":
            zhipu_config = ai_config.get("zhipuai", {})
            cls._instance = ZhipuAIService(
                api_key=zhipu_config.get("api_key", ""),
                model=zhipu_config.get("model", "glm-4.7-flash"),
                api_base=zhipu_config.get("api_base", "https://open.bigmodel.cn/api/paas/v4"),
                timeout=zhipu_config.get("timeout", 30)
            )
        elif provider == "opencode":
            opencode_config = ai_config.get("opencode", {})
            cls._instance = OpenCodeService(
                api_key=opencode_config.get("api_key", ""),
                model=opencode_config.get("model", "kimi-k2.5-free"),
                api_base=opencode_config.get("api_base", "https://api.opencode.ai/v1"),
                timeout=opencode_config.get("timeout", 30)
            )
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")
        
        return cls._instance
    
    @classmethod
    def switch_provider(cls, provider: str, config_path: Optional[str] = None):
        """
        切换AI提供商
        
        Args:
            provider: 提供商名称 (zhipuai | opencode)
        """
        # 关闭当前实例
        if cls._instance is not None:
            import asyncio
            try:
                asyncio.create_task(cls._instance.close())
            except:
                pass
        
        cls._instance = None
        
        # 更新配置
        config = cls.load_config(config_path)
        config["ai"]["provider"] = provider
        cls._config = config
        
        # 创建新实例
        return cls.get_service(config_path)
