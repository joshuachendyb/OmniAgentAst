# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A1 默认安全 hooks(4.1.7 定案)。纯转发壳, 逻辑单一归属 operation_record(DRY),
#   不复制三阶段(DB标记→备份→执行→记录→回滚)逻辑, 仅做接口适配。供 tool_executor/health.py 入口注入。
"""
default_hooks — 默认安全 hooks 实现(转发壳)

设计(4.1.7 硬伤三/修正四点, 小欧 2026-08-12):
  - 实现 app/tools/security_hooks.py 的 ToolSecurityHooks 协议;
  - record_operation / execute_with_safety 直接转发 operation_record 原函数, 零逻辑复制(DRY);
  - 依赖方向: safety → tools(security_hooks 协议) 合法单向。
"""
from typing import Any, Callable, Optional, Tuple

from app.tools.security_hooks import ToolSecurityHooks
from app.safety.operation_record import (
    record_operation as _record_operation,
    execute_with_safety as _execute_with_safety,
)


class DefaultToolSecurityHooks:
    """默认安全 hooks — 纯转发壳, 逻辑单一归属 operation_record — 小欧 2026-08-12"""

    def record_operation(
        self,
        task_id: str,
        operation_type: Optional[str] = None,
        source_path: Optional[Any] = None,
        destination_path: Optional[Any] = None,
        sequence_number: int = 0,
        file_size: Optional[int] = None,
        operation_id: Optional[str] = None,
    ) -> Optional[str]:
        """转发 operation_record.record_operation — 小欧 2026-08-12"""
        return _record_operation(
            task_id=task_id,
            operation_type=operation_type,
            source_path=source_path,
            destination_path=destination_path,
            sequence_number=sequence_number,
            file_size=file_size,
            operation_id=operation_id,
        )

    def execute_with_safety(
        self,
        operation_id: str,
        operation_func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[bool, Optional[str]]:
        """转发 operation_record.execute_with_safety — 小欧 2026-08-12"""
        return _execute_with_safety(operation_id, operation_func, *args, **kwargs)
