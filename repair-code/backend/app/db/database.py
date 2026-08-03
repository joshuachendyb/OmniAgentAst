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
# 2026-07-23 - 小欧 - #14 fix: busy_timeout 30000→500ms + get_conn_with_retry指数退避(max_retries=3: 0.5/1/2s)
#   【病根】busy_timeout=30000 + 无重试: 写竞争时sqlite内部先等30s才抛异常, 再retry等于31.5s比不修更差
#   【改法】①busy_timeout=500(快速失败,不空等30s)②get_conn_with_retry: 仅对OperationalError+"locked"指数退避(0.5/1/2s),time.sleep总阻塞仅3.5s不拖事件循环; IntegrityError直抛不重试(YAGNI)
#   【合规】SRP+KISS-DIRECT+YAGNI
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
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, date, timezone
from typing import Iterator
from app.logger import logger
from app.utils.time_utils import convert_to_utc
from app.db.db_initializer import (
    init_chat_db, init_operations_db, init_task_tracker_db,
)


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
            return {k: convert_to_utc(v) if isinstance(v, (datetime, date)) else v
                    for k, v in params.items()}
        if not isinstance(params, (tuple, list)):
            params = (params,)
        result = []
        for _p in params:
            if isinstance(_p, (datetime, date)):
                _p = convert_to_utc(_p)  # 边界自动归一化: datetime→UTC ISO 8601 Z
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


class DatabaseManager:
    """统一数据库管理器(SDK核心) — 仅负责连接管理"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self._db_dir = Path.home() / ".omniagent"
        self._db_paths = {
            "chat": self._db_dir / "chat_history.db",
            "operations": self._db_dir / "operations.db",
            "observer": self._db_dir / "tool_observer.db",
            "task_tracker": self._db_dir / "task_tracker.db",
        }
        self._db_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_conn(self, db_name: str = "chat") -> Iterator[sqlite3.Connection]:
        """获取数据库连接(上下文管理器)
        
        使用方式:
            with db.get_conn("chat") as conn:
                conn.execute("SELECT ...")
        
        自动处理:
            - 正常退出: commit + close
            - 异常退出: rollback + close
            - 无论如何: 都会关闭连接
        
        支持的db_name: chat, operations, observer, task_tracker
        """
        conn = None
        try:
            if db_name not in self._db_paths:
                raise ValueError(
                    f"Unknown database: {db_name}. "
                    f"Supported: {list(self._db_paths.keys())}"
                )
            
            db_path = self._db_paths[db_name]
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            # 全部库统一WAL模式(含chat) — 小欧 2026-07-17
            # 历史因果(经验累积,勿删): 2026-07-14曾将chat改为DELETE,系误诊"WAL-shm在Windows 2GB+库并发读写Errno22"所致;
            #   同日《后端step单步保存设计说明书》v1.2已更正Errno22真实根因为time_utils潜伏bug(与WAL无关),DELETE属误诊白做但无害、当时未回退。
            #   2026-07-17 E2E验证暴露DELETE模式在chat_message_steps膨胀185万行/2.7GB时写I/O拥塞(每次写journal+fsync),
            #   致create_session同步写>10s超时;故改回WAL统一三库,消除写拥塞。
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=500")  # #14: 30000→500ms (快速失败, 应用层指数退避重试, 不空等30s) — 小欧 2026-07-23
            # M-05: SQLite默认OFF，外键约束不生效 — 小欧 2026-07-10
            conn.execute("PRAGMA foreign_keys=ON")
            
            yield _ParamSafeConnection(conn)  # 小欧 2026-07-18: 参数安全闸门包装, 校验SQL参数类型(非基元类型抛清晰错误)

            conn.commit()
            
        except sqlite3.Error as e:
            # DB级错误(连接/SQL/事务): 回滚 + 记"DB operation failed" — 小欧 2026-07-15
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    logger.warning(f"[db] rollback 失败: {db_name}")
            logger.error(f"DB operation failed [{db_name}]: {e}")
            raise
        except Exception as e:
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
        """
        import time as _time
        for attempt in range(max_retries + 1):
            try:
                with self.get_conn(db_name) as conn:
                    yield conn
                return  # 成功: 退出
            except sqlite3.OperationalError as e:
                if "locked" not in str(e):
                    raise  # 非locked异常不重试
                if attempt == max_retries:
                    logger.error(f"[db] {db_name} locked, {max_retries}次重试后放弃")
                    raise
                delay = 0.5 * (2 ** attempt)  # 0.5, 1, 2 (max_retries=3, 总~3.5s, 控制time.sleep不阻塞事件循环过长) — 小欧 2026-07-23
                logger.warning(f"[db] {db_name} locked, 第{attempt+1}/{max_retries}次重试, 等待{delay:.1f}s")
                _time.sleep(delay)
            except sqlite3.IntegrityError:
                raise  # UNIQUE约束不重试(YAGNI)

    def init(self):
        """初始化所有数据库(应用启动时调用)"""
        import time as _time
        logger.info("Initializing all databases...")
        _ta = _time.time()
        init_chat_db(self.get_conn)
        logger.info(f"[启动耗时] init_chat_db: {_time.time()-_ta:.3f}s")
        _tb = _time.time()
        init_operations_db(self.get_conn)
        logger.info(f"[启动耗时] init_operations_db: {_time.time()-_tb:.3f}s")
        _tc = _time.time()
        init_task_tracker_db(self.get_conn)
        logger.info(f"[启动耗时] init_task_tracker_db: {_time.time()-_tc:.3f}s")
        logger.info(f"[启动耗时] db.init 合计: {_time.time()-_ta:.3f}s")
        logger.info("All databases initialized successfully")
    
    def init_observer(self):
        """初始化observer数据库(后续实现ToolObserver时调用)"""
        logger.info("Observer database initialized (placeholder)")


# 全局SDK实例(唯一入口)
db = DatabaseManager()
