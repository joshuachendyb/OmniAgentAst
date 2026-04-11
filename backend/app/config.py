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
    _config_mtime: Optional[float] = None  # 配置文件修改时间，用于缓存检测
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置文件 - 带缓存优化（双保险）"""
        config_path = self._get_config_path()
        
        # ⭐ 保险1：文件不存在时处理
        if not config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}。"
                "请在前端创建配置文件或手动创建 config/config.yaml"
            )
        
        # ⭐ 保险2：时间戳检查 - 如果缓存存在且mtime相同，使用缓存
        new_mtime = config_path.stat().st_mtime
        if self._config_data is not None and self._config_mtime == new_mtime:
            # 配置文件未变更，使用缓存
            return
        
        # 从文件加载配置
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            
            # 配置文件不能为空
            if not self._config_data:
                raise ValueError("配置文件为空，请检查 config/config.yaml")
        except (yaml.YAMLError, ValueError) as e:
            raise RuntimeError(
                f"加载配置文件失败: {e}。"
                "请检查 config/config.yaml 格式是否正确"
            )
        
        # ⭐ 更新mtime
        self._config_mtime = new_mtime
        
        # 环境变量覆盖
        self._apply_env_overrides()
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        # 优先使用环境变量指定的路径
        env_path = os.getenv('OMNIAGENT_CONFIG_PATH')
        if env_path:
            return Path(env_path)
        
        # 【修复】项目根目录是backend的父目录
        # backend/app/config.py -> .parent=app -> .parent=backend -> .parent=项目根目录
        base_dir = Path(__file__).parent.parent.parent
        return base_dir / "config" / "config.yaml"
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # AI配置 - 只在对应的provider配置存在时才覆盖
        ai_config = self._config_data.get('ai', {})
        
        if os.getenv('ZHIPUAI_API_KEY') and 'zhipuai' in ai_config:
            ai_config['zhipuai']['api_key'] = os.getenv('ZHIPUAI_API_KEY')
        
        if os.getenv('OPENCODE_API_KEY') and 'opencode' in ai_config:
            ai_config['opencode']['api_key'] = os.getenv('OPENCODE_API_KEY')
        
        if os.getenv('AI_PROVIDER'):
            ai_config['provider'] = os.getenv('AI_PROVIDER')
        
        # 日志级别
        logging_config = self._config_data.get('logging', {})
        if os.getenv('LOG_LEVEL'):
            logging_config['level'] = os.getenv('LOG_LEVEL')
    
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
        """重新加载配置 - 强制清空缓存"""
        # 清空缓存，强制重新加载
        self._config_data = None
        self._config_mtime = None
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
