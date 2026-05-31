from app.utils.logger import logger


def _update_theme(config_data: dict, update) -> None:
    config_data.setdefault('app', {})['theme'] = update.theme
    logger.info(f"更新主题: {update.theme}")
