"""L1 final 质量护栏单测 — 重复检测(句子频率法v2)"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app.services.agent.handlers.answer_handler import (
    REPEAT_CHECK_MIN_LEN,
    SENTENCE_MIN_REPEAT,
    _dedup_repeat,
)


# ═══════════════════════════════════════════
# _dedup_repeat — 重复检测(句子频率法)
# ═══════════════════════════════════════════

class TestDedupRepeat:
    """句子频率法去重测试"""

    @staticmethod
    def _make_realistic_block(n_chars: int) -> str:
        """生成 n_chars 字的真实段落(用于构造重复测试)"""
        core = (
            "本次任务已完成全部操作。文件 a 处理成功，结果已保存至 reports 目录。"
            "文件 b 格式转换完成，输出为 csv 格式。文件 c 日志分析完成，异常已归档。"
            "建议用户查看 reports 下的结果文件，确认数据完整性后执行后续操作。"
        )
        while len(core) < n_chars:
            core += "本次任务所有操作均已完成，无异常发生，请查看完整报告。"
        return core[:n_chars]

    def test_short_content_skipped(self):
        """<REPEAT_CHECK_MIN_LEN(250字)→跳过检测, 返回原对象"""
        s = "A" * (REPEAT_CHECK_MIN_LEN - 1)  # 249字, < 250
        assert _dedup_repeat(s) is s

    def test_no_repeat_unchanged(self):
        """无重复→原样返回"""
        s = ("句子A。" + "句子B。" + "句子C。" + "句子D。" + "句子E。"
             + "句子F。" + "句子G。" + "句子H。" + "句子I。" + "句子J。"
             + "句子K。" + "句子L。" + "句子M。" + "句子N。" + "句子O。")
        assert _dedup_repeat(s) == s

    def test_high_ratio_truncated(self):
        """LLM 卡顿循环: 同一段结论反复输出, 句子重复占比>50%→截断"""
        block = self._make_realistic_block(150)
        s = block * 20  # block 重复 20 次, 涵盖多个重复句子
        assert len(s) >= REPEAT_CHECK_MIN_LEN
        result = _dedup_repeat(s)
        assert result != s
        assert len(result) < len(s)

    def test_low_ratio_not_truncated(self):
        """有重复但占比<50%→不截断(守不误伤)"""
        head = "句子A。" * 30  # 30个唯一句子变体
        repeat = "重复句。" * 5  # 5次重复
        s = head + repeat
        result = _dedup_repeat(s)
        assert result == s

    def test_structured_report_not_harmed(self):
        """结构化报告含表头重复→v2排除表行, 不截断"""
        line = "| 名称 | 类型 | 大小 | 修改日期 | 备注 |\n"
        s = "报告标题\n" + line * 40 + "\n文件1.txt   txt   1KB   2026-01-01  -\n" * 20
        assert len(s) >= REPEAT_CHECK_MIN_LEN
        result = _dedup_repeat(s)
        assert result == s

    def test_identical_sentences_truncated(self):
        """同一句子重复多次→截断"""
        block = "本次任务已完成全部操作。结果已保存至 reports 目录。建议查看完整报告。"
        s = block * 20
        result = _dedup_repeat(s)
        assert result != s
        assert len(result) < len(s)
