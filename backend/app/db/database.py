# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - chat库采用DELETE journal模式,其他库维持WAL; Windows大库场景设计选择
# 2026-07-15 - 小欧 - get_conn异常分支拆分: 原except Exception兜底所有异常并记"DB operation failed", 业务异常(如rename目标已存在抛FileExistsError)被误报为数据库故障, 且被execute_with_safety二次记日志形成双重日志(首条为误报)。改后仅sqlite3.Error记DB错误日志, 业务异常仅rollback后raise不误报。
# 2026-07-17 - 小欧 - chat库改回WAL,三库统一WAL。背景因果(经验累积,勿删): 07-14的DELETE源于误诊——
#            当时遇Errno22误判为"WAL-shm在Windows 2GB+库并发读写不稳"; 同日《后端step单步保存设计说明书》v1.2已更正
#            Errno22真实根因为time_utils.ensure_timestamp_milliseconds潜伏bug(Python3.13宽松fromisoformat+漏捕OSError),与WAL无关,
#            DELETE改动属误诊白做但无害、当时未回退。2026-07-17 E2E验证暴露DELETE模式在chat_message_steps膨胀185万行/2.7GB时
#            写I/O拥塞(每次写journal+fsync)致create_session同步写>10s超时,故回归WAL统一三库消除写拥塞。详见notes/经验累积文档。
# 2026-07-18 - 小欧 - 【病根】调用方(如 action_handler)把 task_id 等直接作SQL参数, 若该值为 MagicMock/非基元类型, sqlite3 抛不透明 InterfaceError('type X is not supported'), 排查困难且易误判为DB故障。
#            【解决思路】get_conn 出口用薄包装 _ParamSafeConnection 在 execute/executemany 边界统一校验参数类型(仅允许 str/int/float/bytes/bool/None), 非基元类型直接抛清晰错误; 调用方零改动(无退化), 单一闸门复用(SRP/DRY)。
# 2026-07-18 小沈 修复: _ParamSafeConnection.execute 显式传 None 触发 sqlite3.ProgrammingError(parameters are of unsupported type), 致后端启动失败(init_chat_db 的 CREATE INDEX/ALTER TABLE 均走包装且 params=None); 改为 params is None 时调 self._conn.execute(sql) 不传 None, 冗余最小、单一闸门复用(SRP/KISS)。
# 2026-07-18 小欧 修复回归: _SAFE_PARAM_TYPES 增加 datetime/date/time; sqlite3原生支持此三类参数(内置适配器转ISO串), 原仅允许基元类型致 task_db.complete_task(datetime.now())被误拦(日志报"DB参数类型不被支持: datetime"), 属本次闸门引入的回归。
# 2026-07-18 - 小欧 - _validate 改 datetime/date→convert_to_utc() 自动归一化 UTC Z; _SAFE_PARAM_TYPES 移除 datetime/date 不依赖 sqlite3 废弃适配器
# 2026-07-23 - 小欧 - 修复: busy_timeout 30000→500ms + get_conn_with_retry指数退避(max_retries=3: 0.5/1/2s)
#   【病根】busy_timeout=30000 + 无重试: 写竞争时sqlite内部先等30s才抛异常, 再retry等于31.5s比不修更差
#   【改法】①busy_timeout=500(快速失败,不空等30s)②get_conn_with_retry: 仅对OperationalError+"locked"指数退避(0.5/1/2s),time.sleep总阻塞仅3.5s不拖事件循环; IntegrityError直抛不重试(YAGNI)
#   【合规】SRP+KISS-DIRECT+YAGNI
# 2026-08-07 - 小欧 - 修复: 重试下沉至get_conn统一入口(连接获取a段+commit b段, 单yield无re-yield)
#   【病根】①原实现: 47处调用方用get_conn(无retry), 并发写锁死时静默失败; ②原实现: get_conn_with_retry在except内re-yield违反@contextmanager协议 → "generator didn't stop after throw()"(日志09:11:16)
#   【改法】①get_conn新增max_retries: 连接获取期(a)与commit期(b)对"locked"指数退避(0.5/1/2s), 47处调用零改动即获重试能力(DRY); ②get_conn_with_retry改为get_conn薄包装(仅透传, 单次yield)
#   【合规】DRY+KISS-DIRECT+SRP
# 2026-08-20 - 小欧 - 11.2-C 监控独立库: _db_paths["monitoring"] 注册 monitoring.db + import init_monitoring_db(启动统一初始化), 复用 get_conn/get_conn_with_retry 闸门
# 2026-08-21 - 小欧 - 差异设计落地: ①删observer条目+删init_observer方法(零调用方); ②_db_paths加timers条目(timers.db独立库); ③import加init_timers_db+init()内注册(紧跟init_operations_db之后) — 小欧 2026-08-21
# 2026-08-24 - 小欧 - 后端卡死修复(offload薄壳): 新增 atxn/_run_txn 异步事务壳, 将同步 sqlite3 I/O + 锁重试 time.sleep(get_conn:188/206) 整体 offload 出事件循环; 根治 agent 落库热路径在 loop 主线程同步阻塞致 /health 超时/console 冻结。storage.* 与连接管理零改动(复用既有一切), 唯一入口仍 db。
# 2026-11-16 - 小欧 - 启动迁移连接放宽 busy_timeout: get_conn 新增 busy_timeout_ms 参数(默认 500ms 行为不变), init() 的迁移连接传 30000ms — 双击并发初始化撞写锁时不再立即抛 database is locked 崩启动; 运行期仍 500ms+指数退避。
# 2026-11-21 - 小欧 - 库文件归入 db/ 子目录: 原 5 个库与 assets/recycle_bin 平铺在数据根, 备份/清理
#   无法按类区分(资产与回收站早已是子目录, 只有库落在根上)。新增 _DB_SUBDIR 与 db_file_path() 单一拼装点,
#   get_conn 经 ensure_db_layout() 惰性做一次性迁移(copy-校验-删旧, 幂等; 同目录 -wal/-shm 一并搬);
#   迁移在循环内首连接前完成, 任何不经 lifespan 的上下文(单测/裸脚本/worker)同样拿到新布局。
#   测试注入仍走 _db_overrides, 不触发迁移。
"""DB SDK - 统一数据库操作接口

管理3个SQLite数据库:
- chat_history.db: 对话会话和消息
- operations.db: 文件操作和任务记录
- tool_observer.db: 工具调用审计(后续实现)

使用方式:
    from app.db import db
    
    with db.get_conn("chat") as conn:
        conn.execute("SELECT ...")

设计原则:
- 统一入口:所有DB操作通过db.get_conn()
- 自动事务:上下文管理器自动commit/rollback/close
- 摒弃裸连接:禁止手动管理连接
- SRP拆分:初始化逻辑委托给db_initializer

Author: 小沈 - 2026-05-28
小欧 2026-06-18 SRP拆分: 初始化→db_initializer
小健 2026-06-18 删除向后兼容迁移代码(db_migrator.py)
# 2026-09-29 20:42:06 小欧 - atxn 增 retry_locked(默认0=旧调用逐字不变): 补 body 执行期 locked 有限重试(退避0.5/1/2s),
#   仅捕 sqlite3.OperationalError 且含 "locked", 非锁错误/耗尽一律原样抛出 — 根治并发起跑事务体撞写锁 — 小欧-2026-09-29
# 2026-10-06 - 小欧 - ①: get_conn 增就绪自证(判据表缺失即就地幂等建表, 复用当前连接避免递归, 失败仅告警不阻断)
# 2026-10-30 - 小欧 - atxn 改投 _DB_TXN_POOL(4 worker, db-txn) 并 copy_context,
#   与同步工具(loop 默认池)隔离; run_in_executor 不复制 context, 不显式 copy 会丢 session_id 与目录白名单判据
"""

import asyncio
import contextvars
import functools
import os
import shutil
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Set

from app.db.db_initializer import (
    init_chat_db,  # 12.2-Q7: 加 init_timers_db — 小欧 2026-08-21
    init_operations_db,
    init_task_tracker_db,
    init_timers_db,
)
from app.logger import logger
from app.monitoring.storage import init_monitoring_db  # 11.2-C 监控独立库 init — 小欧 2026-08-20
from app.utils.time_utils import to_local_iso  # 小欧 2026-08-08: datetime/date 归一化为本地ISO无Z

# db_name → 建表函数(① 资源层自证就绪用; 与 _DB_READY_TABLE 同键) — 小欧 2026-10-06
_INIT_BY_DB = {
    "chat": init_chat_db,
    "operations": init_operations_db,
    "timers": init_timers_db,
    "task_tracker": init_task_tracker_db,
    "monitoring": init_monitoring_db,
}


# 2026-10-30 小欧 - DB 事务专用线程池
#   为什么: atxn 原走 asyncio.to_thread → loop 默认池, 与同步工具(bash/grep/树扫描/文件读写)共用。
#   长工具占满池时落库排队, 延迟反压到 SSE 与 REST。DB 写本就被 SQLite 文件锁串行化,
#   池开大只空转, 故单独给 4 个 worker(够并发起跑的多会话排队, 又不与工具抢池)。
_DB_TXN_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db-txn")

# 启动期迁移连接 busy_timeout — 小欧 2026-11-16
# 迁移(建表/去重/建索引)是长事务, 撞写锁时若沿用运行期 500ms 会立即抛 database is locked
# 直接崩掉启动(logs 实证: 双击两次并发 init_chat_db)。迁移是单次启动期动作, 可安全等写锁:
# 30s 内拿到锁就继续, 拿不到才失败(此时确有异常持锁者)。运行期 get_conn 仍用 500ms+指数重试。
_MIGRATION_BUSY_TIMEOUT_MS = 30000


class _ParamSafeConnection:
    """DB 参数安全闸门(薄包装) — 小欧 2026-07-18

    问题根因: 调用方(如 action_handler)把 task_id 等直接作 SQL 参数,
    若该值为 MagicMock/非基元类型, sqlite3 会抛不透明的 InterfaceError('type X is not supported')。
    修复逻辑: 在 execute/executemany 边界统一校验参数类型, 非基元类型(str/int/float/bytes/bool/None)
    直接拒绝对外报清晰错误; 所有调用方零改动(无退化), 复用此单一闸门(DRY/SRP)。
    """

    _SAFE_PARAM_TYPES = (str, int, float, bytes, bool, type(None))  # datetime/date 在 _validate 中自动转 UTC Z 入库, 不依赖 sqlite3 废弃适配器; 小欧 2026-07-18

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    @staticmethod
    def _validate(params):
        """验证并转换参数: datetime/date 自动 UTC ISO 8601 Z 字符串; 返回安全参数列表(或 None/dict) — 小欧 2026-07-18"""
        if params is None:
            return None
        if isinstance(params, dict):
            return {k: to_local_iso(v) if isinstance(v, (datetime, date)) else v
                    for k, v in params.items()}
        if not isinstance(params, (tuple, list)):
            params = (params,)
        result = []
        for _p in params:
            if isinstance(_p, (datetime, date)):
                _p = to_local_iso(_p)  # 小欧 2026-08-08: datetime→本地ISO无Z
            if not isinstance(_p, _ParamSafeConnection._SAFE_PARAM_TYPES):
                raise ValueError(
                    f"DB 参数类型不被支持: {type(_p).__name__}, "
                    f"仅允许 {[t.__name__ for t in _ParamSafeConnection._SAFE_PARAM_TYPES]}"
                )
            result.append(_p)
        return result

    def execute(self, sql, params=None):
        safe_params = self._validate(params)
        if safe_params is None:
            return self._conn.execute(sql)
        return self._conn.execute(sql, safe_params)

    def executemany(self, sql, params_seq):
        seq = [self._validate(p) for p in params_seq]
        return self._conn.executemany(sql, seq)

    def __getattr__(self, name):
        return getattr(self._conn, name)


_DB_FILES = {
    "chat": "chat_history.db",
    "operations": "operations.db",
    "timers": "timers.db",   # 12.2-Q7: 定时器独立库(SRP一库一域) — 小欧 2026-08-21
    "task_tracker": "task_tracker.db",
    "monitoring": "monitoring.db",   # 11.2-C 监控独立库 — 小欧 2026-08-20
}

# 库文件子目录: 数据根下与 assets/recycle_bin 平级, 库不再平铺在根上 — 小欧-2026-11-21
_DB_SUBDIR = "db"

# 各库就绪判据表(①): 与 _DB_FILES 一一对应, get_conn 见缺即就地幂等建表 — 小欧 2026-10-06
_DB_READY_TABLE = {
    "chat": "chat_sessions",
    "operations": "file_operations",
    "timers": "timers",
    "task_tracker": "tasks",
    "monitoring": "http_requests",
}


def resolve_db_dir() -> Path:
    """数据目录唯一解析点: OMNIAGENT_DATA_DIR 优先, 否则 ~/.omniagent — 小欧 2026-09-30

    病根: 路径原在 __init__ 硬编码 Path.home()/".omniagent" 且 db=DatabaseManager() 在导入期构造,
      路径被冻结; 而 conftest 的 isolated_config_dir 只重定向配置文件(OMNIAGENT_CONFIG_PATH),
      管不到数据库 → 任何裸用 db.get_conn() 的测试都写真库(实测污染真库: 空会话/hello/v2 等)。
    改法: 与系统已有的 OMNIAGENT_CONFIG_PATH 对称, 增加 OMNIAGENT_DATA_DIR 开关, 且**在 get_conn
      内惰性解析**(不在 __init__ 冻结) —— 惰性是必须的: db 单例在模块导入期即构造, 若在 __init__ 读 env
      便受导入顺序影响, conftest 来不及设。改后测试只需设 env 即"够不到"真库(AGENTS.md 铁律:
      根治靠"够不到"而非"事后还原"), 无需逐个测试 patch, 也不会漏掉将来新增的测试。
    """
    env = (os.getenv("OMNIAGENT_DATA_DIR") or "").strip()
    return Path(env) if env else Path.home() / ".omniagent"


def db_dir() -> Path:
    """库目录: {数据根}/db — 小欧-2026-11-21"""
    return resolve_db_dir() / _DB_SUBDIR


def db_file_path(db_name: str) -> Path:
    """库文件绝对路径唯一拼装点: {数据根}/db/{库文件名} — 小欧-2026-11-21

    纯路径, 不建目录不迁移(读口/CLI 可直接用); 库文件名真源仍是 _DB_FILES。
    """
    return db_dir() / _DB_FILES[db_name]


_migrated_data_dirs: Set[str] = set()
_migrate_lock = threading.Lock()


def _migrate_flat_db_files(data_dir: Path) -> None:
    """把历史上平铺在数据根的库一次性搬进 db/ 子目录 — 小欧-2026-11-21

    病根: 库与 assets/recycle_bin 平铺同一根, 备份/清理无法按类区分; 后两者早已是子目录,
      只有库落在根上。
    做法: 主库与 -wal 先复制成 .migrating 中间名 → 逐个校验大小一致 → 全部通过才 rename 成正式名,
      最后删原位副本。任一步失败只留中间名并清掉, 原库原样不动, 下次启动重试; 不会出现
      "新库落了但没带 WAL"这种半套状态(SQLite 会把它当成完整库读, 少掉最近事务)。
    幂等: 新位置已有同名库则跳过, 重复运行与「降级回退后再次升级」都安全。
    -shm 不复制: 它是进程本地共享内存索引, 带过来只是过期状态, SQLite 打开时自行重建;
      原位 -shm 随主库一起删除。
    """
    target_dir = data_dir / _DB_SUBDIR
    moved = []
    left = []
    for fname in _DB_FILES.values():
        old = data_dir / fname
        if not old.is_file() or (target_dir / fname).exists():
            continue                      # 无旧库(已迁移) / 新位置已有: 都不动
        staged = []                       # [(中间名, 终点)]
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            for suffix in ("", "-wal"):
                src = data_dir / f"{fname}{suffix}"
                if not src.is_file():
                    continue
                tmp = target_dir / f"{fname}{suffix}.migrating"
                shutil.copy2(src, tmp)
                if tmp.stat().st_size != src.stat().st_size:
                    raise OSError(f"大小校验失败 {src} -> {tmp}")
                staged.append((tmp, target_dir / f"{fname}{suffix}"))
            for tmp, final in staged:
                tmp.replace(final)        # 校验全过才落成正式名
        except OSError as e:
            for tmp, _final in staged:
                try:
                    tmp.unlink()
                except OSError:
                    pass
            logger.error(f"[db] 迁移库文件失败(原库不动, 下次启动重试): {old}: {e}")
            continue
        moved.append(fname)
        # 新库已就位, 原位副本尽量清掉; 被其它进程占用时删不掉只告警, 不影响使用
        for suffix in ("", "-wal", "-shm"):
            side = data_dir / f"{fname}{suffix}"
            if side.is_file():
                try:
                    side.unlink()
                except OSError:
                    left.append(side.name)
    if moved:
        logger.info(f"[db] 库文件已迁入 {target_dir}: {', '.join(moved)}")
    if left:
        logger.warning(f"[db] 新库已就绪, 原位副本被占用未能删除(可人工清理): {', '.join(left)}")


def ensure_db_layout() -> None:
    """确保库目录布局就绪(幂等, 每数据目录只迁移一次) — 小欧-2026-11-21

    在 get_conn 内惰性调用: 与 resolve_db_dir 同款惰性口径, 不吃导入顺序;
    OMNIAGENT_DATA_DIR 指向不同目录时各迁移各的(测试隔离不共享状态)。
    """
    data_dir = resolve_db_dir()
    key = str(data_dir)
    if key in _migrated_data_dirs:
        return
    with _migrate_lock:
        if key in _migrated_data_dirs:
            return
        _migrate_flat_db_files(data_dir)
        _migrated_data_dirs.add(key)


class DatabaseManager:
    """统一数据库管理器(SDK核心) — 仅负责连接管理"""

    def __init__(self):
        """初始化数据库管理器"""
        d = resolve_db_dir()
        d.mkdir(parents=True, exist_ok=True)
        # 测试注入用覆盖口: {"chat": 任意路径} 优先于 _DB_FILES 解析, 并可注册 _DB_FILES 之外的
        # 库名(纯单测需要, 如 test_db_atxn 用 "test")。生产路径不读它, 故不构成第二套解析逻辑 — 小欧 2026-09-30
        self._db_overrides: Dict[str, Any] = {}

    @contextmanager
    def get_conn(self, db_name: str = "chat", max_retries: int = 3,
                 busy_timeout_ms: int = 500) -> Iterator[sqlite3.Connection]:
        """获取数据库连接(上下文管理器) — 统一入口(含locked指数退避重试)
        
        使用方式:
            with db.get_conn("chat") as conn:
                conn.execute("SELECT ...")
        
        自动处理:
            - 连接获取: 对"database is locked"指数退避重试(0.5/1/2s, 不阻塞事件循环过长 — 小欧 2026-08-07)
            - 正常退出: commit + close (commit对lock重试, 无re-yield)
            - 异常退出: rollback + close
            - 无论如何: 都会关闭连接
        
        支持的db_name: chat, operations, observer, task_tracker
        
        修复(小欧 2026-08-07): 原get_conn_with_retry为@contextmanager且在except块内re-yield,
            @contextmanager协议禁止二次yield → 抛出"generator didn't stop after throw()"(日志09:11:16).
            重构: 重试点只在【连接获取】与【commit】两处(均为单yield/无re-yield), 保证generator清洁退出.
            修复(小欧 2026-08-07): 重试逻辑下沉至get_conn统一入口, 47处调用方零改动即获重试能力(DRY).
        """
        import time as _time
        _override = self._db_overrides.get(db_name)
        if _override is None and db_name not in _DB_FILES:
            raise ValueError(
                f"Unknown database: {db_name}. "
                f"Supported: {list(_DB_FILES.keys())}"
            )

        # 惰性解析(见 resolve_db_dir docstring) — 小欧 2026-09-30
        if _override is not None:
            db_path = Path(_override)
        else:
            ensure_db_layout()          # 历史平铺库一次性归入 db/ 子目录(幂等) — 小欧-2026-11-21
            db_path = db_file_path(db_name)
        db_path.parent.mkdir(parents=True, exist_ok=True)   # env 指向的临时目录可能尚不存在
        conn = None

        # (a) 连接获取: 对 connected前的 lock 指数退避重试(单次连接, 无re-yield) — 小欧 2026-08-07
        for attempt in range(max_retries + 1):
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row

                # 全部库统一WAL模式(含chat) — 小欧 2026-07-17
                # 历史因果(经验累积,勿删): 2026-07-14曾将chat改为DELETE,系误诊"WAL-shm在Windows 2GB+库并发读写Errno22"所致;
                #   同日《后端step单步保存设计说明书》v1.2已更正Errno22真实根因为time_utils潜伏bug(与WAL无关),DELETE属误诊白做但无害、当时未回退。
                #   2026-07-17 E2E验证暴露DELETE模式在chat_message_steps膨胀185万行/2.7GB时写I/O拥塞(每次写journal+fsync),
                #   致create_session同步写>10s超时;故改回WAL统一三库,消除写拥塞。
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")  # 默认500ms(快速失败+应用层指数退避); 启动迁移传 30s 等写锁 — 小欧 2026-07-23 / 2026-11-16
                # 外键约束: SQLite默认OFF，外键约束不生效 — 小欧 2026-07-10
                conn.execute("PRAGMA foreign_keys=ON")
                break  # 连接成功
            except sqlite3.OperationalError as _lock_e:
                if "locked" not in str(_lock_e):
                    raise  # 非locked异常不重试
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
                if attempt == max_retries:
                    logger.error(f"[db] {db_name} 连接locked, {max_retries}次重试后放弃")
                    raise
                delay = 0.5 * (2 ** attempt)  # 0.5, 1, 2 (max_retries=3, 总~3.5s, 不阻塞事件循环过长) — 小欧 2026-07-23
                logger.warning(f"[db] {db_name} 连接locked, 第{attempt+1}/{max_retries}次重试, 等待{delay:.1f}s")
                _time.sleep(delay)

        # ① 资源层自证就绪: 判据表缺失即就地幂等建表(健康探测实测空目录只建出4KB空壳库,
        #   全部写入报 no such table; 建表原先只挂在 app 启动 db.init(), 任何不经 lifespan 的
        #   上下文——单测/裸脚本/worker——都拿到空库)。init_* 复用 db_initializer 既幂等实现。
        #   复用当前连接执行(不走 get_conn 避免递归), 失败仅告警不阻断: 调用方的真实操作
        #   自会暴露问题, 此处绝不把"建表失败"变成新的失败源 — 小欧 2026-10-06
        _ready = _DB_READY_TABLE.get(db_name)
        if _ready and conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_ready,)
        ).fetchone() is None:
            try:
                @contextmanager
                def _reuse(_db_name=None):
                    yield _ParamSafeConnection(conn)
                    conn.commit()
                _INIT_BY_DB.get(db_name)(_reuse)
                logger.info(f"[db] {db_name} 缺判据表 {_ready}, 已就地初始化 schema")
            except Exception as _init_e:
                logger.warning(f"[db] {db_name} 就地初始化 schema 失败(不阻断): {_init_e}")

        try:
            yield _ParamSafeConnection(conn)  # 小欧 2026-07-18: 参数安全闸门包装, 校验SQL参数类型(非基元类型抛清晰错误)

            # (b) 提交: 对lock指数退避重试(无re-yield, 省去外层re-yield的隐患) — 小欧 2026-08-07
            for commit_attempt in range(max_retries + 1):
                try:
                    conn.commit()
                    break
                except sqlite3.OperationalError as _commit_e:
                    if "locked" not in str(_commit_e):
                        raise  # 非locked异常不重试
                    if commit_attempt == max_retries:
                        logger.error(f"[db] {db_name} commit locked, {max_retries}次重试后放弃")
                        raise
                    delay = 0.5 * (2 ** commit_attempt)
                    logger.warning(f"[db] {db_name} commit locked, 第{commit_attempt+1}/{max_retries}次重试, 等待{delay:.1f}s")
                    _time.sleep(delay)

        except sqlite3.Error as e:
            # DB级错误(连接/SQL/事务): 回滚 + 记"DB operation failed" — 小欧 2026-07-15
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    logger.warning(f"[db] rollback 失败: {db_name}")
            logger.error(f"DB operation failed [{db_name}]: {e}")
            raise
        except Exception:
            # 业务级异常(如FileExistsError): 仅回滚, 不当DB错误记避免误报; 由调用方(如execute_with_safety)记录 — 小欧 2026-07-15
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    logger.warning(f"[db] rollback 失败: {db_name}")
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    logger.warning(f"[db] 关闭连接失败: {db_name}")

    @contextmanager
    def get_conn_with_retry(self, db_name: str = "chat", max_retries: int = 3) -> Iterator[sqlite3.Connection]:  # max_retries=3 (0.5+1+2=3.5s总阻塞,time.sleep不阻塞事件循环过长) — 小欧 2026-07-23
        """get_conn + 指数退避重试(仅对 database is locked) — 小欧 2026-07-23

        为什么不用busy_timeout死等:
            busy_timeout=30000时已空等30s, 再加retry总等待>31.5s, 比不修更差(KISS-DIRECT违规)
        为什么不对IntegrityError重试:
            UNIQUE约束冲突不因重试而消失, 重试会掩盖真实问题(YAGNI)
        使用方式:
            with db.get_conn_with_retry("chat") as conn:
                conn.execute("INSERT INTO ...")

        小欧 2026-08-07 修复: 原实现于except内re-yield, 违反@contextmanager协议 →
            "generator didn't stop after throw()" (日志09:11:16 operation_record.py:156/214).
            本方法现为get_conn薄包装(仅透传, 单次yield, 无re-yield), 重试逻辑已下沉至get_conn:
              - 连接获取期: get_conn(a)段
              - 提交期:    get_conn(b)段
            调用方(body)异常锁(如execute阶段)不在此重试(见get_conn(b)注释).
        """
        with self.get_conn(db_name, max_retries=max_retries) as conn:
            yield conn

    async def atxn(self, db_name: str, fn, *args, retry_locked: int = 0, **kwargs):
        """异步事务壳(后端卡死修复 小欧 2026-08-24): 在子线程内执行 `with get_conn(db_name) as conn: return fn(conn, *args, **kwargs)`

        为什么需要它:
            原 agent 落库热路径(stream_orchestrator/agent_runner/react_cycle 的 `with db.get_conn...`)
            在事件循环主线程同步执行 sqlite3.connect/execute/commit, 且锁重试 time.sleep(get_conn:188/206)
            直接睡在 loop 线程 → 长 blob 写/锁竞争时 loop 被独占 → 被动 /health 排不上队超时、console 静止(卡死)。
        设计要点(合规/合理/关联):
            - 整段 `with get_conn` 进 to_thread 子线程, 连接创建/使用/关闭同线程 → 零跨线程(规避 sqlite3.ProgrammingError);
            - storage.* / get_conn / 参数闸门 / 锁重试 全部复用, 零改动(DRY/KISS-DIRECT);
            - 多任务写经线程池并发 + SQLite 文件锁串行化, loop 永不被占(满足"多任务写DB可排队"诉求)。

        retry_locked(小欧 2026-09-29): body 执行期 "database is locked" 的有限重试次数, 默认 0。
            为什么需要: get_conn 只覆盖连接获取期/提交期(b段)两处锁, body 内 execute 阶段撞锁直接抛出
              (get_conn(b)注释已明载); 并发多会话起跑时事务体撞写锁是实证高频(PAR-05 19:49 四记 locked)。
            默认 0 = 现有 29 个调用点行为逐字不变(禁止backward/LSP: 唯一契约是"不传即零重试");
              仅由已证实暴露的并发热写路径显式开启, 杜绝全局行为扩大(YAGNI)。
            退避 0.5/1/2s 与 get_conn L188/L206 同一节奏(DRY), 但 sleep 在 async 层,
              不占 to_thread 子线程, 避免与 get_conn 内部 time.sleep 叠加放大等待(KISS-DIRECT)。
            仅捕获 sqlite3.OperationalError 且错误串含 "locked": 非锁 SQL 错误/重试耗尽一律原样抛出,
              杜绝掩盖真实故障(对齐 get_conn "为何不对 IntegrityError 重试" 的既判据)。
        """
        _delay = 0.5
        for _attempt in range(retry_locked + 1):
            try:
                # 2026-10-30 小欧 - 改投专用池, 不再与工具共享 loop 默认池
                # 必须 copy_context: asyncio.to_thread 会复制 context, run_in_executor 不会。
                #   丢了 context 则事务体内日志失去 session_id, 且 path_dir_lists 的
                #   _current_directory_lists ContextVar 变空 → 目录白名单判据失效(fail-closed 抛错)。
                _loop = asyncio.get_running_loop()
                _ctx = contextvars.copy_context()
                return await _loop.run_in_executor(
                    _DB_TXN_POOL,
                    functools.partial(_ctx.run, self._run_txn, db_name, fn, *args, **kwargs),
                )
            except sqlite3.OperationalError as _lock_e:
                if "locked" not in str(_lock_e) or _attempt >= retry_locked:
                    raise
                logger.warning(
                    f"[db] {db_name} 事务体执行撞锁, 第{_attempt + 1}/{retry_locked}次重试, 等待{_delay:.1f}s: {_lock_e}")
                await asyncio.sleep(_delay)
                _delay *= 2

    def _run_txn(self, db_name, fn, *args, **kwargs):
        """atxn 的子线程执行体: 在单线程内开连接→执行业务→提交/回滚/关闭 — 小欧 2026-08-24"""
        with self.get_conn(db_name) as conn:
            return fn(conn, *args, **kwargs)

    def init(self):
        """初始化所有数据库(应用启动时调用)"""
        import time as _time
        logger.info("Initializing all databases...")

        def _migration_conn(db_name: str = "chat"):
            # 启动期迁移用较长 busy_timeout 等写锁, 避免瞬时锁竞争直接崩启动 — 小欧 2026-11-16
            return self.get_conn(db_name, busy_timeout_ms=_MIGRATION_BUSY_TIMEOUT_MS)

        _ta = _time.time()
        init_chat_db(_migration_conn)
        logger.info(f"[启动耗时] init_chat_db: {_time.time()-_ta:.3f}s")
        _tb = _time.time()
        init_operations_db(_migration_conn)
        logger.info(f"[启动耗时] init_operations_db: {_time.time()-_tb:.3f}s")
        _tt = _time.time()
        init_timers_db(_migration_conn)
        logger.info(f"[启动耗时] init_timers_db: {_time.time()-_tt:.3f}s")
        _tc = _time.time()
        init_task_tracker_db(_migration_conn)
        logger.info(f"[启动耗时] init_task_tracker_db: {_time.time()-_tc:.3f}s")
        _tm = _time.time()
        init_monitoring_db(_migration_conn)
        logger.info(f"[启动耗时] init_monitoring_db: {_time.time()-_tm:.3f}s")
        logger.info(f"[启动耗时] db.init 合计: {_time.time()-_ta:.3f}s")
        logger.info("All databases initialized successfully")


# 全局SDK实例(唯一入口)
db = DatabaseManager()
