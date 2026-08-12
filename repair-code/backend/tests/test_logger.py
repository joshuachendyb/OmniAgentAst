"""SafeRotatingFileHandler 测试 — 针对 Windows 文件锁竞争和两种轮转 — 小欧 2026-07-11"""

import os
import io
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, PropertyMock

import pytest

from app.utils.time_utils import now_str


def _make_record(msg="test", level=logging.INFO):
    return logging.LogRecord("test", level, "test.py", 0, msg, (), None)


def _write_many(handler, n=30, msg_len=200):
    for i in range(n):
        r = _make_record("X" * msg_len + str(i))
        handler.emit(r)


# ============================================================
# SafeRotatingFileHandler 核心功能
# ============================================================

class TestSafeRotatingFileHandler:

    def test_constructor_sets_date_and_stream(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=1024, backupCount=1, encoding="utf-8")
        assert len(h._current_date) == 10
        assert h.stream is not None and not h.stream.closed

    # —— 日期轮转 --------------------------------------------

    def test_date_rotation_switches_basefilename(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.logger.config.LOG_DIR", tmp_path)
        monkeypatch.setattr("app.logger.config.now_str",
                            lambda fmt="": "2026-01-01")
        from app.logger.config import SafeRotatingFileHandler, _get_log_file_path

        h = SafeRotatingFileHandler(
            str(_get_log_file_path()),
            maxBytes=1024, backupCount=1, encoding="utf-8",
        )
        monkeypatch.setattr("app.logger.config.now_str",
                            lambda fmt="": "2026-01-02")
        h._check_and_rotate_by_date()

        assert "2026-01-02" in h.baseFilename
        assert h._current_date == "2026-01-02"

    def test_date_rotation_reopens_new_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.logger.config.LOG_DIR", tmp_path)
        monkeypatch.setattr("app.logger.config.now_str",
                            lambda fmt="": "2026-01-01")
        from app.logger.config import SafeRotatingFileHandler, _get_log_file_path

        h = SafeRotatingFileHandler(
            str(_get_log_file_path()),
            maxBytes=1024, backupCount=1, encoding="utf-8",
        )
        monkeypatch.setattr("app.logger.config.now_str",
                            lambda fmt="": "2026-01-02")
        h._check_and_rotate_by_date()

        assert h.stream is not None and not h.stream.closed
        new_file = Path(h.baseFilename)
        assert new_file.exists()
        h.setFormatter(logging.Formatter("%(message)s"))
        h.emit(_make_record("DAY2_OK"))
        assert "DAY2_OK" in new_file.read_text(encoding="utf-8")

    def test_date_rotation_same_day_skips(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.logger.config.now_str",
                            lambda fmt="": "2026-01-01")
        from app.logger.config import SafeRotatingFileHandler, _get_log_file_path

        h = SafeRotatingFileHandler(
            str(_get_log_file_path()),
            maxBytes=1024, backupCount=1, encoding="utf-8",
        )
        old_path = h.baseFilename
        old_stream = h.stream

        h._check_and_rotate_by_date()
        assert h.baseFilename == old_path
        assert h.stream is old_stream

    # —— 大小轮转 --------------------------------------------

    def test_size_rotation_creates_backup(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_sz.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=50, backupCount=2, encoding="utf-8")
        _write_many(h, 30, 200)
        assert (tmp_path / "test_sz.log.1").exists()

    def test_size_rotation_backup_chain(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_chain.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=30, backupCount=3, encoding="utf-8")
        _write_many(h, 80, 200)
        assert (tmp_path / "test_chain.log.1").exists()
        assert (tmp_path / "test_chain.log.2").exists()

    # —— doRollover 错误恢复 ------------------------------------

    def test_doRollover_oserror_recovers_stream(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_err.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=10, backupCount=1, encoding="utf-8")
        with open(str(f), "w") as fh:
            fh.write("X" * 200)
        h.stream = h._open()

        with patch.object(h, "rotate", side_effect=PermissionError("locked")):
            h.doRollover()

        assert h.stream is not None and not h.stream.closed

    def test_doRollover_oserror_emit_continues(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_emit_ok.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=10, backupCount=1, encoding="utf-8")
        with open(str(f), "w") as fh:
            fh.write("X" * 200)
        h.stream = h._open()
        h.setFormatter(logging.Formatter("%(message)s"))

        with patch.object(h, "rotate", side_effect=PermissionError("locked")):
            h.emit(_make_record("SURVIVED"))

        assert "SURVIVED" in f.read_text(encoding="utf-8")

    # —— emit ------------------------------------------------

    def test_emit_writes_message(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_emit.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=1024, backupCount=1, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        h.emit(_make_record("HELLO"))
        assert f.read_text(encoding="utf-8").strip() == "HELLO"

    def test_emit_date_rotation_error_swallowed(self, tmp_path):
        from app.logger.config import SafeRotatingFileHandler
        f = tmp_path / "test_emit_safe.log"
        h = SafeRotatingFileHandler(str(f), maxBytes=1024, backupCount=1, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))

        with patch.object(h, "_check_and_rotate_by_date", side_effect=PermissionError("mock")):
            h.emit(_make_record("SAFE"))
        assert "SAFE" in f.read_text(encoding="utf-8")


# ============================================================
# 单例 + setup_logger（shared_handler）
# ============================================================

class TestSingleton:

    def test_get_shared_handler_is_singleton(self):
        from app.logger.shared_handler import _get_shared_handler
        assert _get_shared_handler() is _get_shared_handler()

    def test_all_loggers_share_handler(self):
        from app.logger.shared_handler import setup_logger
        log_a = setup_logger("test_singleton_a")
        log_b = setup_logger("test_singleton_b")
        fha = [h for h in log_a.handlers if isinstance(h, logging.FileHandler)][0]
        fhb = [h for h in log_b.handlers if isinstance(h, logging.FileHandler)][0]
        assert fha is fhb

    def test_console_handler_unique_per_logger(self):
        from app.logger.shared_handler import setup_logger
        log_a = setup_logger("test_console_u_a")
        log_b = setup_logger("test_console_u_b")
        cha = [h for h in log_a.handlers
               if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)][0]
        chb = [h for h in log_b.handlers
               if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)][0]
        assert cha is not chb


# ============================================================
# 核心 Bug 场景：多 logger 共享 handler + 轮转
# ============================================================

class TestMultiLoggerRotation:

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        import app.logger.shared_handler as sl
        sl._FILE_HANDLER = None
        monkeypatch.setattr("app.logger.config.LOG_DIR", tmp_path)
        self.tmp = tmp_path

    def _loggers(self, n=7):
        from app.logger.shared_handler import setup_logger
        import uuid
        suffix = uuid.uuid4().hex[:8]
        return [setup_logger(f"app.test.ml{i}.{suffix}") for i in range(n)]

    def _new_singleton(self):
        from app.logger.shared_handler import _get_shared_handler
        h = _get_shared_handler()
        h.baseFilename = str(self.tmp / f"app_{datetime.now().strftime('%Y-%m-%d')}.log")
        if h.stream:
            h.stream.close()
        h.stream = h._open()
        return h

    # ---- 多 logger 共享 ------------------------------------------------

    def test_shared_handler_across_loggers(self):
        loggers = self._loggers(7)
        fhs = []
        for lg in loggers:
            for h in lg.handlers:
                if isinstance(h, logging.FileHandler):
                    fhs.append(h)
                    break
        assert len(fhs) == 7
        for fh in fhs[1:]:
            assert fh is fhs[0]

    def test_size_rotation_with_multiple_loggers(self):
        """多 logger 共享 handler → 轮转成功 → 生成备份 — 小欧 2026-07-11"""
        h = self._new_singleton()
        h.baseFilename = str(self.tmp / "multi_rotate.log")
        h.maxBytes = 200
        h.backupCount = 3
        if h.stream:
            h.stream.close()
        h.stream = h._open()
        h.setFormatter(logging.Formatter("%(message)s"))

        loggers = self._loggers(7)
        for i in range(100):
            lg = loggers[i % 7]
            lg.info("X" * 150 + str(i))

        backups = list(self.tmp.glob("multi_rotate.log.*"))
        assert len(backups) > 0, f"应生成备份文件，实际: {backups}"

    def test_no_permissionerror_on_stderr(self, capsys):
        """多 logger 场景 stderr 无 PermissionError — 小欧 2026-07-11"""
        h = self._new_singleton()
        h.baseFilename = str(self.tmp / "stderr_clean.log")
        h.maxBytes = 200
        h.backupCount = 3
        if h.stream:
            h.stream.close()
        h.stream = h._open()

        loggers = self._loggers(7)
        for i in range(50):
            lg = loggers[i % 7]
            lg.info("Y" * 150 + str(i))

        captured = capsys.readouterr()
        assert "PermissionError" not in captured.err
        assert "Logging error" not in captured.err
        assert "WinError" not in captured.err

    def test_date_then_size_rotation_chain(self):
        """日期轮转 → size 轮转，验证链完整 — 小欧 2026-07-11"""
        from app.logger.config import SafeRotatingFileHandler
        import app.logger.config as lc

        lc.now_str = lambda fmt="": "2026-01-01"
        h = SafeRotatingFileHandler(
            str(self.tmp / "app_2026-01-01.log"),
            maxBytes=1024 * 1024, backupCount=5, encoding="utf-8",
        )
        h.setFormatter(logging.Formatter("%(message)s"))
        h.emit(_make_record("DAY1"))

        # 模拟"新的一天"
        lc.now_str = lambda fmt="": "2026-01-02"
        h._check_and_rotate_by_date()

        new_file = self.tmp / "app_2026-01-02.log"
        assert new_file.exists(), f"日期轮转后新文件 {new_file} 应存在"

        h.emit(_make_record("DAY2_LOG"))
        assert "DAY2_LOG" in new_file.read_text(encoding="utf-8")

        # 小 maxBytes → 触发 size 轮转，每个 record ~150b > 100
        h.maxBytes = 100
        h.backupCount = 3
        _write_many(h, 40, 150)

        backups = sorted(self.tmp.glob("app_2026-01-02.log.*"))
        assert len(backups) > 0, f"日期轮转后 size 轮转应生成备份: {backups}"

        # DAY2_LOG 在首次 doRollover 时写入 .1，随后被后续备份覆盖
        # 验证最近的备份文件存在且有内容即可
        assert all(
            p.stat().st_size > 0 for p in backups
        ), f"所有备份文件应有非零大小: {[p.name for p in backups]}"
