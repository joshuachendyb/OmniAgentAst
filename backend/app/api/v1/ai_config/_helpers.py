"""ai_config 包内部公用函数 — YAML读写/配置修复/验证/备份/装饰器

原分散文件: _ordered_dict.py, _write_yaml_with_order.py, _backup_config.py,
_restore_backup_if_needed.py, _fix_config_common_issues.py, _auto_fix_and_validate.py,
_validate_config_integrity.py, _decorators.py
F10合并: 小欧 - 2026-06-08
"""

import shutil
import yaml

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services import get_config_path as _get_config_path, reset
from app.utils.logger import logger
from app.utils.response_utils import handle_api_errors as handle_config_errors


# ====================================================================
# 装饰器
# ====================================================================

__all__ = ["handle_config_errors"]


# ====================================================================
# YAML 有序写入
# ====================================================================

def _write_yaml_with_order(file_path: str, data: dict):
    """使用OrderedDict写入YAML,保持特定顺序 - 小沈 2026-06-09 复用"""
    from app.tools.tool_fc_helper import write_yaml_ordered
    result = write_yaml_ordered(file_path, data)
    if isinstance(result, dict) and "error" in result:
        raise Exception(result.get("error"))


# ====================================================================
# 配置路径 / 读写
# ====================================================================

def get_config_path() -> Path:
    """获取配置文件路径(缓存式调用)"""
    return Path(_get_config_path())


def read_yaml_config(config_path: Path) -> dict:
    """读取 YAML 配置文件,文件不存在时返回空 dict"""
    if not config_path.exists():
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def write_yaml_config(config_path: str, data: dict) -> None:
    """使用有序 Key 写入 YAML 配置文件"""
    _write_yaml_with_order(config_path, data)


def reload_ai_config() -> None:
    """重新加载 AI 配置并重置缓存"""
    from app.config import get_config as get_config_instance
    config_obj = get_config_instance()
    config_obj._load_config()
    reset()


def _set_app_field(config_data: dict, field_name: str, value: Any, display_name: str = "") -> None:
    """设置 app 下单一字段"""
    config_data.setdefault('app', {})[field_name] = value
    logger.info(f"更新{display_name or field_name}: {value}")


def is_provider_metadata_field(field_name: str) -> bool:
    """检查字段是否是provider元数据字段（provider/model），用于遍历ai配置时跳过 — 小欧 2026-06-18"""
    return field_name in ('provider', 'model')


def load_config() -> tuple:
    """加载配置的公共函数 — 小欧 2026-06-18
    返回: (config_path, config)
    """
    config_path = get_config_path()
    config = read_yaml_config(config_path)
    return config_path, config


def save_config(config_path: str, config: dict) -> None:
    """保存配置的公共函数 — 小欧 2026-06-18
    """
    write_yaml_config(config_path, config)
    reload_ai_config()


# ====================================================================
# 备份 / 恢复
# ====================================================================

def _backup_config(config_path: Path) -> Path:
    """备份配置文件"""
    from app.tools.tool_fc_helper import backup_file
    result = backup_file(str(config_path), suffix=".backup")
    bp = Path(result["backup_path"])
    logger.info(f"配置文件已备份: {bp}")
    return bp


def _restore_backup_if_needed(
    backup_path: Optional[Path], config_path: Optional[Path],
    restored_flag: List[bool],
) -> bool:
    """恢复备份配置(仅一次)"""
    if restored_flag[0]:
        return False
    if not backup_path or not config_path or not backup_path.exists():
        return False
    try:
        shutil.copy2(str(backup_path), str(config_path))
        restored_flag[0] = True
        logger.warning(f"已从备份恢复配置: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"备份恢复失败: {e}")
        return False


# ====================================================================
# 配置修复
# ====================================================================

def _fix_config_common_issues(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """自动修复常见的配置问题(删除provider下废弃的model字段)"""
    ai_config = config_data.get('ai', {})
    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            del provider_data['model']
            logger.info(f"已删除 provider '{provider_name}' 下废弃的 model 字段")
    return config_data


# ====================================================================
# 配置验证
# ====================================================================

def _validate_config_integrity(config_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """完整验证配置文件完整性: (是否通过, 错误列表, 警告列表)"""
    errors = []
    warnings = []
    ai_config = config_data.get('ai', {})

    if 'provider' not in ai_config:
        errors.append("缺少 ai.provider 字段")
    if 'model' not in ai_config:
        errors.append("缺少 ai.model 字段")
    if errors:
        return False, errors, warnings

    selected_provider = ai_config['provider']
    selected_model = ai_config['model']

    if selected_provider not in ai_config:
        errors.append(f"provider '{selected_provider}' 不存在")
        return False, errors, warnings

    provider_config = ai_config[selected_provider]

    if 'api_base' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_base 字段")
    if 'api_key' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 api_key 字段")
    if errors:
        return False, errors, warnings

    if 'models' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 models 列表")
        return False, errors, warnings

    models_list = provider_config['models']

    if selected_model not in models_list:
        errors.append(f"model '{selected_model}' 不在 provider '{selected_provider}' 的 models 列表中")
        return False, errors, warnings

    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            warnings.append(f"provider '{provider_name}' 下有废弃的 model 字段,建议删除")

    return True, errors, warnings


# ====================================================================
# 自动修复 + 验证
# ====================================================================

def _auto_fix_and_validate(
    config_data: dict, config_path: Path, backup_path: Optional[Path],
    original_config_data: dict,
) -> Tuple[bool, List[str], List[str], Optional[Dict[str, Any]]]:
    """自动修复+验证,失败则恢复备份"""
    from app.config import get_config as get_config_instance
    config_data = _fix_config_common_issues(config_data)
    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        _restore_backup_if_needed(backup_path, config_path, [False])
        get_config_instance().reload()
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        original_ai = original_config_data.get('ai', {})
        fail_result = {
            "success": False, "message": "配置验证失败", "errors": errors, "warnings": warnings,
            "backup_path": str(backup_path) if backup_path else None,
            "current_provider": original_ai.get('provider', 'unknown'),
            "current_model": original_ai.get('model', 'unknown'),
        }
        return False, errors, warnings, fail_result
    return True, [], warnings, None
