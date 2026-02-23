"""
AI服务工厂
根据配置创建通用AI服务实例 - 支持无限provider
"""

import yaml
import os
import threading
from typing import Optional
from .base import BaseAIService


# 支持的provider列表（用于配置验证）
SUPPORTED_PROVIDERS = [
    "zhipuai",      # 智谱GLM
    "opencode",     # OpenCode
    "deepseek",     # DeepSeek
    "moonshot",     # 月之暗面
    "qwen",         # 通义千问
    "baidu",        # 百度文心
    "ali",          # 阿里
    # 无限扩展...
]


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
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """
        获取AI服务实例 - 通用实现，所有provider使用同一个类
        """
        cls._instance = None
        
        with cls._lock:
            config = cls.load_config(config_path)
            ai_config = config.get("ai", {})
            
            # 获取当前provider
            provider = ai_config.get("provider", "zhipuai")
            cls._current_provider = provider
            
            print(f"[AIServiceFactory] 创建服务实例: provider={provider}")
            
            # 获取对应配置（provider名称作为配置key）
            provider_config = ai_config.get(provider, {})
            
            # 如果没有配置，尝试使用第一个可用的
            if not provider_config.get("api_key"):
                # 查找第一个有api_key的配置
                for key, val in ai_config.items():
                    if key != "provider" and isinstance(val, dict) and val.get("api_key"):
                        provider = key
                        provider_config = val
                        break
            
            # 创建通用服务实例
            cls._instance = BaseAIService(
                api_key=provider_config.get("api_key", ""),
                model=provider_config.get("model", "gpt-3.5-turbo"),
                api_base=provider_config.get("api_base", "https://api.openai.com/v1"),
                timeout=provider_config.get("timeout", 30)
            )
        
        return cls._instance
    
    @classmethod
    def switch_provider(cls, provider: str, config_path: Optional[str] = None):
        """切换AI提供商"""
        print(f"[AIServiceFactory] 切换提供商: {provider}")
        
        # 验证provider（只检查是否在已知列表，不限制）
        if provider not in SUPPORTED_PROVIDERS:
            print(f"[AIServiceFactory] 警告: 未知的provider={provider}，但仍会尝试创建")
        
        with cls._lock:
            old_provider = cls._current_provider
            
            # 关闭当前实例
            if cls._instance is not None:
                import asyncio
                try:
                    asyncio.create_task(cls._instance.close())
                except Exception as e:
                    print(f"[AIServiceFactory] 关闭旧实例出错: {e}")
            
            cls._instance = None
            cls._current_provider = provider
            
            # 更新配置文件
            actual_path = cls.get_config_path(config_path)
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                import re
                pattern = r'(provider:\s*["\']?)(\w+)(["\']?)'
                replacement = rf'\g<1>{provider}\g<3>'
                new_content = re.sub(pattern, replacement, content, count=1)
                
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
