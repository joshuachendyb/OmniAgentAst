# Windows需要ProactorEventLoop支持asyncio subprocess — 小沈 2026-06-28
# 编辑历史:
# 2026-07-15 小欧 修复后台清理闭包命名撞车: 原内部闭包 cleanup_task 与 task_registry.cleanup_task(删单个任务)同名不同义, 违反清晰命名/KISS; 展平为模块级 _periodic_cleanup_loop 并保存 task 引用, shutdown 时 cancel
# 2026-07-28 - 小欧 - BUG#4: version.txt为空时get_version直奔for line in f, 无行进入时version未赋值致UnboundLocalError; 补version="0.0.0"默认值。
# 2026-08-03 - 小欧 - 恢复7-30原设计(DB核实): 删shutdown里的shell_pool.cleanup_all()+日志与import; 该行系8-02恢复工程误加回, 7-30已决策main.py不清理(atexit+task完成清理全覆盖)。
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处异常响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-09 - 小欧 - task006 P7落地(日志级别优化): HTTP 4xx客户端错误与Validation(422)由ERROR降为WARNING, 5xx保持ERROR — 避免测试/非法请求噪音污染ERROR日志, 干扰真实故障排查
# 2026-08-10 - 小欧 - ⑬get_version改调get_code_root(): 定位version.txt改走代码库根(名实分离, 不再用项目根路径推算) — 步骤1实施(北京老陈驱动)
# 2026-08-12 - 小欧 - A4(方案4.4.3): 注册 tool_routes router(工具测试路由由 health.py 迁出), include_router 加 /api/v1 tags=tools — 小欧 2026-08-12
# 2026-08-14 - 小欧 - 改名名实相符: model_routes→config_routes(import与挂载变量model_router→config_router); api/v1/chat/sse→execution_stream(chat_execution_router导入同步)
# 2026-08-14 - 小欧 - monitoring 独立为 app 顶层能力层目录(services/monitoring→app/monitoring), 本文件 import 路径同步
# 2026-08-16 - 小欧 - S2(10.1.7②-6/10.1.8 S2): 注册 token_usage_router(token 四维度查询 API, 新建 app/api/v1/token_usage.py), include_router 加 /api/v1 tags=token-usage
# 2026-08-30 - 小欧 - 控制台写离线化(case09挂起根治): 启动 tip 两条 print→console_put(语义不变仅控制台, 非阻塞镜像), 事件循环线程零同步 stdout 写
# 2026-09-20 - 小沈 - v4.19 Phase 2: 注册 settings_router/model_router（/api/v1/settings /api/v1/models）
# 2026-09-21 - 小欧 - 对齐文档54 9.3.1：model_router 挂载 tags "model"→"models"（文档字面）
# 2026-09-21 - 小欧 - v4.20 单源收敛: 启动日志 LLM 配置改读 ai.model_ref（删扁平 ai.provider/ai.model）
# 2026-09-22 小欧 - [61] constants.py 配置化迁移：import DEFAULT_CORS_ORIGINS 改别名 + CORS 改读 tuning.network.cors_origins
# 2026-09-23 小欧 - 键名去 tuning 前缀：tuning.network.cors_origins → network.cors_origins（系统组，与调优无关）— 小欧-2026-09-23
# 2026-09-25 小欧 - [70] ConnectionScope连接池统一所有者(3.9): shutdown_event 的裸 reset() 改 await shutdown()——原调用只清工厂换代不等共享池关闭, 池归零由 3.6 shutdown 逐退休代 drain 兜底(超时放行不阻塞退出) — 小欧-2026-09-25
# 2026-09-26 小欧 - [72]第九章: 全路由统一 token 鉴权（服务绑 0.0.0.0 是多机部署硬前提不可收窄，
#   原状态下局域网任意设备可直调任何接口：读走全部明文密钥、改擦密钥、越权读会话）。
#   鉴权细节与设计依据见 deps.py 文件头；_mount() 抽成唯一入口的理由见挂载点处注释。
# 2026-09-27 小欧 - ①默认关闭 /docs /redoc /openapi.json（OMNIAGENT_ENABLE_DOCS=1 开启）：这三者是
#   **应用级**路由，不在任何 APIRouter 内，走不到 verify_token，实跑确认无 token 可拉走全部端点与模型。
#   / 的 docs 键同步条件化，避免广播一个必 404 的地址。②访问口令路由改走 _mount()，不再手写
#   include_router 绕过唯一入口。③_ENABLE_DOCS 改用 app.config.env_flag，不再手搓真值列表。
#   同轮精简冗长注释（三堂会审叙事压缩为结论）。
import sys
import asyncio
from typing import Optional
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Windows PowerShell 5.1中文输出编码修复 — 小欧 2026-07-07
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python -u模式下可能抛AttributeError，忽略
        pass

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.tools import ensure_tools_registered
from app.config import get_config, get_code_root, env_flag
from pathlib import Path
import os
import logging

from app.api.v1 import health, sessions, messages, metrics
from app.api.v1.config_routes import router as config_router
from app.api.v1.settings_routes import router as settings_router
from app.api.v1.model_routes import router as model_router
from app.api.v1.tool_routes import router as tool_routes_router  # A4: 工具测试路由迁出 health.py — 小欧 2026-08-12
from app.api.v1.token_usage import router as token_usage_router  # S2(10.1.7②-6): token 四维度查询 API — 小欧 2026-08-16
from app.api.v1.chat import router as chat_router, task_router, execution_stream as chat_execution_router
from app.api.v1.task_queries import router as task_queries_router
# 2026-09-26 小欧 - [72]第九章(9.6-1): 统一 token 鉴权依赖（12 个 router 挂载，/health 豁免）
from app.api.v1.deps import verify_token
# 2026-09-26 小欧 - [72]第九章补: 访问口令设置路由（首次设置豁免在 deps.verify_token 内）
from app.api.v1.auth_routes import router as auth_router
from app.logger import logger
from app.monitoring import setup_monitoring
from app.constants import DEFAULT_CORS_ORIGINS as _D_CORS
from app.config import get_config
from app.services.task.task_registry import cleanup_expired_tasks
from app.db import db

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_version() -> str:
    """从version.txt读取版本号 - 小沈 2026-05-27 - 小欧 2026-08-10 ⑬改调get_code_root"""
    try:
        code_root = Path(get_code_root())  # 代码库根(定位version.txt) — ⑬ 2026-08-10
        version_file = code_root / "version.txt"

        if version_file.exists():
            version = "0.0.0"
            with open(version_file, 'r', encoding='utf-8') as f:
                for line in f:
                    version = line.strip().lstrip('\ufeff')
                    if version:
                        break
            logger.debug(f"Successfully read version from version.txt: {version}")
            return version.lstrip('v')
    except Exception as e:
        logger.warning(f"Failed to read version.txt: {e}")
    return "0.0.0"


app_version = get_version()
logger.info(f"Backend version: {app_version}")

# 2026-09-27 10:15 小欧 - 关闭应用级 API 文档端点（修 [72]核查发现的鉴权缺口）：/docs /redoc /openapi.json
#   是**应用级路由**，不在任何 APIRouter 内，走不到 verify_token —— 实跑确认无 token 可拉走 57 个端点
#   + 44 个请求模型。本机开发需查看时设 OMNIAGENT_ENABLE_DOCS=1（多机部署下别开）。
#   布尔解析复用 config.env_flag（假值列表统一单点），不手搓真值列表。
_ENABLE_DOCS = env_flag("OMNIAGENT_ENABLE_DOCS")
app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=app_version,
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
)
if not _ENABLE_DOCS:
    logger.info("API 文档端点已关闭（如需本地查看设置：OMNIAGENT_ENABLE_DOCS=1）")

logger.info("Backend v" + app_version + " started")

_cors_origins_str = os.getenv("CORS_ORIGINS", get_config().get("network.cors_origins", _D_CORS))
_cors_origins = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_monitoring(app)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 记录请求路径/方法/客户端, 便于定位 404 等异常的真正来源(原日志仅记状态码, 无法定位) — 小欧 2026-07-13
    client = request.client.host if request.client else "unknown"
    # 2026-08-09 小欧: task006 P7 — 4xx客户端错误降WARNING, 5xx服务端错误保持ERROR(真实故障), 减少噪音
    _log = logger.warning if exc.status_code < 500 else logger.error
    _log(f"HTTP Exception: {exc.status_code} - {exc.detail} | {request.method} {request.url.path} client={client}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": get_local_iso_timestamp()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 2026-08-09 小欧: task006 P7 — 422恒为客户端请求参数错误, 由ERROR降WARNING, 避免非法请求噪音污染ERROR日志
    logger.warning(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "请求参数验证失败",
            "details": exc.errors(),
            "timestamp": get_local_iso_timestamp()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled Exception: {error_msg}\n{error_trace}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "服务器内部错误",
            "message": error_msg if app.debug else "请联系管理员",
            "timestamp": get_local_iso_timestamp()
        }
    )


# [72]第九章(9.6-1) - 小欧 - 全路由统一挂 token 鉴权。抽 _mount() 为唯一挂载入口:
#   原写法把 `prefix="/api/v1"` 与 `dependencies` 在 13 行各手写一遍 —— 改前缀必漏改（漏改=该 router
#   挂在错误路径 404），且未来新增 router 谁记得手写 dependencies=？（漏写则该 router 裸奔）。
#   抽成一处后豁免必须显式写 exempt=True，反而更醒目。零行为变化。
_AUTHENTICATED = [Depends(verify_token)]


def _mount(router, tags: str, *, exempt: bool = False) -> None:
    """统一挂载 API router：**默认加 token 鉴权**，仅探活类显式 exempt=True 豁免。

    [72]第九章 9.6-1 —— 全项目唯一挂载入口。新增 router 一律走本函数即自动获得鉴权，
    不再依赖"记得手写 dependencies="（那是本条规则最大的失效来源）。
    """
    app.include_router(
        router,
        prefix="/api/v1",
        tags=[tags],
        dependencies=None if exempt else _AUTHENTICATED,
    )


# 探活/回显豁免（9.6-1 要求，便于探活与排障）。/echo 与 /health 同属 health router 且为
# 纯回显无副作用（已读 health.py:68-76 核实：不落库、不调 LLM），故同享豁免无实际风险。
_mount(health.router, "health", exempt=True)
_mount(tool_routes_router, "tools")  # A4: 工具测试路由 — 小欧 2026-08-12
_mount(chat_router, "chat")
_mount(task_router, "chat")
_mount(config_router, "config")
_mount(settings_router, "settings")
_mount(model_router, "models")  # 设置页模型管理 — 小沈 2026-09-20
_mount(sessions.router, "sessions")
_mount(messages.router, "sessions")
_mount(chat_execution_router.router, "execution")
_mount(metrics.router, "metrics")
_mount(task_queries_router, "task-queries")
_mount(token_usage_router, "token-usage")  # S2(10.1.7②-6) — 小欧 2026-08-16
# 2026-09-27 小欧 - 访问口令路由改走 _mount()：原为绕过唯一入口而手写 include_router，
#   与上方"新增 router 漏 dependencies= 是最大失效来源"的论证自相矛盾。
#   豁免判定（首设自举/只能本机改口令）全在 deps.verify_token 内，与挂载方式无关。
_mount(auth_router, "auth")


_cleanup_task_ref: Optional[asyncio.Task] = None  # 后台清理循环 task 引用, 供 shutdown 时 cancel


async def _periodic_cleanup_loop() -> None:
    """后台周期清理循环: 每 3600s 调用 task_registry.cleanup_expired_tasks 兜底清理过期任务
       命名与 task_registry.cleanup_task(删单个任务) 区分, 避免混淆 (清晰命名/KISS)
    """
    while True:
        try:
            await cleanup_expired_tasks()
        except Exception as e:
            logger.error(f"清理过期任务失败: {e}")
        await asyncio.sleep(3600)


def _start_cleanup_task() -> None:
    """启动后台周期清理任务 — 小沈 2026-06-08; 闭包展平+改名 小欧 2026-07-15"""
    global _cleanup_task_ref
    _cleanup_task_ref = asyncio.create_task(_periodic_cleanup_loop())
    logger.info("后台清理任务已启动")


@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务 — 小健 2026-06-18 内联透传函数"""
    import time as _time
    _t0 = _time.time()
    db.init()
    logger.info(f"[启动耗时] db.init: {_time.time()-_t0:.3f}s")
    _t1 = _time.time()
    ensure_tools_registered()
    logger.info(f"[启动耗时] ensure_tools_registered: {_time.time()-_t1:.3f}s")
    _t2 = _time.time()
    _start_cleanup_task()
    logger.info(f"[启动耗时] _start_cleanup_task: {_time.time()-_t2:.3f}s")
    logger.info(f"[启动耗时] startup_event 合计: {_time.time()-_t0:.3f}s")
    from app.logger.console_writer import console_put  # 小欧 2026-08-30 启动tip离线化(语义不变仅控制台)
    console_put(f"当前版本: {app_version}")
    _cfg = get_config()
    _ref = _cfg.get('ai.model_ref') or {}
    console_put(f"LLM 配置: provider={_ref.get('provider')}, model={_ref.get('model')}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源 — 小健 2026-06-18 内联透传函数; 补充 cancel 清理循环 小欧 2026-07-15"""
    global _cleanup_task_ref
    if _cleanup_task_ref is not None and not _cleanup_task_ref.done():
        _cleanup_task_ref.cancel()
    # [70] 停机收口(小欧 2026-09-25): 换代归还 + 等退休代共享池 lease 归零关闭(超时放行)
    from app.services.lifecycle import shutdown
    await shutdown()


@app.get("/")
async def root():
    # 2026-09-27 小欧 - docs 键随 _ENABLE_DOCS 条件化：默认关闭时无条件返回即对外广播一个必 404 的地址
    return {
        "message": "OmniAgentAst API",
        "version": app_version,
        **({"docs": "/docs"} if _ENABLE_DOCS else {}),
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器自动请求 favicon 时返回 204，避免 main.py:87 全局异常处理器记录 404 噪声 — 小欧 2026-07-13
    return Response(status_code=204)
