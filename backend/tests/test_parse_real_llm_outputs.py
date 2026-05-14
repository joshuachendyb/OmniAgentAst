"""
测试解析真实LLM返回数据 - 小沈 2026-05-14

从app_2026-05-14.log中提取的LLM原始返回，覆盖所有解析路径：
  - Function Calling格式（数组）
  - 直接JSON格式（tool_name+tool_params）
  - 纯文本回答（implicit/answer）
  - 自然语言含工具名（如"（ping）"）
"""
import sys
sys.path.insert(0, r'G:\OmniAgentAs-desk\backend')
import json

from app.services.agent.react_output_parser import parse_react_response


class TestFunctionCallingFormat:
    """Function Calling格式（LLM返回tool_calls数组）"""

    def test_single_tool_call(self):
        """单个工具调用"""
        text = json.dumps([{"index": 0, "id": "call_xxx", "type": "function",
            "function": {"name": "search_web", "arguments": '{"query": "AI发展", "num_results": 10}'}}])
        r = parse_react_response(text)
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"
        assert r["tool_params"]["query"] == "AI发展"

    def test_two_tool_calls(self):
        """两个并行工具（_create_action_result_from_list取最后一个元素为主工具）"""
        text = json.dumps([
            {"index": 0, "id": "call_00", "type": "function",
                "function": {"name": "execute_shell_command",
                    "arguments": '{"command": "ipconfig /all", "shell_type": "powershell"}'}},
            {"index": 1, "id": "call_01", "type": "function",
                "function": {"name": "http_request",
                    "arguments": '{"url": "https://api.ipify.org?format=json", "method": "GET", "timeout": 15000}'}}
        ])
        r = parse_react_response(text)
        assert r["type"] == "action"
        assert r["tool_name"] == "http_request"  # 最后一个元素为主工具
        assert "_pending_calls" in r
        assert len(r["_pending_calls"]) == 1
        assert r["_pending_calls"][0]["name"] == "execute_shell_command"  # 其余为_pending_calls

    def test_three_parallel_tools(self):
        """三个并行工具"""
        text = json.dumps([
            {"index": 0, "id": "call_0", "type": "function",
                "function": {"name": "search_web", "arguments": '{"query": "q1", "num_results": 10}'}},
            {"index": 1, "id": "call_1", "type": "function",
                "function": {"name": "search_web", "arguments": '{"query": "q2", "num_results": 10}'}},
            {"index": 2, "id": "call_2", "type": "function",
                "function": {"name": "list_allowed_directories", "arguments": "{}"}},
        ])
        r = parse_react_response(text)
        assert r["type"] == "action"
        assert r["tool_name"] == "list_allowed_directories"  # 最后一个元素为主工具
        assert len(r["_pending_calls"]) == 2
        assert r["_pending_calls"][0]["name"] == "search_web"
        assert r["_pending_calls"][1]["name"] == "search_web"

    def test_finish_via_function_calling(self):
        """Function Calling格式的finish"""
        text = json.dumps([{"index": 0, "id": "call_finish", "type": "function",
            "function": {"name": "finish", "arguments": '{"result": "done"}'}}])
        r = parse_react_response(text)
        assert r["type"] == "answer" or r["type"] == "action"
        if r["type"] == "action":
            assert r["tool_name"] == "finish"


class TestDirectJsonFormat:
    """直接JSON格式（LLM返回独立JSON对象）"""

    def test_simple_finish_json(self):
        """最简单的finish"""
        r = parse_react_response('{"tool_name":"finish","tool_params":{"result":"done"}}')
        assert r["type"] in ("answer", "action")
        if r["type"] == "action":
            assert r["tool_name"] == "finish"

    def test_json_with_thought_reasoning(self):
        """带thought/reasoning的JSON"""
        r = parse_react_response(json.dumps({
            "thought": "用户询问时间",
            "reasoning": "调用get_current_time",
            "tool_name": "get_current_time",
            "tool_params": {"format": "%Y-%m-%d"}
        }))
        assert r["type"] == "action"
        assert r["tool_name"] == "get_current_time"

    def test_json_with_pending_calls(self):
        """带_pending_calls的JSON（并行工具）"""
        r = parse_react_response(json.dumps({
            "thought": "Calling 2 tools",
            "tool_name": "http_request",
            "tool_params": {"url": "https://httpbin.org/ip", "method": "GET", "timeout": 15000},
            "_pending_calls": [
                {"name": "http_request", "args": {"url": "https://api.ipify.org?format=json", "method": "GET", "timeout": 15000}}
            ]
        }))
        assert r["type"] == "action"
        assert r["tool_name"] == "http_request"
        assert "_pending_calls" in r
        assert len(r["_pending_calls"]) == 1

    def test_json_without_tool_name(self):
        """有content/reasoning但无tool_name的JSON（应返回implicit）"""
        r = parse_react_response(json.dumps({
            "content": "你的公网IP是114.244.125.100",
            "reasoning": "已从api.ipify.org获取"
        }))
        assert r["type"] == "implicit", f"应为implicit，实际={r['type']}"
        assert r["tool_name"] is None

    def test_response_with_content_only(self):
        """只有content字段的JSON"""
        r = parse_react_response(json.dumps({
            "content": "**任务已完成！**"
        }))
        assert r["type"] == "implicit", f"应为implicit，实际={r['type']}"
        assert r["tool_name"] is None


class TestTextResponses:
    """纯文本回答（非JSON）"""

    def test_text_with_ping_in_parentheses(self):
        """自然语言中含（ping）— 不应被提取为工具调用"""
        text = "如果你还想测试一下网络延迟（ping）或者检查特定端口，也可以告诉我！"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer"), f"不应为action，实际={r['type']}"
        assert r["tool_name"] is None, f"不应有tool_name，实际={r['tool_name']}"

    def test_text_task_summary(self):
        """LLM的完整文本回答"""
        text = "好的！我已经成功获取到了相关信息，现在为您汇总一下：\n## 公网IP\n114.244.125.100"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer"), f"不应为action，实际={r['type']}"
        assert r["tool_name"] is None

    def test_text_timeout_recovery(self):
        """LLM对超时的恢复性回答"""
        text = "没问题，刚才ipify.org超时了，没关系～之前已经通过httpbin.org成功查到了公网IP，已经安全了"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer")
        assert r["tool_name"] is None

    def test_text_all_data_collected(self):
        """LLM说数据已收集完毕"""
        text = "太棒了，所有数据都已经获取完毕，我来为你做一个完整汇总！"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer")
        assert r["tool_name"] is None

    def test_httpbin_timeout_response(self):
        """LLM对httpbin也超时的回答"""
        text = "这次httpbin.org这次也超时了，没关系～之前已经有成功数据了，直接给出汇总"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer")
        assert r["tool_name"] is None

    def test_text_containing_curl(self):
        """自然语言中含curl command"""
        text = "我可以用curl命令来测试网络连接，或者用ping来检查延迟"
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer")
        assert r["tool_name"] is None

    def test_markdown_text(self):
        """含markdown格式的文本回答"""
        text = """**任务已完成！**
已成功将文件写入到目录下。
文件路径：`F:\\test.md`"""
        r = parse_react_response(text)
        assert r["type"] in ("implicit", "chunk", "answer")
        assert r["tool_name"] is None


class TestEdgeCases:
    """边界情况"""

    def test_empty_output(self):
        r = parse_react_response("")
        assert r["type"] == "parse_error"

    def test_very_short_output(self):
        r = parse_react_response("ok")
        assert r["type"] in ("parse_error", "chunk", "implicit")

    def test_json_in_code_block(self):
        """```json 包裹的格式"""
        text = '```json\n{"tool_name": "search_web", "tool_params": {"query": "test"}}\n```'
        r = parse_react_response(text)
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"
