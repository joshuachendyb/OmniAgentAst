# -*- coding: utf-8 -*-
"""
tests/conftest.py — 全局测试夹具

编辑历史:
  2026-09-26 - 小欧 - [72]第九章(9.6-3) 新建。**统一为 TestClient 请求注入访问口令**。

背景：第九章给 12 个 router 挂了统一 token 鉴权（`app/api/v1/deps.verify_token`），
  凡未带口令的请求一律 401。项目内用 `fastapi.testclient.TestClient` 的测试
  （test_settings_routes_tdd / test_remote_models_tdd / test_tdd_64_sampling_params）
  默认不带口令 → 集体 401。

处置（按 9.6-3「统一注入，不逐个用例改」）：
  在此用**autouse fixture** 给每个 `TestClient(app)` 实例挂上 `Authorization` 头，
  新建的 client 自动带口令；已建的 client 也会补上（幂等）。测试代码零改动。

口令来源（与 e2e_helpers.AUTH_HEADERS 同一口径）：
  ① 环境变量 OMNIAGENT_ACCESS_TOKEN 优先
  ② 回落读 ~/.omniagent/config.yaml 的 security.access_token
  ③ 都没有 → 用固定测试口令（后端未配置口令时本就会 fail-closed 拒绝，
     故此时设 OMNIAGENT_REQUIRE_AUTH=0 由 fixture 兜底，见下方 _autouse_force_off_when_unset）
"""
import os
import sqlite3
from pathlib import Path

import pytest

TEST_TOKEN = "test-only-token-for-local-cases"


# 2026-10-03 小欧 - 文档[4] 5.11.1 P0: 新增共享内存库夹具(供文档[4] 第5章新增 case 复用)。
#   逐字搬运自 test_s2_s4_review_bugs.py:27-85(AGENTS 1.4「能复制就复制, 不重写」), 仅两处改动:
#     ① chat_sessions 增 link_enabled 列(文档[4] 5.7 项1 的会话级真源列, Phase B′ 的 case 依赖它)
#     ② _build_schema 增加一行差异说明
#   范围说明(重要): 存量有 7 份各自独立的 _build_schema(test_artifacts_11_6 / test_s2_s4_review_bugs /
#     test_t3_trust_norm_domain / test_t4_trust_revoke_consistency / test_token_accumulation_11_1 /
#     test_trust_v15 / test_v2_storage_regression)与 4 份模块内 conn fixture。本次**刻意不合并、不删除**任何
#     存量副本 —— 模块内定义优先于 conftest, 保留它们对既有测试行为零影响; 7 份建表脚本副本属存量 DRY 债务,
#     与本次改造无关, 按 YAGNI 不在本次范围内重构。新 case 一律用本 conftest 提供的 conn。
def _build_schema(conn) -> None:
    """构建与 db_initializer 一致的最小表结构（v2.0 + 2026-08-22 model归一 JSON 列 — 小欧 2026-08-23 同步）
    2026-10-03 小欧 - 文档[4] 5.11.1: chat_sessions 增 link_enabled BOOLEAN DEFAULT FALSE
      （生产侧由 db_initializer._ensure_column 幂等补列, 见 5.7 项1；测试侧须同步, 否则
        get_session_link 的 case 会红在 sqlite3.OperationalError: no such column —— 属环境错(无效 Red)）"""
    conn.executescript("""
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT, updated_at TEXT,
            message_count INTEGER DEFAULT 0, is_deleted BOOLEAN DEFAULT FALSE, is_valid BOOLEAN DEFAULT FALSE,
            title_locked BOOLEAN DEFAULT FALSE, title_updated_at TEXT, version INTEGER DEFAULT 1,
            sessionModel TEXT,
            link_enabled BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, timestamp TEXT, display_name TEXT, task_id TEXT,
            client_os TEXT, browser TEXT, device TEXT, network TEXT, user_message_id INTEGER,
            status TEXT, thought TEXT
        );
        CREATE TABLE chat_task_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ai_message_id INTEGER NOT NULL, session_id TEXT NOT NULL,
            step_index INTEGER NOT NULL, step_json TEXT NOT NULL, created_at TEXT, task_id TEXT,
            usage TEXT, user_message_id INTEGER
        );
        -- 2026-10-02 小欧 - 补生产唯一索引(对齐 db_initializer.py:350), ON CONFLICT 幂等化依赖它
        CREATE UNIQUE INDEX idx_steps_unique
            ON chat_task_steps(ai_message_id, task_id, step_index);
        CREATE TABLE chat_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT UNIQUE NOT NULL, session_id TEXT NOT NULL,
            user_message_id INTEGER, user_input TEXT, response TEXT, artifacts TEXT DEFAULT '[]',
            status TEXT DEFAULT 'executing', start_time TEXT, end_time TEXT, duration REAL,
            context_link_mode TEXT, context_root_task_id TEXT, sessionModel TEXT NOT NULL,
            accumulated_usage TEXT DEFAULT '{}', llm_call_count INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 0,
            retry_count INTEGER DEFAULT 0, max_steps INTEGER DEFAULT 0, error_type TEXT, error_message TEXT,
            ai_message_id INTEGER, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE chat_user_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, content TEXT NOT NULL,
            task_id TEXT, response TEXT, reasoning TEXT, outcome TEXT, chat_model TEXT,
            accumulated_usage TEXT, client_os TEXT, browser TEXT, device TEXT, network TEXT, created_at TEXT
        );
        CREATE TABLE token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, task_id TEXT NOT NULL,
            llm_call_count INTEGER NOT NULL, task_model TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE chat_session_trust (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            created_at TEXT,
            UNIQUE(session_id, tool_name)
        );
    """)


@pytest.fixture()
def conn():
    """内存 SQLite + 建表 —— 供 storage / history_loader 层单测直接使用（文档[4] 5.11）。"""
    cn = sqlite3.connect(":memory:")
    cn.row_factory = sqlite3.Row
    _build_schema(cn)
    yield cn
    cn.close()


@pytest.fixture()
def chat_db(tmp_path, monkeypatch):
    """独立 chat 文件库 + 走真 init_chat_db 建表（与 conftest.isolated_config_dir 同款隔离，够不到真库）。

    2026-10-03 小欧 - 文档[4] 5.11.1 P0: 逐字搬运自 test_journal_steps_reconcile.py:26-33（不重写，AGENTS 1.4）。
      用途：凡需驱动**真** db_initializer（含 _ensure_column 补列）的 case 必须用它 —— 内存 conn 的
      _build_schema 是手写脚本、**不经** _ensure_column，用 conn 测补列属无效验证。
    """
    from app.db import db as db_manager
    from app.db.db_initializer import init_chat_db
    monkeypatch.setitem(db_manager._db_overrides, "chat", str(tmp_path / "chat.db"))
    init_chat_db(db_manager.get_conn)
    yield


def _resolve_token() -> str:
    env = (os.environ.get("OMNIAGENT_ACCESS_TOKEN") or "").strip()
    if env:
        return env
    try:
        p = Path.home() / ".omniagent" / "config.yaml"
        if p.exists():
            import yaml
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            tok = str((data.get("security") or {}).get("api_token") or "").strip()
            if tok:
                return tok
    except Exception:
        pass
    return TEST_TOKEN


@pytest.fixture(autouse=True)
def _inject_auth_token_into_testclient(request):
    """给本用例内**新建的** TestClient 统一挂 Authorization 头（[72]第九章 9.6-3）。

    实现方式：包装 fastapi.testclient.TestClient 构造，使其默认 headers 带 Bearer。
    仅在本测试进程内生效，不影响生产代码与其它测试语义。
    """
    from fastapi.testclient import TestClient as _TC

    token = _resolve_token()
    if not token:
        yield
        return

    # 后端确实配置了口令才注入；未配置时后端 fail-closed 会拒绝一切请求，
    # 此时由 _autouse_force_off_when_unset 关闭鉴权（仅测试进程内）
    from app.api.v1.deps import _resolve_configured_token
    if not _resolve_configured_token():
        os.environ.setdefault("OMNIAGENT_REQUIRE_AUTH", "0")
        yield
        return

    orig_init = _TC.__init__

    def patched_init(self, *args, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("Authorization", f"Bearer {token}")
        kwargs["headers"] = headers
        orig_init(self, *args, **kwargs)

    _TC.__init__ = patched_init
    try:
        yield
    finally:
        _TC.__init__ = orig_init


# =============================================================================
# 配置隔离: 真 config.yaml 一律只读, 测试全部读写临时副本
# =============================================================================
# 2026-09-26 - 小欧 - 按北京老陈指令根治「测试把真配置弄脏」:
#   事故链(实测): tests/test_p9_08_reload_scenarios.py 为测 L2 热重载, 会**真改**
#   F:\OmniAgentAs-repair\config\config.yaml 的 ai.model_ref(该文件 _write_real_model 函数),
#   靠 `real_config` 夹具在 teardown 逐字还原。但**进程被杀(超时/中断/Ctrl-C)时 teardown 不执行**,
#   真配置就被永久留在切换状态。实测已发生两次:
#     ① 基线副本里存着 opencodeZen/deepseek-v4-flash-free —— 开工前就被留在脏状态;
#     ② 本轮我中途打断测试 → 真配置停在 sensenova/sensenova-6.8-flash-lite。
#   根因: 靠"事后还原"兜底, 而还原不是可靠机制(进程可随时被杀)。
#   根治(北京老陈 2026-09-26 定): **永不碰真配置** —— 靠 app/config.py:276 get_config_path()
#   的 OMNIAGENT_CONFIG_PATH 分支(唯一入口, DRY 单源)把整个测试进程的读写重定向到临时副本。
#   真配置退化为"只读模板", 任何中断/超时都不可能污染它(可证: 写操作根本够不到真文件)。
import shutil
import tempfile

import app.config as _app_config


@pytest.fixture(scope="session", autouse=True)
def isolated_config_dir():
    """会话级配置隔离夹具: 把整个测试进程的配置读写重定向到临时副本, 真 config.yaml 只读。

    ── 为什么需要它(事故链, 均为实测) ──────────────────────────────────────
    本文件原先让 tests/test_reload_scenarios.py(原 test_p9_08)为测 L2 热重载去**真改**
    F:\\OmniAgentAs-repair\\config\\config.yaml 的 ai.model_ref, 靠 real_config 夹具在
    teardown 逐字还原。但「事后还原」不是可靠机制 —— 进程被杀(测试超时 / Ctrl-C / 窗口关闭)
    时 teardown 根本不执行, 真配置就永久留在切换状态。已实际发生两次:
      ① 开工时基线副本里就存着脏值 opencodeZen/deepseek-v4-flash-free(上一轮遗留);
      ② 本轮中途打断测试, 真配置停在 sensenova/sensenova-6.8-flash-lite。
    根治思路(北京老陈 2026-09-26 定): 不修"还原", 而让真配置**根本不可写** ——
    真配置退化为「只读模板」, 写操作全部够不到它。

    ── 怎么做到(为什么不 monkeypatch 业务函数) ──────────────────────────────
    系统本来就提供了唯一覆盖入口 app/config.py:276 get_config_path():
        env_path = os.getenv('OMNIAGENT_CONFIG_PATH')
        if env_path: return str(Path(env_path))          # 设了就用它
        return str(_get_code_root() / "config" / filename)
    全项目所有配置读写(read_yaml_config / write_yaml_config / update_provider_config /
    settings_service / model_service / resolver …)都经过这一个函数, 因此:
        只要把 OMNIAGENT_CONFIG_PATH 指到临时副本 → 全链自动改道, 一行业务代码不用动。
    这符合 10 大规范: 复用既有单一权威入口(DRY/复用优先), 而非新造一套并行机制。

    ── 三个易错点(改动本夹具时务必保留) ────────────────────────────────────
    ① 拷的是「只读源」: shutil.copy2(real_path, tmp_path) 只读真配置一次, 此后全程不碰;
    ② 必须清单例: app.config._config_instance 是模块级缓存, 持旧路径数据。
       不置 None 则改道形同虚设(get_config() 会直接返回旧实例);
    ③ 测试代码禁止再硬编码真路径: 必须惰性调 get_config_path() 取当前生效路径。
       惰性还有一个必要理由 —— 本夹具是 session 级, 在 pytest **收集完成之后**才执行;
       若在模块级求值 get_config_path(), 会抢在夹具之前拿到真路径, 隔离直接失效。
    """
    # ① env 未设时 get_config_path() 返回的正是真配置路径, 故必须在设 env 之前取
    real_path = _app_config.get_config_path()
    tmp_dir = Path(tempfile.mkdtemp(prefix="omniagent_test_cfg_"))
    tmp_path = tmp_dir / Path(real_path).name
    if Path(real_path).exists():
        shutil.copy2(real_path, tmp_path)          # 真配置只作只读模板拷一份
    else:
        # 真配置不存在时给最小骨架, 否则本场测试会因"配置文件不存在"集体全红(掩盖真实失败)
        tmp_path.write_text(
            "ai:\n  model_ref:\n    provider: sensenova\n    model: sensenova-6.8-flash-lite\n",
            encoding="utf-8",
        )

    # ② 改道: 此后全进程配置读写一律落临时副本
    prev_env = os.environ.get("OMNIAGENT_CONFIG_PATH")
    os.environ["OMNIAGENT_CONFIG_PATH"] = str(tmp_path)
    # ②-2 数据目录同步改道(小欧 2026-09-30 修订): 配置隔离只管住了 config.yaml, 管不到 SQLite ——
    #   app/db/database.py 原在 __init__ 硬编码 Path.home()/".omniagent", 致任何裸用 db.get_conn() 的
    #   测试直写真库(实测污染真库: 空会话/hello/v2 垃圾会话)。现 database.resolve_db_dir() 认
    #   OMNIAGENT_DATA_DIR 且在 get_conn 内惰性解析, 故此处设 env 即让测试"够不到"真库 ——
    #   无需逐个测试 patch, 也不会漏掉将来新增的测试(AGENTS.md: 根治靠"够不到"而非"事后还原")。
    prev_data_dir = os.environ.get("OMNIAGENT_DATA_DIR")
    os.environ["OMNIAGENT_DATA_DIR"] = str(tmp_dir / "data")
    # ③ 清单例强制按新路径重建(见易错点②)
    _app_config._config_instance = None
    try:
        yield tmp_path
    finally:
        # 还原环境变量与单例, 删除临时目录; 真配置自始至终未被写入, 无需也无法"还原"
        if prev_env is None:
            os.environ.pop("OMNIAGENT_CONFIG_PATH", None)
        else:
            os.environ["OMNIAGENT_CONFIG_PATH"] = prev_env
        if prev_data_dir is None:
            os.environ.pop("OMNIAGENT_DATA_DIR", None)
        else:
            os.environ["OMNIAGENT_DATA_DIR"] = prev_data_dir
        _app_config._config_instance = None
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─── e2e 前置体检(后端不可用则秒级 skip, 不放行后挂死)──────────────
# 小欧 2026-09-29 新建。全量纳入 e2e 后, 后端僵死(端口在听但 HTTP 不应答)会让真实 LLM
# 调用永久挂起 —— 2026-09-29 实测全量在 33% 挂死 30 分钟(test_p9_03 停在 asyncio select)。
# 三层纵深: ①ensure_backend_ready 改 fail-closed; ②pytest.ini timeout 3000→300 兜底;
# ③本钩子收集后统一探活一次, 不可用则 skip e2e, 其余单测照常跑完。

# e2e 用例识别: nodeid 命中即算(与既有 test_p9_* / test_e2e_* 命名一致)
_E2E_NAME_HINTS = ("e2e_", "test_p9_")


def _is_e2e_item(item) -> bool:
    """判定 item 是否为需要活后端的 e2e 用例 — 小欧 2026-09-29"""
    name = item.nodeid.replace("\\", "/")
    return any(hint in name for hint in _E2E_NAME_HINTS)


def pytest_collection_modifyitems(config, items):
    """收集完成后统一探活一次, 后端不可用则 skip 全部 e2e 用例 — 小欧 2026-09-29

    只探一次(而非每 case 各探): 收集阶段探活能覆盖"全量开始时后端是死的"这一主场景,
    且省掉 7~8 次重复探活的 3s+5s 开销。运行中途后端挂掉, 交由 timeout 兜底。
    """
    e2e_items = [it for it in items if _is_e2e_item(it)]
    if not e2e_items:
        return

    # e2e 用例要跑真实 LLM(单用例 3~10 分钟, 实测 INJ-03 = 362s), 远超单测层 timeout=300,
    # 故就地覆盖为 2900s。--timeout 方法为 thread: 触发后强杀线程, 保证全量一定能收尾。
    e2e_timeout = pytest.mark.timeout(2900)
    for it in e2e_items:
        it.add_marker(e2e_timeout)

    # 延迟导入: e2emodel 依赖 e2etests 在 pythonpath 内(pythonpath = . e2etests),
    # 而本文件是 tests/ 的 conftest, 收集期导入失败会连带整场测试报错。
    try:
        from e2emodel.e2e_helpers import ensure_backend_ready
        ready = ensure_backend_ready()
    except Exception as exc:
        print(f"[conftest] e2e 探活器导入异常, 按不可用处理: {exc!r}")
        ready = False

    if ready:
        print(f"[conftest] e2e 前置体检: 后端就绪, {len(e2e_items)} 个 e2e 用例纳入运行")
        return

    reason = ("后端未就绪(:8000 无响应或僵死)。请先启动后端, 再跑全量。"
              "详见 e2etests/全链路E2E测试手册-小健-2026-05-23.md 第六章。")
    print(f"[conftest] e2e 前置体检: 不可用 -> skip {len(e2e_items)} 个 e2e 用例")
    skip = pytest.mark.skip(reason=reason)
    for it in e2e_items:
        it.add_marker(skip)
