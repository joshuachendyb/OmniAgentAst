# 公用函数清单

**创建时间**: 2026-05-29 07:50:00
**维护人**: 小沈
**最后更新时间**: 2026-08-19 05:35:10
**最近更新**: 2026-08-19 小欧 三堂会审复核: 删除已移除的 `create_step_counter` 过期登记条目及对应空章节(该函数已从工具注册表移除, 保留会误导复用, DRY/清单及时更新规范)

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
| `get_utc_timestamp` | 获取UTC时间戳ISO格式 | 无 | str |
| `convert_to_utc` | 转换为UTC ISO格式 | time_value | str |
| `ensure_timestamp_milliseconds` | 确保时间戳转为毫秒 | ts_value | int |
| `timestamp_for_filename` | 文件名时间戳 YYYYMMDD_HHMMSS | 无 | str |
| `now_str` | 当前时间格式化字符串，默认 YYYY-MM-DD HH:MM:SS | fmt | str |

### 1.2 通用函数（display_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `extract_display_name_from_steps` | 从步骤提取显示名称 | execution_steps_data | str或None |
| `build_display_name` | 构建显示名称 | provider, model | str |
| `extract_metadata_from_steps` | 从步骤提取元数据 | execution_steps | dict |
| `format_param_value` | 将参数默认值格式化为字符串（供LLM提示文本使用），None→""、bool→"true"/"false" | val | str |

### 1.3 JSON解析（json_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parse_json` | 解析JSON字符串 | json_str, label, raise_on_error | 解析结果或None |
| `coerce_json` | 若值为JSON字符串则解析为dict/list，否则原样返回 | value: Any | Any |
| `read_json_file` | 读取JSON文件 | file_path, label, raise_on_error | 解析结果或None |
| `_try_fix_incomplete_json` | 修复不完整/非标准JSON字符串(缺括号/单引号Python dict) | json_str: str | Optional[Dict] |
| `_normalize_tool_params` | 递归归一化tool params，修复LLM双倍编码字符串→还原为list/dict | params: Any | Any |

### 1.4 响应工具（response_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `api_success` | 统一成功响应 {"success":True, "message":xxx} | message, **extra | dict |
| `api_failure` | 统一失败响应 {"success":False, "message":xxx} | message, errors, **extra | dict |
| `api_error` | 记录日志并抛 HTTPException | status_code, detail, log_msg | None |
| `handle_api_errors` | 通用API异常处理装饰器 | operation_name | decorator |

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
| `dict_table_to_rows` | dict{headers,rows}转list[list] | dict_table | List[List[str]] |
| `normalize_table_data` | 归一化表格数据，支持list[list]/dict/list[dict]/None | table_data | Optional[List[List[str]]] |

### 1.7 文本处理（text_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `truncate_text` | 通用尾部截断,返回(截断后文本, 是否截断) | text, max_chars, suffix | tuple |
| `smart_truncate_text` | 智能截断(保留头尾省略中间) | content, budget, head_ratio | str |
| `add_line_numbers` | 添加行号前缀 | content, offset | str |
| `extract_tool_call_xml` | 从文本提取 `<tool_call>` XML 工具调用(非破坏性, reasoning/content中LLM降级旧格式时的恢复路径) | text | Optional[Dict[str, Any]] |
| `format_tool_call_markup` | 将LLM输出XML/JSON tool call标记格式化为纯文本(破坏性) | text | str |

### 1.8 ID生成（id_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `generate_operation_id` | 生成统一格式 op-{hex}, 全链路文件/任务操作 ID 同源(替代各处重复的 f"op-{uuid4().hex}") | 无 | str |

### 1.9 路径处理（path_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `to_win_long_path` | Windows长路径 `\\?\` 前缀绕过MAX_PATH(260)限制；仅NT生效，已带前缀或非绝对路径保持原样 | path: Path | str |

> 注：备份(operation_backup)与回收站维护(operation_maintenance)链路统一使用本函数，保证深嵌套备份能写入亦能清理。

### 1.10 文件处理（file_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `backup_file` | 文件备份(.bak) | file_path, backup_dir, suffix | Dict |
| `remove_readonly` | 去除文件只读属性(供删除/清理重试) | func, path, excinfo | None |

---

## 二、工具返回层（app/tools/）

### 2.1 工具返回构建（app/tools/tool_response.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_success` | 构建成功响应 | data, llm_data, other_data, **extra | dict |
| `build_error` | 构建错误响应 | data, llm_data, other_data, **extra | dict |
| `build_warning` | 构建警告响应 | data, llm_data, other_data, **extra | dict |

---

## 三、Agent层（app/services/agent/ + app/services/chat/）

### 3.1 观察文本（observation_formatter.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_observation_text` | 构建观察文本 | execution_result, tool_name, tool_params | str |

### 3.2 步骤存储（storage.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `allocate_and_insert_message` | 预分配 assistant 消息ID + 插入空白行(幂等) | conn, session_id | int(message_id) |
| `append_execution_step` | 逐步落库:一行=一步 | conn, message_id, session_id, step_index, step_dict | None |
| `load_execution_steps` | 从 steps 表组装步骤列表(无数据时从chat_messages.execution_steps列读取) | conn, message_id | Optional[list] |
| `finalize_message` | finally 轻量终态更新(content+status) | conn, message_id, content, status | None |

---

## 四、工具辅助层（app/tools/）

### 4.1 工具函数公共辅助（tool_fc_helper.py）

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
| `_get_connection` | 获取数据库连接 | connection_type, connection_string, db_path, timeout | conn/engine |
| `_close_connection` | 关闭数据库连接 | conn, engine | None |
| `_strip_sql_comments_and_strings` | 去除SQL注释与字符串干扰 | sql | str |

### 4.2 工具辅助文件（app/tools/toolhelper/）

| 文件 | 功能 |
|------|------|
| `line_pager.py` | 行分页/截断工具 `select_lines`(按 offset/limit/tail 选取行, 供 read_text_file/read_docx 复用, Tool 层零限制, 字符截断收口于 observation_formatter) |
| `syntax_validator.py` | 语法护栏(多语言语法校验, 详见 七、语法护栏章节) |
| `error_hints.py` | 工具结果解释层错误提示: `permission_error_hint`(写入权限不足) / `hint_for_write_error`(写入异常按 errno/类型精准提示) / `hint_for_read_error`(读取异常) / `sql_error_hint`(SQL异常, 覆盖 no column/table/UNIQUE/多语句/语法等) / `hint_for_data_error`(数据处理异常, 含 pandas/sqlite3 分支) |

### 4.3 基础工具（app/tools/fundamental/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `safe_read_file` | 安全读取文件内容(utf-8, errors=replace), OSError 返回空串 | path: str | str |

> 定义于 `app/tools/fundamental/shell_engine.py`；被 `execute_shell_command.py` 跨模块复用读 stdout/stderr 结果，且被 PersistentShell 会话池复用读 stderr 残留

---

## 五、LLM核心层（app/llm/）

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
| `validate_syntax` | 多语言(py/pyw/pyi/json/yaml/yml)语法校验；BOM去扰；OCP注册表+unknown fail-open；异常不500(降级invalid) | content: str, language: str, file_path: Optional[str]=None | SyntaxCheckResult(valid/language/error/line/suggestion)；error_text() 组装对外字串 |
| `detect_language` | 探测语言(扩展名+_CODE_EXT, shebang回退, unknown fail-open) | file_path: str="", content: Optional[str]=None | str |
| `SyntaxCheckResult` | 校验结果dataclass | — | .valid/.language/.error/.line/.suggestion + error_text() |
| `VALIDATORS` | 语言→校验器 OCP 注册表 | — | dict |
| `_strip_bom` | 去除行首UTF-8 BOM(efbbbf) | content | str |

---

## 八、Safety层（app/safety/ + app/tools/security/）

### 8.1 路径安全（path_safe_check.py，位于 app/tools/security/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_existing_drives` | 动态获取当前存在的磁盘符号列表（不写死，遍历A-Z探测，应对U盘插拔/盘符重映射；磁盘根递归删除判定时刻使用） | 无 | List[Path] |
| `get_system_drive` | 动态获取真实系统盘符（SystemRoot/WINDIR环境变量→SystemDrive→探测存在\\Windows的盘符→兜底C:；系统目录判定C:模板动态替换） | 无 | str |
| `_get_project_root_safety` | 获取项目根供Safety层判定（统一走 config.get_project_root() 配置优先、未配置→用户主目录；不再以代码位置推算） | 无 | Path |
| `_is_forbidden_path` | 系统敏感路径黑名单（盘根splitdrive全盘符判定 + 系统目录FORBIDDEN_PATHS_WINDOWS_* C:模板动态盘符替换 + **代码库根禁区**：代码库根及其子路径一律forbidden，tool禁区开关无关硬拦截） | file_path: str | Tuple[Optional[str], Optional[str]] |
| `validate_tool_path` | 工具路径校验统一入口（分类→找路径参数→调validate_path；补dest参数 + 遍历所有命中路径参数逐一校验，任一越权即拒；**逻辑路径参数解析**：download.dest相对下载目录/rename.dest纯文件名先解析为真实路径再校验） | tool_name, params | Tuple[bool, Optional[str], Optional[str]]（is_valid, msg, failed_path；failed_path=首个校验失败的真实路径，供临时授权auth_path用，成功时None） |
| `get_default_allowed_paths` | 默认白名单（主目录+`/tmp`+`/var/tmp`+项目根+授权目录；废除「所有现存盘符」全盘放开，lazy动态计算） | 无 | List[Path] |

### 8.2 delete 专属差异判定（delete_safety.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_as_bool` | 布尔强转（防LLM原始参数 'false'/'true' 字符串陷阱: bool('false')==True） | v: Any | bool |
| `check_delete_risk` | delete 差异判定，恒返回 SafetyResult（PASS 免确认，不用None表示放行）；已知风险由 _check_known_risks 覆盖不重复；**多授权域**（项目根+授权目录），授权目录内递归不再误拦 | params: dict | SafetyResult |
| `_get_allowed_roots` | 删除判定允许根列表 = [项目根] + 授权目录 | 无 | list |
| `_is_inside_any` | 目标是否位于任一允许根内（含根自身与子级） | p: Path, roots: list | bool |

> 消费链：tool_safety_checker.check_before_execute 对 delete 一次性计算 delete_risk，危险项入 _check_known_risks 无条件拦截，其余入 _get_needs_confirmation 确认分流

### 8.3 白名单外临时授权（temp_auth.py，位于 app/tools/security/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `grant_temp_auth` | 临时授权某路径（一次一申请、支持递归、per-request ContextVar隔离） | root: str, recursive: bool | None |
| `clear_temp_auth` | 清空当前作用域临时授权 | 无 | None |
| `is_temp_authorized` | 检查路径是否在临时授权范围内（含子目录树） | file_path: str | bool |
| `get_authorized` | 获取当前作用域授权映射 | 无 | Dict[Path, bool] |

> 消费链：tool_safety_checker._check_known_risks 检测到白名单外路径(非禁区) → SafetyResult(requires_confirmation+auth_path，auth_path=failed_path 真正越权参数, 非固定path-or-dest) → action_handler 确认后 grant_temp_auth → validate_path 放行本次；**react_cycle.run_react_cycle task结束 finally 调 clear_temp_auth() 清除(task级清零点)**；禁区(代码库根/系统目录)不受临时授权影响永久封锁

---

## 版本历史

| version | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v3.5 | 2026-08-14 09:02:09 | 正文清除历史痕迹(小欧, 用户要求): 删除正文全部"迁/更正/误登记/来源/已迁"等历史过程说明、BUG编号(BOM-002/BUG-002/BUG-B/C/D)、设计编号(补A/R1/R2/R3-R6/⑦⑧⑨⑪⑫⑯)、署名时间戳(仅版本历史表保留历史信息)；正文只保留当前真实情况 | 小欧 |
| v3.4 | 2026-08-14 08:53:31 | 三遍全文核查修正(小欧): ①1.1 删除不存在的 get_timestamp_ms(全仓无定义) ②create_step_counter 从 1.1 移至 3.3 Agent 层(实际定义于 agent/steps/base.py:84) ③第八章标题 app/services/safety/→app/safety/(safety 为顶层目录) ④⑤8.1 path_safe_check/8.3 temp_auth 标注实际位置 app/tools/security/(A1 2026-08-12 迁入) ⑥4.1 backup_file 注明已迁 app/utils/file_utils.py(P5b re-export) | 小欧 |
| v2.9 | 2026-08-13 | A5职责拆分同步(小欧): 4.2 补登记 `error_hints.py`(5个错误提示函数自 file_path_checker 迁移: permission/error_hint_for_write/read/sql/data, 供 dataanalysis/document/file/network 复用) | 小欧 |
| v2.8 | 2026-08-11 | 三堂会审复核文档同步(小欧): 8.1 `_is_forbidden_path` 返回值更正为 `Tuple[Optional[str], Optional[str]]`(原误写Tuple[bool, Optional[str]]); 8.3 `clear_temp_auth` 清零点更新为 react_cycle task级 finally(R1, 原action_handler工具批finally已迁移H1) | 小欧 |
| v2.7 | 2026-08-10 | ⑦⑯ 2026-08-10 bug复核修复同步(小欧): `validate_tool_path` 返回扩展三元组+新增 `_resolve_path_param`(BUG-B/C: download/rename 逻辑路径参数解析); `_check_known_risks` auth_path 改 failed_path(BUG-D); action_handler 工具批后 finally clear_temp_auth(BUG-E, 补A落地) | 小欧 |
| v2.6 | 2026-08-10 00:55:00 | ①2026-08-10 项目根目录混乱修复同步(小欧): 七章更新 `_get_project_root_safety`(⑤收敛走config)/`_is_forbidden_path`(⑦代码库禁区)/`validate_tool_path`(⑧⑨补dest+多参数全量校验)/`get_default_allowed_paths`(⑪白名单收紧); 8.2 delete_safety ⑫多授权域(_get_allowed_roots/_is_inside_any); 新增8.3 temp_auth.py临时授权(⑮) ②config.py命名分离(_get_project_root→_get_code_root, get_default_project_root→get_code_root, ①兜底改Path.home, ⑩get_allowed_dirs新增) ③delete_file ⑥删复刻+多授权根保护 | 小欧 |
| v2.5 | 2026-08-06 13:36:57 | 补登记 4.3 基础工具(app/tools/fundamental/) safe_read_file（安全读取文件, utf-8 errors=replace, OSError→""；定义于 shell_engine.py，跨模块复用于 execute_shell_command.py，会话池设计 H5 复用读 stderr 残留） | 小欧 |
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
