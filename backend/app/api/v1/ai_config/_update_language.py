from app.utils.logger import logger


def _update_language(config_data: dict, update) -> None:
    config_data.setdefault('app', {})['language'] = update.language
    logger.info(f"更新语言: {update.language}")
