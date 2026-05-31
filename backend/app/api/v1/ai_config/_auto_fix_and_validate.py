from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path
from ._restore_backup_if_needed import _restore_backup_if_needed
from ._fix_config_common_issues import _fix_config_common_issues
from ._validate_config_integrity import _validate_config_integrity
from app.config import get_config as get_config_instance


def _auto_fix_and_validate(
    config_data: dict, config_path: Path, backup_path: Optional[Path],
    original_config_data: dict,
) -> Tuple[bool, List[str], List[str], Optional[Dict[str, Any]]]:
    """自动修复+验证，失败则恢复备份 - 小健 2026-05-25"""
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
