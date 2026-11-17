
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - merged from health/ 3 files, only changed import paths
# 2026-07-23 - 小欧 - 修复: health check 加真实DB连接验证(chat/operations/task_tracker)
#   【病根】health check 始终返回"healthy", 不检查DB就绪状态, 无法发现表缺失/连接异常
#   【改法】遍历三库执行SELECT 1 + sqlite_master查表数, 任一失败则db_status="degraded"
#   【合规】SRP(health只检查状态不修改)+KISS-DIRECT(直接连库查,不引入复杂健康指标)
# 2026-07-28 - 小欧 - BUG#18: 删sqlite_master无用查询(SELECT COUNT(*)结果未赋值未使用); BUG#22: echo路由参数request改名data(避免与FastAPI内置Request类型变量混淆); BUG#23: 删死协程检查(iscoroutine永远为False, run_in_executor内同步函数不返回协程); 额外: list_tools中required_set预计算避免重复构建set
# 2026-08-08 - 小欧 - 全程统一本地时区: 2处响应 timestamp 改 get_local_iso_timestamp() (本地ISO无Z)
# 2026-08-12 - 小欧 - A4(方案4.4.3步骤3): /tool/list + /tool/execute 迁出独立 tool_routes.py, health.py 回归健康检查单一职责;
#   删除 from app.tools import tool_registry 等越层 import(守护测试 api禁tools 变绿)。工具执行改走 services/tool 门面。
# 2026-08-12 - 小欧 - A1过渡红项历史(4.1.7/A4待消, 随A4迁出而移除代码, 历史按规范保留): /tool/execute 曾 API直调不走tool_executor,
#   注入 DefaultToolSecurityHooks 到 ContextVar 防空钩子 NPE; A4 建成 services/tool 门面后该过渡注入由 facade 统一接管, 移除。
# 2026-08-24 - 小欧 - 后端卡死修复: /health 的 SELECT 1 经 db.atxn 进子线程 offload 出事件循环; 被动 health 不再因 loop 被 agent 落库同步写独占而超时(零改动连接管理, 复用 atxn 薄壳)
# 2026-09-21 - 小欧 - 修复: health.version 由 request.app.version(import 时快照, 永不跟随 version.txt 更新)改调
#   settings_service.app_version()(每次实时读文件); 消除与 /settings.version、GET /config/version-file 长期不一致
# 2026-10-15 北京老陈裁定(开关外扩) - /echo(调试通信探针, 非产品功能) 纳入 require_debug_mode 约束:
#   守卫提为共用模块 api/v1/_gates.py, 与 /tool/list、/tool/execute 同一道门; 不在 health.py 复写一遍(违 DRY)。/health 不受影响。
# 2026-11-02 小欧 - /health 响应加 host 字段(Host头): 顶栏服务胶囊需显示真实后端地址, 开发(Vite代理)/打包(同源或直连)通用 — 小欧-2026-11-02
# 2026-11-02 小欧 - /health 再加 server_ip(本机局域网IP, lru_cache)与 pid: 他人访问地址与卡死排错要用的可执行信息 — 小欧-2026-11-02
# 2026-11-02 小欧 - 再加 uptime_s(进程存活时长)与 loop_lag_ms(事件循环调度延迟点采样): 前端"耗时"只能推断卡死,
#   这两个字段把"网络慢"与"事件循环被占死"分开, 与 AGENTS.md 的 py-spy 取证串成一条证据链 — 小欧-2026-11-02
# 2026-11-03 小欧 - server_ip 剔除 127./169.254./0. 并补 UDP 选路兜底: 原实现未过滤, 未配 hosts 的 Windows
#   会给出 127.0.0.1; 兜底仅在前者全不可用时走(VPN 多网卡会命中隧道地址) — 小欧-2026-11-03
# 2026-11-03 小欧 - 组装逻辑抽 build_health_response(host) 共用: main.py 新增裸 /health 别名(外部探针如
#   opencode-cli 每30s打 /health)同源一份真 JSON(DRY); 别名须早于打包态 spa_fallback catch-all 注册 — 小欧-2026-11-03
# 2026-11-03 小欧 - _server_lan_ip 取序反转: UDP 选路(真实出口网卡)提首选、hostname 解析降兜底, 原序在多网卡机器上易先命中虚拟适配器 — 小欧-2026-11-03
# 2026-11-04 小欧 - 新增 spawn 字段(闸门指标): 运行期 thread_start 数、等锁超限次数、CreateProcess 最长持锁,
#   把"正在接近卡死"变成可观测/可告警, 不必等全站僵死再 py-spy — 小欧-2026-11-04
# 2026-11-04 小欧 - DB 探测加 2s 上限: 灾时(线程池/闸门被占)健康检查必须自己先活, 不能跟着一起挂 — 小欧-2026-11-04
# 2026-11-15 小欧 - L1-3: DB 探测改后台刷新 + 读缓存(start_db_status_refresher/stop_db_status_refresher):
#   原实现每次 /health 都提交线程池, 卡死时健康检查自身排队致观测失效; 现 /health 零等待返回上一轮缓存值,
#   unknown 不计为故障(首轮未完成), 刷新任务异常不退出且保留上次值 — 小欧-2026-11-15
# 2026-11-15 小欧 - P2 纪律([42]): /health 新增 build 字段(运行代码指纹): 关键模块 sha256
#   +frozen+app_root, 与部署目录比对即可判定运行的是否为新代码; 病根见 doc-11月优化/[42]
"""
health — merged from health/ 3 files
COPY from individual files, only changed import paths — 小欧 2026-07-10
"""

import asyncio
import os
import socket
import time
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.v1._gates import require_debug_mode  # 2026-10-15 北京老陈裁定: /echo 受调试开关约束
from app.db import db
from app.logger import logger
from app.services.settings.settings_service import app_version as get_app_version
from app.utils.background_tasks import spawn_bg  # 强引用防 GC; shutdown 按引用 cancel — 2026-11-15 小欧
from app.utils.build_fingerprint import build_snapshot  # 2026-11-15 小欧: 运行代码指纹
from app.utils.spawn_gate import snapshot as spawn_snapshot  # 2026-11-04 小欧: 进程/线程创建指标
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区

router = APIRouter()


@lru_cache(maxsize=1)
def _server_lan_ip() -> str:
    """本机出口局域网IP(进程内解析一次) — 2026-11-02 小欧: 供顶栏服务胶囊显示可被他人访问的地址

    2026-11-03 小欧 - 取序: UDP 选路(走真实路由表, 得实际出口网卡地址)首选, hostname 解析兜底; getaddrinfo
    返回序由 hosts/DNS 决定, 多网卡机器常把 VMware/Hyper-V/VPN 虚拟适配器排最前(他人连不上)。两者均剔除
    127./169.254./0.; 进程内缓存免每次探活做名字解析, 网卡变更重启进程即刷新。VPN 有默认路由时两法都可能
    返回隧道地址, 无 psutil 无法按适配器类型甄别 — 小欧-2026-11-03
    """
    def _usable(ip: str) -> bool:
        return bool(ip) and not ip.startswith(("127.", "169.254.", "0."))

    # 首选: UDP 选路 —— 只查路由表不发包, 拿真实出口网卡地址
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            ip = probe.getsockname()[0]
            if _usable(ip):
                return ip
    except OSError:
        pass
    # 兜底: hostname 解析(无默认路由/离线/全部不可用时)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if _usable(info[4][0]):
                return info[4][0]
    except OSError:
        pass
    return ""

# 2026-11-02 小欧 - 进程启动时刻(本模块在 app 导入期加载, 与进程启动同刻); monotonic 不受系统时钟调整影响
_STARTED_AT = time.monotonic()


# DB 健康缓存 — 2026-11-15 小欧
#   病根: 原实现每次 /health 都 await db.atxn(线程池), 卡死时健康检查自己先挂, 观测失效。
#   方案: 常驻后台任务定期探测并写缓存, /health 只读缓存立即返回(允许是上一轮旧值)。
#   任务用 spawn_bg 持强引用: 裸 create_task 只被事件循环弱引用, 挂起中可能被 GC 销毁。
_DB_PROBE_INTERVAL_S = 5.0
_DB_PROBE_TIMEOUT_S = 2.0
_db_status_cache: dict = {"status": "unknown"}   # unknown=首轮未完成, 既非健康也非故障
_db_refresher: Optional[asyncio.Task] = None


async def _probe_db_once() -> str:
    for db_name in ("chat", "operations", "task_tracker"):
        try:
            await asyncio.wait_for(
                db.atxn(db_name, lambda conn: conn.execute("SELECT 1")),
                timeout=_DB_PROBE_TIMEOUT_S)
        except Exception:
            logger.warning(f"[health] DB {db_name} 连接失败")
            return "degraded"
    return "healthy"


async def _db_status_refresher() -> None:
    while True:
        try:
            _db_status_cache["status"] = await _probe_db_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:          # 刷新任务绝不能因单次异常退出
            logger.warning(f"[health] DB 刷新异常(保留上次值): {e!r}")
        await asyncio.sleep(_DB_PROBE_INTERVAL_S)


def start_db_status_refresher() -> None:
    """启动期拉起 DB 健康刷新任务(幂等) — 2026-11-15 小欧"""
    global _db_refresher
    if _db_refresher is None or _db_refresher.done():
        _db_refresher = spawn_bg(_db_status_refresher())


def stop_db_status_refresher() -> None:
    """shutdown 取消刷新任务(幂等) — 2026-11-15 小欧"""
    global _db_refresher
    if _db_refresher is not None and not _db_refresher.done():
        _db_refresher.cancel()
    _db_refresher = None


async def _loop_lag_ms() -> float:
    """事件循环调度延迟(点采样, 毫秒) — 2026-11-02 小欧

    做法: 让出一次控制权, 量"多久才被重新调度"。循环被同步任务占死时该值显著上升,
    故可与前端往返耗时对照, 区分"网络慢"与"事件循环卡住"。只代表此刻, 不是历史峰值。
    """
    started = time.monotonic()
    await asyncio.sleep(0)
    return round((time.monotonic() - started) * 1000, 3)

# ===== health =====

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    db_status: str = "unknown"  # 小欧 2026-07-23 #14: 真实DB连接验证
    host: str = ""  # 2026-11-02 小欧 - 后端视角访问地址(Host头), 顶栏服务胶囊显示真实后端地址(开发/打包通用)
    server_ip: str = ""  # 2026-11-02 小欧 - 本机局域网IP, 供他人访问时使用
    pid: int = 0  # 2026-11-02 小欧 - 进程号, 卡死时直接对应 py-spy dump --pid
    uptime_s: float = 0.0  # 2026-11-02 小欧 - 进程已存活秒数(重启即归零, 与 pid 变化互相印证)
    loop_lag_ms: float = 0.0  # 2026-11-02 小欧 - 事件循环调度延迟点采样, 区分网络慢与循环被占死
    spawn: dict = {}  # 2026-11-04 小欧 - 闸门指标: runtime_thread_starts 应为0, gate_timeouts/popen_max_ms 暴露卡死前兆
    build: dict = {}  # 2026-11-15 小欧 - 运行代码指纹: 与部署目录比对, 判定"跑的是不是新代码"([42] P2)

class EchoRequest(BaseModel):
    message: str

class EchoResponse(BaseModel):
    received: str
    timestamp: str

async def build_health_response(host: str) -> HealthResponse:
    """组装健康响应 — 共用: /api/v1/health 与 main.py 裸 /health 别名同源一份真 JSON — 2026-11-03 小欧
    2026-11-15 小欧: DB 状态改为读后台刷新缓存, 本函数不再提交线程池; 卡死时仍能立即返回。"""
    db_status = _db_status_cache["status"]
    return HealthResponse(
        status="degraded" if db_status == "degraded" else "healthy",   # unknown 不计为故障
        timestamp=get_local_iso_timestamp(),
        version=get_app_version(),
        db_status=db_status,
        # 2026-11-02 小欧 - Host头即前端实际访问到的后端地址: dev经Vite代理(changeOrigin)=proxy target, 打包=访问域名或直连地址
        host=host,
        server_ip=_server_lan_ip(),
        pid=os.getpid(),
        # 2026-11-02 小欧 - 存活时长与循环延迟: 顶栏胶囊据此区分"重启过/网络慢/事件循环被占死"
        uptime_s=round(time.monotonic() - _STARTED_AT, 3),
        loop_lag_ms=await _loop_lag_ms(),
        spawn=spawn_snapshot(),
        build=build_snapshot(),  # 2026-11-15 小欧 - 运行代码指纹([42] P2)
    )

@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    健康检查接口
    """
    return await build_health_response(request.headers.get("host", ""))

@router.post("/echo", response_model=EchoResponse)
async def echo(data: EchoRequest):
    """
    测试通信接口 - 回显收到的消息
    2026-10-15 北京老陈裁定: 调试探针非产品功能, 纳入 require_debug_mode 约束(与 /tool/* 同一道门)。
    """
    require_debug_mode()
    return EchoResponse(
        received=data.message,
        timestamp=get_local_iso_timestamp()
    )

