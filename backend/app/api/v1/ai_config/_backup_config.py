import shutil
from pathlib import Path
from app.utils.logger import logger
from app.utils.time_utils import timestamp_for_filename


def _backup_config(config_path: Path) -> Path:
    """备份配置文件，复用file_helpers.backup_file - 小健 2026-05-25"""
    from app.services.tools.toolhelper.file_helpers import backup_file
    result = backup_file(str(config_path), suffix=".backup")
    if result.get("code") != "SUCCESS":
        timestamp = timestamp_for_filename()
        backup_path = config_path.parent / f"config.yaml.backup.{timestamp}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"配置文件已备份(fallback): {backup_path}")
        return backup_path
    bp = Path(result["data"]["backup_path"])
    logger.info(f"配置文件已备份: {bp}")
    return bp
