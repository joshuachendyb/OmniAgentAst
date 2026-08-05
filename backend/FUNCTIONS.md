# 公用函数清单

**创建时间**: 2026-05-29 07:50:00
**维护人**: 小沈
**最后更新时间**: 2026-08-05 12:13:13

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

### 1.2 通用函数（display_utils.py）【v2.4更正：原登记为 common.py，模块不存在，实际定义于 display_utils.py】

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

### 1.4 响应工具（response_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `api_success` | 统一成功响应 {"success":True, "message":xxx} | message, **extra | dict |
| `api_failure` | 统一失败响应 {"success":False, "message":xxx} | message, errors, **extra | dict |
| `api_error` | 记录日志并抛 HTTPException | status_code, detail, log_msg | None |
| `handle_api_errors` | **【v0.13.33新增】** 通用API异常处理装饰器 | operation_name | decorator |

### 1.5 依赖安装（dependency.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `ensure_dependency` | 确保Python依赖可用，缺失自动安装 | import_name, pip_package, pre_install | bool |

### 1.6 表格辅助（table_helper.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parse_markdown_table` | 解析Markdown表格，返回(表格数据, 结束索引) | lines, start_idx | Tuple[List[List[str]], int] |
| `calculate_column_widths` | 计算列宽比例（按内容长度自适应） | table_data, total_width=1.0 | List[float] |
| `get_table_header_style_config` | 获取表头样式配置（共享配置） | 无 | Dict[str, Any] |
| `get_table_border_config` | 获取表格边框配置（共享配置） | 无 | Dict[str, Any] |
| `dict_table_to_rows` | **【v1.7新增】** dict{headers,rows}转list[list] | dict_table | List[List[str]] |
| `normalize_table_data` | **【v1.7增强】** 归一化表格数据，支持list[list]/dict/list[dict]/None | table_data | Optional[List[List[str]]] |

### 1.7 文本处理（text_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `truncate_text` | 通用尾部截断,返回(截断后文本, 是否截断) | text, max_chars, suffix | tuple |
| `smart_truncate_text` | 智能截断(保留头尾省略中间) | content, budget, head_ratio | str |
| `add_line_numbers` | 添加行号前缀 | content, offset | str |
| `extract_tool_call_xml` | **【v2.1新增】** 从文本提取 `<tool_call>` XML 工具调用(非破坏性, reasoning/content中LLM降级旧格式时的恢复路径) | text | Optional[Dict[str, Any]] |
| `format_tool_call_markup` | **【v2.0新增】** 将LLM输出XML/JSON tool call标记格式化为纯文本(破坏性) | text | str |

> 注：`truncate_text`/`add_line_numbers` 此前曾误登记于 1.5 节(tool_result_utils.py)，实际定义于 text_utils.py；本节为正确归属。 — 小欧 2026-07-16

### 1.8 ID生成（id_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `generate_operation_id` | 生成统一格式 op-{hex}, 全链路文件/任务操作 ID 同源(替代各处重复的 f"op-{uuid4().hex}") | 无 | str |

---

## 二、工具返回层（app/tools/）

### 2.1 工具返回构建（tool_response.py）【v2.4更正：原登记为 app/services/tools/_response.py，路径过时，实际定义于 app/tools/tool_response.py】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_success` | 构建成功响应 | data, llm_data, other_data, **extra | dict |
| `build_error` | 构建错误响应 | data, llm_data, other_data, **extra | dict |
| `build_warning` | 构建警告响应 | data, llm_data, other_data, **extra | dict |

---

## 三、Agent层（app/services/agent/ + app/services/chat/）

### 3.1 观察文本（observation_formatter.py）【v2.4更正：原登记为 agent_utils/message_utils.py 的 build_observation_text，实际定义于 observation_formatter.py】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_observation_text` | 构建观察文本 | execution_result, tool_name, tool_params | str |

### 3.2 步骤存储（storage.py）【v2.4更正：原登记为 app/services/agent/agent_utils/storage.py，实际定义于 app/services/chat/storage.py】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `allocate_and_insert_message` | 预分配 assistant 消息ID + 插入空白行(幂等) | conn, session_id | int(message_id) |
| `append_execution_step` | 逐步落库:一行=一步 | conn, message_id, session_id, step_index, step_dict | None |
| `load_execution_steps` | 从 steps 表组装步骤列表(无数据时从chat_messages.execution_steps列读取) | conn, message_id | Optional[list] |
| `finalize_message` | finally 轻量终态更新(content+status) | conn, message_id, content, status | None |

---

## 四、工具辅助层（app/tools/）

### 4.1 工具函数公共辅助（tool_fc_helper.py）【v2.4补登记：2026-06-22 小欧 从 toolhelper/ 目录迁移合并，原14个helper文件的纯逻辑函数集中于此】

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_check_module` | 检查Python模块是否已安装 | module_name | bool |
| `_check_module_available` | 检查模块可用性(带错误信息) | module_name | Tuple[bool, str] |
| `_check_python_available` | 检查Python可用 | 无 | bool |
| `_check_node_available` | 检查Node可用 | 无 | bool |
| `_decode_bytes_safe` | 安全解码bytes为str(utf-8/gbk/latin-1多编码回退) | data, encodings | str |
| `_serialize_rows` | DataFrame转list[list] | df | List[List[Any]] |
| `_load_dataframe` | 加载数据为DataFrame | source, **kwargs | DataFrame |
| `parse_datetime_any` | 智能解析任意日期时间值 | value | Optional[datetime] |
| `parse_datetime_string` | 解析日期时间字符串 | date_str | Optional[datetime] |
| `is_holiday` | 判断是否节假日(阳历+农历) | date_obj | Tuple[bool, Optional[str]] |
| `calc_next_n_workday` | 计算后N个工作日 | start_date, n | list |
| `get_holiday_date_by_name` | 按名称查节假日日期 | name, year | Optional[Dict] |
| `resolve_timezone` | 解析时区字符串 | tz_str | tzinfo |
| `_check_shell_injection` | 检测shell注入风险 | command | Optional[str] |
| `_read_stream_nonblocking` | 非阻塞读取流 | stream, encoding | str |
| `check_db_exists` | 检查数据库是否存在 | db_path | Dict |
| `validate_csv_content` | 校验CSV内容 | content, max_check_lines | Optional[str] |
| `validate_xml_content` | 校验XML内容 | content | Optional[str] |
| `validate_html_content` | 校验HTML内容(HTMLParser) | content | Optional[str] |
| `_detect_encoding` | 检测文件编码 | file_path | str |
| `_detect_encoding_simple` | 简易编码检测 | path, default | str |
| `_write_json` | 写JSON文件 | file_path, data, encoding, indent, ensure_ascii, create_parents | Dict |
| `_read_csv_basic` | 基础读CSV | file_path, encoding, delimiter, has_header, max_rows, skip_blank_lines | Dict |
| `_parse_yaml` | 解析YAML文件 | file_path, encoding | Any |
| `_write_yaml` | 写YAML文件 | file_path, data, encoding, indent | Dict |
| `write_yaml_ordered` | 保序写YAML(OrderedDict递归) | file_path, data, encoding, indent | Dict |
| `_parse_toml` | 解析TOML文件 | file_path, encoding | Any |
| `_write_toml` | 写TOML文件 | file_path, data, encoding | Dict |
| `_parse_ini` | 解析INI文件 | file_path, encoding | Dict |
| `_parse_xml` | 解析XML为dict | file_path, encoding | Dict |
| `_parse_properties` | 解析properties文件 | file_path, encoding | Dict |
| `backup_file` | 文件备份(.bak) | file_path, backup_dir, suffix | Dict |
| `_get_connection` | 获取数据库连接 | connection_type, connection_string, db_path, timeout | conn/engine |
| `_close_connection` | 关闭数据库连接 | conn, engine | None |
| `_strip_sql_comments_and_strings` | 去除SQL注释与字符串干扰 | sql | str |

> 迁移来源(docstring)：common_helper/exec_helper/data_helper/date_helper/shell_helper/db_helper/content_validation 各helper文件的纯逻辑函数 — 小欧 2026-06-22

### 4.2 工具辅助文件（app/tools/toolhelper/）【v2.4更正：原"三、工具层"登记16个文件，其中14个(common_helper/data_format_helper/data_helper/date_helper/db_helper/exec_helper/file_helpers/gui_helper/hash_helper/network_helper/service_helper/shell_helper/task_helper/window_helper)的纯逻辑函数已于2026-06-22迁移合并至 tool_fc_helper.py(见4.1)，原文件删除；当前目录仅剩以下2个】

| 文件 | 功能 |
|------|------|
| `line_pager.py` | 行分页/截断工具 `select_lines`(按 offset/limit/tail 选取行, 供 read_text_file/read_docx 复用, Tool 层零限制, 字符截断收口于 observation_formatter) — 小欧 2026-07-20 |
| `syntax_validator.py` | 语法护栏(多语言语法校验, 详见 七、语法护栏章节) — 小欧 2026-07-21 |

---

## 五、LLM核心层（app/services/llm_core/）

> `_normalize_tool_params` 已于 v1.5 迁至 `json_utils.py`（集中JSON解析函数）

---

## 六、使用示例

### 6.1 正确做法

```python
# 有公用函数，直接使用
from app.utils.json_utils import parse_json
from app.utils.time_utils import ensure_timestamp_milliseconds

result = parse_json(json_str)
timestamp = ensure_timestamp_milliseconds(ts_value)
```

### 6.2 错误做法

```python
# 错误：重复实现已有函数
def my_parse_json(json_str):
    try:
        return json.loads(json_str)
    except:
        return None  # 禁止！已有parse_json函数
```

---

## 七、语法护栏（app/tools/toolhelper/syntax_validator.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `validate_syntax` | 多语言(py/pyw/pyi/json/yaml/yml)语法校验；BOM去扰(BOM-002)+BUG-002；OCP注册表+unknown fail-open；异常不500(降级invalid) | content: str, language: str, file_path: Optional[str]=None | SyntaxCheckResult(valid/language/error/line/suggestion)；error_text() 组装对外字串 |
| `detect_language` | 探测语言(扩展名+_CODE_EXT, shebang回退, unknown fail-open) | file_path: str="", content: Optional[str]=None | str |
| `SyntaxCheckResult` | 校验结果dataclass | — | .valid/.language/.error/.line/.suggestion + error_text() |
| `VALIDATORS` | 语言→校验器 OCP 注册表 | — | dict |
| `_strip_bom` | 去除行首UTF-8 BOM(efbbbf) | content | str |

> 来源: 从 `file/edit_text_file.py` 内联 `compile()` 抽出为可复用模块；`file/write_text_file.py` 与 `tool_fc_helper.validate_python_content` 复用 — 小欧 2026-07-21 (83379fbb)。

---

## 八、Safety层（app/services/safety/）

### 8.1 路径安全（path_safe_check.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_existing_drives` | 动态获取当前存在的磁盘符号列表（不写死，遍历A-Z探测，应对U盘插拔/盘符重映射；R2磁盘根递归删除判定时刻使用） | 无 | List[Path] |
| `get_system_drive` | 动态获取真实系统盘符（SystemRoot/WINDIR环境变量→SystemDrive→探测存在\\Windows的盘符→兜底C:；系统目录判定C:模板动态替换） | 无 | str |
| `_get_project_root_safety` | 推算真实项目根（复制delete_file._get_project_root上移Safety层，恒非None，消除工具层反向依赖） | 无 | Path |
| `_is_forbidden_path` | 系统敏感路径黑名单（盘根splitdrive全盘符判定 + 系统目录FORBIDDEN_PATHS_WINDOWS_* C:模板动态盘符替换） | file_path: str | Tuple[bool, Optional[str]] |

### 8.2 delete 专属差异判定（delete_safety.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_as_bool` | 布尔强转（防LLM原始参数 'false'/'true' 字符串陷阱: bool('false')==True） | v: Any | bool |
| `check_delete_risk` | delete 差异判定（R3-R6），恒返回 SafetyResult（R3→_PASS 免确认，不用None表示放行）；R1/R2 由 _check_known_risks 覆盖不重复 | params: dict | SafetyResult |

> 消费链：tool_safety_checker.check_before_execute 对 delete 一次性计算 delete_risk，R6 入 _check_known_risks 无条件拦截，R3-R5 入 _get_needs_confirmation 确认分流 — 设计文档 v1.15

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v2.4 | 2026-08-05 12:13:13 | 全面修正登记错误：①删除僵尸条目(1.5工具函数/2.2工具结果 tool_result_utils.py 共7函数、message_utils 无定义的4函数) ②更正模块名(1.2 common.py→display_utils.py、3.1 build_observation_text→observation_formatter.py) ③更正路径(2.1 _response.py→app/tools/tool_response.py、3.2 storage→app/services/chat/storage.py) ④补登记 tool_fc_helper.py(4.1节,原toolhelper/14个helper文件纯逻辑函数2026-06-22迁移合并于此,共35函数)；toolhelper清单(4.2节)更正为当前实际2文件 ⑤修正章节编号(消除两个"三"、1.4表体归位、6.1/6.2子节号) ⑥版本历史顺序重排(倒序) | 小欧 |
| v2.3 | 2026-08-04 13:32:00 | 新增 七、Safety层章节：path_safe_check.py(get_existing_drives/get_system_drive/_get_project_root_safety/_is_forbidden_path动态盘符) + delete_safety.py(_as_bool/check_delete_risk R3-R6) | 小欧 |
| v2.2 | 2026-08-03 00:06:44 | 修正语法护栏落地路径为 app/tools/toolhelper/syntax_validator.py（fundamental 为误建）+API更名为 validate_syntax/detect_language/SyntaxCheckResult/VALIDATORS；从 git-blob-loss archive/_rewrite 实文件恢复 | 小沈 |
| v2.1 | 2026-07-21 | 新增 语法护栏 章节（app/tools/toolhelper/syntax_validator.py）: validate_syntax/detect_language/SyntaxCheckResult/VALIDATORS+_strip_bom（从edit_text_file抽出,BOM去扰+BUG-002+OCP+防500,复用write_text_file+tool_fc_helper） | 小欧 |
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
