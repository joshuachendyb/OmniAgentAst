"""
配置管理模块
统一管理应用配置,支持从YAML文件和环境变量加载
"""

import functools
import os
import yaml
from collections import OrderedDict
from typing import Dict, Any, Optional
from pathlib import Path
@functools.lru_cache(maxsize=1)
def _make_safe_loader() -> type:
    """创建支持 OrderedDict 标签的 SafeLoader — 小欧 2026-06-22"""
    class _Loader(yaml.SafeLoader):
        pass
    def _construct_ordered_dict(loader, node):
        args = loader.construct_sequence(node, deep=True)
        pairs = args[0] if args else []
        return OrderedDict(pairs)
    _Loader.add_constructor(
        'tag:yaml.org,2002:python/object/apply:collections.OrderedDict',
        _construct_ordered_dict,
    )
    return _Loader

class Config:
    """配置管理类"""

    _config_data: Optional[Dict[str, Any]] = None
    _config_mtime: Optional[float] = None  # 配置文件修改时间,用于缓存检测
    
    def _load_config(self):
        """加载配置文件（高层编排，只负责流程控制）
        
        【修复S-2 2026-06-08 小沈】拆分为私有方法，遵守SLAP原则
        """
        config_path = self._get_config_path()
        
        self._check_config_exists(config_path)
        
        if self._is_cache_valid(config_path):
            return
        
        self._load_from_file(config_path)
        self._apply_env_overrides()
    
    def _check_config_exists(self, config_path: Path) -> None:
        """检查配置文件是否存在"""
        if not config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在：{config_path}。"
                "请在前端创建配置文件或手动创建 config/config.yaml"
            )
    
    def _is_cache_valid(self, config_path: Path) -> bool:
        """检查缓存是否有效"""
        new_mtime = config_path.stat().st_mtime
        return self._config_data is not None and self._config_mtime == new_mtime
    
    def _load_from_file(self, config_path: Path) -> None:
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.load(f, Loader=_make_safe_loader())
            
            if not self._config_data:
                raise ValueError("配置文件为空，请检查 config/config.yaml")
        except (yaml.YAMLError, ValueError) as e:
            raise RuntimeError(
                f"加载配置文件失败：{e}。"
                "请检查 config/config.yaml 格式是否正确"
            )
        
        self._config_mtime = config_path.stat().st_mtime
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        env_path = os.getenv('OMNIAGENT_CONFIG_PATH')
        if env_path:
            return Path(env_path)
        return Path(get_config_path())
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖 — 通用模式:{PROVIDER}_API_KEY 自动匹配 — 小健 2026-05-24"""
        ai_config = self._config_data.get('ai', {})
        
        for provider_name, provider_config in ai_config.items():
            if not isinstance(provider_config, dict):
                continue
            env_key = f"{provider_name.upper()}_API_KEY"
            env_value = os.getenv(env_key)
            if env_value:
                provider_config['api_key'] = env_value
        
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
            key: 配置键,支持点号分隔(如 'ai.provider')
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
    

    def get_max_rounds(self, default: int = 100) -> int:
        """获取max_rounds配置 — 对话历史最多保留的FC轮数 — 小欧 2026-07-08"""
        return self.get('app.max_rounds', default)

    def get_max_steps(self, default: int = 10000) -> int:
        """
        获取max_steps配置 - 统一入口

        Args:
            default: 默认值

        Returns:
            max_steps值
        """
        return self.get('app.max_steps', default)

    def get_max_context_chars(self, default: int = 500000) -> int:
        """获取max_context_chars配置 — 对话历史字符上限"""
        return self.get('app.max_context_chars', default)

    def get_project_root(self) -> str:
        """获取项目根目录配置
        
        若未配置(空字符串),返回基于代码位置推算的默认值。
        """
        root = self.get('app.project_root', '')
        if root:
            return root
        return get_default_project_root()

    def reload(self):
        """重新加载配置 - 强制清空缓存"""
        self._config_data = None
        self._config_mtime = None
        self._load_config()

# 全局配置实例
_config_instance: Optional[Config] = None

def get_config() -> Config:
    """
    获取配置实例 — 唯一公共API
    每次调用检查文件mtime，变化则自动重读（支持运行时修改config.yaml）
    
    Returns:
        Config: 配置管理实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    _config_instance._load_config()  # 内部有mtime缓存检查，未变则跳过
    return _config_instance


# ============================================================
# 路径计算函数（从 utils/paths.py 迁入）
# ============================================================

_PROJECT_ROOT: Optional[Path] = None


def _get_project_root() -> Path:
    """唯一项目根目录计算入口——基于当前文件位置推算"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = Path(__file__).parent.parent.parent
    return _PROJECT_ROOT


def get_default_project_root() -> str:
    """获取默认项目根目录(str) — 基于代码位置推算"""
    return str(_get_project_root())


def get_config_path(filename: str = "config.yaml") -> str:
    """统一配置路径获取"""
    return str(_get_project_root() / "config" / filename)


DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_TOOLS_CONFIG_FILENAME = "tools.yaml"
