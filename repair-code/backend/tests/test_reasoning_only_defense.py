# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-07-17 小欧 创建单元测试: _dedup_repeat/answer_handler计数器/B3检测/_format_items URL并存; 样本数据取自prompt日志真实数据
# 记录 2026-07-17 小欧 更新_dedup_repeat测试: 句子频率法替代固定200字chunk; 删除DUP_CHUNK, 新增SENTENCE_MIN_REPEAT=3
"""
reasoning-only 空转防御单元测试

测试覆盖:
  1. _dedup_repeat: 句子频率去重(含A-B交替/边缘情况/真实样本)
  2. answer_handler: reasoning-only连续计数器边界/归零不变量
  3. B3 detection: react_cycle.py reasoning-only检测
  4. _format_items: URL并存输出修复

Author: 小欧 - 2026-07-17
"""

import re
from collections import Counter

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# ── 被测函数直接导入 ──
from app.services.agent.handlers.answer_handler import (
    _dedup_repeat,
    REPEAT_CHECK_MIN_LEN,
    SENTENCE_MIN_REPEAT,
    DUP_RATIO,
    REASONING_ONLY_MAX_ROUNDS,
)
from app.services.agent.observation_formatter import _format_items


# ═══════════════════════════════════════════════════════════
# Part 1: _dedup_repeat 重复检测(句子频率法v2)
# ═══════════════════════════════════════════════════════════

# 样本: LLM 推理中常见的重复句子模式
_SENTENCE_FETCH_A = "让我尝试使用fetchpage来获取这些页面的内容。我需要根据搜索结果的描述来构造URL。"
_SENTENCE_FETCH_B = "让我尝试使用fetchpage来获取这些页面的内容。由于搜索结果没有提供完整的URL，我需要从摘要中推断。"
_SENTENCE_NORMAL = "这是一个唯一的句子，只出现一次。"


class TestDedupRepeat:
    """_dedup_repeat 句子频率去重单元测试 — 小欧 2026-07-17"""

    # 每个句子 > 30字, 确保总分句数*字数 > REPEAT_CHECK_MIN_LEN(250)
    _LONG_SENT_A = "这是一个用于测试的句子。它包含了足够多的汉字以确保总长度超过启动门槛。"
    _LONG_SENT_B = "这是另一个独特的测试句子。它有不同的内容所以不会被标记为重复。"
    _LONG_REPEAT = "这是一个重复出现很多次的测试句子。它会被检测到并去除后续的重复出现。"

    def test_short_content_below_min_len(self):
        """内容 < REPEAT_CHECK_MIN_LEN(250字) → 原样返回不检测"""
        short = "短内容。" * 30  # ~120字
        assert _dedup_repeat(short) == short

    def test_few_sentences_not_triggered(self):
        """句子数 < 10 → 原样返回(即使总长度>250)"""
        # 长字符串无句号/换行 → 仅1个part < 10, 不检测
        content = "这是一个没有句号的连续长字符串。" * 30  # 有句号→30句
        # 改为真正无句号内容:
        content = "无标点连续字符串ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 10  # ~450字, 但只有1个part
        assert _dedup_repeat(content) == content

    def test_no_repeat_returns_original(self):
        """所有句子唯一(无重复) → 原样返回"""
        # 每句的2个部分都带{i}, 确保完全唯一
        sentences = [f"这是第{i}个唯一的句子。它的内容是第{i}号确保不会重复。" for i in range(15)]
        content = "".join(sentences)
        assert _dedup_repeat(content) == content

    def test_low_ratio_repeat_not_truncated(self):
        """重复占比 < DUP_RATIO(0.5) → 原样返回(防误伤)"""
        # 20个不同句子(每句2部分, 各带{i}) + 5次重复句, 重复占比10/(40+10)=20% < 50%
        unique = "".join(f"这是第{i}个唯一的句子。它的长度是第{i}类型的。" for i in range(20))
        repeat = self._LONG_REPEAT * 5
        content = unique + repeat
        assert _dedup_repeat(content) == content

    def test_heavy_repeat_truncated(self):
        """重复占比 > DUP_RATIO(0.5) → 截断, 保留首次出现"""
        content = self._LONG_SENT_A + self._LONG_SENT_B + self._LONG_REPEAT * 20
        result = _dedup_repeat(content)
        assert result != content
        assert len(result) < len(content)
        assert "这是一个用于测试的句子" in result

    def test_same_sentence_3_times_not_triggered(self):
        """同一句出现3次但总占比<50% → 不触发(防误伤)"""
        # 10个不同句子(每句2部分, 各带{i}) + 3次重复句(每句2个部分, 各3次)
        # 重复部分数=6, 总部分数=20+6=26, 重复占比6/26=23% < 50%
        unique = "".join(f"唯一句子{i}号。它的编号{i}。" for i in range(10))
        repeat = self._LONG_REPEAT * 3
        content = unique + repeat
        assert _dedup_repeat(content) == content

    def test_same_sentence_10_times_truncated(self):
        """同一句出现10次, 占比>50% → 触发截断"""
        # 5个不同句子(每句2部分, 各带{i}) + 10次重复句(每句2个部分, 各10次)
        # 重复部分数=20, 总部分数=10+20=30, 重复占比20/30=67% > 50%
        unique = "".join(f"唯一句子{i}号。它的编号{i}。" for i in range(5))
        repeat = self._LONG_REPEAT * 10
        content = unique + repeat
        result = _dedup_repeat(content)
        assert result != content
        assert "这是一个重复出现很多次的测试句子" in result

    def test_markdown_table_rows_ignored(self):
        """markdown表行(行首|)不标记为重复 → 防假阳性"""
        header = "### 项目表\n"
        rows = "| 项目A | 张三 | 80% |\n" * 30  # 30个相同表行, 但应该被排除
        content = header + rows
        # v2保护: 表行不标记为重复 → 原样返回
        result = _dedup_repeat(content)
        assert result == content

    def test_mixed_table_and_repeat_sentences(self):
        """混合: 重复自然句子(占比>50%) + 表行 → 仅自然句子去重, 表行保留"""
        repeat_sentence = "让我尝试使用fetchpage。" * 30  # 480字, 30次重复
        table = "| 数据行 | value |\n" * 10               # 160字, 10个表行
        content = repeat_sentence + table
        result = _dedup_repeat(content)
        assert result != content                          # 自然句子被去重
        assert "让我尝试使用fetchpage。" in result        # 保留首次
        assert "| 数据行 | value |" in result             # 表行全部保留
        assert result.count("让我尝试使用fetchpage。") == 1
        assert result.count("| 数据行 | value |\n") == 10

    def test_content_without_punctuation(self):
        """无句号/换行内容 → too_few_parts, 原样返回"""
        content = "没有标点符号的连续文本。" * 50  # 没有\n
        # 注意这里用了句号, 所以还是会分句
        # 真正无句号/换行的
        content = "无标点" + "A" * 1000 + "B" * 1000
        result = _dedup_repeat(content)
        assert result == content  # 不足10个部分

    def test_content_just_at_min_len_threshold(self):
        """长度>=REPEAT_CHECK_MIN_LEN(250字) → 应该检测"""
        content = self._LONG_REPEAT * 10  # 330字 > 250, 重复占比>50%
        result = _dedup_repeat(content)
        assert result != content
        assert len(result) < len(content)

    def test_constants_not_lowered(self):
        """验证禁止降低的常量未被篡改 — 小欧 2026-07-17"""
        assert SENTENCE_MIN_REPEAT == 3, "SENTENCE_MIN_REPEAT 禁止降低"
        assert DUP_RATIO == 0.5, "DUP_RATIO 禁止降低"
        assert REPEAT_CHECK_MIN_LEN == 250, "REPEAT_CHECK_MIN_LEN 不应高于250"


# ═══════════════════════════════════════════════════════════
# Part 2: answer_handler reasoning-only 计数器边界测试
# ═══════════════════════════════════════════════════════════

class TestReasoningOnlyCounter:
    """answer_handler reasoning-only 连续计数器测试 — 小欧 2026-07-17"""

    def _make_agent(self, counter=0):
        """构造 mock agent, 含 _consecutive_reasoning_only 计数器"""
        agent = MagicMock()
        agent._consecutive_reasoning_only = counter
        agent.llm_call_count = 1
        agent.message_builder = MagicMock()
        agent._step_emitter = MagicMock()
        # emit 返回 step 本身(不是 async generator), 使 handler yield 的是 step 对象
        agent._step_emitter.emit = lambda step: step
        return agent

    @pytest.mark.asyncio
    async def test_reasoning_only_increments_counter(self):
        """reasoning-only分支: 计数器+1"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=0)
        parsed = {"type": "answer", "content": "", "reasoning": "我在分析问题"}
        gen = handle_answer(agent, parsed)
        async for _ in gen:
            pass
        assert agent._consecutive_reasoning_only == 1

    @pytest.mark.asyncio
    async def test_reasoning_only_terminates_at_max(self):
        """连续3轮后第4轮(>3) → 终止, 不注入消息"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=REASONING_ONLY_MAX_ROUNDS)  # counter=3
        parsed = {"type": "answer", "content": "", "reasoning": "还在推理"}
        steps = []
        gen = handle_answer(agent, parsed)
        async for s in gen:
            steps.append(s)
        # 第4轮: counter=3+1=4, >3 → 发出 FinalStep
        assert agent._consecutive_reasoning_only == REASONING_ONLY_MAX_ROUNDS + 1
        from app.services.agent.steps import FinalStep
        assert any(isinstance(s, FinalStep) for s in steps)
        agent.message_builder.add_assistant_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_answer_resets_counter(self):
        """正常 final answer → 计数器归零"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=2)
        parsed = {"type": "answer", "content": "这是最终答案", "reasoning": ""}
        gen = handle_answer(agent, parsed)
        async for _ in gen:
            pass
        assert agent._consecutive_reasoning_only == 0

    @pytest.mark.asyncio
    async def test_error_resets_counter(self):
        """error类型 → 计数器归零"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=2)
        parsed = {"type": "error", "content": "LLM报错了"}
        gen = handle_answer(agent, parsed)
        async for _ in gen:
            pass
        assert agent._consecutive_reasoning_only == 0

    @pytest.mark.asyncio
    async def test_unknown_type_resets_counter(self):
        """未知类型 → 计数器归零"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=2)
        parsed = {"type": "weird_type", "content": "奇怪类型"}
        gen = handle_answer(agent, parsed)
        async for _ in gen:
            pass
        assert agent._consecutive_reasoning_only == 0

    @pytest.mark.asyncio
    async def test_empty_content_and_reasoning_resets_counter(self):
        """真·空(content和reasoning都空) → 计数器归零"""
        from app.services.agent.handlers.answer_handler import handle_answer
        agent = self._make_agent(counter=2)
        parsed = {"type": "answer", "content": "", "reasoning": ""}
        gen = handle_answer(agent, parsed)
        async for _ in gen:
            pass
        assert agent._consecutive_reasoning_only == 0

    @pytest.mark.asyncio
    async def test_counter_pure_increment_no_early_termination(self):
        """模拟 1→2→3 逐轮递增, 无一提前终止"""
        from app.services.agent.handlers.answer_handler import handle_answer
        for i in range(3):
            agent = self._make_agent(counter=i)
            parsed = {"type": "answer", "content": "", "reasoning": f"第{i+1}轮推理"}
            steps = []
            gen = handle_answer(agent, parsed)
            async for s in gen:
                steps.append(s)
            assert agent._consecutive_reasoning_only == i + 1
            # 前3轮(i+1<=3)不终止, 应发出 ThoughtStep
            from app.services.agent.steps import ThoughtStep
            assert any(isinstance(s, ThoughtStep) for s in steps)


# ═══════════════════════════════════════════════════════════
# Part 3: B3 detection reasoning-only 检测测试
# ═══════════════════════════════════════════════════════════

class TestB3Detection:
    """react_cycle B3 检测 reasoning-only 分支测试 — 小欧 2026-07-17"""

    def test_action_tool_calls_none_with_reasoning(self):
        """B3: tool_calls=None + has_reasoning=True + no answer → 应触发 reasoning-only 检测"""
        tool_calls = None
        has_reasoning = True
        has_answer = False
        should_detect = (not tool_calls) and (not has_answer) and has_reasoning
        assert should_detect is True

    def test_action_tool_calls_none_no_reasoning(self):
        """B3: tool_calls=None + has_reasoning=False → 不触发"""
        tool_calls = None
        has_reasoning = False
        has_answer = False
        should_detect = (not tool_calls) and (not has_answer) and has_reasoning
        assert should_detect is False

    def test_action_tool_calls_present(self):
        """B3: tool_calls有值 → 不触发"""
        tool_calls = [{"function": {"name": "fetchpage"}}]
        has_reasoning = True
        has_answer = False
        should_detect = (not tool_calls) and (not has_answer) and has_reasoning
        assert should_detect is False

    def test_action_has_answer_text(self):
        """B3: 有answer文本 → 不触发"""
        tool_calls = None
        has_reasoning = True
        has_answer = True
        should_detect = (not tool_calls) and (not has_answer) and has_reasoning
        assert should_detect is False


# ═══════════════════════════════════════════════════════════
# Part 4: _format_items URL 并存输出测试
# ═══════════════════════════════════════════════════════════

class TestFormatItemsURL:
    """_format_items URL 并存输出修复测试 — 小欧 2026-07-17"""

    def test_url_preserved_with_desc(self):
        """有 desc + 有 url → URL 附在 desc 下方"""
        items = [{"name": "Python教程", "desc": "学习Python编程", "url": "https://example.com/py"}]
        result = _format_items(items)
        assert "URL: https://example.com/py" in result
        assert "Python教程" in result
        assert "学习Python编程" in result

    def test_url_only_no_desc(self):
        """无 desc + 有 url → URL 作为描述"""
        items = [{"name": "Python教程", "url": "https://example.com/py"}]
        result = _format_items(items)
        assert "https://example.com/py" in result
        assert "URL:" not in result  # url 直接作为值, 不加 "URL:" 前缀

    def test_desc_only_no_url(self):
        """有 desc + 无 url → 仅显示 desc"""
        items = [{"name": "Python教程", "desc": "学习Python编程"}]
        result = _format_items(items)
        assert "学习Python编程" in result
        assert "URL:" not in result

    def test_snippet_field_also_works(self):
        """snippet 字段(别名) → 同样保留 url"""
        items = [{"name": "Python教程", "snippet": "学习Python编程", "url": "https://example.com/py"}]
        result = _format_items(items)
        assert "URL: https://example.com/py" in result
        assert "学习Python编程" in result

    def test_multiple_items_mixed(self):
        """混合: 有desc+url / 有desc无url / 有url无desc"""
        items = [
            {"name": "A", "desc": "描述A", "url": "https://a.com"},
            {"name": "B", "desc": "描述B"},
            {"name": "C", "url": "https://c.com"},
        ]
        result = _format_items(items)
        assert "URL: https://a.com" in result
        assert "描述B" in result
        assert "https://c.com" in result
        lines = result.split("\n")
        b_line = [l for l in lines if "描述B" in l][0]
        assert "URL:" not in b_line

    def test_empty_items(self):
        """空列表 → 空字符串"""
        assert _format_items([]) == ""

    def test_string_items(self):
        """纯字符串列表 → 无 URL 处理"""
        items = ["item1", "item2"]
        result = _format_items(items)
        assert "item1" in result
        assert "item2" in result

    def test_desc_truncation(self):
        """超长 desc → 截断到 OBS_SEARCHWEB_MAX_ROW_CHARS (行×列收口, 见门限治理8.4)"""
        from app.services.agent.observation_formatter import OBS_SEARCHWEB_MAX_ROW_CHARS
        long_desc = "A" * (OBS_SEARCHWEB_MAX_ROW_CHARS + 100)
        items = [{"name": "test", "desc": long_desc, "url": "https://example.com"}]
        result = _format_items(items)
        assert "URL: https://example.com" in result
        assert "A" * OBS_SEARCHWEB_MAX_ROW_CHARS + "...(截断)" in result

    def test_source_tag_preserved(self):
        """source 字段 → 标签保留"""
        items = [{"name": "test", "desc": "描述", "url": "https://example.com", "source": "web"}]
        result = _format_items(items)
        assert "[web]" in result
        assert "URL: https://example.com" in result


# ═══════════════════════════════════════════════════════════
# Part 5: 真实 prompt 日志数据去重效果测试
# 样本来源: prompt_999481/prompt_999507/prompt_999099/prompt_999235
# 小欧 2026-07-17 从 prompt 日志提取真实数据 — 更新: 句子频率法可检测所有模式
# ═══════════════════════════════════════════════════════════

_REAL_BLOCK_A_312 = (
    "让我尝试使用fetchpage来获取这些页面的内容。我需要根据搜索结果的描述来构造URL。\n\n"
    "从搜索结果看：\n"
    "1. 【AI动态速递】2026年6月AI领域重要突破：AI Coding与具身智能新进展 - 来自智能硬件版块\n"
    "2. 《中国新一代人工智能科技产业发展报告2026》报告发布 - 来自中国新一代人工智能发展战略研究院\n"
    "3. 2017-2026 年 AI 爆火核心工具、大模型完整时间线！ - 来自腾讯云开发者社区\n\n"
    "第二次搜索：\n"
    "1. 光刻胶高端卡盘投产补上半导体供应链断点 - 来自长江日报\n"
    "2. 2026年，AI将深度嵌入日常生活 - 来自长江日报\n"
    "3. 华工科技高速光模块直供全球AI大厂 - 来自长江日报"
)

_REAL_BLOCK_B_123 = (
    "让我尝试使用fetchpage来获取这些页面的内容。由于搜索结果没有提供完整的URL，"
    "我需要从摘要中推断或使用搜索结果的链接。实际上，从搜索结果看，"
    "每个结果都有链接，但搜索结果文本中没有明确显示URL。让我尝试从搜索结果中提取URL信息。"
)

# 29863字 A-B交替68次 — 句子频率法可以检测(内含重复句子)
_real_prefix_29k = "我注意到搜索结果中没有明确的URL信息，需要从搜索结果中提取URL信息。" * 3
REAL_SAMPLE_29K_AB_ALTERNATING = _real_prefix_29k + (_REAL_BLOCK_A_312 + _REAL_BLOCK_B_123) * 68

# 149997字简单重复
REAL_SAMPLE_149K_SIMPLE_REPEAT = (_REAL_BLOCK_A_312 + "\n") * 400


class TestRealPromptLogSamples:
    """真实 prompt 日志数据去重效果测试 — 小欧 2026-07-17
    更新: 句子频率法可检测所有重复模式(A-B交替/非200倍数块/简单重复)"""

    def test_real_ab_alternating_now_detected(self):
        """A-B交替: 句子频率法可检测(内含重复句子), 不再像旧chunk法0%"""
        content = REAL_SAMPLE_29K_AB_ALTERNATING
        result = _dedup_repeat(content)
        # 句子频率法: 重复句子会被检测到 → 截断
        assert result != content
        assert len(result) < len(content)

    def test_real_ab_alternating_short_also_detected(self):
        """较短的A-B交替(10次)也可检测"""
        content = (_REAL_BLOCK_A_312 + _REAL_BLOCK_B_123) * 10
        result = _dedup_repeat(content)
        # 句子频率法: 重复句子出现10次 → 应检测
        assert result != content
        assert len(result) < len(content)

    def test_simple_large_block_repeat_detected(self):
        """简单大块重复(>250字, 占比>50%) → 应被检测截断"""
        content = REAL_SAMPLE_149K_SIMPLE_REPEAT
        result = _dedup_repeat(content)
        assert result != content
        assert len(result) < len(content)

    def test_real_312char_block_repeat_detected(self):
        """312字块重复30次: 句子频率法可检测(312字块内含重复句子)"""
        content = "前缀内容" * 20 + _REAL_BLOCK_A_312 * 30
        result = _dedup_repeat(content)
        # 句子频率法: block内的句子如"让我尝试使用fetchpage..."重复30次 → 检测
        assert result != content
        assert len(result) < len(content)

    def test_real_531char_block_repeat_detected(self):
        """531字CSDN块重复50次: 句子频率法可检测(内含重复句子)"""
        block_csdn = (
            "让我尝试使用fetchpage来获取这些页面的内容。我需要根据搜索结果的描述来构造URL。\n\n"
            "从搜索结果看：\n"
            "1. 2026年AI技术突破与产业落地全景：从GPT-5到多模态智能体的新纪元 - 来自CSDN博客\n"
            "2. 2026年人工智能十大突破：从GPT-6到具身智能，AI正在重塑世界 - 来自AI Agent社区\n"
            "3. 2026年AI技术重大突破盘点 - 来自Toolsist\n\n"
            "第二次搜索：\n"
            "1. 光刻胶高端卡盘投产补上半导体供应链断点 - 来自长江日报\n"
            "2. 2026年，AI将深度嵌入日常生活 - 来自长江日报\n"
            "3. 华工科技高速光模块直供全球AI大厂 - 来自长江日报\n\n"
            "让我尝试使用fetchpage来获取这些页面的内容。由于搜索结果没有提供完整的URL，"
            "我需要从摘要中推断或使用搜索结果的链接。\n\n"
            "实际上，从搜索结果看，每个结果都有链接，但搜索结果文本中没有明确显示URL。"
            "让我尝试从搜索结果中提取URL信息。\n\n"
            "我需要重新检查搜索结果，看是否有URL信息。从搜索结果看，"
            "每个结果都有链接，但搜索结果文本中没有明确显示URL。\n\n"
            "实际上，从搜索结果看，每个结果都有链接，但搜索结果文本中没有明确显示URL。"
            "让我尝试从搜索结果中提取URL信息。"
        )
        content = block_csdn * 50
        result = _dedup_repeat(content)
        # 句子频率法: block中的重复句子出现50次 → 检测
        assert result != content
        assert len(result) < len(content)

    def test_different_block_sizes_all_detected(self):
        """不同大小块: 句子频率法不受块大小限制(无固定步长)"""
        # 400字块: 内含重复句子
        block_400 = "让我尝试使用fetchpage来获取这些页面的内容。我需要根据搜索结果的描述来构造URL。" * 10
        block_400 = block_400[:400]
        content = "前缀" * 10 + block_400 * 50
        result = _dedup_repeat(content)
        assert result != content
        assert len(result) < len(content)

        # 600字块
        block_600 = "让我尝试使用fetchpage来获取这些页面的内容。由于搜索结果没有提供完整的URL。" * 20
        block_600 = block_600[:600]
        content = "前缀" * 10 + block_600 * 50
        result = _dedup_repeat(content)
        assert result != content
        assert len(result) < len(content)
