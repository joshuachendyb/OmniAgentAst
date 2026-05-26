from pathlib import Path
from app.utils.logger import logger


def get_version() -> str:
    """从version.txt读取版本号 - 小沈 2026-05-27"""
    try:
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent.parent
        project_root = backend_dir.parent
        version_file = project_root / "version.txt"

        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                version = f.readline().strip()
            logger.info(f"Successfully read version from version.txt: {version}")
            return version.lstrip('v')
    except Exception as e:
        logger.warning(f"Failed to read version.txt: {e}")
    return "0.13.36"
