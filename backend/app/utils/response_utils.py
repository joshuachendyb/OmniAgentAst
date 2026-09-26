"""统一响应格式工具 — 标准化 success/failure/error 响应 + 通用装饰器

【小健 2026-05-31】新建:统一响应函数 + handle_api_errors 装饰器
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
            # 2026-09-26 - 小欧 - 修 D22 + E12「ValueError 被统一兜成 500，客户端错误被当服务端故障」
            # （三遍核实确认成立；改在此处而非各 service，是 DRY：一条规则覆盖全部调用方）：
            #   原实现只有 HTTPException 直通，其余**一律** 500。而本项目里 ValueError 是
            #   **客户端提交内容不成立**的既定表达（provider 不存在、不支持的字段、没有有效字段、
            #   add_provider 的 name 非法…），被 handle_config_errors 包住后一律变成 500。
            #   危害：①5xx 会被前端/网关/监控当服务端故障（自动重试、告警噪声），而重试永远不会成功；
            #        ②detail 变成"XXX失败: ..."，用户看不出是自己填错了；③既有 TDD
            #           test_empty_api_key_not_overwrite 固化的就是"抛错 + 绝不落盘"，
            #           说明"报错"是既定设计，错的只是**级别**。
            #   修法：ValueError（含其子类，如 KeyError 之外的常见输入类错误）显式映射为 **400**，
            #     语义不变、级别纠正，且**不改动任何 service 的既有契约与测试**。
            #   刻意不把 KeyError/AttributeError 等也归入 400：那些是代码缺陷，理应继续 500（可观测）。
            #   —— 编辑：小欧 2026-09-26
            except ValueError as e:
                logger.warning(f"{operation_name}参数/数据不合法: {e}")
                raise HTTPException(status_code=400, detail=str(e))
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
