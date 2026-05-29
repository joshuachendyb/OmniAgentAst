# -*- coding: utf-8 -*-
"""
llm_response_parser - ReAct输出统一解析器包

对外接口：parse_react_response(output) → Dict

Author: 小沈
Date: 2026-05-28
Version: 2.0（从 react_output_parser.py 按职责拆分为6个内部模块）
"""

# 从各内部模块导入并重新导出
from ._utils import (
    REACT_KEYWORDS,
    _add_reasoning_warning,
    _normalize_result_to_str,
    _build_handler_result,
    _make_action_result_dict,
    _extract_json_with_balanced_braces,
    _extract_key_value_pairs,
    _get_all_tool_names,
)

from ._tool_params import (
    _TOOL_NAME_FALLBACK_KEYS,
    _TOOL_PARAMS_FALLBACK_KEYS,
    _build_action_result,
    _fallback_tool_name,
    _normalize_tool_params,
    _normalize_tool_params_content,
    _filter_tool_params,
    _process_tool_params,
    _extract_tool_params_from_thought,
    _extract_tool_params_from_text,
    _extract_content_value_from_json_str,
    _extract_params_by_regex_from_json_str,
    _extract_params_by_regex,
)

from ._json_strategies import (
    _extract_json_string,
    _strategy_direct_parse,
    _strategy_encoding_fix,
    _strategy_chinese_quotes,
    _strategy_newline_fix,
    _strategy_trailing_comma,
    register_strategy,
    get_strategies,
    _try_parse_with_strategies,
    _FIELD_ALIASES,
    _try_extract_single_field,
    _extract_fields_from_json_str,
    _try_extract_last_tool_call,
    _extract_json_block,
    _try_parse_non_standard_json,
)

STRATEGIES = get_strategies()

from ._result_builders import (
    _process_json_result,
    _build_parse_error_result,
    _build_answer_result,
    _build_chunk_result,
    _build_action_from_fc_format,
    _build_action_from_new_format,
    _build_action_from_old_format,
    _resolve_return_type,
    _create_action_result_from_dict,
    _create_action_result_from_list,
    _convert_function_calling_items,
    _create_action_result,
)

from ._keyword_parsers import (
    _parse_thought_only,
    _try_codeblock_parse,
    _try_keyword_parse,
    _make_fallback_result,
    _determine_parse_type,
    _parse_action,
    _parse_answer,
    _parse_action_input,
    _try_parse_chain,
    _try_markdown_parse,
    _try_json_parse,
    _try_balanced_braces,
    _try_single_quotes,
    _try_kv_parse,
    _extract_fields_partial,
)

from .parse_react_response import (
    _handle_dict_input,
    _handle_list_input,
    _handle_json_array_string,
    _handle_empty_input,
    _handle_standard_json,
    _handle_non_standard_json,
    _handle_mixed_text_json,
    _handle_regex_fallback,
    _handle_known_tool_match,
    _handle_keyword_match,
    _HANDLERS,
    parse_react_response,
    _try_regex_tool_call_fallback,
)


__all__ = [
    "parse_react_response",
]
