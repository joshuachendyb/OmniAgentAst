import shutil
from pathlib import Path
from app.utils.logger import logger
from app.utils.time_utils import timestamp_for_filename


def _backup_config(config_path: Path) -> Path:
    """备份配置文件"""
    from app.services.tools.toolhelper.file_helpers import backup_file
    result = backup_file(str(config_path), suffix=".backup")
    if result.get("code") != "SUCCESS":
        raise RuntimeError(f"配置文件备份失败: {result.get('message', '')}")
    bp = Path(result["data"]["backup_path"])
    logger.info(f"配置文件已备份: {bp}")
    return bp
