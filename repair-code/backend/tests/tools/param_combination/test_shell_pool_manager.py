# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-30 - 小沈 - ShellPoolManager 单元测试: acquire/release/隔离/满池/temp/cleanup/多线程
# 2026-08-06 - 小欧 - MockShell 补齐 _start/_probe 与 v2.7 acquire() Phase2 接口对齐; 并发用例暴露槽位泄漏Bug(100s→41s)
# 2026-08-06 - 小欧 - 测试合理性校准(正确行为校准, 不被错误case误导): ①4个temp用例补@patch(ACQUIRE_WAIT_TIMEOUT)消除10s真实等待(41s→~1s, 测试验证行为而非等待); ②n>=3/n>=2宽松断言精确化(n==3/n==2, 修复D双计后精确可查); ③新增cleanup归还sem槽位回归测试(修复A保护, 断言_v2槽位恢复=满值, 防limiter枯零回归)
# 2026-08-06 - 小欧 - v2.8测试校准(单一信号量硬限流): 删2个temp用例+temp清理用例(死代码); 新增池满抛ShellPoolBusyError/启动失败异常路径归还槽位/double-release不超归/cleanup后release不超归回归; 并发用例把ShellPoolBusyError视为限流正常(非错误), 不误导正确行为
# 2026-08-06 - 小欧 - 修复cleanup_all遗漏: 归还sem槽位(防limiter枯零); 恢复test_cleanup_all_returns_sem_slots回归测试
# 2026-08-06 - 小健 - 打猎测试并入(v2.9): ①MockShell升级为真实语义(_proc属性+_ensure_alive/_start自愈+exec自愈重启镜像真实PersistentShell, 修"MockShell.exec对已关闭实例抛异常"不真实问题); ②新增SemiDeadShell(半死探活失败); ③新增鲁棒性测试: 半死剔除/exec自愈/cleanup_all后再acquire/并发release+cleanup不超归/复用探活失败池干净/高并发sem不越界守恒/并发后槽位全归还; ④修复用例错误: hunt_1把ShellPoolBusyError当错误记录(应为限流正常)、hunt_8断言范围写错(合法0~max), 均校准
# 2026-08-06 - 小健 - 打猎测试并入(v2.10): 新增BlockingStartShell(_start第一次阻塞后失败/第二次成功, 配_gate放行) + TestShellPoolAcquireCleanupRace两用例, 确定性复现Bug#7「acquire Phase2阻塞期间并发cleanup原子pop+sem.release归还槽位 → Phase3重试注册新实例后调用方release再归一次 → BoundedSemaphore超归ValueError」; 修复(acquire owning_slot/lost_slot重取槽)后两用例绿, 池套件28→30用例
# 2026-08-06 - 小欧 - v2.11测试(C13死实例放回池): 新增3用例 → ①死实例(_proc=None, 模拟C8/C14超时close)release不放回池+close+下次acquire新建; ②进程自然退出(poll非None)release不放回池; ③对照健康实例正常放回池复用(功能零退化)。池套件30→33用例
"""
test_shell_pool_manager — ShellPoolManager 单元测试

用 MockShell 替代真实 PersistentShell（不启动真实子进程），
专注测试池管理逻辑：acquire/release/隔离/满池/cleanup/并发/鲁棒性。 — 小沈 2026-07-30
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.tools.fundamental.shell_engine import ShellPoolBusyError, ShellPoolManager


class MockShell:
    """轻量 MockShell — 替代 PersistentShell，记录生命周期"""
    _counter = 0

    def __init__(self, workdir=None, shell_type="ps7"):
        self.workdir = workdir
        self.shell_type = shell_type
        MockShell._counter += 1
        self._seq = MockShell._counter
        self._alive = True
        self._closed = False
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        # 镜像真实 PersistentShell._proc（供 acquire C6 淘汰日志 / get_all_pids 使用） — 小健 2026-08-06
        self._proc = type("P", (), {"pid": 9000 + self._seq, "poll": lambda self: None})()

    def _ensure_alive(self, env=None) -> bool:
        # 镜像真实 PersistentShell._ensure_alive: 死进程/未启动 → _start 重启 — 小健 2026-08-06
        if self._alive and self._proc and self._proc.poll() is None:
            return True
        return self._start(env)

    def _start(self, env=None) -> bool:
        """模拟启动(新实例): 总是成功, 且自愈重启(死实例变活) — 小健 2026-08-06 对齐真实语义"""
        self._alive = True
        self._closed = False
        return True

    def _probe(self, env=None, timeout=None) -> bool:
        """模拟响应性探活: alive 即健康 — 小健 2026-08-06 与 acquire Phase2 对齐"""
        return self._alive

    def close(self):
        self._closed = True
        self._alive = False

    def exec(self, command, timeout=60, env=None):
        # 镜像真实 PersistentShell.exec: 已关闭实例自愈重启(调 _start), 不抛崩溃级异常 — 小健 2026-08-06
        for attempt in range(2):
            if not self._ensure_alive(env):
                if attempt == 0:
                    continue
                return {"stdout": "", "stderr": "", "exit_code": -1}
            return {"stdout": f"mock-{self._seq}", "stderr": "", "exit_code": 0}
        return {"stdout": "", "stderr": "", "exit_code": -1}

    @property
    def current_dir(self):
        return self.workdir

    @classmethod
    def reset_counter(cls):
        cls._counter = 0


class FailingShell(MockShell):
    """启动失败的Shell — 模拟 pwsh 不可用, _start 恒 False — 小欧 2026-08-06"""
    def _start(self, env=None) -> bool:
        return False


class SemiDeadShell(MockShell):
    """半死: 进程活着但响应性探活失败(_probe恒False) → acquire Phase2探活失败 → Phase3销毁剔除 — 小健 2026-08-06"""
    def _probe(self, env=None, timeout=None) -> bool:
        return False


class BlockingStartShell(MockShell):
    """Bug#7 竞态模拟: _start 第一次阻塞(可被外部放行)后失败, 第二次(重试)成功 — 小健 2026-08-06
    配合并发 cleanup_by_task: acquire Phase2 阻塞期间 cleanup 原子pop+sem.release 归还槽位
    → 复现「重试注册新实例后调用方 release 再归一次 → BoundedSemaphore 超归 ValueError」"""
    _gate = None

    def __init__(self, workdir=None, shell_type="ps7"):
        super().__init__(workdir, shell_type)
        self._seq = MockShell._counter   # 取创建序号(同测试内递增), 供断言重试到第2个

    def _start(self, env=None) -> bool:
        if self._seq == 1:   # 第一个实例: 阻塞等放行
            self._gate.wait(5)
            return False     # 放行后失败 → Phase3剔除 → 重试
        self._alive = True
        return True


@pytest.fixture(autouse=True)
def reset_mock_counter():
    MockShell.reset_counter()
    yield


@pytest.fixture
def pool():
    """创建一个 max_per_type=2 的池，便于触发满池分支"""
    return ShellPoolManager(max_per_type=2)


class TestShellPoolAcquireRelease:
    """基本 acquire/release"""

    def test_acquire_basic(self, pool):
        with patch.object(pool, "_make_shell", return_value=MockShell()):
            inst = pool.acquire("task1", "ps7")
            assert inst is not None
            pool.release(inst)

    def test_acquire_release_different_tasks(self, pool):
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task2", "ps7")
            assert a is not b  # 不同任务隔离
            pool.release(a)
            pool.release(b)

    def test_release_idle_reuse(self, pool):
        """release 后 acquire → 拿到同一个实例"""
        with patch.object(pool, "_make_shell", return_value=MockShell()):
            a = pool.acquire("task1", "ps7")
            pool.release(a)
            b = pool.acquire("task1", "ps7")
            assert a is b  # 复用

    def test_acquire_same_task_same_type(self, pool):
        """同一任务 shell_type 命中同一个池"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            assert a is not b  # 2 个不同实例
            assert pool._pool[("task1", "ps7")] == [a, b]
            pool.release(a)
            pool.release(b)

    def test_acquire_same_task_different_shell_type(self, pool):
        """不同 shell_type 分到不同池"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps5")
            assert a is not b
            assert ("task1", "ps7") in pool._pool
            assert ("task1", "ps5") in pool._pool
            pool.release(a)
            pool.release(b)


class TestShellPoolMaxPerType:
    """满池测试 — v2.8 单一信号量硬限流: 超限明确抛异常(不temp绕过限流)"""

    def test_pool_fills_and_reuses_idle(self, pool):
        """先填满 max_per_type=2, 释放后复用"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            pool.release(a)
            pool.release(b)
            c = pool.acquire("task1", "ps7")
            d = pool.acquire("task1", "ps7")
            assert c is a  # 先释放的先复用
            assert d is b

    @patch("app.tools.fundamental.shell_engine.ACQUIRE_WAIT_TIMEOUT", 0.05)
    def test_pool_full_raises(self, pool):
        """v2.8: 同key并发超上限 → 明确抛异常(不temp), 释放后恢复"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            sem = pool._sem[("task1", "ps7")]
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            assert sem._value == 0  # 2 槽全占
            with pytest.raises(ShellPoolBusyError):
                pool.acquire("task1", "ps7")  # busy 2/2, 拿不到槽 → 明确失败(非temp非卡死)
            pool.release(a)
            pool.release(b)
            c = pool.acquire("task1", "ps7")  # 释放后恢复
            assert c is not None
            pool.release(c)

    def test_acquire_failure_returns_sem(self, pool):
        """v2.8: 启动失败抛异常后, 槽位必须归还(异常路径防泄漏)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: FailingShell()):
            sem = pool._sem[("task1", "ps7")]
            with pytest.raises(RuntimeError):
                pool.acquire("task1", "ps7")
            assert sem._value == pool._max_per_type  # 异常路径归还槽位


class TestShellPoolCleanup:
    """cleanup_by_task / cleanup_all"""

    def test_cleanup_by_task_returns_sem_slot(self, pool):
        """修复A回归: cleanup_by_task 清理忙(busy)实例必须归还信号量槽位, 防 limiter 枯零(teardown后free 2→1→0→0)导致后续acquire卡满超时"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            sem = pool._sem[key]
            assert sem._value == pool._max_per_type  # 初始满槽=2
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            assert sem._value == 0  # 2 槽全占(busy)
            # 关键: 不 release 直接 cleanup — 模拟 task teardown 清理 busy 实例(真实泄漏路径)
            pool.cleanup_by_task("task1")
            # 修复A: cleanup 归还忙实例槽位, 不复现 free 2→1→0→0 枯零
            assert sem._value == pool._max_per_type
            assert len(pool._busy) == 0
            assert a._closed and b._closed
            # 槽位健康 → 后续 acquire 立即成功(无需等满超时走temp)
            c = pool.acquire("task1", "ps7")
            assert c is not None
            assert c._closed is False
            pool.release(c)

    def test_cleanup_all_returns_sem_slots(self, pool):
        """修复A回归: cleanup_all 归还所有实例的槽位(防 limiter 枯零)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task2", "ps7")
            pool.release(a)
            pool.release(b)
            pool.cleanup_all()
            assert pool._sem[("task1", "ps7")]._value == pool._max_per_type
            assert pool._sem[("task2", "ps7")]._value == pool._max_per_type
            assert len(pool._pool) == 0
            assert len(pool._busy) == 0

    def test_cleanup_by_task_other_task_unaffected(self, pool):
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task2", "ps7")
            pool.release(a)
            pool.release(b)
            pool.cleanup_by_task("task1")
            assert b._closed is False  # task2 的实例还在
            pool.cleanup_by_task("task2")
            assert b._closed is True

    def test_cleanup_all(self, pool):
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task2", "ps7")
            pool.release(a)
            pool.release(b)
            n = pool.cleanup_all()
            assert n == 2
            assert a._closed
            assert b._closed
            assert len(pool._pool) == 0
            assert len(pool._inst_map) == 0
            assert len(pool._busy) == 0


class TestShellPoolConcurrency:
    """并发安全测试"""

    @patch("app.tools.fundamental.shell_engine.ACQUIRE_WAIT_TIMEOUT", 0.05)
    def test_concurrent_acquire_release(self, pool):
        """多线程并发 acquire/release 不崩; ShellPoolBusyError 是限流正常结果(非错误)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            n_threads = 8
            results = []
            errors = []

            def worker():
                ok = 0
                busy = 0
                try:
                    for _ in range(10):
                        try:
                            inst = pool.acquire("task1", "ps7")
                            time.sleep(0.001)
                            pool.release(inst)
                            ok += 1
                        except ShellPoolBusyError:
                            busy += 1   # 同key并发>max: 限流明确失败(正常)
                        except Exception as e:
                            errors.append(str(e))
                    results.append((ok, busy))
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            assert len(errors) == 0, f"并发错误: {errors}"
            assert len(results) == n_threads
            assert sum(ok for ok, _ in results) > 0  # 至少有成功执行的

    @patch("app.tools.fundamental.shell_engine.ACQUIRE_WAIT_TIMEOUT", 0.05)
    def test_concurrent_cleanup_by_task(self, pool):
        """cleanup_by_task 和 acquire 并发不冲突"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            # 先在 task1 占满 2 槽
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            pool.release(a)
            pool.release(b)
            # 并发：一边 cleanup，一边 acquire
            errors = []

            def clean():
                try:
                    pool.cleanup_by_task("task1")
                except Exception as e:
                    errors.append(str(e))

            t = threading.Thread(target=clean)
            t.start()
            time.sleep(0.005)
            d = pool.acquire("task1", "ps7")  # 可能复用(cleanup前)或新建(cleanup后槽位已归还)
            pool.release(d)
            t.join(timeout=10)
            assert len(errors) == 0


class TestShellPoolEdgeCases:
    """边界情况"""

    def test_double_release(self, pool):
        """double release 安全不崩溃, 且不超归(BoundedSemaphore超归会ValueError)"""
        with patch.object(pool, "_make_shell", return_value=MockShell()):
            sem = pool._sem[("task1", "ps7")]
            inst = pool.acquire("task1", "ps7")
            assert sem._value == 1
            pool.release(inst)
            assert sem._value == pool._max_per_type  # 归还
            pool.release(inst)  # 第二次无副作用
            assert sem._value == pool._max_per_type  # 不超归(靠 _inst_map 防重入)

    def test_release_after_cleanup_no_overrelease(self, pool):
        """v2.8: cleanup 后再 release 已清理实例, 不超归"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            sem = pool._sem[("task1", "ps7")]
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            pool.cleanup_by_task("task1")  # 归还 2 槽
            assert sem._value == pool._max_per_type
            pool.release(a)  # _inst_map 已被 cleanup pop → 无副作用, 不超归
            pool.release(b)
            assert sem._value == pool._max_per_type

    def test_release_unknown(self, pool):
        """release 未跟踪的实例安全"""
        inst = MockShell()
        pool.release(inst)  # 不应抛异常
        assert True

    def test_acquire_different_workdir(self, pool):
        """workdir 参数传递到 _make_shell"""
        collected = []

        def _make(st, w):
            collected.append((st, w))
            return MockShell()

        with patch.object(pool, "_make_shell", side_effect=_make):
            pool.acquire("task1", "ps7", workdir="/tmp/test")
            assert collected[0][1] == "/tmp/test"

    def test_cleanup_by_task_empty(self, pool):
        """空任务 cleanup 安全"""
        n = pool.cleanup_by_task("nonexistent")
        assert n == 0


class TestShellPoolRobustness:
    """鲁棒性: 半死剔除/exec自愈/槽位守恒 — 小健 2026-08-06"""

    def test_semidead_probe_false_evicts(self, pool):
        """半死实例(复用探活失败)必须被销毁剔除, acquire拿到健康实例, 槽位守恒"""
        made = []
        def _make(*a):
            m = SemiDeadShell()
            made.append(m)
            return m
        with patch.object(pool, "_make_shell", side_effect=_make):
            sem = pool._sem[("task1", "ps7")]
            inst = pool.acquire("task1", "ps7")   # 半死 → Phase3剔除 → 重试新建
            assert inst is not None
            assert sem._value == 1                  # 仍占1槽(重试共用, 不泄漏)
            pool.release(inst)
            assert sem._value == pool._max_per_type

    def test_exec_after_close_self_heals(self, pool):
        """exec已关闭实例 → 自愈重启(不崩溃、返回exit_code=0)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            inst = pool.acquire("task1", "ps7")
            pool.cleanup_by_task("task1")   # 关闭inst, 但外部仍持有引用
            r = inst.exec("echo x")
            assert r.get("exit_code") == 0, f"应自愈重启返回0, 实际: {r}"

    def test_acquire_after_cleanup_all(self, pool):
        """cleanup_all 后再 acquire → 新健康实例, 槽位正常"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            pool.release(a)
            pool.release(b)
            n = pool.cleanup_all()
            assert n == 2
            c = pool.acquire("task1", "ps7")
            assert c is not None and c._closed is False
            pool.release(c)

    def test_reuse_probe_fail_then_pool_clean(self, pool):
        """复用实例探活失败→剔除, 池中无残留"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            a = pool.acquire("task1", "ps7")   # a 保持 busy(不release), 占用1槽
            # 手动注入半死实例到池, 模拟池中被污染(非busy, 空闲可用)
            bad = SemiDeadShell()
            with pool._lock:
                key = ("task1", "ps7")
                pool._pool[key].append(bad)
                pool._last_used[id(bad)] = time.time()
            # 复用bad→probe False→Phase3剔除销毁→新建健康实例
            b = pool.acquire("task1", "ps7")
            assert b is not bad
            assert b._closed is False
            assert bad._closed is True
            pool.release(a)
            pool.release(b)
            with pool._lock:
                assert bad not in pool._pool[("task1", "ps7")]

    def test_release_cleanup_concurrent_no_overrelease(self, pool):
        """并发 cleanup_by_task + release 同一实例池 → 槽位守恒, 不超归(BoundedSemaphore超归即ValueError)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            for _ in range(300):
                a = pool.acquire("task1", "ps7")
                b = pool.acquire("task1", "ps7")
                sem = pool._sem[key]
                t = threading.Thread(target=pool.cleanup_by_task, args=("task1",))
                t.start()
                pool.release(a)          # 与cleanup并发
                pool.release(b)
                t.join(timeout=5)
                assert 0 <= sem._value <= pool._max_per_type, f"第{_}轮sem越界: {sem._value}"
            assert pool._sem[key]._value == pool._max_per_type

    def test_release_after_cleanup_order_invariant(self, pool):
        """release 与 cleanup 顺序不定 → 均不超归"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            for _ in range(200):
                a = pool.acquire("task1", "ps7")
                sem = pool._sem[("task1", "ps7")]
                if _ % 2 == 0:
                    pool.release(a)
                    pool.cleanup_by_task("task1")
                else:
                    pool.cleanup_by_task("task1")
                    pool.release(a)
                assert 0 <= sem._value <= pool._max_per_type, f"sem越界: {sem._value}"

    def test_release_dead_instance_not_returned_to_pool(self, pool):
        """[卡死C13] v2.11: C8/C14超时关闭后(死实例, _proc=None) release → 不放回池, 直接close。
        否则下次acquire复用死实例→probe见_proc=None→反复C13噪音。"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            inst = pool.acquire("task1", "ps7")
            # 模拟 C8/C14 命令超时: _exec_locked 内部 _close() 已置 _proc=None(死实例)
            inst._proc = None
            inst._alive = False
            pool.release(inst)
            # 死实例不放回池
            with pool._lock:
                assert inst not in pool._pool[key], "死实例不应放回池"
                assert pool._last_used.get(id(inst)) is None
            assert inst._closed is True, "死实例应被close"
            # 下次acquire应新建健康实例(不复用死实例 → 不触发C13)
            b = pool.acquire("task1", "ps7")
            assert b is not inst and b._closed is False
            pool.release(b)
            assert pool._sem[key]._value == pool._max_per_type

    def test_release_exited_process_not_returned_to_pool(self, pool):
        """[卡死C13] v2.11: 进程自然退出(poll()非None) release → 不放回池, 直接close"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            inst = pool.acquire("task1", "ps7")
            # 模拟进程已退出: _proc 非None但 poll() 返回非None
            inst._proc = type("P", (), {"pid": 9001, "poll": lambda self: 1})()
            inst._alive = False
            pool.release(inst)
            with pool._lock:
                assert inst not in pool._pool[key], "进程已退出的实例不应放回池"
            assert inst._closed is True

    def test_release_live_instance_still_returned(self, pool):
        """[卡死C13] v2.11 对照: 健康实例正常放回池(功能零退化)"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            inst = pool.acquire("task1", "ps7")
            pool.release(inst)
            with pool._lock:
                assert inst in pool._pool[key], "健康实例应放回池供复用"
            # 复用同一健康实例(不新建)
            b = pool.acquire("task1", "ps7")
            assert b is inst and b._closed is False
            pool.release(b)

    def test_slot_invariant_after_cleanup(self, pool):
        """不变量: 已占用槽位数 == _inst_map 中仍跟踪的实例数"""
        with patch.object(pool, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("task1", "ps7")
            a = pool.acquire("task1", "ps7")
            b = pool.acquire("task1", "ps7")
            assert pool._sem[key]._value == pool._max_per_type - 2
            assert len(pool._inst_map) == 2
            pool.cleanup_by_task("task1")   # 原子pop归还2槽
            assert pool._sem[key]._value == pool._max_per_type
            assert len(pool._inst_map) == 0
            pool.release(a)   # 已pop无副作用
            pool.release(b)
            assert pool._sem[key]._value == pool._max_per_type


class TestShellPoolAcquireCleanupRace:
    """Bug#7: acquire Phase2阻塞重试 与 并发cleanup 的 sem双归竞态 — 小健 2026-08-06
    根因: acquire已acquire 1槽后, Phase2阻塞期间并发cleanup原子pop+sem.release归还槽位;
    若 acquire Phase3 重试并注册新实例, 调用方 release(Y) 会再归一次 → BoundedSemaphore超归ValueError"""

    def _acquire_with_blocking_start(self, max_per_type, gate):
        BlockingStartShell._gate = gate
        p = ShellPoolManager(max_per_type=max_per_type)
        acquired = []

        def do_acquire():
            try:
                acquired.append(p.acquire("t", "ps7"))
            except Exception as e:
                acquired.append(e)

        with patch.object(p, "_make_shell", side_effect=lambda *a: BlockingStartShell()):
            t = threading.Thread(target=do_acquire)
            t.start()
            time.sleep(0.3)          # 等 acquire 进入 Phase2 阻塞在 _start
            p.cleanup_by_task("t")   # 并发 cleanup: pop X注册 + sem.release
            gate.set()               # 放行 → X._start失败 → Phase3剔除 → 重试Y
            t.join(timeout=5)
        return p, acquired

    def test_blocking_start_concurrent_cleanup_no_overrelease(self):
        """Bug#7主复现: acquire被cleanup夺槽后重试, release(Y)不得超归, 槽位守恒"""
        gate = threading.Event()
        p, acquired = self._acquire_with_blocking_start(1, gate)

        assert len(acquired) == 1
        inst = acquired[0]
        assert not isinstance(inst, Exception), f"acquire异常: {inst}"
        assert isinstance(inst, BlockingStartShell)
        assert inst._seq == 2, f"应重试到第2个实例, 实际 #{inst._seq}"

        key = ("t", "ps7")
        try:
            p.release(inst)
        except ValueError as e:
            pytest.fail(f"Bug#7确认: 重试实例release超归 ValueError: {e}")
        assert p._sem[key]._value == p._max_per_type, f"槽位未恢复: {p._sem[key]._value}"

    def test_blocking_acquire_retry_sem_conserved(self):
        """Bug#7关联: 整个acquire重试期间 sem不越界, 槽位守恒(多槽场景)"""
        gate = threading.Event()
        p, acquired = self._acquire_with_blocking_start(2, gate)

        assert len(acquired) == 1
        inst = acquired[0]
        assert not isinstance(inst, Exception), f"acquire异常: {inst}"
        key = ("t", "ps7")
        try:
            p.release(inst)
        except ValueError as e:
            pytest.fail(f"Bug#7确认: 重试实例release超归: {e}")
        assert p._sem[key]._value == p._max_per_type, f"槽位未恢复: {p._sem[key]._value}"


class TestShellPoolStressConcurrency:
    """高并发压力: sem 守恒 + 槽位全归还 — 小健 2026-08-06"""

    @patch("app.tools.fundamental.shell_engine.ACQUIRE_WAIT_TIMEOUT", 0.02)
    def test_sem_never_underflow_or_overflow(self):
        """高并发 acquire/release: sem._value 恒在 [0, max] 内, 最终全归还"""
        p = ShellPoolManager(max_per_type=4)
        with patch.object(p, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("t", "ps7")
            stop = threading.Event()
            errors = []

            def worker():
                try:
                    while not stop.is_set():
                        try:
                            inst = p.acquire("t", "ps7")
                        except ShellPoolBusyError:
                            continue   # 限流正常结果, 非错误
                        if not (0 <= p._sem[key]._value <= 4):
                            errors.append(f"sem越界: {p._sem[key]._value}")
                        time.sleep(0.0005)
                        p.release(inst)
                        if not (0 <= p._sem[key]._value <= 4):
                            errors.append(f"sem越界(release后): {p._sem[key]._value}")
                except Exception as e:
                    errors.append(f"worker异常: {type(e).__name__}: {e}")

            threads = [threading.Thread(target=worker) for _ in range(6)]
            for t in threads:
                t.start()
            time.sleep(1.0)
            stop.set()
            for t in threads:
                t.join(timeout=10)
            assert not errors, f"并发错误: {errors[:5]}"
            assert p._sem[key]._value == 4   # 全部归还

    @patch("app.tools.fundamental.shell_engine.ACQUIRE_WAIT_TIMEOUT", 0.01)
    def test_cleanup_release_race_no_overrelease_stress(self):
        """强化: 大量并发 cleanup + release → 槽位守恒, 永不超归"""
        p = ShellPoolManager(max_per_type=3)
        with patch.object(p, "_make_shell", side_effect=lambda *a: MockShell()):
            key = ("t", "ps7")
            errors = []

            def hammer(i):
                try:
                    for _ in range(200):
                        try:
                            inst = p.acquire("t", "ps7")
                        except ShellPoolBusyError:
                            continue   # 限流正常
                        if (i + _) % 2 == 0:
                            p.release(inst)
                            p.cleanup_by_task("t")
                        else:
                            p.cleanup_by_task("t")
                            p.release(inst)
                except Exception as e:
                    errors.append(f"w{i}: {type(e).__name__}: {e}")

            threads = [threading.Thread(target=hammer, args=(i,)) for i in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            assert not errors, f"竞态错误: {errors[:5]}"
            assert p._sem[key]._value == 3   # 并发后槽位全归还
