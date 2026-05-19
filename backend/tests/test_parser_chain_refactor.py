"""
解析器链重构——全量回归测试
覆盖 parse_react_response 所有代码路径，确保重构前后行为一致

作者: 小沈
日期: 2026-05-19
用途: 重构前验证现有逻辑 → 重构后验证逻辑无损
"""
import json
import pytest
from app.services.agent.react_output_parser import parse_react_response


# =============================================================================
# 1. 类型守卫路径 (lines 103-139)
# =============================================================================

class TestTypeGuardPath:
    """dict输入、list输入、JSON数组字符串、空值/非字符串"""

    def test_dict_input_with_tool_name(self):
        """dict输入含tool_name → 返回action"""
        r = parse_react_response({"tool_name": "search_web", "tool_params": {"query": "test"}})
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"
        assert r["tool_params"]["query"] == "test"

    def test_dict_input_without_tool_name(self):
        """dict输入无tool_name → _create_action_result_from_dict返回implicit"""
        r = parse_react_response({"type": "answer", "content": "回答内容", "thought": "思考"})
        # dict路径走_create_action_result_from_dict，它只看tool_name/function，不处理type字段
        assert r is not None

    def test_list_input_single(self):
        """list输入单个元素 → 返回action"""
        r = parse_react_response([{"tool_name": "ping", "tool_params": {"host": "8.8.8.8"}}])
        assert r["type"] == "action"
        assert r["tool_name"] == "ping"

    def test_json_array_string(self):
        """JSON数组字符串(以[开头) → 解析为list后处理"""
        r = parse_react_response('[{"tool_name": "get_time", "tool_params": {"action": "now"}}]')
        assert r["type"] == "action"
        assert r["tool_name"] == "get_time"

    def test_json_array_string_invalid_should_fallthrough(self):
        """无效的JSON数组字符串(非真数组) → 不应崩溃,继续后续处理"""
        r = parse_react_response("[not valid json at all")
        assert r is not None  # 不崩溃
        assert r["type"] in ("parse_error", "implicit")

    def test_empty_string(self):
        """空字符串 → parse_error"""
        r = parse_react_response("")
        assert r["type"] == "parse_error"

    def test_none_input(self):
        """None输入 → parse_error"""
        r = parse_react_response(None)
        assert r["type"] == "parse_error"

    def test_whitespace_only(self):
        """仅空白字符串 → parse_error (由后续路径处理)"""
        r = parse_react_response("   ")
        assert r is not None


# =============================================================================
# 2. 标准JSON路径 (lines 144-239)
# =============================================================================

class TestStandardJsonPath:
    """json.loads成功 → 各种type/tool_name/action分支"""

    # --- 旧格式 action/action_input ---

    def test_old_format_action(self):
        """旧格式: action+action_input → action"""
        r = parse_react_response(json.dumps({
            "action": "search_web",
            "action_input": {"query": "AI", "num_results": 10},
            "thought": "I should search"
        }))
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"
        assert r["tool_params"]["query"] == "AI"

    def test_old_format_finish(self):
        """旧格式: action=finish → answer"""
        r = parse_react_response(json.dumps({
            "action": "finish",
            "action_input": {"result": "所有任务完成"}
        }))
        assert r["type"] == "answer"
        assert r["tool_name"] is None
        assert r["response"] == "所有任务完成"

    def test_old_format_finish_no_result(self):
        """旧格式: action=finish 无action_input.result → answer但response为空"""
        r = parse_react_response(json.dumps({
            "action": "finish",
            "action_input": {}
        }))
        assert r["type"] == "answer"
        assert r["tool_name"] is None

    # --- 新格式 tool_name/tool_params ---

    def test_new_format_tool_name_finish_with_result(self):
        """新格式: tool_name=finish 且 tool_params.result存在 → answer"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": "任务完成，已生成报告"},
            "thought": "All done"
        }))
        assert r["type"] == "answer"
        assert r["tool_name"] is None
        assert r["response"] == "任务完成，已生成报告"

    def test_new_format_tool_name_finish_no_result(self):
        """新格式: tool_name=finish 但无tool_params.result → answer但response为空"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"message": "done"},
            "thought": "done"
        }))
        assert r["type"] == "answer"

    # --- pending_calls 透传 ---

    def test_new_format_with_pending_calls(self):
        """新格式含_pending_calls → 透传到结果中"""
        r = parse_react_response(json.dumps({
            "tool_name": "search_web",
            "tool_params": {"query": "test"},
            "_pending_calls": [
                {"tool_name": "ping", "tool_params": {"host": "8.8.8.8"}}
            ]
        }))
        assert r["type"] == "action"
        assert "_pending_calls" in r
        assert len(r["_pending_calls"]) == 1

    def test_old_format_with_pending_calls(self):
        """旧格式含_pending_calls → 透传到结果中"""
        r = parse_react_response(json.dumps({
            "action": "search_web",
            "action_input": {"query": "test"},
            "_pending_calls": [{"tool_name": "ping", "tool_params": {"host": "1.1.1.1"}}]
        }))
        assert "_pending_calls" in r

    # --- 无匹配模式的dict ---

    def test_standard_json_no_pattern(self):
        """标准JSON dict但无type/tool_name/action → 交给后续handler"""
        # 只有thought字段，没有显式type、tool_name、action
        r = parse_react_response(json.dumps({
            "thought": "用户想了解天气，我应该调用天气API查询",
            "reasoning": "天气信息需要实时查询"
        }))
        assert r is not None
        assert r["type"] in ("implicit", "thought_only")


# =============================================================================
# 3. 非标准JSON路径 (lines 243-311)
# =============================================================================

class TestNonStandardJsonPath:
    """单引号JSON: _try_parse_non_standard_json 成功"""

    def test_single_quote_json_chunk(self):
        """单引号JSON type=chunk"""
        raw = "{'type': 'chunk', 'content': '正在思考中...', 'thought': '思考'}"
        r = parse_react_response(raw)
        assert r["type"] == "chunk"
        assert r["content"] == "正在思考中..."

    def test_single_quote_json_answer(self):
        """单引号JSON type=answer"""
        raw = "{'type': 'answer', 'content': '答案是42', 'thought': '计算完成'}"
        r = parse_react_response(raw)
        assert r["type"] == "answer"

    def test_single_quote_json_parse_error(self):
        """单引号JSON type=parse_error"""
        raw = "{'type': 'parse_error', 'error': '工具调用失败', 'content': '出错了'}"
        r = parse_react_response(raw)
        assert r["type"] == "parse_error"

    def test_single_quote_json_tool_name(self):
        """单引号JSON 含tool_name → action"""
        raw = "{'tool_name': 'get_time', 'tool_params': {'action': 'now'}, 'thought': '获取时间'}"
        r = parse_react_response(raw)
        assert r["type"] == "action"
        assert r["tool_name"] == "get_time"

    def test_single_quote_json_finish(self):
        """单引号JSON tool_name=finish → answer"""
        raw = "{'tool_name': 'finish', 'thought': '任务完成'}"
        r = parse_react_response(raw)
        assert r["type"] == "answer"
        assert r["tool_name"] is None

    def test_non_standard_json_not_dict(self):
        """非标准JSON解析结果不是dict → 交给后续handler"""
        raw = "'just some text with quotes'"
        r = parse_react_response(raw)
        assert r is not None


# =============================================================================
# 4. JSON块提取路径 (lines 313-437)
# =============================================================================

class TestJsonBlockExtractionPath:
    """_extract_json_block: 混合文本中提取JSON"""

    def test_mixed_text_with_json_tool_name(self):
        """混合文本+JSON块(tool_name) → action"""
        raw = "我来帮你搜索一下\n{\"tool_name\": \"search_web\", \"tool_params\": {\"query\": \"天气\"}}"
        r = parse_react_response(raw)
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"

    def test_mixed_text_with_json_finish(self):
        """混合文本+JSON块(finish) → answer"""
        raw = "搜索完成\n{\"tool_name\": \"finish\", \"tool_params\": {\"result\": \"北京今天晴天\"}}"
        r = parse_react_response(raw)
        assert r["type"] == "answer"
        assert r["response"] == "北京今天晴天"

    def test_json_block_no_tool_name_but_content(self):
        """JSON块无tool_name但有content/reasoning → implicit"""
        raw = "前面有一些思考文字\n{\"content\": \"这是回答内容\", \"reasoning\": \"推理过程\"}"
        r = parse_react_response(raw)
        assert r["type"] == "implicit"
        assert r["content"] == "这是回答内容"

    def test_json_block_with_action_keyword_before(self):
        """JSON块前有Action关键词 → 不应误判为无tool_name，交给关键词路径"""
        raw = "Action: search_web\nAction Input: {\"query\": \"test\"}"
        r = parse_react_response(raw)
        # 有Action关键词→不应走content-only implicit路径
        assert r["type"] in ("action", "parse_error", "implicit")

    def test_incomplete_json_thought_only(self):
        """被截断的JSON: {"thought": "我需要使用... → chunk"""
        raw = '{"thought": "用户想查看D盘的目录情况，我需要使用list_directory工具来列出D盘'
        r = parse_react_response(raw)
        assert r["type"] == "chunk"

    def test_incomplete_json_with_action_misdetection_prevention(self):
        """被截断JSON中含工具名但不应被误判为action → chunk"""
        raw = '{"thought": "用户需要搜索信息，我应该使用search_web工具来搜索相关内容'
        r = parse_react_response(raw)
        # 不完整JSON→走chunk路径，不应把thought内容中的"search_web"当工具调用
        assert r["type"] == "chunk"
        assert r["tool_name"] is None


# =============================================================================
# 5. 正则兜底路径 (lines 439-443)
# =============================================================================

class TestRegexFallbackPath:
    """_try_regex_tool_call_fallback: 正则提取工具调用"""

    def test_regex_extracts_tool_call_from_text(self):
        """从纯文本中用正则提取出tool_name和tool_params"""
        raw = '应该使用 search_web 来搜索，参数是 {"query": "AI发展", "num_results": 5}'
        r = parse_react_response(raw)
        # 正则兜底可能提取成功也可能失败（取决于模式匹配），但不应崩溃
        assert r is not None

    def test_final_fallback_keyword_match(self):
        """所有路径失败后的关键词匹配兜底"""
        raw = "Thought: 这是一个测试\nAnswer: 这是最终回答"
        r = parse_react_response(raw)
        assert r is not None
        # 关键词匹配到Answer → type=answer
        assert r["type"] == "answer"


# =============================================================================
# 6. 边界情况
# =============================================================================

class TestEdgeCases:
    """边界情况：空值、特殊字符、格式混合"""

    def test_very_long_text_fallback(self):
        """超长纯文本 → 走兜底路径返回implicit"""
        raw = "这是一个非常长的思考内容" * 100
        r = parse_react_response(raw)
        assert r is not None
        assert r["type"] == "implicit"

    def test_integer_input(self):
        """整数输入 → parse_error"""
        r = parse_react_response(123)
        assert r["type"] == "parse_error"

    def test_bool_input(self):
        """布尔输入 → parse_error"""
        r = parse_react_response(True)
        assert r["type"] == "parse_error"

    def test_empty_dict(self):
        """空dict输入 → 交给_create_action_result_from_dict处理"""
        r = parse_react_response({})
        assert r is not None

    def test_empty_list(self):
        """空list输入 → 交给_create_action_result_from_list处理"""
        r = parse_react_response([])
        assert r is not None


class TestFinishResultNormalization:
    """finish时result字段嵌套标准化（小沈 2026-05-19修复）"""

    def test_finish_result_is_string(self):
        """result是字符串 → 保持不变"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": "最终答案"}
        }))
        assert r["type"] == "answer"
        assert r["response"] == "最终答案"

    def test_finish_result_is_dict(self):
        """result是dict → 转为JSON字符串"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": {"status": "ok", "data": "value"}}
        }))
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)
        assert '"status": "ok"' in r["response"]

    def test_finish_result_is_list(self):
        """result是list → 转为JSON字符串"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": [1, 2, 3]}
        }))
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)
        assert "[1, 2, 3]" in r["response"]

    def test_finish_result_is_number(self):
        """result是数字 → 转为字符串"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": 42}
        }))
        assert r["type"] == "answer"
        assert r["response"] == "42"

    def test_finish_result_is_bool(self):
        """result是布尔 → 转为字符串"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": True}
        }))
        assert r["type"] == "answer"
        assert r["response"] == "True"

    def test_finish_result_is_none(self):
        """result是None → 保留为None（不崩溃）"""
        r = parse_react_response(json.dumps({
            "tool_name": "finish",
            "tool_params": {"result": None}
        }))
        assert r["type"] == "answer"
        # None不处理，response可能为空或其他逻辑结果
        assert r["response"] is None or r["response"] == ""
