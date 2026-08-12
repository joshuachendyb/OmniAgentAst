"""prompt-log 终态落盘修复单元测试 — 小欧 2026-07-18

验证两点（对应设计 C-1 删谎报 / C-2 新增 set_terminal_status）：
1. save() 不再把"处理中"私自升级为"已完成"
2. 生产者路径：start_request → log_step_yield(final) → set_terminal_status → save()
   落盘文件必含 final 步骤 + 状态如实
"""

import json
import pytest


def _make_logger(tmp_path, monkeypatch):
    from app.logger.prompt_logger import get_prompt_logger
    pl = get_prompt_logger()
    # 重定向日志目录到临时区，避免污染 logs/prompt-logs
    monkeypatch.setattr(pl, "log_dir", tmp_path)
    # 跳过 DB：start_request 内 get_user_message_id 返回固定值
    monkeypatch.setattr(
        "app.logger.prompt_logger.get_user_message_id",
        lambda sid: 123,
    )
    return pl


def test_save_no_status_upgrade(monkeypatch, tmp_path):
    """C-1 验证：save() 不得把"处理中"升级为"已完成" — 小欧 2026-07-18"""
    pl = _make_logger(tmp_path, monkeypatch)
    log = {
        "基本信息": {
            "时间戳": "2026-07-18 00:00:00",
            "会话ID": "s-test-1",
            "用户消息ID": 1,
            "AI消息ID": 99,
            "用户消息": "hi",
            "状态": "处理中",
        },
        "Prompt组装过程": [],
        "LLM调用记录": [{"轮次": 1}],
    }
    pl._set_current_log(log)
    pl.save()

    files = list(tmp_path.glob("prompt_*.json"))
    assert len(files) == 1, "应生成1个 prompt-log 文件"
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    # 关键断言：状态未被谎报升级
    assert saved["基本信息"]["状态"] == "处理中"


def test_producer_path_final_in_log(monkeypatch, tmp_path):
    """C-2 + 生产者全权路径验证：落盘文件必含 final + 状态如实 — 小欧 2026-07-18"""
    pl = _make_logger(tmp_path, monkeypatch)
    # 生产者路径：创建 → 写步骤 → 设态 → 存盘
    pl.start_request("hello", "s-test-2")
    final_dict = {
        "type": "final", "step": 5, "response": "任务完成",
        "thought": "ok", "outcome": "completed",
        "error_type": "", "error_message": "",
    }
    pl.log_step_yield(final_dict, round_number=5)
    pl.set_terminal_status("已完成")
    pl.save()

    files = list(tmp_path.glob("prompt_*.json"))
    assert len(files) == 1, "应生成1个 prompt-log 文件"
    saved = json.loads(files[0].read_text(encoding="utf-8"))

    # 断言1：状态如实
    assert saved["基本信息"]["状态"] == "已完成"
    # 断言2：步骤产出含 final
    finals = [s for s in saved["步骤产出"] if s["步骤类型"] == "final"]
    assert len(finals) == 1, "步骤产出应含1个 final"
    assert finals[0]["数据"].get("outcome") == "completed"


def test_producer_path_cancelled_status(monkeypatch, tmp_path):
    """增强验证：cancelled 场景状态如实"已取消" — 小欧 2026-07-18"""
    pl = _make_logger(tmp_path, monkeypatch)
    pl.start_request("hello", "s-test-3")
    final_dict = {
        "type": "final", "step": 3, "response": "任务已取消",
        "thought": "", "outcome": "cancelled",
        "error_type": "", "error_message": "",
    }
    pl.log_step_yield(final_dict, round_number=3)
    pl.set_terminal_status("已取消")
    pl.save()

    files = list(tmp_path.glob("prompt_*.json"))
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["基本信息"]["状态"] == "已取消"
    finals = [s for s in saved["步骤产出"] if s["步骤类型"] == "final"]
    assert len(finals) == 1
    assert finals[0]["数据"].get("outcome") == "cancelled"
