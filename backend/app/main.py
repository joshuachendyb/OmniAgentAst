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
# 2026-09-26 - 小欧 - [72]第九章(9.6-1) 落地: 全路由统一 token 鉴权（一处生效，KISS-DIRECT）
#   ①新增 import: fastapi.Depends + app.api.v1.deps.verify_token
#   ②include_router 处统一 dependencies=[Depends(verify_token)]，**不去改 13 个 router 的定义**（9.6-1 指定方式）
#   ③/api/v1/health **豁免**（9.6-1 要求，便于探活与排障）；其余 12 个 router 全部需鉴权
#   依据 9.4: `--host 0.0.0.0` 是多机部署硬前提**保持不变**（收窄则其他机器全部连不上、服务作废），
#   真正要修的是"零身份验证"这一缺陷 —— 原状态下局域网任意设备/程序/网页跨源请求可直调任何接口
#   （读走全部 provider 明文密钥 / 改擦密钥 / 越权读他人会话与消息）。
#   依赖本体 fail-closed：未配置 token 时拒绝一切受保护请求（绝不"没配就全放行"= 等于没做鉴权）；
#   失败文案统一不区分"未配置"与"不匹配"避免被探测；比较用 hmac 常量时间防计时侧信道。
#   连带(12.6 硬依赖): 第十二章明文接口与本轮同批上线，避免"明文接口 + 零鉴权"成为新的泄露口 — 小欧-2026-09-26
# 2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范复核, 本文件 2 处已改（均已实测行为等价）:
#   ①[DRY + 失效来源] 13 行 include_router 各自手写 `prefix="/api/v1"` 与 `dependencies=_AUTHENTICATED`,
#     同一事实写 13 遍。真正危害不是"啰嗦"，而是**新增 router 时的静默漏鉴权**: 加第 14 个 router
#     谁记得手写 dependencies=? 漏写即该 router 裸奔 —— 而"零身份验证"正是第九章要消灭的核心缺陷,
#     意味着这条安全规则会"修一次漏一次"。已抽 _mount() 为唯一挂载入口(前缀只写一次、默认鉴权、
#     豁免必须显式 exempt=True)。豁免面表达方式由"逐行不写"变为"显式声明"，反而更醒目不易漏。
#     实测等价性: 总路由 72、受保护路径 54、/api/v1/health 与 /api/v1/echo 仍豁免、
#     /api/v1/auth/status 仍受保护 —— 零行为变化。
#   ②[DRY 注释重复] 挂载点上方 6 行注释与本文件头编辑历史同条目**全文重复**。同一事实写两处,
#     改一处忘另一处就产生两个互相矛盾的"事实来源"。已改为指向文件头，不重复抄写。
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
from app.config import get_config, get_code_root
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

app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=app_version
)

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


# [72]第九章(9.6-1) - 小欧 - 2026-09-26: 全路由统一挂 token 鉴权依赖（一处生效，KISS-DIRECT）。
#   要点与设计依据见文件头编辑历史同条目（不在此重复抄写一遍 —— 同一事实全文写两处，
#   改一处忘另一处即产生两个互相矛盾的"事实来源"，是本项目吃过亏的坑，见 ProviderConfig 注释教训）。
# 2026-09-26 - 小欧 - [72]三堂会审后修正(DRY · 13 遍重复抽成一处):
#   原写法把 `prefix="/api/v1"` 与 `dependencies=_AUTHENTICATED` **在 13 行里各手写一遍**。两处真实问题:
#     ①DRY: 同一事实(前缀/鉴权)写 13 遍, 改前缀必漏改(漏改=该 router 挂在错误路径 → 404);
#     ②**新增 router 时的静默漏鉴权风险**: 未来加第 14 个 router, 谁记得手写 dependencies=?
#        漏写则该 router 默认裸奔 —— 而"零身份验证"正是 [72]第九章要消灭的核心缺陷, 修一次漏一次。
#   故抽 _mount() 为唯一挂载入口: 前缀与"默认鉴权"只写一次, 豁免必须显式写 exempt=True。
#   行为等价性已逐条核对: health 仍豁免(豁免面由"逐行不写"改为"显式 exempt=True", 反而更醒目不易漏)，
#   其余 12 个 router + auth 仍全部鉴权, 端点路径与 tag 均不变 —— 零行为变化的重构。
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
# 2026-09-26 小欧 - [72]第九章补: 访问口令设置路由(挂鉴权依赖; deps.verify_token 内含"未配置口令时
#   对 /auth/token 与 /auth/status 的首次设置豁免", 故未设口令时可自举, 已设后改口令需当前有效 token)
app.include_router(auth_router, prefix="/api/v1", tags=["auth"], dependencies=_AUTHENTICATED)


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
    return {
        "message": "OmniAgentAst API",
        "version": app_version,
        "docs": "/docs"
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器自动请求 favicon 时返回 204，避免 main.py:87 全局异常处理器记录 404 噪声 — 小欧 2026-07-13
    return Response(status_code=204)
