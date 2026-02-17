"""
配置管理模块
统一管理应用配置，支持从YAML文件和环境变量加载
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    """配置管理类"""
    
    _instance: Optional['Config'] = None
    _config_data: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置文件"""
        # 默认配置
        self._config_data = self._get_default_config()
        
        # 尝试从文件加载
        config_path = self._get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        # 合并配置（文件配置覆盖默认配置）
                        self._merge_config(self._config_data, file_config)
            except Exception as e:
                print(f"[Config] 警告: 加载配置文件失败: {e}，使用默认配置")
        
        # 环境变量覆盖
        self._apply_env_overrides()
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        # 优先使用环境变量指定的路径
        env_path = os.getenv('OMNIAGENT_CONFIG_PATH')
        if env_path:
            return Path(env_path)
        
        # 【修复】项目根目录是backend的父目录，需要再退一级
        # backend/app/config.py -> .parent=app -> .parent=backend -> .parent.parent=项目根目录
        base_dir = Path(__file__).parent.parent.parent.parent
        return base_dir / "config" / "config.yaml"
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "ai": {
                "provider": "zhipuai",
                "zhipuai": {
                    "model": "glm-4.7-flash",
                    "api_key": "",
                    "api_base": "https://open.bigmodel.cn/api/paas/v4",
                    "timeout": 60
                },
                "opencode": {
                    "model": "kimi-k2.5-free",
                    "api_key": "",
                    "api_base": "https://opencode.ai/zen/v1",
                    "timeout": 60
                }
            },
            "file_operations": {
                "workspace_dir": "./workspace",
                "safe_mode": True,
                "max_file_size": 10
            },
            "logging": {
                "level": "INFO",
                "file": "logs/app.log",
                "max_size": "10MB",
                "backup_count": 5
            }
        }
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # AI配置
        if os.getenv('ZHIPUAI_API_KEY'):
            self._config_data['ai']['zhipuai']['api_key'] = os.getenv('ZHIPUAI_API_KEY')
        
        if os.getenv('OPENCODE_API_KEY'):
            self._config_data['ai']['opencode']['api_key'] = os.getenv('OPENCODE_API_KEY')
        
        if os.getenv('AI_PROVIDER'):
            self._config_data['ai']['provider'] = os.getenv('AI_PROVIDER')
        
        # 日志级别
        if os.getenv('LOG_LEVEL'):
            self._config_data['logging']['level'] = os.getenv('LOG_LEVEL')
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键，支持点号分隔（如 'ai.provider'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_ai_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        获取AI配置
        
        Args:
            provider: 提供商名称，如果不指定则使用默认提供商
            
        Returns:
            AI配置字典
        """
        if provider is None:
            provider = self.get('ai.provider', 'zhipuai')
        
        return self.get(f'ai.{provider}', {})
    
    def get_api_key(self, provider: Optional[str] = None) -> str:
        """
        获取API密钥
        
        Args:
            provider: 提供商名称
            
        Returns:
            API密钥
        """
        ai_config = self.get_ai_config(provider)
        return ai_config.get('api_key', '')
    
    def reload(self):
        """重新加载配置"""
        self._load_config()
    
    @property
    def raw_config(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._config_data.copy()


# 全局配置实例
_config_instance: Optional[Config] = None

def get_config() -> Config:
    """
    获取配置实例
    
    Returns:
        Config: 配置管理实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# 便捷函数
def get(key: str, default: Any = None) -> Any:
    """获取配置项"""
    return get_config().get(key, default)

def get_ai_config(provider: Optional[str] = None) -> Dict[str, Any]:
    """获取AI配置"""
    return get_config().get_ai_config(provider)

def get_api_key(provider: Optional[str] = None) -> str:
    """获取API密钥"""
    return get_config().get_api_key(provider)
