# 公用函数清单

**创建时间**: 2026-05-29 07:50:00
**维护人**: 小沈

---

## 使用规则

1. **写代码前先查本清单**
2. **有公用函数必须使用，禁止重复实现**
3. **没有才创建新的**
4. **新函数必须添加到本清单**
5. **禁止向后兼容：不保留旧名称别名**

---

## 一、全局层（app/utils/）

### 1.1 时间处理（time_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `create_timestamp` | 创建毫秒时间戳 | 无 | int |
| `get_timestamp_ms` | 获取UTC毫秒时间戳 | 无 | int |
| `get_utc_timestamp` | 获取UTC时间戳ISO格式 | 无 | str |
| `convert_to_utc` | 转换为UTC ISO格式 | time_value | str |
| `ensure_timestamp_milliseconds` | 确保时间戳转为毫秒 | ts_value | int |
| `create_step_counter` | 创建步骤计数器 | 无 | Callable |
| `timestamp_for_filename` | **【v0.13.33新增】** 文件名时间戳 YYYYMMDD_HHMMSS | 无 | str |
| `now_str` | **【v0.13.33新增】** 当前时间格式化字符串，默认 YYYY-MM-DD HH:MM:SS | fmt | str |

### 1.2 通用函数（common.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `extract_display_name_from_steps` | 从步骤提取显示名称 | execution_steps_data | str或None |
| `build_display_name` | 构建显示名称 | provider, model | str |
| `extract_metadata_from_steps` | 从步骤提取元数据 | execution_steps | dict |
| `format_param_value` | **【v1.3新增】** 将参数默认值格式化为字符串（供LLM提示文本使用），None→""、bool→"true"/"false" | val | str |

### 1.3 JSON解析（json_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parse_json` | 解析JSON字符串 | json_str, label, raise_on_error | 解析结果或None |
| `coerce_json` | **【v0.16.3新增】** 若值为JSON字符串则解析为dict/list，否则原样返回 | value: Any | Any |
| `read_json_file` | **【v1.4新增】** 读取JSON文件 | file_path, label, raise_on_error | 解析结果或None |
| `_try_fix_incomplete_json` | **【v1.5新增】** 修复不完整/非标准JSON字符串(缺括号/单引号Python dict) | json_str: str | Optional[Dict] |
| `_normalize_tool_params` | **【v1.5新增】** 递归归一化tool params，修复LLM双倍编码字符串→还原为list/dict（从llm层迁入） | params: Any | Any |

### 1.4 响应工具（response_utils.py）【v0.13.33新增】

### 1.5 依赖安装（dependency.py）【v0.16.5新增】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `ensure_dependency` | 确保Python依赖可用，缺失自动安装 | import_name, pip_package, pre_install | bool |

### 1.6 表格辅助（table_helper.py）【v0.17.0新增】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parse_markdown_table` | 解析Markdown表格，返回(表格数据, 结束索引) | lines, start_idx | Tuple[List[List[str]], int] |
| `calculate_column_widths` | 计算列宽比例（按内容长度自适应） | table_data, total_width=1.0 | List[float] |
| `get_table_header_style_config` | 获取表头样式配置（共享配置） | 无 | Dict[str, Any] |
| `get_table_border_config` | 获取表格边框配置（共享配置） | 无 | Dict[str, Any] |
| `dict_table_to_rows` | **【v1.7新增】** dict{headers,rows}转list[list] | dict_table | List[List[str]] |
| `normalize_table_data` | **【v1.7增强】** 归一化表格数据，支持list[list]/dict/list[dict]/None | table_data | Optional[List[List[str]]] |

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `api_success` | 统一成功响应 {"success":True, "message":xxx} | message, **extra | dict |
| `api_failure` | 统一失败响应 {"success":False, "message":xxx} | message, errors, **extra | dict |
| `api_error` | 记录日志并抛 HTTPException | status_code, detail, log_msg | None |
| `handle_api_errors` | **【v0.13.33新增】** 通用API异常处理装饰器 | operation_name | decorator |

### 1.7 文本处理（text_utils.py）【v2.1新增 — 小欧 2026-07-16】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `truncate_text` | 通用尾部截断,返回(截断后文本, 是否截断) | text, max_chars, suffix | tuple |
| `smart_truncate_text` | 智能截断(保留头尾省略中间) | content, budget, head_ratio | str |
| `add_line_numbers` | 添加行号前缀 | content, offset | str |
| `extract_tool_call_xml` | **【v2.1新增】** 从文本提取 `<tool_call>` XML 工具调用(非破坏性, reasoning/content中LLM降级旧格式时的恢复路径) | text | Optional[Dict[str, Any]] |
| `format_tool_call_markup` | **【v2.0新增】** 将LLM输出XML/JSON tool call标记格式化为纯文本(破坏性) | text | str |

> 注：`truncate_text`/`add_line_numbers` 此前曾误登记于 1.5 节(tool_result_utils.py)，实际定义于 text_utils.py；本节为正确归属。 — 小欧 2026-07-16

### 1.8 ID生成（id_utils.py）【v2.2新增 — 小欧 2026-07-16】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `generate_operation_id` | 生成统一格式 op-{hex}, 全链路文件/任务操作 ID 同源(替代各处重复的 f"op-{uuid4().hex}") | 无 | str |

### 1.5 工具函数（tool_result_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `format_output_for_llm` | 格式化输出给LLM | stdout, stderr, max_chars | dict |
| `format_file_content_llm` | 格式化文件内容给LLM | content, max_chars | dict |
| `make_json_safe` | 使JSON安全 | data, max_depth, max_str_len | data |
| `truncate_data_for_frontend` | 截断数据给前端 | data, max_chars | dict |


---

## 二、工具层（app/services/tools/）

### 2.1 工具返回构建（_response.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_success` | 构建成功响应 | data, message, warning, llm_data, ... | dict |
| `build_error` | 构建错误响应 | code, message, data, ... | dict |
| `build_warning` | 构建警告响应 | code, message, data, ... | dict |

---

## 三、Agent层（app/services/agent/agent_utils/）

### 2.1 消息工具（message_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_llm_messages` | 构建LLM消息列表 | message, history | list |
| `build_observation_text` | 构建观察文本 | execution_result, tool_name, tool_params | str |
| `inject_tools_info` | 注入工具信息 | history_dicts, tools_content | list |
| `inject_schema_text` | 注入Schema文本 | history_dicts, schema_text | list |
| `build_schema_text` | 构建Schema文本 | openai_tools | str |

### 2.2 工具结果（tool_result_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `create_tool_result` | 创建工具结果 | data, message, retry_count, metadata, error_message, error_type, return_direct | dict |
| `create_error_tool_result` | 创建错误工具结果 | error_message, error_type, retry_count, metadata | dict |
| `create_warning_tool_result` | 创建警告工具结果 | warning_message, data, retry_count, metadata | dict |

### 3.3 步骤存储（storage.py）【2026-07-14 — 小欧】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `allocate_and_insert_message` | 预分配 assistant 消息ID + 插入空白行(幂等) | conn, session_id | int(message_id) |
| `append_execution_step` | 逐步落库:一行=一步 | conn, message_id, session_id, step_index, step_dict | None |
| `load_execution_steps` | 从 steps 表组装步骤列表(无数据时从chat_messages.execution_steps列读取) | conn, message_id | Optional[list] |
| `finalize_message` | finally 轻量终态更新(content+status) | conn, message_id, content, status | None |

---

## 三、工具层（app/tools/toolhelper/）

| 文件 | 功能 |
|------|------|
| `common_helper.py` | 通用辅助函数 |
| `data_format_helper.py` | 数据格式化辅助 |
| `data_helper.py` | 数据辅助函数 |
| `date_helper.py` | 日期辅助函数 |
| `db_helper.py` | 数据库辅助函数 |
| `exec_helper.py` | 执行辅助函数 |
| `file_helpers.py` | 文件辅助函数 |
| `gui_helper.py` | GUI辅助函数 |
| `hash_helper.py` | 哈希辅助函数 |
| `line_pager.py` | 行分页/截断工具 `select_lines`(按 offset/limit/tail 选取行, 供 read_text_file/read_docx 复用, Tool 层零限制, 字符截断收口于 observation_formatter) — 小欧 2026-07-20 |
| `network_helper.py` | 网络辅助函数 |
| `service_helper.py` | 服务辅助函数 |
| `shell_helper.py` | Shell辅助函数 |
| `task_helper.py` | 任务辅助函数 |
| `window_helper.py` | 窗口辅助函数 |

---

## 四、LLM核心层（app/services/llm_core/）

> `_normalize_tool_params` 已于 v1.5 迁至 `json_utils.py`（集中JSON解析函数）

---

## 五、使用示例

### 4.1 正确做法

```python
# 有公用函数，直接使用
from app.utils.json_utils import parse_json
from app.utils.time_utils import ensure_timestamp_milliseconds

result = parse_json(json_str)
timestamp = ensure_timestamp_milliseconds(ts_value)
```

### 4.2 错误做法

```python
# 错误：重复实现已有函数
def my_parse_json(json_str):
    try:
        return json.loads(json_str)
    except:
        return None  # 禁止！已有parse_json函数
```

---

**最后更新时间**: 2026-07-16 07:30:00
**维护人**: 小沈

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v2.0 | 2026-07-16 | 新增1.7 text_utils.py章节：登记extract_tool_call_xml(XML提取,LLM旧格式恢复路径)与format_tool_call_markup；truncate_text/add_line_numbers归属修正至text_utils.py | 小欧 |
| v1.9 | 2026-07-14 | 新增storage.py步骤存储4函数(allocate_and_insert_message/append_execution_step/load_execution_steps/finalize_message) | 小欧 |
| v1.8 | 2026-07-10 | 删除test_marker.py（已废弃） | 小沈 |
| v1.7 | 2026-07-08 | table_helper新增dict_table_to_rows，增强normalize_table_data（支持dict/list[dict]/None） | 小欧 |
| v1.6 | 2026-07-05 | text_utils新增add_line_numbers公共函数 | 小欧 |
| v1.5 | 2026-07-02 | _try_fix_incomplete_json新增,_normalize_tool_params从llm_core迁入json_utils.py | 小沈 |
| v1.4 | 2026-06-17 | 新增read_json_file函数 | 小沈 |
| v1.3 | 2026-06-14 | 新增llm_core层_normalize_tool_params函数 | 小沈 |
| v1.2 | 2026-06-13 | 新增test_marker.py测试标记工具 | 小沈 |
| v1.1 | 2026-06-09 15:45:00 | 新增extract_data_summary函数 | 小沈 |
| v1.0 | 2026-05-29 07:50:00 | 初始版本 | 小沈 |
