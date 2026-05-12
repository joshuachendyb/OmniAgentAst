# -*- coding: utf-8 -*-
"""
CRSS双维度评分测试（v3：类型×动作）

测试 covers:
1. 基础边界（空输入）
2. 10个类型分类检测
3. 类型+动作调制路由正确
4. 同动作不同类型能区分
5. 纯动作兜底（无类型词）
6. 多分类（一句话涉及多个类型）
7. 无匹配→LLM兜底
8. 阈值边界测试
9. 危险命令检测

小健 - 2026-05-13
"""
import pytest
from app.services.intents.crss_scorer import (
    detect_intent_v2, _compute_intent_scores
)
from app.services.tools.registry import ToolCategory


class TestCRSSV3EdgeCases:
    """边界条件测试"""

    def test_empty_input(self):
        primary, candidates, conf = detect_intent_v2("")
        assert primary is None and candidates == [] and conf == 0.0

    def test_whitespace_input(self):
        primary, candidates, conf = detect_intent_v2("   ")
        assert primary is None and candidates == [] and conf == 0.0

    def test_chat_no_match(self):
        """纯对话→无匹配→LLM兜底"""
        primary, candidates, conf = detect_intent_v2("你好")
        assert primary is None

    def test_chat_weather(self):
        primary, candidates, conf = detect_intent_v2("今天天气怎么样")
        assert primary is None

    def test_chat_explain(self):
        primary, candidates, conf = detect_intent_v2("解释一下量子计算")
        assert primary is None


class TestCRSSV3TypeDetection:
    """第一层：10个类型独立检测"""

    def test_file_by_chinese(self):
        """文件：中文类型词"""
        primary, candidates, conf = detect_intent_v2("读取文件")
        assert primary == ToolCategory.FILE
        assert conf > 0.3

    def test_file_by_dir(self):
        """文件：英文类型词"""
        primary, candidates, conf = detect_intent_v2("ls -la")
        assert primary == ToolCategory.FILE
        assert conf > 0.3

    def test_shell_by_npm(self):
        primary, candidates, conf = detect_intent_v2("npm install")
        assert primary == ToolCategory.SHELL and conf > 0.3

    def test_shell_by_python(self):
        primary, candidates, conf = detect_intent_v2("python script.py")
        assert primary == ToolCategory.SHELL and conf > 0.3

    def test_time_by_chinese(self):
        primary, candidates, conf = detect_intent_v2("现在几点了")
        assert primary == ToolCategory.TIME and conf > 0.3

    def test_time_by_date(self):
        primary, candidates, conf = detect_intent_v2("date")
        assert primary == ToolCategory.TIME and conf > 0.3

    def test_network_by_ping(self):
        primary, candidates, conf = detect_intent_v2("ping 8.8.8.8")
        assert primary == ToolCategory.NETWORK and conf > 0.3

    def test_network_by_curl(self):
        primary, candidates, conf = detect_intent_v2("curl https://example.com")
        assert primary == ToolCategory.NETWORK and conf > 0.3

    def test_desktop_by_screenshot(self):
        primary, candidates, conf = detect_intent_v2("截图")
        assert primary == ToolCategory.DESKTOP and conf > 0.3

    def test_desktop_by_click(self):
        primary, candidates, conf = detect_intent_v2("click")
        assert primary == ToolCategory.DESKTOP and conf > 0.3

    def test_env_by_path(self):
        primary, candidates, conf = detect_intent_v2("查看PATH环境变量")
        assert primary == ToolCategory.ENVIRONMENT and conf > 0.3

    def test_system_by_cpu(self):
        primary, candidates, conf = detect_intent_v2("CPU使用情况")
        assert primary == ToolCategory.SYSTEM and conf > 0.3

    def test_system_by_memory(self):
        primary, candidates, conf = detect_intent_v2("memory usage")
        assert primary == ToolCategory.SYSTEM and conf > 0.3

    def test_database_by_sql(self):
        primary, candidates, conf = detect_intent_v2("select * from users")
        assert primary == ToolCategory.DATABASE and conf > 0.3

    def test_database_by_chinese(self):
        primary, candidates, conf = detect_intent_v2("查询数据库")
        assert primary == ToolCategory.DATABASE and conf > 0.3

    def test_document_by_pdf(self):
        primary, candidates, conf = detect_intent_v2("读取pdf文件")
        # "文件"→FILE+2.0, "pdf"→DOCUMENT+1.0 → FILE稍高，但两个类型都在候选
        assert primary in (ToolCategory.FILE, ToolCategory.DOCUMENT)
        assert len(candidates) >= 2

    def test_document_by_chinese(self):
        primary, candidates, conf = detect_intent_v2("打开文档")
        assert primary == ToolCategory.DOCUMENT and conf > 0.3

    def test_code_execution(self):
        primary, candidates, conf = detect_intent_v2("编译程序")
        assert primary == ToolCategory.CODE_EXECUTION and conf > 0.3


class TestCRSSV3TypeActionDisambiguation:
    """同动作不同类型→正确区分"""

    def test_read_file(self):
        """读取文件→FILE（不是DATABASE）"""
        scores = _compute_intent_scores("读取文件")
        assert scores.get(ToolCategory.FILE, 0) > scores.get(ToolCategory.DATABASE, 0)

    def test_read_database(self):
        """读取数据库→DATABASE（不是FILE）"""
        scores = _compute_intent_scores("读取数据库")
        assert scores.get(ToolCategory.DATABASE, 0) > scores.get(ToolCategory.FILE, 0)

    def test_delete_file(self):
        """删除文件→FILE"""
        primary, _, _ = detect_intent_v2("删除文件")
        assert primary == ToolCategory.FILE

    def test_query_database(self):
        """查询数据→DATABASE"""
        primary, _, _ = detect_intent_v2("查询users表")
        assert primary == ToolCategory.DATABASE

    def test_run_shell(self):
        """运行脚本→SHELL"""
        primary, _, _ = detect_intent_v2("运行python脚本")
        assert primary == ToolCategory.SHELL

    def test_open_desk(self):
        """打开D盘→FILE"""
        primary, _, _ = detect_intent_v2("打开D盘")
        assert primary == ToolCategory.FILE

    def test_open_browser(self):
        """打开浏览器→DESKTOP（浏览器是桌面应用）"""
        primary, _, conf = detect_intent_v2("打开浏览器")
        assert primary == ToolCategory.DESKTOP and conf > 0.3


class TestCRSSV3ActionOnlyFallback:
    """纯动作兜底（无类型词时用动作反推）"""

    def test_delete_alone(self):
        """单独"删除"→动作推断FILE但conf<0.3→路由层走LLM"""
        primary, _, conf = detect_intent_v2("删除")
        assert conf < 0.3  # 低于阈值，路由层会走LLM

    def test_create_without_type(self):
        """"创建"→动作推断FILE但conf<0.3→LLM"""
        primary, _, conf = detect_intent_v2("帮我创建一个")
        assert conf < 0.3

    def test_search_without_type(self):
        """"搜索"→动作推断DATABASE但conf<0.3→LLM"""
        primary, _, conf = detect_intent_v2("搜索一下")
        assert conf < 0.3


class TestCRSSV3MultiCategory:
    """多分类支持"""

    def test_file_and_database_both_scored(self):
        """"读取文件并保存到数据库"→两类都有分"""
        scores = _compute_intent_scores("读取文件并保存到数据库")
        assert ToolCategory.FILE in scores
        assert ToolCategory.DATABASE in scores
        assert len(scores) >= 2

    def test_multi_candidate(self):
        """多候选列表"""
        primary, candidates, conf = detect_intent_v2("读取文件并保存到数据库")
        assert len(candidates) >= 2
        assert primary is not None

    def test_candidates_sorted(self):
        """候选按置信度降序"""
        scores = _compute_intent_scores("读取文件")
        items = list(scores.items())
        for i in range(len(items) - 1):
            assert items[i][1] >= items[i + 1][1]


class TestCRSSV3Threshold:
    """阈值边界"""

    def test_above_threshold_file(self):
        """明确文件操作→超过阈值"""
        _, _, conf = detect_intent_v2("读取文件")
        assert conf >= 0.3

    def test_above_threshold_shell(self):
        _, _, conf = detect_intent_v2("npm install")
        assert conf >= 0.3

    def test_below_threshold_ambiguous(self):
        """模糊请求→低于阈值"""
        _, _, conf = detect_intent_v2("处理一下这个事情")
        assert conf < 0.3 or conf == 0.0


class TestCRSSV3Dangerous:
    """危险命令"""

    def test_dangerous_rm(self):
        primary, _, conf = detect_intent_v2("rm -rf /")
        assert primary == ToolCategory.SHELL and conf > 0.3

    def test_dangerous_sudo(self):
        primary, _, conf = detect_intent_v2("sudo rm -rf /var")
        assert primary == ToolCategory.SHELL and conf > 0.3

    def test_dangerous_format(self):
        primary, _, conf = detect_intent_v2("format c:")
        assert primary is not None and conf > 0.3
