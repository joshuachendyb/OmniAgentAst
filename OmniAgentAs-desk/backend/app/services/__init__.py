"""
AI服务工厂
根据配置创建对应的AI服务实例
"""

import yaml
import os
import threading
from typing import Optional
from .base import BaseAIService
from .zhipuai import ZhipuAIService
from .opencode import OpenCodeService

class AIServiceFactory:
    """AI服务工厂（线程安全版）"""
    
    _instance: Optional[BaseAIService] = None
    _current_provider: str = "zhipuai"  # 显式跟踪当前提供商
    _config: Optional[dict] = None  # 配置缓存（用于测试）
    _lock: threading.Lock = threading.Lock()  # 【修复】线程锁，确保线程安全
    
    @classmethod
    def get_config_path(cls, config_path: Optional[str] = None) -> str:
        """获取配置文件路径"""
        if config_path is not None:
            return config_path
        # 【修复】项目根目录是backend的父目录，需要多退一级
        # backend/app/services/__init__.py -> 退到项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(base_dir, "config", "config.yaml")
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> dict:
        """加载配置文件 - 优先使用缓存（用于测试），否则从文件读取"""
        # 如果已设置缓存配置（用于测试），直接返回
        if cls._config is not None:
            return cls._config
            
        actual_path = cls.get_config_path(config_path)
        
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                config = loaded_config if loaded_config is not None else {}
        except Exception as e:
            print(f"[AIServiceFactory] 警告: 无法加载配置文件 {actual_path}: {e}")
            # 返回默认配置
            config = {
                "ai": {
                    "provider": cls._current_provider,
                    "zhipuai": {
                        "model": "glm-4.7-flash",
                        "api_key": "",
                        "api_base": "https://open.bigmodel.cn/api/paas/v4",
                        "timeout": 30
                    },
                    "opencode": {
                        "model": "kimi-k2.5-free",
                        "api_key": "",
                        "api_base": "https://opencode.ai/zen/v1",
                        "timeout": 30
                    }
                }
            }
        
        return config
    
    @classmethod
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """
        获取AI服务实例（线程安全）
        
        Returns:
            BaseAIService: AI服务实例
        """
        # 【修复】第一次检查（无锁，快速路径）
        if cls._instance is not None:
            return cls._instance
        
        # 【修复】获取锁，确保线程安全
        with cls._lock:
            # 【修复】第二次检查（有锁，防止重复创建）
            if cls._instance is not None:
                return cls._instance
            
            # 强制重新加载配置（不使用缓存）
            config = cls.load_config(config_path)
            ai_config = config.get("ai", {})
            
            # 【修复】优先使用配置文件的提供商（支持热更新配置），其次使用显式跟踪的
            provider = ai_config.get("provider", "zhipuai")
            
            # 【修复】同步更新 _current_provider，确保 get_current_provider() 返回正确值
            cls._current_provider = provider
            
            print(f"[AIServiceFactory] 创建服务实例: provider={provider}")
            
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
                    api_base=opencode_config.get("api_base", "https://opencode.ai/zen/v1"),
                    timeout=opencode_config.get("timeout", 30)
                )
            else:
                raise ValueError(f"不支持的AI提供商: {provider}")
        
        return cls._instance
    
    @classmethod
    def switch_provider(cls, provider: str, config_path: Optional[str] = None):
        """
        切换AI提供商 - 线程安全版
        注意：此方法只更新状态和配置，不验证服务是否可用
        验证应该由调用方在切换后单独进行
        
        Args:
            provider: 提供商名称 (zhipuai | opencode)
        """
        print(f"[AIServiceFactory] 切换提供商: {provider}")
        
        # 验证提供商名称
        if provider not in ["zhipuai", "opencode"]:
            raise ValueError(f"不支持的AI提供商: {provider}")
        
        # 【修复】获取锁，确保线程安全
        with cls._lock:
            # 保存旧状态（用于可能的回滚）
            old_provider = cls._current_provider
            
            # 关闭当前实例
            if cls._instance is not None:
                import asyncio
                try:
                    asyncio.create_task(cls._instance.close())
                    print(f"[AIServiceFactory] 关闭旧实例")
                except Exception as e:
                    print(f"[AIServiceFactory] 关闭旧实例出错: {e}")
            
            # 清空实例缓存
            cls._instance = None
            
            # 更新显式跟踪的提供商
            cls._current_provider = provider
            
            # 更新配置文件（通过文本替换，保留格式）
            actual_path = cls.get_config_path(config_path)
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 使用正则或简单字符串替换更新provider字段
                import re
                # 匹配 provider: "xxx" 或 provider: xxx
                pattern = r'(provider:\s*["\']?)(\w+)(["\']?)'
                replacement = rf'\g<1>{provider}\g<3>'
                new_content = re.sub(pattern, replacement, content, count=1)
                
                with open(actual_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"[AIServiceFactory] 配置文件已更新: {actual_path}")
                
            except Exception as e:
                print(f"[AIServiceFactory] 警告: 无法更新配置文件: {e}")
        
        # 创建新实例（使用新配置）- get_service 内部也有锁
        try:
            new_service = cls.get_service(config_path)
            print(f"[AIServiceFactory] 新实例创建成功: {provider}")
            return new_service
        except Exception as e:
            # 如果创建失败，回滚到旧状态
            print(f"[AIServiceFactory] 创建新实例失败，回滚到旧提供商: {old_provider}")
            with cls._lock:
                cls._current_provider = old_provider
                cls._instance = None
            raise e
    
    @classmethod
    def get_current_provider(cls) -> str:
        """
        获取当前使用的AI提供商
        
        Returns:
            str: 提供商名称 (zhipuai | opencode | unknown)
        """
        # 优先返回显式跟踪的提供商
        if cls._current_provider:
            return cls._current_provider
        
        # 其次从配置文件读取
        try:
            config = cls.load_config()
            return config.get("ai", {}).get("provider", "unknown")
        except:
            return "unknown"
    
    @classmethod
    def reset(cls):
        """重置工厂状态（用于测试）"""
        cls._instance = None
        cls._current_provider = "zhipuai"
        print("[AIServiceFactory] 工厂状态已重置")
