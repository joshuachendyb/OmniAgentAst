"""统一响应格式工具 — 标准化 success/failure/error 响应 + 通用装饰器

【小健 2026-05-31】新建：统一响应函数 + handle_api_errors 装饰器
"""

from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar

from fastapi import HTTPException

from app.utils.logger import logger

F = TypeVar("F", bound=Callable[..., Awaitable])


def api_success(message: str = "ok", **extra: Any) -> dict:
    """统一成功响应：{"success": True, "message": xxx, **extra}"""
    return {"success": True, "message": message, **extra}


def api_failure(message: str = "", errors: Optional[list] = None, **extra: Any) -> dict:
    """统一失败响应：{"success": False, "message": xxx, "errors": [], **extra}"""
    result: dict = {"success": False, "message": message}
    if errors:
        result["errors"] = errors
    result.update(extra)
    return result


def api_error(status_code: int, detail: str, log_msg: str = "") -> None:
    """记录日志并抛出 HTTPException（仅用于非 CRUD 通用错误）"""
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
            except Exception as e:
                logger.error(f"{operation_name}失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"{operation_name}失败: {str(e)}"
                )
        return wrapper  # type: ignore
    return decorator


__all__ = [
    "api_success",
    "api_failure",
    "api_error",
    "handle_api_errors",
]
