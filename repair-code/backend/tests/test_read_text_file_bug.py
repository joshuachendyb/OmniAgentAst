# -*- coding: utf-8 -*-
"""Temp test to reproduce read_text_file int+None bug
编辑历史: 2026-07-18 小健 修正环境变量泄漏，改用临时配置并清理"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_cfg_dir = None
_cfg_path = None


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch):
    global _cfg_dir, _cfg_path
    _cfg_dir = tempfile.mkdtemp(prefix="readtext_cfg_")
    _cfg_path = os.path.join(_cfg_dir, "config.yaml")
    with open(_cfg_path, "w", encoding="utf-8") as _f:
        _f.write("app:\n  project_root: ''\nai: {}\nlogging:\n  level: INFO\n")
    monkeypatch.setenv("OMNIAGENT_CONFIG_PATH", _cfg_path)
    yield
    monkeypatch.delenv("OMNIAGENT_CONFIG_PATH", raising=False)


@pytest.mark.asyncio
async def test_read_text_file_offset_limit():
    from app.tools.file.read_text_file import readtext

    d = tempfile.mkdtemp()
    fp = Path(d) / "tail.txt"
    fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

    cases = [(-1, None), (5, 2), (5, None), (0, None), (None, None), (-1, 5), (10, None)]
    for offset, limit in cases:
        r = await readtext(path=str(fp), offset=offset, limit=limit)
        ec = r.get("llm_data", {}).get("status", {}).get("exec_code", "?")
        msg = r.get("llm_data", {}).get("status", {}).get("message", "")[:60]
        print("offset=" + str(offset) + ", limit=" + str(limit) + ": " + str(ec) + " - " + str(msg))
    await asyncio.sleep(0)
