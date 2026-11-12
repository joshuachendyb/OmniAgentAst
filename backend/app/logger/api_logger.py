
# -*- coding: utf-8 -*-
"""
APILogger — 从 setup.py 拷出

拷贝来源: setup.py 第106-207行
"""
# 编辑历史:
# 2026-11-03 - 小欧 - 删 __init__ 期 debug_mode 快照, 两处改实时读 LogConfig.is_debug_mode():
#   原快照致设置页切换调试模式需重启才生效 — 小欧-2026-11-03
# 2026-11-12 - 小欧 - ① __new__ 去掉手动 __init__ 调用(type.__call__ 已会在返回实例上调用, 原为重复初始化);
#   ② _request_times 增 TTL 清理: 超时/异常未走 log_response_with_time 的条目原永久驻留, dict 无界增长;
#   ③ 删死代码 _should_log(全仓零调用, YAGNI) — 小欧-2026-11-12

import logging
import time
import uuid
from typing import Optional

from app.logger.config import LogConfig
from app.logger.shared_handler import setup_logger


_REQUEST_TTL_SECONDS = 300


class APILogger:
    """拷贝自 setup.py 第106-207行"""

    _instance: Optional['APILogger'] = None

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self.logger: logging.Logger = setup_logger(__name__)
        self._request_times: dict = {}
        self._initialized = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _prune_request_times(self) -> None:
        """清理超过 TTL 仍未响应的请求记录, 防超时/异常路径下 _request_times 无界增长 — 小欧-2026-11-12"""
        cutoff = time.time() - _REQUEST_TTL_SECONDS
        for rid in [k for k, v in self._request_times.items() if v.get('start_time', 0) < cutoff]:
            self._request_times.pop(rid, None)

    def log_request_start(self, provider: str, model: str, message_len: int, history_count: int = 0) -> str:
        self._prune_request_times()
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
        if LogConfig.is_debug_mode():
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
        if exc_info and LogConfig.is_debug_mode():
            self.logger.exception(f"[{provider}] 异常: {error}")
        else:
            self.logger.error(f"[{provider}] 错误: {error}")

