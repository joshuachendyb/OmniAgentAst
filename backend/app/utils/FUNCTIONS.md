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

### 1.1 数据处理（data_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `safe_truncate` | 安全截断数据 | data, limit | 截断后的数据 |
| `parse_json` | 解析JSON字符串 | json_str, label | 解析结果或None |

### 1.2 时间处理（time_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `create_timestamp` | 创建毫秒时间戳 | 无 | int |
| `get_timestamp_ms` | 获取UTC毫秒时间戳 | 无 | int |
| `get_utc_timestamp` | 获取UTC时间戳ISO格式 | 无 | str |
| `convert_to_utc` | 转换为UTC ISO格式 | time_value | str |
| `ensure_timestamp_milliseconds` | 确保时间戳转为毫秒 | ts_value | int |
| `create_step_counter` | 创建步骤计数器 | 无 | Callable |

### 1.3 通用函数（common.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `extract_display_name_from_steps` | 从步骤提取显示名称 | execution_steps_data | str或None |
| `build_display_name` | 构建显示名称 | provider, model | str |
| `extract_metadata_from_steps` | 从步骤提取元数据 | execution_steps | dict |

### 1.4 工具函数（tool_result_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `truncate_text` | 截断文本 | text, max_chars, suffix | tuple |
| `format_output_for_llm` | 格式化输出给LLM | stdout, stderr, max_chars | dict |
| `format_file_content_llm` | 格式化文件内容给LLM | content, max_chars | dict |
| `make_json_safe` | 使JSON安全 | data, max_depth, max_str_len | data |
| `truncate_data_for_frontend` | 截断数据给前端 | data, max_chars | dict |
| `build_next_actions` | 构建下一步操作 | actions | list |

---

## 二、Agent层（app/services/agent/agent_utils/）

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

---

## 三、工具层（app/services/tools/toolhelper/）

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
| `network_helper.py` | 网络辅助函数 |
| `service_helper.py` | 服务辅助函数 |
| `shell_helper.py` | Shell辅助函数 |
| `task_helper.py` | 任务辅助函数 |
| `window_helper.py` | 窗口辅助函数 |

---

## 四、使用示例

### 4.1 正确做法

```python
# 有公用函数，直接使用
from app.utils.data_utils import parse_json
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

**最后更新时间**: 2026-05-29 07:50:00
**维护人**: 小沈
