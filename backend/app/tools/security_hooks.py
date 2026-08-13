# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: 工具层安全 hook 协议(A1 硬伤三修正)。签名逐字对齐 app/safety/operation_record 真实函数,
#   直接透传零参数转换(KISS-DIRECT)。工具经 get_current_hooks() 取实现, 不再直接 import app.safety, 消除 tools→safety 越层。
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): 新增 NoOpHooks(tools 层空操作 hooks), 供 get_current_hooks() 兜底,
#   消除工具内 _hooks.record_operation() 的 NPE 风险(入口未注入时, 如测试直接调工具函数);
#   NoOpHooks 不依赖 safety 层, tools 自给自足, record_operation 返回 None(无 DB 记录), execute_with_safety 直接执行 operation_func。
"""
security_hooks — 工具执行安全 hook 接口(Protocol)

设计(4.1.7 实测校准定案, 小欧 2026-08-12):
  - 接口仅声明 record_operation + execute_with_safety 两个核心能力(ISP);
  - 签名逐字对齐 operation_record.record_operation / execute_with_safety, 禁止参数重组;
  - 实现由入口层(tool_executor / health.py)经 ContextVar 注入, 工具内 get_current_hooks() 读取;
  - 默认实现 DefaultToolSecurityHooks 位于 app/safety/default_hooks.py(纯转发壳, DRY 单一归属)。
"""
from typing import Any, Callable, Optional, Protocol, Tuple


class ToolSecurityHooks(Protocol):
    """工具执行安全 hook 接口 — 封装 record_operation + execute_with_safety 两个核心能力
    小欧 2026-08-12(4.1.7 硬伤三修正: 签名对齐 operation_record, 不再自造 (tool_name, params) 签名)
    """

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
        """记录操作并返回 operation_id, 供后续 execute_with_safety 使用
        签名与 app/safety/operation_record.record_operation 完全一致 — 小欧 2026-08-12
        """
        ...

    def execute_with_safety(
        self,
        operation_id: str,
        operation_func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[bool, Optional[str]]:
        """安全执行: DB标记→备份→执行→记录结果→失败保留备份供回滚
        语义与 app/safety/operation_record.execute_with_safety 完全一致:
          - 预期失败: operation_func return False 或 (False, str), 不得 raise
          - 意外异常: 让异常抛出, 本函数 catch 后 return (False, str(e))
          - 成功: return True 或 (True, None)
        小欧 2026-08-12
        """
        ...


class NoOpHooks:
    """空操作 hooks(tools 层自给自足兜底, 无 DB 记录) — 小沈 2026-08-13 BUG-3修复

    用途: get_current_hooks() 返回 None 时(入口未注入, 如测试直接调工具函数),
          兜底返回本类实例, 消除工具内 _hooks.record_operation() NPE。
    设计: 不依赖 safety 层(避免 tools→safety 越层), record_operation 返回 None
          (无 operation_id, 工具走"DB不可用直接执行"分支), execute_with_safety
          直接调用 operation_func 并按成功/失败返回 Tuple。
    """

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
        """无 DB 记录, 返回 None(工具走直接执行分支) — 小沈 2026-08-13"""
        return None

    def execute_with_safety(
        self,
        operation_id: str,
        operation_func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[bool, Optional[str]]:
        """直接执行 operation_func, 无备份/回滚 — 小沈 2026-08-13"""
        try:
            result = operation_func(*args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2:
                return result
            if result is False:
                return (False, "operation returned False")
            return (True, None)
        except Exception as e:
            return (False, str(e))
