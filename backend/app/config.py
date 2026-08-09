
"""
配置管理模块
统一管理应用配置,支持从YAML文件和环境变量加载
"""
# 编辑历史:
# 2026-07-22 小欧 get_max_context_chars→get_max_context_tokens 重命名（语义纠正），默认值 500000→200000 对齐 constants.py

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

    def get_max_context_tokens(self, default: int = 200000) -> int:
        """获取max_context_tokens配置 — 对话历史 Token 上限"""
        return self.get('app.max_context_tokens', default)

    def get_project_root(self) -> str:
        """获取项目根目录配置 — 小欧 2026-08-10 ①改兜底

        项目根=tool工作区: 配置 `app.project_root` 优先;
        未配置(空) → 用户主目录 `Path.home()`(不再用代码位置当项目根)。
        代码库根另行由 `get_code_root()` 提供(定位 config/version.txt 等程序资源)。
        """
        root = self.get('app.project_root', '')
        if root:
            return root
        return str(Path.home())

    def get_allowed_dirs(self) -> list:
        """获取授权目录列表(可多个) — 小欧 2026-08-10 ⑩新增

        除项目根外, tool 额外授权访问的工作目录, 配置 `app.allowed_dirs`(列表)。
        项目根天然在授权内, 无需重复列入。
        边界约束: 任一授权目录指向代码库根或其父/子级 → 抛 ValueError 拒绝加载
        (与⑦ tool禁区冲突, 防止授权目录变相开放代码库)。
        """
        raw = self.get('app.allowed_dirs', None)
        if not raw:
            return []
        if not isinstance(raw, list):
            raise ValueError("app.allowed_dirs 必须是列表(list)")
        result = []
        code_root = Path(_get_code_root()).resolve()
        for item in raw:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"app.allowed_dirs 含非法条目: {item!r}, 必须是非空字符串路径")
            d = Path(item).resolve()
            if d == code_root:
                raise ValueError(f"app.allowed_dirs 禁止指向代码库根: {item}")
            if code_root in d.parents or d in code_root.parents:
                raise ValueError(f"app.allowed_dirs 禁止指向代码库根的父/子级: {item}")
            result.append(str(d))
        return result

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

_CODE_ROOT: Optional[Path] = None


def _get_code_root() -> Path:
    """代码库根(程序安装/代码所在目录)计算入口 — 小欧 2026-08-10 ②改名(原_get_project_root)
    基于当前文件位置推算, 仅用于定位 config/config.yaml、version.txt、logs/、模板等程序自身资源。
    tool 禁区: 任何tool操作触达此根一律禁止(Safety层⑦硬拦截)。
    """
    global _CODE_ROOT
    if _CODE_ROOT is None:
        _CODE_ROOT = Path(__file__).parent.parent.parent
    return _CODE_ROOT


def get_code_root() -> str:
    """获取代码库根(str)公开API — 小欧 2026-08-10 ③改名(原get_default_project_root)
    名实一致(代码库根, 非项目根); 项目根请用 get_project_root()。
    """
    return str(_get_code_root())


def get_config_path(filename: str = "config.yaml") -> str:
    """统一配置路径获取 — 代码库根下 config 目录(非项目根) — 小欧 2026-08-10 ④内部改调"""
    return str(_get_code_root() / "config" / filename)


DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_TOOLS_CONFIG_FILENAME = "tools.yaml"

