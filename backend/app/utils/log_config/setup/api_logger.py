# -*- coding: utf-8 -*-
"""
APILogger — 从 setup.py 拷出

拷贝来源: setup.py 第106-207行
"""

import logging
import time
import uuid
from typing import Optional

from app.utils.log_config.config import LogConfig
from app.utils.log_config.setup.setup_logger_func import setup_logger


class APILogger:
    """拷贝自 setup.py 第106-207行"""

    _instance: Optional['APILogger'] = None

    def __init__(self):
        self.logger: logging.Logger = setup_logger("OmniAgentAst.API")
        self.debug_mode: bool = LogConfig.is_debug_mode()
        self._request_times: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__init__()
        return cls._instance

    def _should_log(self, level: int) -> bool:
        return self.logger.isEnabledFor(level)

    def log_request_start(self, provider: str, model: str, message_len: int, history_count: int = 0) -> str:
        request_id = str(uuid.uuid4())[:8]
        self._request_times[request_id] = {
            'start_time': time.time(),
            'provider': provider,
            'model': model
        }
        self.logger.info(
            f"[{provider}] 请求开始 | ID: {request_id} | 模型: {model} | "
            f"消息长度: {message_len} | 历史消息数: {history_count}"
        )
        if self.debug_mode:
            self.logger.debug(f"[{provider}] 调试模式: 消息内容长度={message_len}")
        return request_id

    def log_response_with_time(self, request_id: str, provider: str, status_code: int,
                               content_len: int = 0, error: Optional[str] = None):
        elapsed_time = 0.0
        model_info = ""
        if request_id in self._request_times:
            request_info = self._request_times[request_id]
            elapsed_time = time.time() - request_info['start_time']
            model_info = f"模型: {request_info['model']} | "
            del self._request_times[request_id]
        if error:
            self.logger.error(
                f"[{provider}] 响应错误 | ID: {request_id} | {model_info}"
                f"状态码: {status_code} | 耗时: {elapsed_time:.2f}s | 错误: {error}"
            )
        else:
            self.logger.info(
                f"[{provider}] 响应成功 | ID: {request_id} | {model_info}"
                f"状态码: {status_code} | 内容长度: {content_len} | 耗时: {elapsed_time:.2f}s"
            )
        return elapsed_time

    def log_timeout(self, provider: str, timeout_seconds: int):
        self.logger.warning(
            f"[{provider}] 请求超时 | 超时时间: {timeout_seconds}秒"
        )

    def log_switch(self, from_provider: str, to_provider: str, success: bool, reason: Optional[str] = None):
        if success:
            self.logger.info(f"[切换] {from_provider} -> {to_provider} | 成功")
        else:
            self.logger.error(
                f"[切换] {from_provider} -> {to_provider} | 失败 | 原因: {reason}"
            )

    def log_validation(self, provider: str, model: str, success: bool, message: str):
        if success:
            self.logger.info(f"[{provider}] 验证成功 | 模型: {model}")
        else:
            self.logger.warning(
                f"[{provider}] 验证失败 | 模型: {model} | 原因: {message}"
            )

    def log_error(self, provider: str, error: str, exc_info: Optional[Exception] = None):
        if exc_info and self.debug_mode:
            self.logger.exception(f"[{provider}] 异常: {error}")
        else:
            self.logger.error(f"[{provider}] 错误: {error}")
