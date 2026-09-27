"""统一响应格式工具 — 标准化 success/failure/error 响应 + 通用装饰器

编辑历史:
  2026-05-31 小健 - 新建：统一响应函数 + handle_api_errors 装饰器。
  2026-09-26 小欧 - ValueError 显式映射 400（原一律 500，客户端错误被当服务端故障）。
  2026-09-27 小欧 - [75]DEFECT-7（CWE-209）：500 的 detail 不再回显 str(e)，异常全文与堆栈只落日志。
"""

from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar

from fastapi import HTTPException

from app.logger import logger

F = TypeVar("F", bound=Callable[..., Awaitable])


def api_success(message: str = "ok", **extra: Any) -> dict:
    """统一成功响应:{"success": True, "message": xxx, **extra}"""
    return {"success": True, "message": message, **extra}


def api_failure(message: str = "", errors: Optional[list] = None, **extra: Any) -> dict:
    """统一失败响应:{"success": False, "message": xxx, "errors": [], **extra}"""
    result: dict = {"success": False, "message": message}
    if errors:
        result["errors"] = errors
    result.update(extra)
    return result


def api_error(status_code: int, detail: str, log_msg: str = "") -> None:
    """记录日志并抛出 HTTPException(仅用于非 CRUD 通用错误)"""
    if log_msg:
        logger.error(log_msg)
    raise HTTPException(status_code=status_code, detail=detail)


def handle_api_errors(operation_name: str) -> Callable[[F], F]:
    """通用 API 异常处理装饰器

    消除各 endpoint 文件中重复的 try/except HTTPException/except Exception 模板代码。

    用法:
        @router.get("/some/path")
        @handle_api_errors("获取XXX")
        async def my_endpoint():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except ValueError as e:
                # ValueError 在本项目是"客户端提交内容不成立"的既定表达，映射 400 而非 500
                # （500 会被前端/网关/监控当服务端故障而反复重试）。KeyError/AttributeError
                # 属代码缺陷，刻意留在 500 以保持可观测。
                logger.warning(f"{operation_name}参数/数据不合法: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                # [75] DEFECT-7（CWE-209）：detail 不回显 str(e)，避免泄露内部绝对路径与实现细节
                logger.error(f"{operation_name}失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"{operation_name}失败")
        return wrapper  # type: ignore
    return decorator


__all__ = [
    "api_success",
    "api_failure",
    "api_error",
    "handle_api_errors",
]
