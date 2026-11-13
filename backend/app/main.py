# Windows需要ProactorEventLoop支持asyncio subprocess — 小沈 2026-06-28
# 编辑历史:
# 2026-07-15 小欧 修复后台清理闭包命名撞车: 原内部闭包 cleanup_task 与 task_registry.cleanup_task(删单个任务)同名不同义, 违反清晰命名/KISS; 展平为模块级 _periodic_cleanup_loop 并保存 task 引用, shutdown 时 cancel
# 2026-07-28 - 小欧 - BUG#4: version.txt为空时get_version直奔for line in f, 无行进入时version未赋值致UnboundLocalError; 补version="0.0.0"默认值。
# 2026-08-03 - 小欧 - 恢复7-30原设计(DB核实): 删shutdown里的shell_pool.cleanup_all()+日志与import; 该行系8-02恢复工程误加回, 7-30已决策main.py不清理(atexit+task完成清理全覆盖)。
# 2026-08-08 - 小欧 - 全程统一本地时区: 3处异常响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-09 - 小欧 - task006 落地(日志级别优化): HTTP 4xx客户端错误与Validation(422)由ERROR降为WARNING, 5xx保持ERROR — 避免测试/非法请求噪音污染ERROR日志, 干扰真实故障排查
# 2026-08-10 - 小欧 - ⑬get_version改调get_code_root(): 定位version.txt改走代码库根(名实分离, 不再用项目根路径推算) — 步骤1实施(北京老陈驱动)
# 2026-08-12 - 小欧 - 注册 tool_routes router(工具测试路由由 health.py 迁出), include_router 加 /api/v1 tags=tools — 小欧 2026-08-12
# 2026-08-14 - 小欧 - 改名名实相符: model_routes→config_routes(import与挂载变量model_router→config_router); api/v1/chat/sse→execution_stream(chat_execution_router导入同步)
# 2026-08-14 - 小欧 - monitoring 独立为 app 顶层能力层目录(services/monitoring→app/monitoring), 本文件 import 路径同步
# 2026-08-16 - 小欧 - 注册 token_usage_router(token 四维度查询 API, 新建 app/api/v1/token_usage.py), include_router 加 /api/v1 tags=token-usage
# 2026-08-30 - 小欧 - 控制台写离线化(case09挂起根治): 启动 tip 两条 print→console_put(语义不变仅控制台, 非阻塞镜像), 事件循环线程零同步 stdout 写
# 2026-09-20 - 小沈 - v4.19 Phase 2: 注册 settings_router/model_router（/api/v1/settings /api/v1/models）
# 2026-09-21 - 小欧 - model_router 挂载 tags "model"→"models"（OpenAPI 分组标签）
# 2026-09-21 - 小欧 - v4.20 单源收敛: 启动日志 LLM 配置改读 ai.model_ref（删扁平 ai.provider/ai.model）
# 2026-09-22 小欧 - constants.py 配置化迁移：import DEFAULT_CORS_ORIGINS 改别名 + CORS 改读 tuning.network.cors_origins
# 2026-09-23 小欧 - 键名去 tuning 前缀：tuning.network.cors_origins → network.cors_origins（系统组，与调优无关）— 小欧-2026-09-23
# 2026-09-25 小欧 - ConnectionScope 连接池统一所有者：shutdown_event 的裸 reset() 改 await shutdown()——
#   原调用只清工厂换代不等共享池关闭，池归零由逐退休代 drain 兜底（超时放行不阻塞退出） — 小欧-2026-09-25
# 2026-09-26 小欧 - 全路由统一 token 鉴权（服务绑 0.0.0.0 是多机部署硬前提不可收窄，
#   原状态下局域网任意设备可直调任何接口：读走全部明文密钥、改擦密钥、越权读会话）。
#   鉴权细节与设计依据见 deps.py 文件头；_mount() 抽成唯一入口的理由见挂载点处注释。
# 2026-09-27 小欧 - 默认关闭 /docs /redoc /openapi.json（OMNIAGENT_ENABLE_API_DOCS=1 开启）：这三者是
#   **应用级**路由，不在任何 APIRouter 内，走不到 verify_token，实跑确认无 token 可拉走全部端点与模型。
#   / 的 docs 键同步条件化，避免广播一个必 404 的地址。访问口令路由改走 _mount()，不再手写
#   include_router 绕过唯一入口。_ENABLE_DOCS 改用 app.config.env_flag，不再手搓真值列表。
# 2026-09-27 小欧 - 启动自检：startup_event 调 deps.warn_startup_checks()，对"未收到
#   forwarded_allow_ips 注入"与"白名单含全网通配"告警。只观测，不改判定逻辑。
# 2026-09-29 小欧 - L0 僵尸任务收尾(北京老陈驱动): startup_event 调 storage.reconcile_orphaned_tasks, 收尾崩溃残留的 executing 残行(按 start_time<进程启动时刻判归属, 不误伤多 worker) — 小欧-2026-09-29
# 2026-09-29 小欧 - 挂 _start_journal_retention_task 定期清理超保留期的已终态事件；
#   退出时同生命周期 cancel（存引用防 GC）— 小欧 2026-09-29
# 2026-10-03 小欧 - startup_event 增 journal_steps_reconcile 一次性对账 Journal 事件与 chat_task_steps 步骤表;
#   只告警不自动补, 失败仅 warning 不阻断启动 — 小欧 2026-10-03
# 2026-10-03 - 小欧 - 笔误修正: _t4con 改回 _t_recon(与 _recon_n 配对的 reconcile 计时变量; 同批新增 _t4 串扰致误改, 读写一致故功能未坏)。
# 2026-10-21 小欧 - GZipMiddleware 显式 compresslevel=1（Starlette 默认 9）：文件树 20MB 响应
#   实测 level9 压 4~5 秒、level1 压 0.09 秒（体积 1.5MB vs 1.4MB，差别可忽略）— 小欧-2026-10-21
# 2026-10-15 - 小欧 - _periodic_cleanup_loop 内加 cleanup_expired_trust(会话信任 TTL 过期回收)。
#   独立 try: 与 cleanup_expired_tasks 无依赖, 信任表清理挂掉(如锁库)不得连带影响任务清理。
#   用 db.atxn 回调式(非 async with): 整段 with get_conn 跑在 to_thread 子线, 不占事件循环。— 小欧-2026-10-15
# 2026-10-21 小杨 - 挂 GZipMiddleware(minimum_size=2048): 文件树大 JSON 响应压缩(3.4MB→~0.4MB),
#   浏览器自动解压, 零协议改动 — 小杨-2026-10-21
# 2026-10-21 小欧 - compresslevel 1(Starlette 默认 9): 20MB 树响应实测 level9 压 4~5 秒、
#   level1 只要 0.09 秒且体积 1.5MB（13 倍压缩率已足够）—— 大 JSON 场景 level9 是纯亏 — 小欧-2026-10-21
# 2026-10-21 小欧 - GZipMiddleware 显式 compresslevel=1（Starlette 默认 9）：文件树 20MB 响应
#   实测 level9 压 4~5 秒、level1 压 0.09 秒（体积 1.5MB vs 1.4MB，差别可忽略）— 小欧-2026-10-21
# 2026-10-25 小欧 - 删模块级 uvicorn.access setLevel(WARNING) 与 import logging:
#   该句与 setup_uvicorn_loggers 冲突(访问日志须保留), 且被其无条件覆盖成死代码。
#   日志级别唯一 owner 收敛到 LogConfig。 — 小欧-2026-10-25
# 2026-10-25 小欧 - 日志级别热重载: 新增 _log_level_watcher_loop(10s 周期) + _start_log_level_watcher,
#   startup 起、shutdown cancel(同 _cleanup_task_ref 生命周期); refresh_log_levels 幂等重刷已装配 logger。
#   — 小欧-2026-10-25
# 2026-10-27 小欧 - 双击exe完整应用: 前端 dist 由 spec datas 塞入 _internal/web/, main.py 加
#   StaticFiles mount /assets + SPA catch-all fallback → 浏览器访问 http://127.0.0.1:8500 直接出前端页面,
#   /api/v1 同源无需 CORS, 一个端口搞定。源码调试模式读 ../frontend/dist/。
# 2026-10-29 小欧 - 访问日志噪音过滤: startup_event 调 install_access_noise_filter(),
#   探活+状态刷新高频轮询 access log 不再上屏落盘(零排障价值); dev/exe 两模式生效。 — 小欧-2026-10-29
# 2026-10-30 小欧 - 请求耗时埋点+ X-Request-Id 中间件(_RequestTimingMiddleware, 纯 ASGI),
#   给"前端 60s 超时"提供后端侧对账依据; 改后用纯 ASGI(不用 BaseHTTPMiddleware)并补异常穿出日志
#   reqId 日志 —— 理由见中间件定义处注释。 — 小欧-2026-10-30
# 2026-11-01 小欧 - 静态托管: 开发态不判任何目录(API-only 零告警); 打包态逐项验 assets 与 index.html,
#   缺哪项点名 error 且不挂载 — 小欧-2026-11-01
# 2026-11-01 20:10 小欧 - 静态托管收进打包态, 开发 8000 纯 API(root 404, 零 dist 引用) — 小欧-2026-11-01
# 2026-11-03 小欧 - 接 _start_monitoring_retention_task(每小时清 monitoring 超期数据,后台子线) + 启动期 chat_retention(读 system.chat_retention_days, 默认关闭), 均失败只告警不阻断 — 小欧-2026-11-03
# 2026-11-03 小欧 - 新增裸 /health 别名(与 /api/v1/health 同源一份真 JSON): 外部探针(opencode-cli 每30s打 /health)
#   在 dev 态原 404 刷屏、打包态被 spa_fallback 拿 index.html 假 200; 别名须注册在 _IS_FROZEN catch-all 之前 — 小欧-2026-11-03
# 2026-11-03 小欧 - http_exception_handler 4xx 全降 INFO(客户端请求不合法/资源不存在, 非服务端故障)、
#   5xx 保持 ERROR; 422 校验错误同降 INFO。原 probe-404 特例随之删除 — 小欧-2026-11-03
# 2026-11-03 21:30 小欧 - 四处后台任务 create_task→spawn_bg(强引用防 GC 收口, shutdown 仍按引用 cancel) — 小欧-2026-11-03
# 2026-11-04 小欧 - 预热: startup 预建默认线程池(新增 threading/ThreadPoolExecutor import),
#   非 shell 同步工具 asyncio.to_thread 运行期不再在事件循环线程懒建 Thread.start(同 shell 卡死病灶另一半) — 小欧-2026-11-04
# 2026-11-04 小欧 - shell 卡死根治(启动期): startup 最早处 install_spawn_gate()(CreateProcess × Thread.start 闸门,
#   有界等待+快速失败); 串行预热 ps7/ps5 可执行体(prewarm_shell_binaries, 首次 CreateProcessW 移出请求路径);
#   启动收尾 mark_runtime_started()(此后 Thread.start 计入 /health.runtime_thread_starts, 应为 0) — 小欧-2026-11-04
# 2026-11-04 小欧 - 线程源清零(第五版): anyio worker 池预热 40 + MAX_IDLE_TIME 10s→24h(同步端点原空闲即回收重建),
#   db-txn/browse-probe 线程池建满(ThreadPoolExecutor 懒建即运行期 Thread.start); 与闸门可回收租约配套 — 小欧-2026-11-04
# 2026-11-06 小欧 - 附件域路由挂载(重建): import attachments/material_packs 路由, _mount 挂载
#   /api/v1/attachments(上传/列表/详情/删除/collect/local) 与 /api/v1/material-packs(CRUD), 走统一 token 鉴权 — 小欧-2026-11-06
# 2026-11-08 小欧 - startup 接老 capabilities 一次性迁移(幂等, 无残留零改动; 先于配置读取) — 小欧-2026-11-08
# 2026-11-08 小欧 - startup 补调 setup_uvicorn_loggers(): 裸 uvicorn 与 run_server.py 同一收口
#   (只落盘不上屏); 否者 dictConfig console handler 残留 + 10s 热重载刷 DEBUG 必刷屏 — 小欧-2026-11-08
# 2026-11-13 商量 - startup 缓存主事件循环给 shell_background(工作线程后台命令完成后
#   run_coroutine_threadsafe 提交回主循环唤醒) — 商量-2026-11-13
# 2026-11-13 商量 - shutdown_event 关闭前杀全部后台进程树(主循环关闭致等待协程被取消,
#   不主动杀则子进程脱离父进程存活成孤儿); startup 清理上一世后台结果产物(重启后注册表为空,
#   惰性清理覆盖不到致磁盘残留) — 商量-2026-11-13
# 注: shell_background 必须"函数体内 import"——该模块 import 时即创建 WorkerPool 常驻线程
#   (有副作用), 提到文件顶部会让任何 import main 的场景(测试/脚本)连带起线程, 副作用外泄
import asyncio
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import anyio  # 2026-11-04 小欧: anyio worker 池预热(同步端点承载), 消除运行期 Thread.start

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Windows PowerShell 5.1中文输出编码修复 — 小欧 2026-07-07
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python -u模式下可能抛AttributeError，忽略
        pass

import os
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import (
    GZipMiddleware,  # 2026-10-21 小杨 - 文件页大 JSON 降量（树 3.4MB→~0.4MB）
)
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders  # 2026-10-30 小欧: 纯 ASGI 计时中间件回写响应头
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import health, messages, metrics, sessions

# 2026-11-04 小欧 - 附件上传/列表/详情/删除 + 素材包 CRUD 路由（重建后重启挂载） — 小欧-2026-11-06
from app.api.v1.attachments import router as attachments_router

# 2026-09-26 小欧 - 访问口令设置路由（首次设置豁免在 deps.verify_token 内）
from app.api.v1.auth_routes import router as auth_router
from app.api.v1.chat import execution_stream as chat_execution_router
from app.api.v1.chat import router as chat_router
from app.api.v1.chat import task_router
from app.api.v1.config_routes import router as config_router

# 2026-09-26 小欧 - 统一 token 鉴权依赖（12 个 router 挂载，/health 豁免）
from app.api.v1.deps import verify_token, warn_startup_checks
from app.api.v1.file_routes import (
    router as file_router,  # 2026-10-13 小欧: 文件浏览底座 — 小欧-2026-10-13
)

# 2026-11-07 小欧 - 同机文件系统路由(磁盘列表/授权目录), 「我的电脑」自研浏览器底座 — 小欧-2026-11-07
from app.api.v1.fs_routes import router as fs_router
from app.api.v1.material_packs import router as material_packs_router
from app.api.v1.model_routes import router as model_router
from app.api.v1.settings_routes import router as settings_router
from app.api.v1.task_queries import router as task_queries_router
from app.api.v1.token_usage import (
    router as token_usage_router,  # token 四维度查询 API — 小欧 2026-08-16
)
from app.api.v1.tool_routes import (
    router as tool_routes_router,  # 工具测试路由迁出 health.py — 小欧 2026-08-12
)
from app.config import env_flag, get_code_root, get_config
from app.constants import DEFAULT_CORS_ORIGINS as _D_CORS
from app.db import db
from app.logger import logger
from app.logger.shared_handler import (  # 2026-10-29 小欧: /health + /v1/models 访问日志噪音过滤; 2026-11-08 小欧补 setup_uvicorn_loggers(裸 uvicorn 同样收口 uvicorn 三 logger 只落盘不上屏)
    install_access_noise_filter,
    setup_uvicorn_loggers,
)
from app.monitoring import setup_monitoring
from app.safety.trust_db import cleanup_expired_trust  # 2026-10-15 小欧: 过期会话信任回收(TTL)
from app.services.chat.storage import (
    reconcile_orphaned_tasks,  # L0 启动期僵尸任务收尾(chat_tasks 状态单一 owner) — 小欧 2026-09-29
)

# 2026-11-08 小欧 - 启动一次性迁移老 capabilities 到 input/output 双维度(幂等)
from app.services.model.model_service import migrate_legacy_capabilities
from app.services.task.task_registry import cleanup_expired_tasks
from app.tools import ensure_tools_registered
from app.tools.fundamental.shell_engine import (
    prewarm_shell_binaries,  # 启动期预热 ps7/ps5 — 2026-11-04 小欧
)
from app.utils.background_tasks import (
    spawn_bg,  # 2026-11-03 小欧: 后台任务统一存引用防 GC(与 middleware 同源)
)
from app.utils.spawn_gate import (  # 2026-11-04 小欧: 进程×线程创建闸门
    install_spawn_gate,
    mark_runtime_started,
)
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区


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

# 2026-09-27 10:15 小欧 - 关闭应用级 API 文档端点（修鉴权缺口）：/docs /redoc /openapi.json
#   是**应用级路由**，不在任何 APIRouter 内，走不到 verify_token —— 实跑确认无 token 可拉走 57 个端点
#   + 44 个请求模型。本机开发需查看时设 OMNIAGENT_ENABLE_API_DOCS=1（多机部署下别开）。
#   布尔解析复用 config.env_flag（假值列表统一单点），不手搓真值列表。
_ENABLE_DOCS = env_flag("OMNIAGENT_ENABLE_API_DOCS")
app = FastAPI(
    title="OmniAgentAst API",
    description="OmniAgentAst 桌面版后端API",
    version=app_version,
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
)
if not _ENABLE_DOCS:
    logger.info("API 文档端点已关闭（如需本地查看设置：OMNIAGENT_ENABLE_API_DOCS=1）")

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

  # 2026-10-21 小杨 - 文件页大 JSON 降量（第一步）：
  #   GZipMiddleware 对大响应（树 3.4MB→~0.4MB）压缩 ~10 倍，浏览器自动解压，零协议改动。
app.add_middleware(GZipMiddleware, minimum_size=2048, compresslevel=1)

# 2026-10-30 小欧 - 请求耗时埋点 + X-Request-Id 前后端对账
#   为什么: 前端 60s 超时提示原无法归因 —— 后端只记 4xx/5xx, 成功的慢请求(如 12s 的
#   /files/tree)零痕迹, 出事只能靠猜。本中间件给每个响应回 X-Request-Id, 且只对 >3s
#   的请求落一条 [slow] 日志(不刷屏)。
#   已知限制: 响应头只能在 response.start 时写, 超时/断连的请求前端收不到该头 —— req=
#   只对 4xx/5xx 与成功请求可用, 超时场景靠 URL+耗时+时间窗对账。
#   两处修正(2026-10-30 小欧):
#     不能用 @app.middleware("http")(BaseHTTPMiddleware): 它会为每个请求再起一个任务、
#       用内存流搬运 body, 而本应用的 SSE 断连清理完全依赖 client-disconnect 传到 reader
#       生成器(GeneratorExit → deactivate); 多一层搬运等于给这条链加不确定延迟, 且长连接
#       会长期占住这层的内存流。改成纯 ASGI(只包 send, 零缓冲零额外任务), 写法同
#       monitoring/middleware.py(DRY/KISS-DIRECT)。
#     补"异常逃出 app"的路径: 路由内异常本就被 general_exception_handler 转成正常 500 响应
#       (头照写、[slow] 照记); 但中间件自身或流式 body 迭代期抛的异常会直接穿出本层 —— 无论
#       响应头是否已发, 都落一条带 reqId+耗时的 [error] 日志(head= 标明头是否已发出), 再原样
#       抛出(异常处理权仍归外层, 不吞)。
#   计时口径: 量到 response.start(TTFB)即停 —— SSE 连接可能挂数小时, 按总时长落 [slow] 会把
#     每条长连接都记成慢请求(纯噪声); 排障要看的本来就是"客户端等了多久才见首字节"。
_SLOW_REQUEST_SECONDS = 3.0
_REQUEST_ID_LEN = 12


class _RequestTimingMiddleware:
    """响应头回 X-Request-Id + 首字节耗时留痕(纯 ASGI) — 小欧 2026-10-30"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = uuid.uuid4().hex[:_REQUEST_ID_LEN]
        method = scope.get("method", "-")
        path = scope.get("path", "-")   # 只记 path, 不记 query(可能含凭据)
        _t0 = time.perf_counter()
        _logged = False

        async def _send(message):
            nonlocal _logged
            if message["type"] == "http.response.start" and not _logged:
                _logged = True
                _elapsed = time.perf_counter() - _t0
                MutableHeaders(scope=message)["X-Request-Id"] = rid
                if _elapsed >= _SLOW_REQUEST_SECONDS:
                    logger.warning(
                        f"[slow] {method} {path} {message['status']} "
                        f"{_elapsed:.1f}s req={rid}"
                    )
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as _e:
            # 只有异常**穿出** app 时才会到这里(路由内异常已被 general_exception_handler 转成 500 响应):
            #   响应头可能已发(流式 body 迭代期抛), 也可能未发 —— 两种情况都必须留一条带 reqId 的日志,
            #   否则最需要 reqId 的"SSE 中途炸"反而留白。head= 标明头是否已发出, 供前端按时间窗对账。
            logger.error(
                f"[error] {method} {path} {type(_e).__name__}: {_e} "
                f"{time.perf_counter() - _t0:.1f}s "
                f"head={'sent' if _logged else 'none'} req={rid}"
            )
            raise


app.add_middleware(_RequestTimingMiddleware)

setup_monitoring(app)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 记录请求路径/方法/客户端, 便于定位 404 等异常的真正来源(原日志仅记状态码, 无法定位) — 小欧 2026-07-13
    client = request.client.host if request.client else "unknown"
    # 2026-11-03 小欧 - 4xx 一律 INFO(客户端请求不合法/资源不存在, 非服务端故障, 不该占 WARNING 刷屏);
    #   5xx 保持 ERROR(真实故障)。原 probe-404 特例随 4xx 全降而失效, 一并删除 — 小欧-2026-11-03
    _log = logger.info if exc.status_code < 500 else logger.error
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
    # 2026-11-03 小欧 - 422 恒为客户端参数错误, 由 WARNING 降 INFO(不占真故障档位, 不进控制台) — 小欧-2026-11-03
    logger.info(f"Validation Error: {exc.errors()}")
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


# 全路由统一挂 token 鉴权。抽 _mount() 为唯一挂载入口:
#   原写法把 `prefix="/api/v1"` 与 `dependencies` 在 13 行各手写一遍 —— 改前缀必漏改（漏改=该 router
#   挂在错误路径 404），且未来新增 router 谁记得手写 dependencies=？（漏写则该 router 裸奔）。
#   抽成一处后豁免必须显式写 exempt=True，反而更醒目。零行为变化。
_AUTHENTICATED = [Depends(verify_token)]


def _mount(router, tags: str, *, exempt: bool = False) -> None:
    """统一挂载 API router：**默认加 token 鉴权**，仅探活类显式 exempt=True 豁免。

    全项目唯一挂载入口。新增 router 一律走本函数即自动获得鉴权，
    不再依赖"记得手写 dependencies="（那是本条规则最大的失效来源）。
    """
    app.include_router(
        router,
        prefix="/api/v1",
        tags=[tags],
        dependencies=None if exempt else _AUTHENTICATED,
    )


# 探活/回显豁免（便于探活与排障）。/echo 与 /health 同属 health router 且为
# 纯回显无副作用（已读 health.py:68-76 核实：不落库、不调 LLM），故同享豁免无实际风险。
_mount(health.router, "health", exempt=True)
_mount(tool_routes_router, "tools")  # 工具测试路由 — 小欧 2026-08-12
# 2026-10-13 小欧 - 文件浏览路由走 _mount()（自动获得 token 鉴权，勿手写 include_router）
_mount(file_router, "files")
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
_mount(token_usage_router, "token-usage")  # token 四维度查询 API — 小欧 2026-08-16
# 2026-09-27 小欧 - 访问口令路由改走 _mount()：原为绕过唯一入口而手写 include_router，
#   与上方"新增 router 漏 dependencies= 是最大失效来源"的论证自相矛盾。
#   豁免判定（首设自举/只能本机改口令）全在 deps.verify_token 内，与挂载方式无关。
_mount(auth_router, "auth")
# 2026-11-04 小欧 - 附件上传/列表/详情/删除/导入 + 素材包 CRUD（重建后挂载；走 token 鉴权） — 小欧-2026-11-06
_mount(attachments_router, "attachments")
_mount(material_packs_router, "material-packs")
# 2026-11-07 小欧 - 同机文件系统(磁盘/授权目录); 端点内部再判同机, 跨机 403 — 小欧-2026-11-07
_mount(fs_router, "fs")


# ── 前端静态文件服务（2026-10-27 小欧 双击exe完整应用）──
# 2026-11-01 小欧 - 静态托管仅打包态(exe); 开发态 8000 纯 API, 不解析 dist — 小欧-2026-11-01
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_IS_FROZEN = getattr(sys, "frozen", False)
_WEB_DIR = _ASSETS_DIR = _INDEX_HTML = None   # 开发态不解析任何 dist 路径 — 小欧 2026-11-01
if _IS_FROZEN:
    _WEB_DIR = Path(sys._MEIPASS) / "web"       # 打包态: spec datas 铺在 _internal/web/
    # 2026-11-01 小欧 - 全仓只有 assets 缺失会导致崩溃: StaticFiles.__init__ 抛 RuntimeError;
    #   index.html 缺失只是 FileResponse 打空, 请求期兜住即可(见下方打包态逐项验) — 小欧-2026-11-01
    _ASSETS_DIR = _WEB_DIR / "assets"
    _INDEX_HTML = _WEB_DIR / "index.html"


_cleanup_task_ref: Optional[asyncio.Task] = None  # 后台清理循环 task 引用, 供 shutdown 时 cancel
_journal_retention_ref: Optional[asyncio.Task] = None  # [63] 3.6.7 Journal 清理 task 引用, 供 shutdown 时 cancel（同 _cleanup_task_ref 模式）


async def _periodic_cleanup_loop() -> None:
    """后台周期清理循环: 每 3600s 调用 task_registry.cleanup_expired_tasks 兜底清理过期任务
       命名与 task_registry.cleanup_task(删单个任务) 区分, 避免混淆 (清晰命名/KISS)
    """
    while True:
        try:
            await cleanup_expired_tasks()
        except Exception as e:
            logger.error(f"清理过期任务失败: {e}")
        # 2026-10-15 小欧 - 会话信任 TTL 过期回收。
        #   独立 try: 信任表清理挂掉(如锁库)不得连带影响上方任务清理(两者无依赖)。
        #   atxn 是回调式(非 async with): 整段 with get_conn 跑在 to_thread 子线, 不占事件循环。
        try:
            _n = await db.atxn("chat", lambda conn: cleanup_expired_trust(conn))
            if _n:
                logger.info(f"清理过期会话信任 {_n} 条")
        except Exception as e:
            logger.error(f"清理过期会话信任失败: {e}")
        await asyncio.sleep(3600)


def _start_cleanup_task() -> None:
    """启动后台周期清理任务 — 小沈 2026-06-08; 闭包展平+改名 小欧 2026-07-15"""
    global _cleanup_task_ref
    _cleanup_task_ref = spawn_bg(_periodic_cleanup_loop())  # 2026-11-03 小欧: 强引用防 GC 收口 spawn_bg
    logger.info("后台清理任务已启动")


def _start_journal_retention_task() -> None:
    """Journal 保留期清理：独立后台任务，绝不进请求链路 — 小欧 2026-09-29"""
    global _journal_retention_ref
    from app.services.chat.stream_event_journal import checkpoint_wal, retention_cleanup
    async def _loop() -> None:
        while True:
            try:
                n = await retention_cleanup(get_config().get("tuning.live_front.journal_retention_days", 7))
                if n:
                    logger.info(f"[Journal] 清理已终态过期事件 {n} 个 task")
            except Exception as exc:            # 清理失败只 warning，不阻断聊天主链路
                logger.warning(f"[Journal] retention 清理失败: {exc}")
            try:
                # 顺带做一次 WAL checkpoint：自动 checkpoint 阈值约 1000 页，写够就同步一次，
                # 实测会把单帧落库卡到 0.6~1.1s。挪到空闲期做，尖峰只留在清理那一刻
                ck = await checkpoint_wal()
                if ck:
                    logger.info(f"[Journal] WAL checkpoint busy={ck.get('busy')} pages={ck.get('log')}/{ck.get('wal')}")
            except Exception as exc:
                logger.warning(f"[Journal] WAL checkpoint 失败: {exc}")
            await asyncio.sleep(3600)
    _journal_retention_ref = spawn_bg(_loop())   # 2026-11-03 小欧: 强引用防 GC 收口 spawn_bg(shutdown 仍按此引用 cancel)
    logger.info("Journal 保留期清理任务已启动")


_monitoring_retention_ref = None  # xiaoou 2026-11-03: monitoring retention task ref


def _start_monitoring_retention_task() -> None:
    """monitoring.db retention cleanup: independent background task, never on request path - xiaoou 2026-11-03"""
    global _monitoring_retention_ref
    async def _loop() -> None:
        while True:
            try:
                from app.monitoring import storage as _mon_storage
                n = await _mon_storage.retention_cleanup_monitoring(
                    http_days=7, metrics_days=7, task_days=30, llm_days=30)
                if n and any(v for v in n.values()):
                    logger.info("[Monitoring] retention cleanup: %s" % n)
            except Exception as exc:
                logger.warning("[Monitoring] retention cleanup failed (degrade): %r" % exc)
            await asyncio.sleep(3600)
    _monitoring_retention_ref = spawn_bg(_loop())   # 2026-11-03 小欧: 强引用防 GC 收口 spawn_bg
    logger.info("Monitoring retention cleanup task started")


async def _log_level_watcher_loop() -> None:
    """日志级别热重载: 周期检查 config 并重刷已装配 logger 级别 — 小欧 2026-10-25
    config.yaml 的 logging.debug / logging.level 改动后, 最迟一个周期内生效, 免重启。
    get_config() 内置 mtime 缓存, 未变则零成本; refresh_log_levels 幂等, 未变则零操作。
    """
    from app.logger.shared_handler import refresh_log_levels
    while True:
        await asyncio.sleep(10)
        try:
            refresh_log_levels()
        except Exception as e:
            logger.error(f"[Logger] 级别热重载失败: {e}")


_log_watcher_ref: Optional[asyncio.Task] = None  # 同 _cleanup_task_ref 模式, 供 shutdown cancel


def _prewarm_loop_default_executor() -> None:
    """启动期预热 loop 默认线程池: 阻塞任务逐个逼建满 worker, Thread.start 全部发生在启动期循环线程。
    非 shell 同步工具经 asyncio.to_thread 走此池, 运行期不再热路径懒建线程(与 shell 执行器同一病因)。— 小欧 2026-11-04"""
    _n = min(32, (os.process_cpu_count() or 1) + 4)   # 与 CPython 默认 executor 的 max_workers 同式, 容量语义不变
    _block = threading.Event()
    _ex = ThreadPoolExecutor(max_workers=_n, thread_name_prefix="tool-sync")
    for _ in range(_n):
        _ex.submit(_block.wait, 10)   # 阻塞任务使 idle 计数归零, 逐次强制 spawn 至建满
    _block.set()   # 立即放行, worker 后台自行收尾
    asyncio.get_running_loop().set_default_executor(_ex)
    logger.info(f"[启动耗时] 默认线程池预热: {_n} workers 已建满(tool-sync)")


def _prewarm_executor_pool(ex: ThreadPoolExecutor, n: int, label: str) -> None:
    """把 ThreadPoolExecutor 的 worker 提前建满: 懒建 = 运行期 Thread.start = 闸门热点 — 小欧 2026-11-04"""
    _block = threading.Event()
    for _ in range(n):
        ex.submit(_block.wait, 10)
    _block.set()
    logger.info(f"[启动耗时] {label} 预热: {n} workers 已建满")


async def _prewarm_anyio_workers() -> None:
    """预热 anyio 工作线程池 + 取消 10s 空闲回收 — 小欧 2026-11-04

    同步端点(file_routes 等 def 端点)由 anyio 线程池承载; 原 MAX_IDLE_TIME=10s, 空闲即回收、
    下次请求重建 = 运行期 Thread.start, 与 CreateProcess 抢 loader lock(11:28 的 16 条 AnyIO 超时即此)。
    """
    try:
        from anyio._backends._asyncio import WorkerThread
    except Exception as e:              # anyio 换实现: 预热失效但绝不能拖垮启动
        logger.error(f"[启动预热] anyio 内部结构不可用, 运行期仍可能建线程: {e}")
        return
    WorkerThread.MAX_IDLE_TIME = 86400   # 24h: 等价于"不回收", 线程常驻
    _n = 40                              # anyio 默认 CapacityLimiter 上限
    _base = threading.active_count()
    _gate = threading.Event()

    async def _hold() -> None:
        await anyio.to_thread.run_sync(_gate.wait, 10)

    _tasks = [asyncio.create_task(_hold()) for _ in range(_n)]
    _t0 = time.monotonic()
    while threading.active_count() < _base + _n and time.monotonic() - _t0 < 10:
        await asyncio.sleep(0.02)
    _gate.set()                          # 放行阻塞, worker 归还池
    await asyncio.gather(*_tasks, return_exceptions=True)
    logger.info(f"[启动耗时] anyio 预热: {threading.active_count() - _base} workers 新增, "
                f"MAX_IDLE_TIME={WorkerThread.MAX_IDLE_TIME}s")


def _start_log_level_watcher() -> None:
    """启动日志级别热重载后台任务 — 小欧 2026-10-25"""
    global _log_watcher_ref
    _log_watcher_ref = spawn_bg(_log_level_watcher_loop())   # 2026-11-03 小欧: 强引用防 GC 收口 spawn_bg


@app.on_event("startup")
async def startup_event():
    """应用启动时注册工具 + 启动后台任务 — 小健 2026-06-18 内联透传函数"""
    # 2026-11-03 小欧 - 删函数内 `import time as _time`(模块级已有 import time, 重复导入违反 DRY):
    #   本函数内 13 处调用同步改回 time.* — 小欧-2026-11-03
    _t0 = time.time()
    # 2026-11-04 小欧 - 进程×线程创建闸门: 必须在任何运行期并发开始前装好(有界等待, 超限快速失败)
    install_spawn_gate()
    # 2026-11-13 商量 - 缓存主事件循环 + 注册后台完成通知路由(services 层回调, 防 tools→services 越层)
    from app.services.chat.bg_shell_notifier import notify_bg_shell_done
    from app.tools.fundamental.shell_background import set_main_loop, set_notify_router
    set_main_loop(asyncio.get_running_loop())
    set_notify_router(notify_bg_shell_done)
    # 2026-11-13 商量 - 启动期清理上一世后台结果产物: 结果惰性清理只走注册表, 重启后注册表为空,
    #   上一世的 .log/.bat 永不会被清 → 磁盘残留泄漏; 此处一次性收口(只动 bgsh_* 命名空间)
    from app.tools.fundamental import shell_background as _shell_bg
    _n_orphan = _shell_bg.cleanup_orphan_artifacts(time.time())
    if _n_orphan:
        logger.info(f"[启动] 清理后台孤儿结果产物 {_n_orphan} 个")
    # 2026-10-29 小欧: /health 探活 + /v1/models 模型列表高频轮询访问日志去噪(零排障价值, dev/exe 两模式生效)
    install_access_noise_filter()
    # 2026-11-08 小欧 - startup 补调 setup_uvicorn_loggers(): 裸 uvicorn 与 run_server 同一收口(只落盘不上屏),
    #   根治 dictConfig console handler 残留被 10s 热重载刷 DEBUG 刷屏 — 小欧-2026-11-08
    setup_uvicorn_loggers()
    # 2026-11-08 小欧: 老 capabilities 一次性迁移(先于任何配置读取; 幂等, 无残留零改动)
    migrate_legacy_capabilities()
    # 2026-11-04 小欧 - 预热 ps7/ps5 可执行体: 首次 CreateProcessW(Defender 扫描)挪到启动期,
    #   请求路径不再冷启动; 必须在预热线程池之前串行跑完, 不与任何 Thread.start 并发。
    _t_shell = time.time()
    prewarm_shell_binaries()
    logger.info(f"[启动耗时] prewarm_shell_binaries: {time.time()-_t_shell:.3f}s")
    # 2026-11-04 小欧 - R1: 预热线程池必须在任何后台任务/请求动用 executor 前建满
    _prewarm_loop_default_executor()
    # 2026-11-04 小欧 - 线程源清零: anyio 池长驻+预热(同步端点), db/probe 池建满(懒建=运行期 Thread.start)
    await _prewarm_anyio_workers()
    from app.monitoring.loop_watchdog import prewarm as prewarm_loop_watchdog
    prewarm_loop_watchdog()   # 首个 SSE reader 原会在运行期建线程, 收口到启动期 — 小欧 2026-11-04
    from app.db.database import _DB_TXN_POOL
    _prewarm_executor_pool(_DB_TXN_POOL, _DB_TXN_POOL._max_workers, "db-txn")
    from app.file_browse.browse_service import _probe_pool
    _prewarm_executor_pool(_probe_pool, _probe_pool._max_workers, "browse-probe")
    # 进程启动时刻（ISO）：L0 僵尸收尾的归属判据，只收尾 start_time 早于本值的残行，
    # 只收尾"本进程启动之前创建"的行：防御性护栏，防有人误起第二个后端进程时误伤对方任务 — 小欧 2026-09-29
    _boot_iso = get_local_iso_timestamp()
    db.init()
    logger.info(f"[启动耗时] db.init: {time.time()-_t0:.3f}s")
    # L0 僵尸任务收尾：崩溃遗留的 executing 残行改终态，不让任务列表永远显示"执行中" — 小欧 2026-09-29
    _t_recon = time.time()
    _recon_n = await db.atxn("chat", lambda c: reconcile_orphaned_tasks(c, _boot_iso))
    if _recon_n:
        logger.warning(f"[启动] 收尾僵尸任务 {_recon_n} 个（上次进程中断残留，已标 failed/task_interrupted）")
    logger.info(f"[启动耗时] reconcile_orphaned_tasks({_recon_n} 行): {time.time()-_t_recon:.3f}s")
    _t1 = time.time()
    ensure_tools_registered()
    logger.info(f"[启动耗时] ensure_tools_registered: {time.time()-_t1:.3f}s")
    _t2 = time.time()
    _start_cleanup_task()
    logger.info(f"[启动耗时] _start_cleanup_task: {time.time()-_t2:.3f}s")
    _start_journal_retention_task()   # [63] 3.6.7：Journal 保留期清理；保留期读 tuning.live_front 配置
    _start_monitoring_retention_task()  # 2026-11-03 xiaoou: monitoring.db retention (http/metrics 7d, task/llm 30d), never on request path
    # 2026-11-03 小欧 - chat_retention 启动参数: 只读 system.chat_retention_days(删已迁移旧键回退, 禁 backward),
    #   复用模块级 os, get_config() 单次; int() 失败降级 0 仅告警, 不让坏 env 抛穿启动 — 小欧-2026-11-03
    _retention_raw = (os.getenv('OMNIAGENT_CHAT_RETENTION_DAYS')
                      or get_config().get('system.chat_retention_days', 0) or 0)
    try:
        _chat_retention_days = int(_retention_raw)
    except (TypeError, ValueError):
        logger.warning(f"[chat_retention] 保留天数值非法({_retention_raw!r}), 本轮不清理(降级)")
        _chat_retention_days = 0
    if _chat_retention_days > 0:
        try:
            from app.services.chat.chat_retention import retention_cleanup_chat as _crc
            _n = await _crc(_chat_retention_days)
            logger.info('[chat_retention] startup sweep deleted %d sessions (retention=%d days)' % (_n, _chat_retention_days))
        except Exception as _exc:
            logger.warning('[chat_retention] startup sweep failed (degrade): %r' % _exc)
    _start_log_level_watcher()   # 2026-10-25 小欧: 日志级别热重载, config 改动免重启
    # 2026-10-03 小欧 - 启动期一次性对账 Journal 事件与 chat_task_steps 步骤表, 只告警不自动补
    _t4 = time.time()
    try:
        from app.services.chat.stream_event_journal import journal_steps_reconcile as _reconcile
        for _bad in await _reconcile():
            logger.error(f"[Reconcile] Journal({_bad['journal_frames']}帧) vs steps"
                         f"({_bad['step_rows']}行) 不一致: task={_bad['task_id']} —— "
                         f"步骤已落库但 Journal 缺帧, 该任务重连回放将缺内容")
    except Exception as exc:            # 对账失败只 warning, 不阻断启动(同 retention_cleanup 降级范式)
        logger.warning(f"[Reconcile] Journal/steps 对账失败: {exc}")
    logger.info(f"[启动耗时] journal_steps_reconcile: {time.time()-_t4:.3f}s")
    # 鉴权配置自检（未注入 forwarded_allow_ips / 白名单全网通配 → 告警），只观测不改判定
    _t3 = time.time()
    warn_startup_checks()
    logger.info(f"[启动耗时] warn_startup_checks: {time.time()-_t3:.3f}s")
    logger.info(f"[启动耗时] startup_event 合计: {time.time()-_t0:.3f}s")
    # 启动期结束: 之后任何 Thread.start 都计入 runtime_thread_starts(/health 暴露), 应为 0 — 2026-11-04 小欧
    mark_runtime_started()
    from app.logger.console_writer import (
        console_put,  # 小欧 2026-08-30 启动tip离线化(语义不变仅控制台)
    )
    console_put(f"当前版本: {app_version}")
    _cfg = get_config()
    _ref = _cfg.get('ai.model_ref') or {}
    console_put(f"LLM 配置: provider={_ref.get('provider')}, model={_ref.get('model')}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源 — 小健 2026-06-18 内联透传函数; 补充 cancel 清理循环 小欧 2026-07-15"""
    # 2026-11-13 商量 - 关闭先杀全部后台进程树: 主循环关闭会使等待协程被取消, 不主动杀则子进程
    #   脱离父进程继续存活(Windows 父死子不重挂)→ 跨重启孤儿; 同步收口, shutdown 允许短暂阻塞
    from app.tools.fundamental.shell_background import kill_all_background
    _n_bg = kill_all_background("shutdown")
    if _n_bg:
        logger.warning(f"[shutdown] 已终止 {_n_bg} 个后台进程, 防孤儿跨重启")
    global _cleanup_task_ref
    if _cleanup_task_ref is not None and not _cleanup_task_ref.done():
        _cleanup_task_ref.cancel()
    if _journal_retention_ref is not None and not _journal_retention_ref.done():   # [63] 3.6.7 关联：新增任务与 _cleanup_task_ref 同生命周期
        _journal_retention_ref.cancel()
    if _monitoring_retention_ref is not None and not _monitoring_retention_ref.done():   # 2026-11-03 xiaoou
        _monitoring_retention_ref.cancel()
    if _log_watcher_ref is not None and not _log_watcher_ref.done():   # 2026-10-25 小欧: 日志级别热重载任务同生命周期
        _log_watcher_ref.cancel()
    # 停机收口(小欧 2026-09-25): 换代归还 + 等退休代共享池 lease 归零关闭(超时放行)
    from app.services.lifecycle import shutdown
    await shutdown()


@app.get("/")
async def root():
    # 2026-11-01 小欧 - 开发态 root 严谨 404(纯 API, 页面走 5173); 打包态出页面 — 小欧-2026-11-01
    if _IS_FROZEN:
        if _INDEX_HTML.is_file():   # 只防 FileResponse 打不存在的文件(发送期抛未处理异常→500) — 小欧-2026-11-01
            return FileResponse(str(_INDEX_HTML))
        # docs 键随 _ENABLE_DOCS 条件化: 关闭时无条件返回即对外广播一个必 404 的地址 — 小欧 2026-09-27
        return {
            "message": "OmniAgentAst API",
            "version": app_version,
            **({"docs": "/docs"} if _ENABLE_DOCS else {}),
        }
    return JSONResponse(status_code=404, content={"detail": "开发环境是纯 API 端口；前端页面请走 http://localhost:5173"})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # 浏览器自动请求 favicon 时返回 204，避免 main.py:87 全局异常处理器记录 404 噪声 — 小欧 2026-07-13
    return Response(status_code=204)


@app.get("/health", response_model=health.HealthResponse, include_in_schema=False)
async def health_alias(request: Request):
    # 2026-11-03 小欧 - 裸 /health 别名同源真 JSON(dev 态探针404刷屏根治); 须在 _IS_FROZEN catch-all 前注册 — 小欧-2026-11-03
    return await health.build_health_response(request.headers.get("host", ""))


# ── SPA fallback: 非 /api 非 /assets 路径全部返回 index.html（React Router 接管）──
# 注册在所有精确路由之后，API 请求先被精确匹配，不会误入此 handler。
# 2026-10-27 小欧 双击exe完整应用: 前端 dist 由 spec datas 塞入 _internal/web/
# 2026-11-01 小欧 - 静态托管收进打包态; 开发态纯 API, 零 dist 引用零告警 — 小欧-2026-11-01
_STATIC_MOUNTED = False
if _IS_FROZEN:
    _missing_web: list[str] = []                 # 打包态逐项验 assets/ 与 index.html
    if not _ASSETS_DIR.is_dir():
        _missing_web.append(str(_ASSETS_DIR))
    if not _INDEX_HTML.is_file():
        _missing_web.append(str(_INDEX_HTML))
    for _p in _missing_web:
        logger.error(f"[前端] 打包缺文件, 前端不可用: {_p}")
    if not _missing_web:
        try:
            app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="static-assets")
            _STATIC_MOUNTED = True
            logger.info(f"前端静态目录已定位: {_WEB_DIR}")
        except RuntimeError as exc:
            logger.error(f"[前端] 打包态静态挂载失败: {exc}")
    if _STATIC_MOUNTED:
        # 只在 /assets 真挂上时才注册 catch-all: 否则 /assets/*.js 会落到这里拿到 HTML,
        # 浏览器按 text/html 解析 JS → 报错比 404 更难查 — 小欧-2026-11-01
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str):
            """前端 SPA catch-all: 浏览器路由(/chat /files /settings)返回 index.html; 文件不在则回 404 JSON。"""
            if not _INDEX_HTML.is_file():
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"前端页面资源缺失: {_INDEX_HTML}"},
                )
            return FileResponse(str(_INDEX_HTML))
