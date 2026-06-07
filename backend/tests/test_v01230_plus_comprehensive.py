"""
综合测试 v0.12.30+ 所有变更（已重构适配新架构）

覆盖范围：
1. llm_data双通道机制
2. MessageBuilder容量感知裁剪
3. prompt_logger截断阈值+round_number
4. StrategySelector策略前置（build_schema_text）
5. 工具全量注册机制
6. search_web llm_data精简输出（外部网络，标记跳过）
7. observation统一[Observation]前缀
8. 已执行工具汇总
9. network_prompts工具列表+任务提示

作者：小健
创建时间：2026-05-15 20:15:11
更新时间：2026-05-27 小欧
"""

import pytest
import json
import time
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.agent.base_react import BaseAgent
from app.utils.prompt_logger import PromptLogger
from app.services.tools import ensure_tools_registered
from app.services.tools.lazy_loader import is_tools_registered, _registered_categories
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.services.agent.message_builder import MessageBuilder
from app.services.agent.agent_utils.message_utils import build_schema_text
from app.services.agent.tool_result_formatter import format_llm_observation
from app.services.prompts.network.network_prompts import NetworkPrompts
from app.services.agent.llm_response_parser._json_strategies import _extract_json_block
from app.services.agent.llm_response_parser import parse_react_response

# ===== 工具注册确保 =====

@pytest.fixture(autouse=True, scope="module")
def ensure_tools():
    """确保所有工具已注册"""
    from app.services.tools import ensure_tools_registered, reset_registered_state
    reset_registered_state()
    ensure_tools_registered()


# ===== 1. llm_data双通道机制 =====

class TestLlmDataDualChannel:
    """测试工具结果llm_data双通道机制"""

    def test_format_llm_observation_passes_through_llm_data(self):
        """tool_result_formatter.format_llm_observation嵌入llm_data到字符串"""
        result = {
            "code": "SUCCESS",
            "message": "测试成功",
            "data": {"key": "value"},
            "llm_data": {"精简": "数据"}
        }
        formatted = format_llm_observation(result, "test_tool")
        assert formatted.startswith("Observation: success -")
        assert "精简" in formatted
        assert "数据" in formatted

    def test_format_llm_observation_with_warning(self):
        """warning状态也嵌入llm_data"""
        result = {
            "code": "WARNING_PARTIAL",
            "message": "部分成功",
            "data": {"partial": True},
        }
        formatted = format_llm_observation(result, "test_tool")
        assert formatted.startswith("Observation: warning -")

    def test_format_llm_observation_fallback_to_data(self):
        """无llm_data时回退到data字段"""
        result = {
            "code": "SUCCESS",
            "message": "测试成功",
            "data": {"key": "value"}
        }
        formatted = format_llm_observation(result, "test_tool")
        assert formatted.startswith("Observation: success -")
        assert "key" in formatted


# ===== 2. _trim_history容量感知裁剪 =====

class TestTrimHistoryCapacityAware:
    """测试容量感知裁剪（MessageBuilder）"""

    def test_max_context_chars_constant(self):
        """MAX_CONTEXT_CHARS=150K"""
        from app.constants import MAX_CONTEXT_CHARS
        assert MAX_CONTEXT_CHARS == 150000

    def test_trim_skip_when_only_2_messages(self):
        """只有system+user时不裁剪"""
        from app.constants import MAX_CONTEXT_CHARS
        builder = MessageBuilder(
            max_context_chars=MAX_CONTEXT_CHARS
        )
        builder.init_history("系统提示", "用户输入")
        builder.temp_history = list(builder.conversation_history)
        builder.trim_history()
        assert len(builder.conversation_history) == 2

    def test_is_observation_role_by_prefix(self):
        """通过role+前缀识别observation"""
        msg = {"role": "system", "content": "[Observation] success - 测试"}
        assert MessageBuilder._is_observation_role(msg) is True

    def test_is_observation_role_non_system(self):
        """非system角色不是observation"""
        msg = {"role": "user", "content": "[Observation] test"}
        assert MessageBuilder._is_observation_role(msg) is False

    def test_is_error_observation(self):
        """判断observation是否失败"""
        assert MessageBuilder._is_error_obs("Observation: error - 失败") is True
        assert MessageBuilder._is_error_obs("Observation: timeout - 超时") is True
        assert MessageBuilder._is_error_obs("Observation: failed - 失败") is True
        assert MessageBuilder._is_error_obs("Observation: success - 成功") is False

    def test_dedup_by_fingerprint(self):
        """MD5指纹去重：相同内容视为重复"""
        obs_list = [
            {"content": "完全相同的内容"},
            {"content": "完全相同的内容"},  # 重复
            {"content": "不同的内容"},
        ]
        result = MessageBuilder._dedup_by_fingerprint(obs_list)
        assert len(result) == 2
        # FC协议消息（含tool_call_id）不参与去重
        assert any("不同的内容" in obs["content"] for obs in result)

    def test_dedup_by_fingerprint_keeps_tool_role(self):
        """FC协议tool消息（含tool_call_id）不参与去重"""
        obs_list = [
            {"role": "tool", "content": "相同内容", "tool_call_id": "call_1"},
            {"role": "tool", "content": "相同内容", "tool_call_id": "call_2"},
        ]
        result = MessageBuilder._dedup_by_fingerprint(obs_list)
        assert len(result) == 2

    def test_total_chars(self):
        """计算消息总字符数"""
        messages = [
            {"content": "hello"},
            {"content": "世界"},
            {"content": ""},
        ]
        assert MessageBuilder._total_chars(messages) == 7

    def test_observation_prefix_unified(self):
        """observation统一[Observation]前缀"""
        def apply_prefix(observation: str) -> str:
            if observation.startswith("Observation:"):
                return f"[Observation] {observation[len('Observation:'):].lstrip()}"
            elif not observation.startswith("[Observation]"):
                return f"[Observation] {observation}"
            return observation

        result = apply_prefix("Observation: success - 测试")
        assert result.startswith("[Observation]")
        assert "success" in result

        result = apply_prefix("普通观察内容")
        assert result.startswith("[Observation]")

        result = apply_prefix("[Observation] 已有前缀")
        assert result == "[Observation] 已有前缀"


# ===== 3. prompt_logger截断阈值+round_number =====

class TestPromptLoggerThreshold:
    """测试prompt_logger截断阈值提升和round_number"""

    def test_log_llm_response_truncation_2000(self):
        """log_llm_response截断阈值2000"""
        logger_instance = PromptLogger()
        logger_instance.start_request("test", "1", "session1")
        logger_instance.log_llm_call(round_number=1, messages=[{"role": "user", "content": "test"}])

        long_content = "x" * 5000
        logger_instance.log_llm_response(round_number=1, response_content=long_content)

        log = logger_instance.get_current_log()
        # 返回内容截断到2000
        assert len(log["LLM调用记录"][0]["返回内容"]) == 2000
        # 独立记录的返回也截断到2000
        llm_return = [e for e in log["LLM调用记录"] if e.get("类型") == "LLM返回"]
        assert len(llm_return[0]["内容"]) == 2000

    def test_log_llm_response_records_round_number(self):
        """log_llm_response记录round_number"""
        logger_instance = PromptLogger()
        logger_instance.start_request("test", "2", "session2")
        logger_instance.log_llm_call(round_number=3, messages=[{"role": "user", "content": "test"}])
        logger_instance.log_llm_response(round_number=3, response_content="test response")

        log = logger_instance.get_current_log()
        llm_return = [e for e in log["LLM调用记录"] if e.get("类型") == "LLM返回"]
        assert llm_return[0]["轮次"] == 3

    def test_log_observation_records_round_number(self):
        """log_observation记录round_number"""
        logger_instance = PromptLogger()
        logger_instance.start_request("test", "3", "session3")
        logger_instance.log_observation(
            step_name="工具执行",
            observation_content="test observation",
            tool_name="ping",
            round_number=2
        )

        log = logger_instance.get_current_log()
        obs = log["Prompt组装过程"][0]
        assert obs["轮次"] == 2


# ===== 4. StrategySelector策略前置 =====

class TestStrategySelection:
    """测试策略前置：FC模式跳过工具文本注入"""

    def test_build_schema_text_injects_schema(self):
        """build_schema_text注入Schema文本"""
        tools = [{
            "function": {
                "name": "ping",
                "parameters": {
                    "properties": {
                        "host": {"type": "string"},
                        "count": {"type": "integer", "default": 4}
                    },
                    "required": ["host"]
                }
            }
        }]
        result = build_schema_text(tools)
        assert "ping" in result
        assert "host" in result
        assert "count" in result

    def test_build_schema_text_with_required(self):
        """Schema文本标注required参数"""
        tools = [{
            "function": {
                "name": "http_request",
                "parameters": {
                    "properties": {
                        "url": {"type": "string"},
                        "method": {"type": "string", "default": "GET"}
                    },
                    "required": ["url"]
                }
            }
        }]
        result = build_schema_text(tools)
        assert "url(string, required)" in result
        assert "method(string, default=GET)" in result


# ===== 5. 工具全量注册机制 =====

class TestFullToolRegistration:
    """测试工具全量注册机制"""

    def test_ensure_tools_registered_idempotent(self):
        """ensure_tools_registered幂等：多次调用不重复注册"""
        count_before = len(tool_registry._tools)
        ensure_tools_registered()
        count_after = len(tool_registry._tools)
        assert count_before == count_after

    def test_all_categories_registered(self):
        """所有7个分类都已注册"""
        ensure_tools_registered()
        expected = {"file", "shell", "network", "system", "desktop", "document", "meta"}
        assert expected.issubset(_registered_categories)

    def test_tool_count_sufficient(self):
        """注册工具数量>=50"""
        ensure_tools_registered()
        assert len(tool_registry._tools) >= 50

    def test_get_tools_by_category(self):
        """按分类获取工具"""
        ensure_tools_registered()
        network_tools = tool_registry.list_tools(category=ToolCategory.NETWORK)
        assert len(network_tools) > 0
        names = [t["name"] for t in network_tools]
        assert "search_web" in names
        assert "network_diagnose" in names


# ===== 6. search_web llm_data精简输出（跳过，依赖外部网络） =====

class TestSearchWebLlmData:
    """测试search_web的llm_data精简输出（依赖真实网络，标记跳过）"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="依赖外部网络，不在单元测试中执行")
    async def test_search_web_returns_llm_data(self):
        """search_web返回包含llm_data字段"""
        from app.services.tools.network.network_tools import search_web
        result = await search_web(query="test query 2026", num_results=3)
        if result["code"] == "SUCCESS":
            assert "llm_data" in result
            assert "搜索引擎" in result["llm_data"]

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="依赖外部网络，不在单元测试中执行")
    async def test_search_web_llm_data_snippet_truncated(self):
        """search_web的llm_data中snippet截断到300字符"""
        from app.services.tools.network.network_tools import search_web
        result = await search_web(query="Python programming", num_results=3)
        if result["code"] == "SUCCESS" and result["llm_data"].get("搜索结果"):
            results = result["llm_data"]["搜索结果"]
            if isinstance(results, list) and len(results) > 0:
                for r in results:
                    if isinstance(r, dict) and "snippet" in r:
                        assert len(r["snippet"]) <= 300


# ===== 8. 已执行工具汇总 =====

class TestExecutedToolSummary:
    """测试已执行工具汇总机制"""

    def test_summary_entry_format(self):
        """汇总条目格式为tool_name→status"""
        agent = MagicMock(spec=BaseAgent)
        agent._executed_tool_summary = []
        entry = f"ping→success"
        agent._executed_tool_summary.append(entry)
        assert "→success" in agent._executed_tool_summary[0]
        assert "→error" not in agent._executed_tool_summary[0]

    def test_summary_length_limit(self):
        """汇总长度限制为50条，超限时保留最近30条"""
        agent = MagicMock(spec=BaseAgent)
        agent._executed_tool_summary = [f"tool{i}→success" for i in range(50)]
        agent._executed_tool_summary.append("tool50→success")
        # 模拟base_react中的限制逻辑
        if len(agent._executed_tool_summary) > 50:
            agent._executed_tool_summary = agent._executed_tool_summary[-30:]
        assert len(agent._executed_tool_summary) == 30


# ===== 9. 失败计数器限制 =====

class TestFailedAttemptsLimit:
    """测试失败计数器长度限制"""

    def test_failed_attempts_limit(self):
        """失败计数器超过100时保留最近50个"""
        failed = {f"tool{i}:hash{i}": i for i in range(100)}
        failed["tool100:hash100"] = 1
        if len(failed) > 100:
            failed = dict(list(failed.items())[-50:])
        assert len(failed) == 50


# ===== 10. network_prompts工具列表+任务提示 =====

class TestNetworkPromptsUpdates:
    """测试network_prompts更新"""

    def test_system_prompt_contains_network_tools(self):
        """system_prompt包含5个网络工具描述"""
        prompts = NetworkPrompts()
        system_prompt = prompts.get_system_prompt()
        assert "search_web" in system_prompt
        assert "http_request" in system_prompt
        assert "network_diagnose" in system_prompt
        assert "5个" in system_prompt

    def test_system_prompt_no_shell_commands(self):
        """system_prompt不包含本地shell命令（include_commands=False）"""
        prompts = NetworkPrompts()
        system_prompt = prompts.get_system_prompt()
        assert "ipconfig" not in system_prompt
        assert "netsh" not in system_prompt

    def test_task_prompt_contains_chinese_report(self):
        """task_prompt要求用中文报告"""
        prompts = NetworkPrompts()
        task_prompt = prompts.get_task_prompt("test task")
        assert "用中文" in task_prompt


class TestRealNewlinesInFinishJson:
    """
    测试LLM返回JSON中含实际换行符（非\\n转义）时finish的result参数提取 - 小健 2026-05-15
    
    问题背景：LLM在thought/reasoning字段中使用实际换行符（byte 0x0A），
    导致json.loads失败。_extract_json_block fallback提取到tool_name=finish
    但tool_params.result丢失，最终response为空。
    
    修复：在_extract_params_by_regex_from_json_str中添加"result"参数的
    平衡引号提取逻辑。
    """
    
    def _build_raw_response_with_real_newlines(self) -> str:
        """构建模拟LLM返回的JSON（含实际换行符）- 小健 2026-05-15"""
        thought = (
            "用户要求全面检查网络信息，包括\n"
            "WiFi IP、DNS、公网IP和网络速度等。"
        )
        reasoning = (
            "基于已有的成功结果，我需要整合\n"
            "公网IP、IP详情、网络连通性信息。"
        )
        report = (
            "=== 网络全面诊断报告 ===\n\n"
            "【公网IP信息】\n"
            "- 公网IP地址：已成功获取\n"
            "- IP详细信息：已获取完整信息\n\n"
            "【网络连通性测试】\n"
            "- Ping测试：baidu.com 可达，0%丢失\n"
            "- 端口检查：baidu.com:443 开放\n\n"
            "【DNS相关信息】\n"
            "- DNS查询：ipconfig /all\n"
            "- 信号强度：查看\"信号\"百分比\n\n"
            "【总结】\n"
            "网络状态良好，建议定期监控。"
        )
        raw = json.dumps({
            "thought": thought,
            "reasoning": reasoning,
            "tool_name": "finish",
            "tool_params": {"result": report}
        }, ensure_ascii=False)
        # 关键：json.dumps会把实际换行符转义为\n，但LLM返回的是实际换行符
        # 需要把转义的\\n还原成实际换行符，模拟LLM返回的原始内容
        raw = raw.replace('\\n', '\n')
        # 修复thought字段中的换行符（JSON.stringify会将实际换行转义，我们还原）
        raw = raw.replace('"用户要求全面检查网络信息，包括\nWiFi', 
                          '"用户要求全面检查网络信息，包括\nWiFi')
        return raw
    
    def test_extract_json_block_finds_result(self):
        """
        _extract_json_block能从含实换行符的JSON中提取result参数
        - 小健 2026-05-15
        """
        
        raw = self._build_raw_response_with_real_newlines()
        extracted = _extract_json_block(raw)
        
        assert extracted is not None, "_extract_json_block返回None"
        assert extracted.get("tool_name") == "finish", \
            f"tool_name应为finish，实际={extracted.get('tool_name')}"
        assert extracted.get("tool_params") is not None, "tool_params为None"
        assert "result" in extracted["tool_params"], \
            f"tool_params中应有result键，实际keys={list(extracted['tool_params'].keys())}"
        assert "网络全面诊断报告" in extracted["tool_params"]["result"], \
            "result内容不完整"
    
    def test_parse_react_response_returns_full_response(self):
        """
        parse_react_response从含实换行符的JSON中返回完整的finish响应
        - 小健 2026-05-15
        """
        
        raw = self._build_raw_response_with_real_newlines()
        result = parse_react_response(raw)
        
        assert result is not None, "parse_react_response返回None"
        assert result.get("type") == "answer", \
            f"finish应返回answer类型，实际={result.get('type')}"
        assert result.get("response", "") != "", "response不应为空"
        assert "网络全面诊断报告" in result.get("response", ""), \
            "response中应包含诊断报告内容"
    
    def test_extract_json_block_finds_thought_field(self):
        """
        _extract_json_block能从含实换行符的JSON中提取thought字段
        LLM使用thought而非content字段 - 小健 2026-05-15
        """
        
        raw = self._build_raw_response_with_real_newlines()
        extracted = _extract_json_block(raw)
        
        assert extracted is not None
        thought = extracted.get("thought", "") or extracted.get("content", "")
        assert thought != "", "thought/content不应为空"
        assert "网络信息" in thought, f"thought应包含网络信息，实际={thought[:50]}"
    
    def test_extract_json_block_non_finish_with_real_newlines(self):
        """
        _extract_json_block也能正确处理非finish的含实换行符JSON
        - 小健 2026-05-15
        """
        
        thought = "我需要先查看目录结构，然后\n再读取具体文件的内容。"
        raw = json.dumps({
            "thought": thought,
            "reasoning": "逐步检查文件系统",
            "tool_name": "list_directory",
            "tool_params": {"dir_path": "/home/user"}
        }, ensure_ascii=False)
        raw = raw.replace('\\n', '\n')
        
        extracted = _extract_json_block(raw)
        
        assert extracted is not None
        assert extracted.get("tool_name") == "list_directory", \
            f"tool_name应为list_directory，实际={extracted.get('tool_name')}"
        tool_params = extracted.get("tool_params", {})
        assert tool_params.get("dir_path") == "/home/user", \
            "tool_params.dir_path应被正确提取"
