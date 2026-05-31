# -*- coding: utf-8 -*-
"""
_handle_run_exception — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第106-111行
Author: 小沈 - 2026-05-31
"""

import traceback
from typing import Any, Dict

from app.utils.logger import logger


class HandleRunExceptionMixin:
    """未捕获异常兜底"""

    def _handle_run_exception(self, e: Exception, step_count: int) -> Dict[str, Any]:
        """复制自 react_handler_mixin.py 第106-111行"""
        self.message_builder.temp_history.clear()
        traceback.print_exc()
        logger.error(f"Agent run_stream error: {e}", exc_info=True)
        return self._exit_with_error(step_count, "unhandled_exception", str(e))
