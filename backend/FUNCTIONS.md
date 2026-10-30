# 公用函数清单

**创建时间**: 2026-05-29 07:50:00
**维护人**: 小沈
**最后更新时间**: 2026-10-30 21:12:41
**最近更新**: 2026-10-30 21:12:41 小欧 §3.8 `report_refs` 口径修正: `paths=` 路径与行区间一律完整不截断(删原 60 字符右截断, 避免同文件整份/片段截后变成同一串), 行长度只由 5 条上限+"另N条"控制

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
| `format_llm_data_text` | 将工具结果 llm_data 格式化为前端展示文本（JSON美化，失败回退str）；2026-08-25 小欧 从 action_handler 内嵌闭包拆出至全局层（纯函数，零改动） | llm_data | str |
| `is_blank_secret` | 判定密钥/敏感值是否"未配置"（None/空串/纯空白/非字符串均算未配置）。[72]第二章「key 空白即失败」一致语义的唯一权威，`lifecycle/validation.py` 与 `model/resolver.py` 两处复用（DRY，避免第三份不一致写法）；2026-09-26 小欧 新建于 secret_utils.py | value: Any | bool |
| `redact_sensitive_params` | 敏感参数脱敏（系统级唯一出口）：`SENSITIVE_PARAM_KEYS`（password/token/api_key/secret/authorization/credential/connection_string）中的键值统一替换为 `***`，其余原样；非 dict/无敏感键零拷贝原样返回。`handle_action`（日志/预览 SSE/canonical 落库）、`tool_runner`（工具结果日志）、`hitl_gateway._desensitize`（确认弹窗）复用；`tool_constants.SENSITIVE_FIELDS` 派生自同源 `SENSITIVE_PARAM_KEYS`；2026-10-19 小欧 新建于 secret_utils.py（取代 redact_params_for_log） | params: Any | Any |
| `SENSITIVE_PARAM_KEYS` | 敏感参数键的全局权威集合（含 `connection_string`）；供 `redact_sensitive_params` 与 `tool_constants.SENSITIVE_FIELDS`（派生、排除 connection_string）共用，杜绝敏感键集合多处维护漂移；2026-10-19 小欧 定义于 secret_utils.py | — | frozenset |

### 1.2.1 窗口句柄操作（desktop/window_ops.py）

| 函数 | 说明 | 入参 | 返回 |
| --- | --- | --- | --- |
| `is_zoomed` | 窗口是否最大化；**不用 `win32gui.IsZoomed`**（当前 pywin32 build 无该属性，实测 `hasattr=False`，调用即 AttributeError），改判 `GetWindowPlacement` 的 showCmd 是否 `SW_SHOWMAXIMIZED`。`set_window_state` 与 `window_resize` 共用此单源；2026-10-19 小欧 新建于 window_ops.py | hwnd: int | bool |
| `focus_window` | 窗口切前台；Windows 前台锁下裸调 `SetForegroundWindow` 必被系统拒，故按 Alt 解锁 → `ShowWindow(SW_RESTORE)` → `BringWindowToTop`+`SetActiveWindow` → `SetForegroundWindow` 逐级尝试，并以 `GetForegroundWindow()` 实测是否真切换（**返回值不可靠**，不返 BOOL/返 0）；最多 3 轮 × 0.2s。`AttachThreadInput` 经实测排除（不返 BOOL 无法判成败，且目标与前台常同线程致系统拒 error 5）；2026-10-19 小欧 新建于 window_ops.py | hwnd: int, attempts: int = 3, interval: float = 0.2 | bool |

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
| `dependency_status` | **纯检查**依赖是否可用，零 subprocess（不装任何东西） | import_name, pip_package, version | bool |
| `install_missing` | **唯一装包入口**：纯检查→一次 pip 装全部缺失→复检，返回仍缺的 | Iterable[(imp,pkg,ver,pre)] | list[tuple] |
| `resolve_missing` | 从归一依赖元组里筛出不可用的（纯检查） | Iterable[tuple] | list[tuple] |
| `normalize_dep` | str/dict 两种依赖声明归一为 (import_name, pip_package, version, pre_install) | str \| dict | tuple |
| `dep_install_spec` | 依赖的可读 pip 规格串（供日志与缺库提示指名该装什么） | imp, pkg, version | str |
| `install_batch` | 一次 pip 调用装多个包 | Iterable[str] | None |
| `locked_conflict` | 该安装请求是否会顶掉锁定包 | pkg, version | bool |

**实现要点**

- `dependency_status` 与安装必须分开：`ensure_dependency` 早期把"检查+安装"混在一处，导致批量预装空转（判缺失那一步自己就把包单装掉，N 个依赖仍起 N 次 pip）。要批量化必须先有只看不装的判定源。
- `normalize_dep` 存在的原因：`import_name` 与 `pip_package` 不可混用 —— pip 名 `python-docx` 不可 `import`，import 名 `docx` 装不上，混用必判缺库。
- 锁定包（`LOCKED_PACKAGES`：httpx/httpcore）由 `_constraints_file()` 生成 pip 约束文件，随每次装包以 `-c` 带上：装任意新包时其传递依赖若想抬升锁定版本，pip 直接判冲突而非静默换版本。
- `install_missing` 是启动期预装与运行期自愈的共同入口（DRY）：两处各写一遍判定逻辑正是假修复的温床。

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
| `normalize_blank_lines` | 空行规约(13.11): 连续空行(含整行空格/制表)折叠为一个空行, 段首尾trim, 幂等; 落库收口入口(与前端 normalizeBlankLines 同一张规则表) | text | str |

### 1.8 类型转换（type_utils.py）

> 无依赖叶子模块（刻意不 import 项目内模块，否则 app.config 无法复用 → 循环导入）。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `to_int_or` | 配置值转 int；None/非数字回落默认值，**0 视为合法值不吞** | value, default | int |

### 1.9 ID生成（id_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `generate_operation_id` | 生成统一格式 op-{hex}, 全链路文件/任务操作 ID 同源(替代各处重复的 f"op-{uuid4().hex}") | 无 | str |

### 1.10 路径处理（path_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `to_win_long_path` | Windows长路径 `\\?\` 前缀绕过MAX_PATH(260)限制；仅NT生效，已带前缀或非绝对路径保持原样 | path: Path | str |
| `path_has_reserved_char` | 文件名(basename)含 Windows 保留字符则返回该字符，否则 None；纯拼写零IO | basename: str | Optional[str] |
| `path_has_reserved_name` | 路径任一分段是 Windows 保留名则返回该分段，否则 None；纯拼写零IO | file_path: str | Optional[str] |
| `path_has_extra_drive` | 路径尾部含多余盘符则返回原因，否则 None；纯拼写零IO | file_path: str | Optional[str] |
| `validate_str_param` | 字符串参数基础校验（非路径通用参数用；路径非空由 SA1 覆盖）；None/非str/空串返回错误信息 | value: Any, param_name: str | Optional[str] |
| `get_output_dir` | 输出目录(project_root/output)，generate_chart/download 默认输出基准 | 无 | str |

> 注：备份(operation_backup)与回收站维护(operation_maintenance)链路统一使用本函数，保证深嵌套备份能写入亦能清理。

### 1.11 文件处理（file_utils.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `backup_file` | 文件备份(.bak) | file_path, backup_dir, suffix | Dict |
| `remove_readonly` | 去除文件只读属性(供删除/清理重试) | func, path, excinfo | None |

### 1.12 白名单语法（allowlist.py，位于 app/utils/）

免口令 IP 白名单的语法单一权威。写侧（settings_service 落盘前校验+归一）与读侧（deps 准入匹配）共用，规则无法各写一套而漂移。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `normalize` | 任意来源形态→干净条目列表（拆 , ; 换行及全角、去空白、去空项），落盘恒为 list | raw: str \| list \| None | List[str] |
| `invalid_entries` | 返回非法 IP/网段原文，供落盘前报错（全部合法则空列表） | raw: str \| list \| None | List[str] |
| `matches` | 来源 IP 是否命中白名单（支持单 IP 与 CIDR）；fail-closed：IP 非法/白名单空/条目非法均不命中 | ip: str, raw: str \| list \| None | bool |

### 1.13 控制台镜像（app/logger/console_writer.py）
| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `console_put` | 控制台镜像写(非阻塞): 全局 queue+daemon写线程, stdout阻塞时队列满则丢弃新消息, 绝不阻塞调用线程; log_and_print(logger/__init__.py)及裸print收口点(action_handler/main/config)统一出口 | msg: str | None |

### 1.14 shell 命令静态守卫（shell_static_guard.py，位于 app/tools/fundamental/）

shell 命令执行前的**静态风险判定**单一权威。三类同域关注点合居一处（同属「这条 shell 命令静态看起来有什么风险」）：**只读白名单**（可否免预检直放）、**命令规范化**（拼接折叠，供前两者前置）、**杀进程防护**（不可隔离动词 + 受保护进程）。常量 `READONLY_PREFIXES` / `FAST_CHANNEL_FORBIDDEN` / `UNCONTAINABLE_VERBS` 同在此模块。

> **2026-10-10 小欧 位置与命名更正（北京老陈指出"代码名称确实要名副其实"）**：本节函数原在 `app/utils/shell_readonly.py`。原落点理由是"架构边界要求 tools 禁 import safety"，但 `tests/test_architecture_boundaries.py` 的强制规则为 `"tools": {"app.services", "app.safety"}` —— **只单向禁止，`safety → tools` 合法**（先例：`tool_safety_checker` 一直 import `execute_shell_command_safety`），故无需中转 utils。同日曾按 SRP 拆为三个文件，复核后判定属**过度拆分**（`normalize_for_intent` 只服务杀进程判定、非独立可复用能力，单独成文件违反 YAGNI），遂并回一处。按 AGENTS.md 1.4「能复制就复制，不重写」逐行合并未改业务逻辑，仅调整文件位置与导入路径。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `is_readonly_whitelisted` | 只读白名单快速通道判定：前缀命中且无管道/分号/重定向符（须在写意图扫描之后调用的定序约束见函数 docstring） | command: str | bool |
| `normalize_for_intent` | 折叠字符串拼接（循环至不动点，`'a'+'b'+'c'` 三段拼接单趟必漏）后去引号，使 `'Stop'+'-Process'` 还原为 `Stop-Process`；2026-10-10 猎杀补 `[char]N` 解码 + `()[]{}` 噪音剥离（顺序解码→剥噪音→折叠→去引号）。**只服务"检测"不服务"执行"**：归一只可能让词更易命中、不会让已命中的词消失，故只增不减（取严）。根因：字面量被 `+` 拆开时词表查不到连续动词 → 判定放行 → 预检在宿主真跑 → 后端自杀（审计 P1-1） | command: str | str |
| `has_uncontainable_intent` | 不可隔离动词判定：杀进程（Stop-Process 任意形态 / taskkill / wmic process / pkill / killall / kill）与停服务（Stop-Service / Restart-Service）；大小写不敏感，只认完整独立动词；取原文与归一文并集；2026-10-10 猎杀补 `.Terminate()`/`.Kill()` 方法调用（只认调用点，不认裸词）、`Invoke-CimMethod`、`-EncodedCommand`/`-enc`（内容不可见，转 HITL 为残留风险）。根因：shell 沙箱预检会在宿主**真跑一遍**命令，而 Job Object 非硬墙拦不住子进程杀别的进程 —— 词表漏判则预检即真跑，E2E P9-03 实录后端被 agent 的 `Get-Process python \| Stop-Process -Force` 杀掉。命中即须转 HITL，**不得进入预检 run** | command: str | bool |
| `extract_kill_target_pids` | 提取命令显式指定的杀进程目标 PID：覆盖 `Stop-Process -Id a,b` / `taskkill /PID n` / `kill [-9] n` 三形态；2026-10-10 猎杀补 `taskkill /FI "PID eq N"`；按名与 pkill 形态目标由名字决定、静态枚举不了，返回空集 | command: str | set[int] |
| `is_process_kill_protected` | 命令目标是否命中受保护进程（后端自身/父进程/shell 池），命中即 blocked。**PID + 名字双口径**：2026-10-10 审计 P1-3 补按名匹配（`-Name` / 管道 / `/IM` / `killall` 四形态），修掉原只抽显式 PID 时对事故原形恒返空集的盲区；2026-10-10 猎杀补引号名（同步扫归一文）、`/FI IMAGENAME`、WMI `where`/`Name=`、pkill 实参（含 `-f` 模式串，fnmatch 双向匹配）；名字归一化（去 `.exe` + casefold + fnmatch 通配）在内。**无目标兜底**：有杀意但抽不出任何目标（管线裸杀/无参 taskkill/wmic 质量动作/方法杀无名/`kill %1` 之类）直接 blocked（停服务动词、`/?`/`--help`/`-WhatIf`、wmic 裸查询、引号内纯提及不在此列）。`protected_pids`/`protected_names` 均由调用方注入（组装归 safety 侧，见 8.4） | command: str, protected_pids: set, protected_names: set = None | bool |

> 曾用条目 **1.15 shell 杀进程/停服务防护**、**1.17 shell 命令规范化** —— 2026-10-10 已随位置更正并入本节，历史见版本历史 v5.0/v5.1。

### 1.16 异步流收尾（astream.py，位于 app/utils/）

异步生成器上抛收尾的统一入口（2026-10-07 新增）。上游流在提前退出（取消/异常/break）时若不关闭会残留连接与协程；本函数做能力探测式关闭，兼容无 `aclose()` 的测试 mock。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `aclose_stream` | 安全关闭异步流：存在 `aclose()` 则 await 并吞掉收尾期异常（收尾失败不应掩盖主流程异常），无则退化为 `close()`；供 `llm_call.py` / `base_service.py` 的 finally 复用 | stream: Any | None |

---

## 二、工具返回层（app/tools/）

### 2.1 工具返回构建（app/tools/tool_response.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `build_success` | 构建成功响应 | data, llm_data, other_data, **extra | dict |
| `build_error` | 构建错误响应 | data, llm_data, other_data, **extra | dict |
| `build_warning` | 构建警告响应 | data, llm_data, other_data, **extra | dict |
| `build_missing_dep_error` | 缺库统一错误体（`ERR_MISSING_DEPENDENCY`）。文案分三级：系统自动装失败 → LLM 用 `bash` 自装 → 转管理员；锁定依赖（httpx/httpcore）不给自装指示，直指按锁定版本由管理员装；收尾统一给"改用其他工具继续任务"的出路，**不终止 ReAct loop**。错误码落 `llm_data.status.code`，随全项目错误体约定 | tool_name: str, missing: list = None, agent_can_install: bool = None | dict |

---

## 二·五、工具注册层（app/tools/registry.py）

### 2.2 工具注册与依赖可见性（app/tools/registry.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `preinstall_tool_dependencies` | 启动期批量装依赖（经 `install_missing` 一次 pip 装齐），返回仍未就位的规格串 | 无 | list[str] |
| `heal_missing_deps` | 运行期缺库自愈：**只装包、返回仍缺清单，不改元数据**（经 `to_thread` 在工作线程执行，改元数据会读到中间态） | name: str | list[str] |
| `apply_heal_result` | 把自愈结果写进元数据（须在主线程调用），返回是否恢复可用 | name: str, missing: list | bool |
| `ToolMetadata.visible_to_llm` | 属性。"该不该给 LLM 看"的**唯一判据** = `expose_to_llm and available`。原先各消费方各写双判断，加维度需同步改多处，漏一处即口径分裂 | — | bool |

**实现要点**

- 依赖检查结论必须落元数据（`available`/`missing_deps`）：原先 `_check_dependencies` 算完即弃，缺库工具照样进 LLM 工具列表，LLM 试调一次才知不可用、白耗一轮。
- 缺库工具在三个暴露点都要挡住：`to_openai_tools`、`generate_param_reminder`、`tool_search` 的 BM25 索引（后者漏了会出现"搜到 1 个却注入 0 类"的误导）。
- `heal_missing_deps` 与 `apply_heal_result` 必须拆开：前者经 `to_thread` 跑在工作线程，与事件循环并发读同一份 meta，跨线程写会读到 `available` 已翻而 `missing_deps` 未写的中间态。
- 运行期自愈需加冷却窗（如 `_HEAL_COOLDOWN_SEC`）：装不上时每次工具调用都重试 = 每次都起一个 pip。

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
| `append_execution_step` | 运行期逐步落库:一行=一步(task_id 缺失即抛, fail-loud; ON CONFLICT DO NOTHING 幂等) | conn, ai_message_id, session_id, step_index, step_dict, task_id, usage, user_message_id | None |
| `load_execution_steps` | 从 chat_task_steps 表组装步骤列表(v2.0 起不再回退读 chat_messages.execution_steps, 未命中返回[]; thought 经 `_strip_thought_content` 收口) | conn, ai_message_id, task_id | Optional[list] |
| `_strip_thought_content` | thought 步骤出参收口:剥 content, 只留 thought/reasoning(`load_execution_steps` 与 `load_steps_by_task` 共用, 两入口形状一致) | steps(list) | list |
| `finalize_message` | finally 轻量终态更新(content+status) | conn, message_id, content, status | None |
| `query_task_accumulation` | 读取任务级 token 累计(JSON, 缺行/缺键归一3键零值) | conn, task_id | dict |
| `query_session_accumulation` | 读取会话级 token 累计(JSON, 缺行/缺键归一) | conn, session_id | dict |
| `update_task_accumulation` | 任务级 token 实时累计(Db读-加-写, 影响0行显式告警) | conn, task_id, llm_call_count_token | None |
| `update_session_accumulation` | 会话级 token 实时累计(Db读-加-写, 影响0行显式告警) | conn, session_id, llm_call_count_token | None |
| `query_chain_accumulation` | 上下文链 token 累计(按context_root聚合, 排除当前任务, 计算派生不落库) | conn, context_root_task_id, current_task_id | dict |
| `fetch_session_user_message_pairs` | 重建"用户消息+其配对AI回答"有序列表(北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 从 chat_user_message LEFT JOIN chat_tasks 读取; 每项为一条用户消息及可选配对的AI回答, ai_message_id=None表示AI未生成; 供 get_session_messages/_load_previous_messages/execution_stream 复用, DRY/复用优先; 不含 execution steps, 步骤经 load_execution_steps 另行读取; 2026-09-28 [76] 精确归属: JOIN 改 COALESCE(子查询 task_id=cum.task_id, 子查询 user_message_id=cum.id) 取 MAX(id), 注入行凭 cum.task_id 归任务、登记首条凭 cum.id 归任务, 删会话级模糊兜底防跨任务错配; 增返回 pair_task_id 供渲染层同任务判据) | conn, session_id, lower_id, upper_id | list |
| `reconcile_orphaned_tasks` | 启动期僵尸任务收尾(2026-09-29 L0 新增, 零 DDL 零新状态值; 启动时把崩溃遗留的 status='executing' 残行改 failed + error_type=task_interrupted; 按 start_time<boot_iso 判归属以降低多 worker 误伤; 幂等, duration 不补算) | conn, boot_iso | int(受影响行数) |
| `get_chain_summary_anchor` | linked 增量摘要锚点(2026-10-14 小欧新增): 取同链最近一条 task_summary 非空任务行(task_id/summary/uid+增量下界), 无则 None 走老路 | conn, context_root_task_id, current_task_id | dict 或 None |
| `save_chain_cover_summary` | linked 增量摘要写回单一出口(2026-10-14 小欧新增): 摘要写链内上一个任务行(下次锚点); 空摘要/无覆盖行/影响行≠1 返 None 仅告警 | conn, context_root_task_id, current_task_id, summary | task_id 或 None |

### 3.2.1 事件 Journal（stream_event_journal.py，P3 新增 — [63] 3.6.3）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `append` | 单事件落库 chat_stream_events（基线形态；合批挂载点见 [63] 3.5.2，帧 1:1、seq 逐帧） | task_id, session_id, seq, event_type, payload | None |
| `read_after` | 回放读取 seq >= after_seq，同事务附终态存在性与归属 session_id；**列 seq 为 DB 权威序号**，payload 原样返回由调用方做类型闸门 | task_id, after_seq, limit=PAGE_SIZE(500) | (list[tuple[列seq, payload]], bool has_terminal, Optional[str] owner_session_id) |
| `is_producer_alive` | producer 存活判定：最近事件在 window 内写入即视为活着(3.7 第5步"后端已重启"前提校正, 零 DDL 判据)；**未来时间戳不判活**(时钟回拨/脏数据，容差 5s)，否则死任务永不收敛 | task_id, window_seconds=60 | bool |
| `get_persisted_task_status` | 终态权威 chat_tasks.status 唯一读取口（读 DB 持久行；与 task_state 的 get_running_task_status 读内存活跃表语义正交，严禁同名） | task_id | Optional[str] |
| `retention_cleanup` | 清理已终态且超保留期的事件；活跃/非终态永不删，end_time 缺失的终态按 created_at 双倍保留期兜底 | retention_days | int(清理 task 数) |

### 3.3 沙箱执行闸门（handlers/sandbox_gate.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `sandbox_precheck` | destructive级沙箱预检; 返回None=无需预检(safe级直通)/异常兜底(M4)也返回None直通 | safety_result, tool_name, params | Optional[PreCheckResult] |
| `sandbox_resolve` | 预检结果处置: 危险型失败→denied登记+error步骤; 未完成有效验证→复用HITL原语请用户裁决; 杜绝LLM原样重发死循环 | agent, step, call, tool_name, params, pre, safety_result, denied_list | Tuple[bool, list] |

> 落点说明(2026-08-25 小欧 合规重构): 原逻辑在 action_handler 内以嵌套闭包实现, 违反 1.3 公用函数规范(分层/先查后建/登记) 与 KISS-DIRECT(隐式捕获约10个外层变量); 现拆为 Agent 编排层模块级函数(依赖方向 handler→sandbox 单向, 无环), 逻辑零改动(复制不重写)。

### 3.4 服务模型配置解析（app/services/lifecycle/service.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parse_model_params` | 解析 provider 配置的 model_params → (extra_body_params, context_limit)；DRY 唯一权威(create_service_instance 与 stream_orchestrator L2 快照同用)；context_limit 配置优先否则 DEFAULT_CONTEXT_LIMIT 兜底，余量作 extra_body_params(无则 None) | provider_config: dict, model: str | Tuple[Optional[dict], int] |

> 落点说明(2026-09-01 小欧 复用优先/DRY 归一): 原逻辑双份嵌在 create_service_instance(service.py) 与 stream_orchestrator(L2 跨 provider 快照), 归一为本函数唯一权威, 消除双份漂移; 行为与历史一致(仅去重, 不改逻辑)。

### 3.5 上下文压缩（services/agent/compaction/）

C4 锚定摘要与 C3 剪枝的公用原语（2026-10-08 摘要前降本接线时新增/修正）。降本原则：工具输出原文只对最近几轮有价值，故保尾区保留、更早的清零。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `prune_tool_output_keeping_tail` | 摘要降本策略（已接入 `start_step._compact_injected_history`）：保尾区 tool 结果原样保留，只清零更早的。边界由调用方给（`split_turn.find_tail_start` 按保尾预算算），故本模块不 import split_turn（零新依赖、职责不混）；不改入参，越界下标由切片语义兜住 | messages: List[Dict], tail_start: int | (新列表, 释放 token 估算) |
| `fc_atomic_units` | 把 assistant(tool_calls) 与其 tool 结果编成 FC 原子单元（整组取舍，永不拆散）。**唯一真源**：`fc_message_types.fc_atomic_units`（2026-10-20 小欧 由 compaction/prune 私有实现迁至协议层——prune 顶层 import message_builder，反向导入必成环；迁中立层后 message_builder 裁剪与 prune 价值保留共用一份）。调用方须按组整体取舍、组内升序展开，保证 assistant 恒在 tool 之前 | messages: List[Dict] | List[List[int]] |
| `_msg_cost` | 单条消息的预算占用 token，复用 `MessageBuilder._estimate_tokens` 同一真源（原 `len(content)/CHARS_PER_TOKEN` 自算漏算 tool_calls 结构开销，实测决策消息 0 vs 41，致 budget 约束不准） | msg: Dict | int |
| `_valid_summary_or_empty` | C4 摘要结构校验（单函数，两摘要函数共用）：空响应/长度下限/六段齐全/拒绝开头/压缩比，任一不过返空串走零退化；阈值优先读 `tuning.compaction.summary_min_chars`（缺省 200） | text: str, src_len: int = 0 | str（有效原文/空串） |
| `estimate_tokens` | **chars→token 估算唯一实现**（`services/agent/token_estimate.py`，与系数真源 `compaction_constants.CHARS_PER_TOKEN` 同域）：`int(len(str(content))/CHARS_PER_TOKEN)`。2026-10-30 收口 `prune._released_tokens` 与 `refs.budget._tokens_of` 两份同款单行（DRY）；口径只算文本，不算消息列表的 tool_calls 结构开销（那属 `MessageBuilder._estimate_tokens`） | content: Any（None/空 → 0） | int |

> 落点说明(2026-10-08 小欧): 真实 205 条实测，未降本 feed 135362 tok；本策略降至 86472 tok（省 36%）且摘要保住可核对的具体数字/签名/时间戳（纯全清零版 83673 tok 但摘要仅 1521 字符且失掉证据）。开关见 `compaction_constants.SUMMARY_PRUNE_TOOL_OUTPUT`，置 False 即刻回退全量喂。
> 2026-10-20 小欧: `fc_atomic_units` 唯一真源已迁至 `services/agent/fc_message_types.py`（协议层，零依赖），本模块 `keep_valuable_messages` 与 `message_builder` 裁剪复用；本表保留于 3.5 节以示与降本链路的关系。

### 3.6 会话使用目录（`services/chat/workspace_service.py`）

**会话使用的目录**（本次任务产物落在这里）的存储与落值（2026-10-10 新增，2026-10-10 概念订正重写）。⚠ **授权目录不在本模块** —— 授权目录归全局配置管（`workspace.allowed_dirs` / `project_root`）。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `ws_prop_value` | **属性归一化唯一源（入库值）**：None/空→read_write；中文标签→机器值；自定义原样保留。纯文字标签不做权限判定 | raw | str |
| `ws_prop_label` | **属性展示/注入唯一源**：机器值→中文标签；自定义原样；缺失→读写工作区 | raw | str |
| `_normalize_ws_meta` | **属性/备注归一化唯一源**：trim→空归默认→超长截断→memo换行转空格。非法值放行不拒单 | prop, memo | tuple[str, Optional[str]] |
| `get_session_workspaces` | 读该会话使用的目录行（含属性/备注/默认标志，`ORDER BY rowid`） | conn, session_id | list[Row] |
| `_normalize_ws_path` | **归一化唯一源**：空串/非绝对/超长硬拒 → resolve + 去尾分隔符，**保大小写入库**。⚠ 空串必须硬拒；仍可能抛 OSError/ValueError，调用方必须捕获 | p: str | str |
| `_ws_deny_reason` | 会话目录**合法性判据**：`_is_forbidden_path` **串联** `validate_path(mode="write")` 的 `category=="system"` + 宽根规则 | p: str | Optional[str] |
| `_is_broad_root` | 宽根判据：家目录本身及其上级禁；家目录**之内**不拦。**fail-closed**：解析异常按宽根拒绝 + 告警 | p: str | bool |
| `_ws_precheck` | 逐条走合法性判据，返回被拒清单（不抛异常，调用方整单 422） | paths: list[str] | list[dict] |
| `set_session_workspaces` | **PATCH 唯一写入口**：数量先拦 → 归一化 → 去重(casefold 键) → 预检 → 写库。入参固定 list[dict]（path/workspace_property/memo），不收 list[str]。⚠ **只改数据库行，绝不删除磁盘目录** | conn, session_id, items: list[dict] | list[dict] |
| `_ws_apply` | 覆盖写（PATCH 唯一写库实现）：DELETE 全删 → executemany INSERT(path, prop, memo, is_default)。is_default 按 path 继承旧默认行 | conn, session_id, entries: list[tuple] | None |
| `classify_workspace_rows` | **过滤唯一真源**：行→(有效条目集 `list[tuple]`, 不可用清单)。属性/备注/默认标志只透传不参与裁决；禁区判定先于存在判定；`is_dir()`；unusable 带机器可读 `kind` | rows | Tuple[list, list] |
| `reconcile_session_workspaces` | **创建新Task唯一落盘入口**：默认工作区始终存在（项目根感知+旧默认降级）→ classify 裁决 → 禁区行清库 / 缺目录建目录 → 返回四元组 | conn, session_id | list[tuple[str, str, Optional[str], bool]] |
| `_load_workspaces_conn` | 任务快照源：读行→过滤（复用 classify），不可用行告警；返回四元组供 _load_ws_snapshot 构造 | conn, session_id | list[tuple[str, str, Optional[str], bool]] |
| `_build_default_workspace_dir` | 默认目录名 = `{项目根}\{时间}-{会话标识前4位}`（编排器下沉至此；BUG-13 撤回：完整 session_id 属过度工程，已恢复 [:4]） | session_id: str | Optional[str] |
| `session_exists` | 会话存在且未删才放行（`COALESCE(is_deleted,FALSE)`，NULL 按未删）；否则端点返 404 | conn, session_id | bool |

> 落点说明(2026-10-10 小欧): ①判据接全局 `validate_path` 是会审关键修正。②**10轮会审20bug已修**(v5.5)：过滤收敛到 classify 单一真源（删 `load_effective_workspaces` 死函数、删 `(path,恒0)` 裸 tuple）；`is_dir()` 拒文件；上限前置；NULL 用 COALESCE；宽根 fail-closed；存值保大小写 + 库级 NOCASE；快照 build 去嵌套。（BUG-13"目录名前4位重名"系误报已撤回：验证场景系人为构造，真实概率可忽略，恢复 [:4] 原设计。）常量 `MAX_WORKSPACES=64` / `MAX_PATH_CHARS=240` 同文件定义。
> 2026-10-28 小欧 - [54]全链路重构: 新增 `ws_prop_value`/`ws_prop_label`/`_normalize_ws_meta`（属性归一化唯一源）；全链路四元组化(prop/memo/is_default)；reconcile 重写为始终创建默认工作区(项目根感知+旧默认降级)。标注字段不参与安全判定。

### 3.7 LLM 调用层（`services/agent/llm_call.py`）(2026-10-20 新增 §, 小欧)

全系统「发起 LLM 调用」唯一入口层（原 `llm_stream.py`, 8.5 拆分改名）。`call_llm_text_task` 原为压缩摘要私有 `_extract_response_content`, 按 北京老陈令(2026-10-20) 升格公用并**宿主迁至本模块**(SRP 归位: 通用纯文本调用不属压缩摘要引擎; 逻辑逐行复制零变化, `compaction/summary.py` 改薄引用, 两摘要函数调用点零变化)。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `call_llm_text_task` | 通用「纯文本任务」LLM 调用: 先问 provider 适配器 `callTextForTask` 接管(zen 免费层经此补 `GATE_STUBS` 门禁), 未接管回落 `call_llm_with_fallback`(openai_tools 恒 None 纯文本）。摘要主链与工具层共享(fetchpage prompt 提取经 `tool_executor` 注入 `app.tools.context._current_text_task` ContextVar 回调消费——工具层禁 import app.services 的守护合规管道), 任何 provider/model 通用。不抛异常, 失败/错误响应返回空串由调用方自定降级 | llm_agent: Agent 对象(须含 .llm_client / _task_llm_model), feed: List[Dict](任意 role) | str（最终正文/空串） |

### 3.8 引用处置观测（`services/refs/notice.py`）(2026-10-30 新增 §, 小欧)

引用在 `services.refs.pipeline.prepare_refs` 裁决完成后、进入 loop 之前的一段可观测链路。核心纪律：**`summarize_refs` 是日志与 SSE notice 的唯一数字源**（两通道逐项可对账）；**引用正文永不落日志**（正文只留在 `agent._start_meta["refs"]`，日志只有条数/路径/行区间/字符/token/reason）。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `summarize_refs` | 处置汇总（唯一数字源）：`files` 去重路径数（整份与区间同 path 只算 1）、`fragments` 带 lineRange 条目数、`items` 实际进入 prompt 条目数、`tokens` 进入正文的 `estimate_tokens` 合计、`rejected` 回执条目数 | final_refs: List[Dict], notices: List[Dict] | Dict[str, int] |
| `refs_counts_text` | 计数文案：无片段→`N 个文件`；有片段→`N 个文件、M 个行片段（共 K 项）`（片段与文件不可相加，故显式给总项数） | summary: Dict[str, int] | str |
| `report_refs` | 落日志：1 行汇总（`log_and_print`，行首 `OK`/`BLOCKED`，`paths=` ≤5 条、**路径与行区间完整不截断**，超条数以"另N条"计数）进控制台+文件；明细 ≤5 行（进入项给 span/chars/tokens/path，未进入项给 reason/detail/label）仅进文件，超出写"明细另 N 条已省略"。调用方只在 `refs` 非空时调 | scope: str, summary, final_refs, notices | None |
| `build_refs_ready_notice` | 组 `refs_ready` 通知载荷（走既有 `notice` 信封，无结构化 refs 字段）：`items>0` → `phase=done`（`引用进入本轮：…` / 插话前缀 `插话引用进入：`）；否则 `phase=failed`（`引用全部不可用：N 项未能进入本轮，请求已阻断`）。token 文案 <1000 显原值、≥1000 折 k 一位 | scope: str, summary | Dict（type/kind/phase/content/step） |
| `create_refs_ready_event` | 组 `refs_ready` 的 SSE 帧（首发 `yield`；插话取 `build_refs_ready_notice` 载荷经 `_emit_to_target` → 目标任务 buffer publish 下发，新 POST 流前端只 `readToEnd` 收不到 `yield`） | scope: str, summary | str（SSE 帧） |

> 载体纪律（与 `refs_notice` 同）：首发路径是新建任务流，前端 pump 直接消费，`yield` 即可见；插话路径帧发在新 POST 流上，必须经目标任务 buffer 下发才能到前端。`refs_ready` 只发 `done`/`failed`、不发 `start`（`start` 会占位4 抢主任务提示）；对应前端位4 的 `notice done` 已收紧为"只清自己 kind"（`useTaskInfo.ts`），避免插话的 `refs_ready_done` 抹掉主任务"生成摘要中"。登记点：`NOTICE_KINDS`（`services/agent/steps/__init__.py`）与 `execution.ts` 通名同步。

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
| `tool_utils.py` | 工具通用辅助: `save_text_to_file`(调 write 工具落盘, 基准 project_root, 完整安全链路) |

### 4.3 基础工具（app/tools/fundamental/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `safe_read_file` | 安全读取文件内容(utf-8, errors=replace), OSError 返回空串 | path: str | str |

---

### 4.4 信任机制辅助（app/safety/trust_db.py + app/safety/trust.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `norm_trust_path` | 信任路径规范化: 文件域 Path.resolve() 绝对化; 非文件信任域(registry/sql)原样 strip(信任落库/查询/撤销双侧一致的单一来源) | path: Optional[str], tool_name: Optional[str]=None | Optional[str] |
| `trust_scope_path` | 信任登记范围归一(文件类收敛到【所在目录】, 目录/非文件信任域原样) —— 写入端产出读取端能匹配的东西, 否则「信任此操作」退化为只信任单个文件名 | path: Optional[str], tool_name: Optional[str]=None | Optional[str] |
| `insert_session_trust` | HITL「信任本次会话」落库(UNIQUE(session_id,tool_name,path) 幂等), 同步写 expires_at=now+TTL | conn, session_id, tool_name, path=None | None |
| `check_session_trust` | 信任豁免判定(SA2 实体): path=None 命中本工具通配行; path 给定则命中「本工具通配行」或「任意工具登记路径为该目标祖先/等于」(目录信任跨工具前缀豁免); **过期行不豁免** | conn, session_id, tool_name, path=None | bool |
| `cleanup_expired_trust` | 回收已过期信任行(删 expires_at<=now, 判据与 check 同源单源) —— 由 main.py 周期调用, 独立 try | conn | int(删除条数) |
| `get_session_id_by_task` | 按 task_id 反查 session_id(HITL trust 落库/豁免用, 禁止伪 agent.session_id) | conn, task_id | Optional[str] |
| `extract_trust_path` | 从工具调用提取信任落库/查询的目标路径(文件域经 _parse_paths, 非文件信任域定向别名仅认规范 path) | name: str, params: Dict | Optional[str] |

> **会话信任 TTL**（文档[33] 5.17，2026-10-15 小欧）：`insert` 写 `expires_at = now + security.trust_ttl_days`（默认 90 天）；
> `check` 只查未过期行（`expires_at IS NULL` 视为**不过期**，存量行不被误杀）；`cleanup` 删过期行回收存储。
> **即使 cleanup 没跑，check 的过滤已使过期行不豁免** —— 清理只负责回收存储，不承担正确性。
> 边界：UNIQUE + `INSERT OR IGNORE` 下**重复信任不续期**（续期等于「点一次就永久有效」，与 TTL 初衷相悖）。


### 4.5 Agent步骤辅助（observation_content.py）
| `build_content_items`+`render_line` | tool_result[]→7字段数组→一句人话（详见设计文档3.7.3） | tool_result/item | List[Dict]/str |

---

## 五、LLM核心层（app/llm/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `create_payload_chunk` | 元事件载荷工厂: meta事件(retrying/error/usage/停顿)统一经 payload 随 chunk 直送, 废弃二元tuple协议(文档[6]2.5.1/5.9); 与取消/错误族工厂同列单行构造 | chunk_model: ModelRef, payload: Dict | StreamChunk |
| `create_cancelled_chunk` | 取消响应工厂(取消语义, payload恒None) | chunk_model: ModelRef | StreamChunk |
| `create_error_chunk` | 错误响应工厂(流异常/出错, payload恒None) | chunk_model, error, error_type="http_error" | StreamChunk |
| `SharedClientLease` | [70] 共享连接池的一次引用(引用计数核心): 构造即持一份, `acquire()` 加计数, `release()` 减计数且归零者负责 aclose(幂等, 二次 release 无害); 配套 `_SharedClientPool` 管计数与池级锁 | client: Any, close_on_zero: bool = True | lease 实例; 属性 client/ref_count/is_released |
| `LLMClient.relinquish_ownership` | [70] 所有权移交(幂等): 移交后本实例 `close()` 对共享池变 no-op, 池生命周期交 ConnectionScope 引用计数管理 | — | None |
| `LLMClient.client` | [70] 公开底层 httpx 客户端 property(替代跨层摸 `_client` 私有字段) | — | httpx.AsyncClient |
| `BaseAIService.ensure_client_pool` | [70] 建池 + 所有权移交(幂等) 并返回底层共享客户端; **ConnectionScope.ensure_pool 唯一调用点**, 重复调用复用已建池 | — | httpx.AsyncClient |
| `ConnectionScope` | [70] 共享连接池唯一所有者(一代配置 = 一个 scope): 建池(ensure_pool)/发计数(acquire_lease)/换代退休(release_owner)/停机等待(drain); 不做业务查询、不做归还中介 | ai_service: BaseAIService | scope 实例; 属性 ai_service/ref_count/is_released |
| `get_scope` | [70] 取当前代 ConnectionScope(无则经 get_service 惰性建代); **orchestrator 唯一所有者入口** | — | ConnectionScope |
| `get_retired_scopes` | [70] 已退休代快照(list 拷贝), 供 `shutdown` 逐个 drain | — | List[ConnectionScope] |
| `shutdown` | [70] 停机收口 = `reset()` 换代归还 + 逐退休代 `drain`(timeout 为**全停机总预算**, 各代按剩余预算等, 耗尽即 warning 放行不阻塞退出) | timeout: float = 30.0 | None |
| `get_provider_adapter` | provider 适配层唯一查询口(注册表分派, 未注册回落默认单例)；**消费点 2 处**: client_sdk 组头/门禁/body 转换, model_service 组 Authorization。新 provider 接入 = `_ADAPTERS` 加一行 + adapters/ 加文件, 其余代码零改动 | provider: str | ProviderAdapter |
| `ProviderAdapter` | 适配基类(普通 class + 全 staticmethod, 非 Protocol/ABC 故无强制实现约束), 7 钩子默认行为==现状: `static_headers`(仅 Authorization) / `per_request_headers`(空) / `ensure_gate_body`(原样) / `endpoint_for`("/chat/completions") / `force_stream`(False) / `to_responses_body`(原样) / `error_message_map`(空)。**边界**: 只承载 HTTP 接缝差异与门禁 body/端点路由; schema/reasoning/工具别名属全局层绝不 provider 化 | — | Dict / bool / body |


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

## 八、Safety层（app/safety/）

### 8.1 路径属性判定（path_guard.py）— 是什么路径

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `is_system_protected_path` | 系统保护目录判定（检测+策略单源：展开后取盘符后第一段比对 SYSTEM_PROTECTED_DIR_NAMES；mode 决定禁否，`read` 放行 / `write`·`delete` 拦；异常不静默放行） | file_path: str, mode: str | bool |
| `is_disk_root` | 是否磁盘根（`C:\` / `D:\`），三处判定收敛到此 | file_path: str | bool |
| `is_code_root_path` | 是否落在代码库根及其子/父级（tool 禁区，开关无关硬拦截） | file_path: str | bool |
| `is_protected_root_itself` | 是否受保护根自身或其上级祖先（B 族，可授权）；fail-closed：根集读取失败按禁处理 | file_path: str, extra_roots: Optional[Iterable[str]] | Optional[str] |
| `SYSTEM_PROTECTED_DIR_NAMES` | 系统保护目录名单（windows / program files / programdata / winnt / system32 / system 等，大小写不敏感） | — | frozenset[str] |

> 2026-10-15 小欧 文档[35] 阶段五：由 `app/utils/path_utils.py` 迁回安全域（原为绕 tools→safety 越层而寄居 utils，属职责错位）。本模块零配置零 I/O、不读 `security.enabled`，是全套路径安全中**唯一允许工具层直接依赖**的部分（守护白名单 `TOOLS_SAFETY_ALLOWED`）。

### 8.2 路径可用范围（path_scope.py）— 哪里能用

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_existing_drives` | 动态获取当前存在的磁盘符号列表（不写死，遍历A-Z探测，应对U盘插拔/盘符重映射） | 无 | List[Path] |
| `get_system_drive` | 动态获取真实系统盘符（SystemRoot/WINDIR环境变量→SystemDrive→探测存在\Windows的盘符→兜底C:） | 无 | str |
| `get_default_allowed_paths` | 默认白名单（主目录+`/tmp`+`/var/tmp`+项目根+授权目录+会话工作区；废除「所有现存盘符」全盘放开，lazy动态计算） | 无 | List[Path] |
| `_get_project_root_safety` | 获取项目根供Safety层判定（统一走 config.get_project_root()，未配置→用户主目录） | 无 | Path |

> 2026-10-15 小欧 文档[35] 阶段四：自 `path_safe_check.py` 拆出（环境事实查询，与"路径是否属禁区"是两种关注点）。本模块不含安全判定。

### 8.3 三线共用判定步骤（path_check_common.py）— 怎么查

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `check_preconditions` | 路径穿越硬拦前置：路径含 `..` 或 realpath 解析出穿越 → 命中返回原因文案，通过返回 None（空值先由 `reject_reason_empty_path` 判；归属由 safety 层定） | file_path: str | Optional[str] |
| `has_path_traversal` | 路径穿越轻量判定（工具层专用）：按 `\` 和 `/` 切分后任一段 == `..` 即 True；纯内存/无 realpath，适合工具入口快速拦截 | path: str | bool |
| `check_whitelist` | 白名单前缀匹配（含盘根特例） | file_path: str, allowed_paths: List[Path] | bool |
| `resolve_allowed_paths` | 白名单取值：显式传入优先，否则取 `path_scope.get_default_allowed_paths()` | allowed_paths: Optional[List[Path]] | List[Path] |

> 2026-10-15 小欧 文档[35] 阶段一新建。**禁区分类不在本模块**：`_is_forbidden_path` 按 mode 决定读放行/写删拦，三线传入的 mode 不同，故由三线各自直调。

### 8.4 读/写/删三线（read/write/delete_path_check.py）— 各线策略

三线签名相同：`validate(file_path: str, allowed_paths: Optional[List] = None) -> Tuple[bool, Optional[str], Optional[str]]`

| 模块 | 常量 | 独有策略 | 禁区判定档位 |
|---|---|---|---|
| `read_path_check` | `READ_MODE="read"` | 禁区放行 + 白名单外放行（读不写盘，内容敏感性交 contentFilter） | 传 `READ_MODE` |
| `write_path_check` | `WRITE_MODE="write"` | system 硬拦；non_system 与白名单外可申请任务级授权 | 传 `WRITE_MODE` |
| `delete_path_check` | `DELETE_MODE="delete"` | **所有禁区一律硬拦、无授权分支**（删不可逆）；白名单外可申请授权 | 传 `DELETE_MODE` |

**三线权限封装口（返回 `SafetyResult`，供确认段统一消费）— 2026-10-17 小欧 文档[38] 基础归一化：**

| 封装口 | 返回 | 语义 |
|---|---|---|
| `read_path_check.check_read_permission(path, params=None)` | `SafetyResult` | 读线放行；仅空/穿越/异常 `blocked` |
| `write_path_check.check_write_permission(path, params=None)` | `SafetyResult` | system→`blocked`；non_system/白名单外→`requires_confirmation`+`auth_path`；合法→放行 |
| `delete_path_check.check_delete_permission(path, params=None)` | `SafetyResult` | `guard`(删根底线)→`check_delete_risk`(非法输入 fail-closed + 权限矩阵出 拒绝/确认/放行) |

> 2026-10-17 小欧 文档[38] 基础归一化：read/write 新增 `check_*_permission`，与既有 `check_delete_permission` 同签名同返回；read/write 两封装口照搬 `path_tool_safety_checker._check_known_risks` 单路径分流口径。

> 2026-10-15 小欧 文档[35] 阶段一新建。**九格契约表（读/写/删 × 各类区域）单一真源在 `path_safe_check.py` 模块头**，三线只负责本线实现，不重复维护表格。

### 8.5 路径检查总入口（path_check_entry.py）— 三通道分发

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `validate_tool_path` | SA5 唯一入口：按 `ToolMetadata.action_kind` 分派（`none` 直接放行 / `multi` 走多动作通道 / 其余走对应线）；**返回值四元组**，`failed_path` 由本层填真实解析后路径（BUG-D 修复要点） | tool_name: str, params: Dict | Tuple[bool, Optional[str], Optional[str], Optional[str]] |

> 2026-10-15 小欧 文档[35] 阶段一新建。已删除原 `validate_path` 及其 `mode` 参数（用参数模拟分支者当消灭），**不设转发壳、不留兼容入口**。

### 8.6 多动作通道（multi_path_check.py）— 一次调用多个动作

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `MULTI_ACTION_PARAMS` | 6 个复合工具的参数档位声明（copy/move/compress/extract/rename/edit 的 path 与 dest **一律 write** —— 源虽只读但意图是把数据搬离原地，判读线会导致系统文件可被压缩复制 = 数据外泄） | — | Dict[str, Dict[str, str]] |
| `resolve_path_param` | 工具逻辑路径参数→真实文件系统路径（download.dest 相对下载目录 / rename.dest 仅文件名需解析） | tool_name, key, value, params | str |
| `validate_multi_path` | 复合工具按声明表逐参数选线校验 | tool_name, params | 四元组 |
| `validate_bash_targets` | bash 命令内写/删目标抽取（不解析 shell 语法；命删动词走删线，命写动词/重定向走写线） | command: str | 四元组 |

> 2026-10-15 小欧 文档[35] 阶段一新建。删除动词正则 `_DELETE_CMD_RE` 仍留在 `app/tools/fundamental/shell_command_guard.py`（属工具层 shell 静态检查职责，迁移会新增 tools→safety 依赖）。

### 8.7 禁区分类内核（path_safe_check.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_is_forbidden_path` | 判断路径属哪类禁区（磁盘根/系统敏感文件目录/系统保护目录→`"system"`；代码库根与受保护根→`"non_system"`；非禁区→`None`）；异常一律判 `"system"`（fail-closed） | file_path: str, mode: str | Tuple[Optional[str], Optional[str]] |

> 2026-10-15 小欧 文档[35]：由 577 行瘦身至 215 行，只保留禁区分类内核（读/写/删三线共同调用并传本线 mode）与九格契约表。原 `validate_path` / `validate_tool_path` / `_resolve_path_param` / `_validate_shell_write_targets` 及磁盘枚举、白名单构建均已迁出。

### 8.8 delete 专属差异判定（delete_safety.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_as_bool` | ~~布尔强转（防LLM原始参数 'false'/'true' 字符串陷阱: bool('false')==True）~~ **已于 2026-10-15 删除**（内联进 check_delete_risk，isinstance 前置为冗余分支；全仓唯一布尔解析实现见 app/config.py `env_flag`） | ~~v: Any~~ | ~~bool~~ |
| `check_delete_risk` | delete 差异判定，恒返回 SafetyResult；非法输入(空/`..`穿越) fail-closed blocked；归属查 `path_dir_lists` 名单 + `PERMISSION` 矩阵出 拒绝/确认/放行；fail-closed：格式化异常或名单读取失败一律 blocked | params: dict | SafetyResult |
| `_get_allowed_roots` | ~~删除判定允许根列表~~ **已于 2026-10-15 删除**（根集合收为 `app/utils/path_utils.py` 的 `get_allowed_roots()` 公开单源） | — | — |
| `_is_inside_any` | ~~目标是否位于任一允许根内~~ **已于 2026-10-15 删除**（零外部调用，内联为 `any(p == root or root in p.parents for root in roots)`） | — | — |

> 消费链：path_tool_safety_checker.check_before_execute 对 delete 一次性计算 delete_risk，危险项入 _check_known_risks 无条件拦截，其余入 _get_needs_confirmation 确认分流

### 8.9 路径格式化与归属判定内核（path_dir_lists.py）— 全系统单一真源

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `format_path` | 路径格式化唯一真源：把同一目标的多种写法(剥 `\\?\`/`\\?\UNC\` 前缀、expanduser、realpath 解 symlink/8.3 短名/正斜杠、折叠重复分隔符、去尾部分隔符保盘根、盘符大写)统一到一种格式；名单构建 `_complete`、查询判定 `classify_path`、安全入口工具参数三处共用 | file_path: str | str |
| `classify_path` | 路径格式化 + 五档归属判定(禁区系统/禁区非系统/白名单自身/白名单下级/白名单外)唯一入口；读/写/删/dual/shell 各线共用 | file_path: str | Tuple[str, Optional[DirRule]] |
| `absolutize_path` | 相对路径绝对化唯一真源：绝对原样；相对 = `abspath(join(base, path))`，`base` 由调用方按语义传入(工具工作区/下载目录/源父目录等)，不内置工具专属基准、不用进程 cwd；不做穿越处理。安全入口 `_format_tool_paths` 与 download 工具共用 | path: str, base: str | str |
| `get_download_dir` | 下载目录唯一真源 = `get_config().get_project_root()/download`(未配回落用户主目录)；download 工具与安全入口 `_format_tool_paths` 共用(在安全层调用不反向依赖工具) | 无 | str |

### 8.3 白名单外临时授权（temp_auth.py，位于 app/safety/）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `grant_temp_auth` | 临时授权某路径（一次一申请、支持递归、per-request ContextVar隔离） | root: str, recursive: bool | None |
| `clear_temp_auth` | 清空当前作用域临时授权 | 无 | None |
| `is_temp_authorized` | 检查路径是否在临时授权范围内（含子目录树） | file_path: str | bool |
| `get_authorized` | 获取当前作用域授权映射 | 无 | Dict[Path, bool] |

> 消费链：path_tool_safety_checker._check_known_risks 检测到白名单外路径(非禁区) → SafetyResult(requires_confirmation+auth_path，auth_path=failed_path 真正越权参数, 非固定path-or-dest) → action_handler 确认后 grant_temp_auth → validate_path 放行本次；**react_cycle.run_react_cycle task结束 finally 调 clear_temp_auth() 清除(task级清零点)**；禁区(代码库根/系统目录)不受临时授权影响永久封锁

### 8.4 受保护进程集合（path_tool_safety_checker.py，位于 app/safety/）

宿主关键进程 PID 的唯一组装点（2026-10-08 事故驱动新增）。供给 1.15 的 `is_process_kill_protected` 判定"命令是否要杀宿主自己"。此前 `check_shell_command_risk` 的 `protected_pids` 参数全项目无第二处传值，保护盾恒不生效。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_protected_pids` | 组装宿主关键进程集合：后端自身 `getpid()` + 父进程 `getppid()`（uvicorn `--reload` 为父子双进程，只护自己漏一半）+ shell 池 `get_all_pids()`（池未初始化时降级为只护自身，不拖垮安全判定）。**已知不完美**：`getppid()` 覆盖不到 `--reload` 派生的 worker 子进程，待办 | 无 | set[int] |

> 消费链：`_get_needs_confirmation` 的 shell 分支前置 `is_process_kill_protected(cmd, _protected_pids())`，命中即 `blocked=True` 直返（不进弹窗、不进沙箱预检）。

---

## 九、E2E测试层（backend/e2etests/e2emodel/）

### 9.1 E2E公共辅助（e2e_helpers.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `verify_db_tool_usage` | DB侧工具步骤统一校验（case脚本唯一入口）: 工具步骤数≥min_tool_steps、expect_any_tools至少命中一个、每个工具步骤按step号配对observation步骤tool_result[]非空; 内部复用_is_action_step/_action_entries新旧协议自适应, §10.3模型变更仅改此一处 | db: Dict[str,Any](check_db返回值), expect_any_tools: Optional[List[str]]=None, min_tool_steps: int=1 | List[str] 问题列表(空=通过) |
| `READ_TOOLS` | 读类工具名唯一源常量(DRY): {"read","read","readmedia"}; SSE has_read断言与verify_db_tool_usage(expect_any_tools=READ_TOOLS)共用, case侧禁再散落本地read_tools字面量 | 无（set常量） | Set[str] |

---

## 十、模型/配置域（app/services/settings/ + app/services/model/）（v4.19 登记 — 小沈 2026-09-20）

### 10.1 设置页服务（settings_service.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_all_groups` | 设置页 6 组全量读（data+sources+版本+mtime），env 标注 + secret 掩码 | 无 | Dict: {groups, version, mtime} |
| `load_security_docs` | 安全 Tab 三段只读说明文案：读 `app/datafile/*.md` 插值 5 个 `{{占位符}}`（含 `FORBIDDEN_PATHS_WINDOWS_REL_*` 相对段清单）；单文件缺失降级为一行提示并落 warning，不抛异常 | 无 | Dict: {policy, flow, classification}（值为已插值 md） |
| `get_group` | 单组刷新（未知组名 ValueError 拒） | group: str | Dict: {data, sources, mtime} |
| `get_schema` | 6 分组 schema（前端初始化/核对） | 无 | Dict: {groups} |
| `get_setting` | 后端任意处一行读取有效值（env 覆盖自动生效） | key: str, default: Any | Any |
| `update_settings` | PUT /settings：全部 key 一次 merge_region_patch 单次落盘；ai.model_ref 内联结构+扁平双写 | patch: Dict[str, Any] | Dict: {ok, updated, need_restart, warnings, mtime}（失败时含 errors） |

### 10.2 通用 region 合并 / secret 掩码（service/model/config_helpers.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `merge_region_patch` | 通用 region 合并写（settings_service/model_service 共用，DRY 单点；v4.11 核查 B2 上提）：filelock 并发锁→备份→内存合并→_validate_config_integrity 校验→_order_for_dump 保序→atomic_write 原子写→重读逐键验证→reload→异常回滚，返回 backup_path | region_updates: Dict[str, Any], scope: str | str（backup_path） |
| `mask_secret_value` | secret 掩码唯一权威（全项目共用，永不返明文）。2026-09-27 起返 {configured, masked} 两键，masked 为后端一次生成的最终可显示串：len>8 → 前4+`****`+后4；4<len<=8 → `****`+后4；len<=4 → `****`；空 → {configured:False, masked:""}。前端只回显 | value: Any | Dict: {configured: bool, masked: str} |

### 10.3 模型编排器（model_service.py）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `get_models` | GET /models：providers/models 层级 + current_model_ref | 无 | Dict: {providers, current_model_ref} |
| `get_providers` | GET /providers：provider 列表（含掩码 key） | 无 | List[Dict] |
| `add_model` | POST /models：校验存在+唯一 → 单次 region 合并落盘 | provider, model, label, default_params, range_, capabilities | Dict: {ok, mtime, ...} |
| `update_model` | PUT /models/{p}/{m}：label/range/capabilities 写 model_meta；default_params 逐键 merge；remove_params 键级删除（先从 model_params/range/param_options 删键再 merge default_params，空 dp=整块清空与 P8 叠加） | provider, model, fields | Dict: {ok, model, mtime} |
| `delete_model` | DELETE：models[] 移除 + 清 model_params/model_meta 块；删当前 → 自动切换（switched_to）；无模型跨 provider 回退 | provider, model | Dict: {ok, switched_to, mtime} |
| `add_provider` | POST /providers：name 唯一 → 写入 ai.{name} 块 | name, label, api_base, api_key, model, timeout | Dict: {ok, provider, mtime} |
| `update_provider_config` | PUT /providers/{name}：改 api_key/base_url/timeout 立即生效；clear=true 清空 api_key | name, fields | Dict: {ok, provider, mtime} |
| `delete_provider` | DELETE /providers：级联删 ai.{name} 全块 + 删当前自动切换（switched_to）；禁删最后一个 | name | Dict: {ok, switched_to, mtime} |
| `_require_provider_for_fetch` | [68] 拉取前置校验层：provider 存在性 + api_base 非空，返回 (p, api_base) | name, ai | Tuple[Dict[str, Any], str] |
| `_http_get_remote_models` | [68] HTTP 拉取层 GET {api_base}/models → (resp, err)；网络异常统一 err 文案；timeout 30s | api_base, headers | Tuple[Any, Optional[str]] |
| `_KEY_ALIASES` + `_canon_item` | [68] 中央别名表 + 入口归一：同义键（name/display_name/title、pricing/pricings、context_length/context_window、max_output_length/max_output_tokens、supported_parameters/supported_sampling_parameters）在此收敛，新厂商只加表行不碰逻辑；`_first_alias` 已退役删除 | 表 + item | Dict |
| `_str_list` | [68] 远端值收敛为 List[str]：非数组退空列表、非字符串成员丢弃（防错型打挂挂 response_model 的 DTO） | value | List[str] |
| `_flatten_pricings` | [68] zenmux 式 pricings（复数嵌套）拍平 → {prompt/completion: str}；只取 perMTokens（perCount 跳过，不污染免费判据） | pricings | Dict[str, str] |
| `_merge_capabilities` | [68] capabilities:{reasoning:bool} 对象并入 supported_features（去重）；其它键不猜语义 | feats, capabilities | List[str] |
| `_parse_remote_models_body` | [68] 响应解析层 → (models, err)；HTTP>=400 提取 error.message / 非JSON / data 非数组 → err；id 缺失丢弃；**键名先经 `_canon_item` 中央别名表归一**（`{**architecture, **item}` 合成查找视图管层级，顶层优先嵌套兜底 → input/output_modalities）；下发 15 字段含 max_output_length/input_modalities/output_modalities/supported_features/publish_time | resp | Tuple[Optional[List[Dict]], Optional[str]] |
| `fetch_remote_models` | [68] GET /providers/{name}/remote-models：后端代理绕 CORS；本地校验 400/404，远端失败统一 200+ok:false；key 取值三级优先（probe_key → env `{NAME}_API_KEY` → config）；**key 空白时 pop 掉 Authorization 头**（基类无条件造空 Bearer，无鉴权端点会 400），不动 adapter 基类以免波及 LLM 主链 | name, probe_key=None | Dict: {ok, provider, models, count, configured, current_model, status_code, category, message?} |
| `replace_provider_models` | [68] PUT /providers/{name}/models：替换式写 ai.{name}.models + 差集孤儿清理（removed 键写 None 叶，禁空 dict）；env 接管/空列表/移除当前全局模型 → 400 | name, models | Dict: {ok, mtime, added, removed} |

---

## 版本历史

| version | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v5.16 | 2026-10-30 21:12:41 | **§3.8 `report_refs` 口径修正：`paths=` 不截断**(小欧, 北京老陈令): 删 `_paths_text` 的 60 字符右截断与常量 `REF_LOG_PATH_MAX_CHARS` —— 右截断会连 `:start-end` 与文件名一起切掉, 同一文件的"整份"与"行片段"在汇总行变成完全相同的字符串, 定位信息丢失; 现给完整路径, 行长度只由 5 条上限 + "另N条"计数控制 | 小欧 |
| v5.15 | 2026-10-30 20:21:41 | **§3.5 新登记 `estimate_tokens` + 新增 §3.8 引用处置观测**(小欧): ①`services/agent/token_estimate.py` 成为 chars→token 唯一实现, 收口 `compaction.prune._released_tokens` 与 `refs.budget._tokens_of` 两份同款单行(DRY, 5 处调用点改公共函数); ②§3.8 登记 `summarize_refs`/`refs_counts_text`/`report_refs`/`build_refs_ready_notice`/`create_refs_ready_event`——引用进 loop 前 1 行汇总日志(log_and_print)+≤5 行明细+SSE `notice(kind=refs_ready)` 三通道共用同一份数字, 引用正文永不落日志 | 小欧 |
| v5.14 | 2026-10-26 12:27:19 | **§1.10 新登记 `get_output_dir` + §4.2 新登记 `save_text_to_file`**(小沈): ①`get_output_dir()`(project_root/output) 从 generate_chart._get_output_dir 抽取至 path_utils.py 公用, download/generate_chart 默认输出统一 output/; ②`save_text_to_file` 从 fetch_webpage._save_to_file 抽取至 toolhelper/tool_utils.py, 调 write 工具走完整安全链路; ③DRY: download_file._stream_download 合并至 HTTPClient.download(SDK 增强版) | 小沈 |
| v5.13 | 2026-10-20 16:03:19 | **§3.5→§3.7 登记迁移**(小欧, 三堂会审账实不符修正): `call_llm_text_task` 函数体宿主按北京老陈裁定自 `compaction/summary.py` 原样迁至 `services/agent/llm_call.py`(全系统"发起LLM调用"唯一入口层, SRP 归位; summary 改薄引用, 逻辑零变化), 清单条目新立 **§3.7 LLM 调用层** 承接(§3.5 压缩清单条目移除); v5.12 条目描述的 §3.5 位置按本条目作废以 §3.7 为准 | 小欧 |
| v5.12 | 2026-10-20 15:45:50 | **§3.5 新登记 `call_llm_text_task`**(北京老陈令, 小欧): 压缩摘要私有 `_extract_response_content` 纯改名升格公用(逻辑零变化), fetchpage prompt 提取复用——工具层守护禁 tools→app.services, 故 tools/context 新增 `_current_text_task` ContextVar, 由 `tool_executor.execute_tool` 注入闭包, `fetch_webpage._extract_by_prompt` 经 `get_current_text_task` 消费(A1 hooks 同款管道); 同批修复 #1 searchweb 域名过滤(见 search_web.py 编辑历史) | 小欧 |
| v5.11 | 2026-10-19 21:02:35 | **路径格式化收口**(小欧): §8.9 新登记 `format_path`(全系统唯一真源: 名单构建/查询判定/安全入口三处共用) 与 `classify_path`; `normalize_path` 删除(同口径重复实现, DRY); 安全入口 `check_before_execute` 在 directory_lists_scope 内对非 shell 工具的 path/dest 值就地格式化(键名不变, 只格式化绝对值, 相对值交各工具 resolve_path_param); 术语由"归一化"改"格式化" | 小欧 |
| v5.10 | 2026-10-19 19:41:15 | **路径检查回归修复 + 死代码清理**(小欧): §8.3 `check_preconditions` 返回契约归一为 `Optional[str]`(原三元组第三元素恒为旧 category `"system"`, 目录数组化后无对应枚举); §8.4 `check_delete_permission` 链条订正(`guard`→`check_delete_risk`, `validate_delete` 死代码删除); §8.5 `check_delete_risk` 描述订正(非法输入 fail-closed + `path_dir_lists` 名单/矩阵)。修复写/删线 `..`穿越与空路径被降级为"确认"(fail-open)及 `security_docs` 设置页 500 | 小欧 |
| v5.9 | 2026-10-16 23:57:15 | **tool去检查化(北京老陈裁定: 系统层检查的事tool层不重复, tool只执行+业务警告)**: §1.10 补登记 `path_has_reserved_char`/`path_has_reserved_name`/`path_has_extra_drive`/`validate_str_param`(自 file_path_checker 迁入 utils); file_path_checker 终点为三纯警告函数(`for_write/delete/overwrite`); 合法性规则(`OpCategory`/`validate_path_layers12`)迁 safety `path_1st_legality_check`(SA1 唯一检查点) | 小欧 |
| v5.8 | 2026-10-15 | **路径订正 + TTL 登记**(小欧, 文档[33] 5.23 / P5步21-22): ①§4.4 与§八 标题/小节路径按终态订正 —— `app/tools/trust_db.py`+`app/tools/trust.py` → `app/safety/trust_db.py`+`app/safety/trust.py`; 第八章标题去掉已删的 `app/tools/security/`; §8.1/§8.3 标注位置由 `app/tools/security/` 改 `app/safety/`(该包 5.15 已整包删除) ②§4.4 补登记 `trust_scope_path`/`insert_session_trust`/`check_session_trust`/`cleanup_expired_trust`/`get_session_id_by_task` 五个原漏登函数, 并加**会话信任 TTL** 说明(写 expires_at / 查未过期 / 周期回收, NULL=不过期兼容存量, 重复信任不续期)。注: 本文件未记录 `SafetyResult` 的模块路径(仅作形参名出现), 故设计 5.23「SafetyResult 改 app/tools/tool_types.py」一节无对应条目可改 | 小欧 |
| v5.7 | 2026-10-14 10:47:03 | **linked 增量摘要**(小欧): §3.2 登记 `get_chain_summary_anchor`(取链内最近非空摘要锚点) + `save_chain_cover_summary`(摘要写覆盖上界任务行, 单一出口); 模块内私有装配辅助(`_build_history_context`/`_strip_history_msgs`/`_assemble_anchor_delta`, 单消费者)按惯例不入清单 | 小欧 |
| v5.6 | 2026-10-11 07:30:12 | **中央别名表收敛厂商键名漂移**(小欧): `_KEY_ALIASES` + `_canon_item` 入口归一（name/display_name/title、pricing/pricings、context_length/context_window、max_output_length/max_output_tokens、supported_parameters/supported_sampling_parameters），`_first_alias` 退役删除（唯一调用点改直读）；longcat 两变体首批入表；zenmux 映射（_flatten_pricings/_merge_capabilities/publish_time）保持。回归 94 passed + 真实 zenmux 201 条/DTO 零失败 + 老厂商口径零变化 | 小欧 |
| v5.5 | 2026-10-10 12:50 | **10轮会审21bug修复(小欧)**: §3.6 函数清单同步新契约 —— 新增 `reconcile_session_workspaces`(进入会话唯一真源)/`_build_default_workspace_dir`(下沉)/`_drop_nested`(context 快照去嵌套); 删 `load_effective_workspaces` 死函数; `MAX_PATH_CHARS` 240→200 | 小欧 |
| v5.4 | 2026-10-10 12:40 | **会话使用目录概念订正(小欧)**: 三、Agent层 §3.6 全面重写 —— "会话授权目录"改称**会话使用目录**(授权目录归全局 config 管, 不在本模块); 删 `resolve_ws_initialized()` 与 `is_default` 分档(表里无"授权目录"可区分); 补 `_ws_apply` 登记; 落点说明加"只改库行、绝不删磁盘目录"硬约束 | 小欧 |
| v5.3 | 2026-10-10 10:49:50 | **登记会话 Workspace 落地(10 轮会审后, 小欧)**: 三、Agent层 新增 §3.6 `workspace_service.py` 共 10 个函数(`classify_workspace_rows` 过滤唯一真源 / `_ws_deny_reason` 授权判据 / `_is_broad_root` 宽根判据 / `_normalize_ws_path` 归一化唯一源 等)。**判据全部复用全局真源**(`_is_forbidden_path` 串联 `validate_path`),不自造黑名单 —— 会审实证此前只用了较弱判据,导致 `C:\Program Files`/`ProgramData` 可被授权 | 小欧 |
| v5.2 | 2026-10-10 10:32:51 | **猎杀 10 bug 全修**(本地探针门级 verdict 逐条实证, 小欧): 1.14 四函数口径同步更新 — ①`normalize_for_intent` 增 `[char]N` 解码 + `()[]{}` 噪音剥离(顺序解码→剥噪音→折叠→去引号; 逗号/分号不动)；②`has_uncontainable_intent` 增 `.Terminate()`/`.Kill()` 方法调用(只认调用点, 不认裸词)、`Invoke-CimMethod`、`-EncodedCommand`/`-enc`(内容不可见, 转 HITL 为残留风险)；③`extract_kill_target_pids` 增 `taskkill /FI "PID eq N"`；④`is_process_kill_protected` 增引号名(同步扫归一文)、`/FI IMAGENAME`、WMI `where`/`Name=`、pkill 实参(含 `-f` 模式串) + **无目标兜底**(有杀意无目标直接 blocked；停服务动词、`/?`/`--help`/`-WhatIf`、wmic 裸查询、引号内纯提及不在此列)。回归 303 passed 零退化 | 小欧 |
| v5.1 | 2026-10-10 09:55:09 | **位置与命名更正**(北京老陈指出"代码名称确实要名副其实", 小欧): ①**落点** `app/utils/` → `app/tools/fundamental/shell_static_guard.py` — 原落 utils 的理由"架构边界要求 tools 禁 import safety"经 `tests/test_architecture_boundaries.py` 实证**不成立**(该守卫只禁 `"tools": {"app.services","app.safety"}`, `safety→tools` 合法, 先例= tool_safety_checker 一直 import execute_shell_command_safety), 无需中转 utils; shell 代码归 shell 代码同目录, 不散落。②**更名** `shell_readonly.py` → `shell_static_guard.py`(名副其实: 对 shell 命令做静态守卫判定, 原名仅覆盖约 1/3 内容)。③**并回一处** 曾短暂拆为 shell_readonly/shell_danger/shell_normalize 三文件, 复核判定属**过度拆分** — normalize_for_intent 只服务杀进程判定、非独立可复用能力, 单独成文件违反 YAGNI, 且制造 shell_danger→shell_normalize 跨文件依赖。④注册表 1.15/1.17 并入 **1.14 shell 命令静态守卫**(条目号保留作指引, 不重排后续编号)。生产调用点 4 处、测试 4 处、守卫 CHECKS 已同步。按 AGENTS.md 1.4 逐行合并未改业务逻辑 | 小欧 |
| v5.0 | 2026-10-10 09:46:42 | SRP 拆分同步(AGENTS.md §1.4「能复制就复制，不重写」, 小欧): `app/utils/shell_readonly.py` 原同时承载**只读白名单 / 杀进程防护 / 命令规范化**三类互不相干关注点，文件名与职责不符(仅约 1/3 内容与 readonly 有关)，故拆分为三文件并同步注册表 — ①**1.15 落点变更**: `shell_readonly.py` → `shell_danger.py`(含 `UNCONTAINABLE_VERBS`/`_UNCONTAINABLE_RE`/`_PID_TARGET_RES`/`_KILL_NAME_RES` 词表与 5 个函数)，业务逻辑逐行照搬未改；②**新增 1.17 shell 命令规范化**(`shell_normalize.py`: `normalize_for_intent`，审计 P1-1 产物，被 1.15 依赖)；③**1.14 不变**(`is_readonly_whitelisted`/`READONLY_PREFIXES`/`FAST_CHANNEL_FORBIDDEN` 留在 `shell_readonly.py`，既有调用方落点不变)。同步更新生产调用点 2 处(tool_safety_checker/executor)、测试导入 3 处、`test_functions_md_consistency.py` 注册表 4 条。回归 262 passed 零退化 | 小欧 |
| v4.9 | 2026-10-08 10:26:28 | 补登记漏项(AGENTS.md §1.3 违反修复, 小欧): ①**1.15 shell 杀进程/停服务防护**(shell_readonly.py: `has_uncontainable_intent`/`extract_kill_target_pids`/`is_process_kill_protected`) — 事故驱动, E2E P9-03 实录 agent 发 `Get-Process python \| Stop-Process -Force`、沙箱预检在宿主真跑一遍即杀死后端自身; 收录标准= 现有 SHELL_DANGEROUS_PATTERNS 只到 MEDIUM(弹窗后仍进预检)拦不住者, HIGH 级不重复收录(DRY); ②**1.16 异步流收尾**(astream.py: `aclose_stream`) — 2026-10-07 随 llm_call/base_service 流关闭修复同批, 当时漏登记; ③**3.5 上下文压缩**(compaction/: `prune_tool_output_keeping_tail` 摘要降本策略已接入 start_step + `_fc_atomic_units` FC 原子单元修 provider 400 + `_msg_cost` 统一 token 口径), 真实 205 条 feed 135362→86472 tok; ④**8.4 受保护进程集合**(`_protected_pids`) — 此前 protected_pids 全项目无第二处传值致保护盾恒不生效。已知不完美如实登记: getppid() 覆盖不到 --reload worker 子进程(待办) | 小欧 |
| v4.8 | 2026-10-06 20:15:00 | 10.1 新登记 `load_security_docs`（读 `app/datafile/*.md` 三段说明 + 5 个占位符插值 + 缺文件降级）；同批 `FORBIDDEN_PATHS_WINDOWS_*` 改存与盘符无关相对段并抽出 `FALLBACK_SYSTEM_DRIVE`，去掉 `.replace("C:", ...)` 字符串替换 | 小欧 |
| v4.7 | 2026-10-05 23:05:00 | ①**补登记漏项**(AGENTS.md §1.3 违反修复): 五章新增适配层 3 条 `get_provider_adapter`/`ProviderAdapter`(7 钩子与边界"schema 类绝不 provider 化")/`OpencodeZenAdapter`, 适配层 2026-09-23 落地至今零登记; ②10.3 `_parse_remote_models_body`/`fetch_remote_models` 描述订正漂移(补 probe_key 参数、status_code/category 字段, 前者 2026-09-26 起即缺) + 新登记 `_first_alias`/`_str_list`; ③记录 2026-10-05 模型库增强: 厂商字段别名归一(SenseNova 实抓 9 模型 16 字段, 此前静默丢弃 11 个)+ 4 字段下发 + key 空白时不发 Authorization。**本次未动解析层既有 10 字段口径**(裸数组兼容/id 回退 model/字母序排序/opencodeZen 的 supported_parameters 全部逐字回归验证通过) | 小欧 |
| v4.6 | 2026-10-01 | [1] 刷新显示其他任务结果 修复(全链根因+契约)。**A组 运行期逐步落库**: agent_runner 末尾扫描 event_log 机制退役, step 落库前移到 StreamBuffer.persist_sink(buffer.publish 唯一收口, 覆盖 _emit_publish/handle_action 直连/_events 批量三条发布路径), 单消费者 FIFO 队列零背压, finally flush; step_index 改独立计数器(itertools.count, 解耦内存列表); append_execution_step 增 ON CONFLICT DO NOTHING 幂等 + task_id fail-loud; token_usage 明细改实时。**E组**: MessageResponse 增 task_id(E4) + load_execution_steps 三调用点补传 pair_task_id(E3, 堵跨任务混读); chat_user_message 正文回填前移至 final 帧(E13); total_steps 剔除集统一复用 agent_telemetry.M_SKIP(E1/E2, 含补齐 chunk/thought-start/error/rejected 使两统计源恒等); 新增 _strip_thought_content 供两读入口共用(E11); get_task_tool_stats 改 json_each 支持并行多工具(E7); _warn_zero_row 增 level 参数, update_task 0 行升级 error(E9)。**YAGNI 清理**: save_execution_steps/其端点/sse_events 死函数/前端 saveExecutionSteps/ExecutionStepsUpdate/derive_status_from_steps 整删(E8) | 小欧 |
| v4.5 | 2026-09-29 20:49:50 | 3.3 数据库SDK(app/db/database.py) atxn 签名增关键字参数 retry_locked(默认0=既有 29 个调用点行为逐字不变, 禁止backward): 补 body 执行期 "database is locked" 有限重试(退避 0.5/1/2s 与 get_conn 同节奏, sleep 置 async 层不占 to_thread 子线程), 仅捕 sqlite3.OperationalError 且串含 "locked", 非锁错误/耗尽一律原样抛出; 根治 get_conn 只覆盖连接期+提交期、业务事务体撞写锁直抛的缺口(2026-09-29 19:49 PAR-05 实锤); 已在 5 处实证高危写路径启用 retry_locked=3(编排⑨ _setup_task_db + agent_runner 的 _persist/异常终态/守卫兜底终态/终态 UPDATE), 其余 24 处维持默认 0(YAGNI); 另 storage 新增模块私有 _warn_zero_row 作 UPDATE 影响0行告警统一出口(非公用函数不单列条目), update_task 补 0 行告警 | 小欧 |
| v4.4 | 2026-09-28 21:29:00 | 3.2 新增 bind_message_to_task（[76] 活跃任务注入 6.5① 执行期归属，零 DDL 复用 chat_user_message.task_id 列，WHERE task_id IS NULL 防覆盖，返回 bool 供调用方判别两成因）；同步 fetch_session_user_message_pairs 描述（精确归属 COALESCE 双子查询取 MAX(id) 取代会话级模糊兜底，增返回 pair_task_id）——补 [76] 首轮遗漏的公用函数登记(AGENTS.md §1.3) | 小欧 |
| v4.3 | 2026-09-24 23:20:00 | 10.3 新增 [68] 模型库 5 函数：_require_provider_for_fetch/_http_get_remote_models/_parse_remote_models_body/fetch_remote_models/replace_provider_models（设置页模型库 Tab 远程拉取+替换写入，HTTPException 防 500，孤儿清理 None 叶） | 小欧 |
| v4.2 | 2026-09-24 21:16:00 | 10.3 update_model 描述补 remove_params 键级删除通道（②设置页参数行 × 删除按钮，先删 model_params/range/param_options 键再 merge default_params；空 dp=整块清空与既有 P8 叠加） | 小欧 |
| v4.1 | 2026-09-24 19:34:00 | 9.1 新增常量 READ_TOOLS（北京老陈指示归一helper）: 读类工具名唯一源{"read","read","readmedia"}; ling-3.0实调read而非read致P9-04 has_read误Fail; case侧禁再散落本地read_tools字面量, 供SSE断言与verify_db_tool_usage共用(DRY) | 小欧 |
| v4.0 | 2026-09-21 07:45:00 | 新增 十、模型/配置域 章节（v4.19 9.3.8）: 登记 settings_service.get_all_groups/get_group/get_schema/get_setting/update_settings、config_helpers.merge_region_patch/mask_secret_value、model_service.get_models/get_providers/add_model/update_model/delete_model/add_provider/update_provider_config/delete_provider | 小欧 |
| v3.15 | 2026-09-16 07:04:06 | 新增 4.4 信任机制辅助(app/tools/trust_db.py+trust.py): norm_trust_path 函数化公开(文件域 resolve / 非文件信任域 strip, insert/check/delete 落库·查询·撤销统一单一来源, DRY 消除 storage 层双份逐字副本); extract_trust_path 补登记(hitl_gateway 直调 + resolve_skip 复用) | 小欧 |
| v3.14 | 2026-08-30 14:50:00 | 13.11 空行规约(北京老陈 2026-08-30 批准): 1.7 text_utils 新增 normalize_blank_lines(连续空行折叠为一个空行+段首尾trim, 幂等, 后端落库收口入口, 与前端 normalizeBlankLines 同一张规则表); format_tool_call_markup 末尾压缩收敛复用(行为逐字节等价, DRY); agent_runner._persist 与 storage.load_steps_by_task 的 C2/规约逻辑为模块内私有改动不单列条目 | 小欧 |
| v3.13 | 2026-08-30 08:05:00 | 新增 1.11 控制台镜像(app/logger/console_writer.py): console_put 非阻塞控制台写(全局queue+daemon写线程, 满则丢弃, 事件循环零同步stdout写); log_and_print 与 action_handler/main/config 裸print 收口点统一复用(根治 case09 挂起) | 小欧 |
| v3.12 | 2026-08-25 16:30:00 | 合规重构(北京老陈驱动): ①新增 3.3 Agent层 handlers/sandbox_gate.py(sandbox_precheck/sandbox_resolve, 从 action_handler 嵌套闭包拆出, 去隐式耦合/分层落点); ②1.2 display_utils.py 新增 format_llm_data_text(从 action_handler.build_observation 内嵌闭包拆出的纯展示格式化函数, 全局层复用优先); 两处均逻辑零改动(复制不重写)、登记本清单、action_handler 去内联与死 import | 小欧 |
| v3.11 | 2026-08-24 12:19:40 | 目录前导(北京老陈裁定): file_persist 新增常量 SESSION_DIR_PREFIX="Sion_" / TASK_DIR_PREFIX="Task_"(唯一源, DRY); 物理目录(TaskFileWriter._dir/purge_task/purge_session)与 chat_tasks.files_dir 落库锚(stream_orchestrator 编排⑨)全部经常量同源拼装, 排查定位链不断; 旧目录不迁移不兼容(禁止backward) | 小欧 |
| v3.10 | 2026-08-24 11:53:30 | 后端卡死修复收尾: ①action_handler check_safety_and_confirm 的 session 反查+信任预查(2处)、stream_orchestrator 编排③链根/⑤DB兜底user_msg_id/⑥sessionModel(3处) 同步 db.get_conn(_with_retry) 改经 atxn offload; ②hitl_confirmation resolve_confirmation(同步函数)信任落库旁路块改 daemon 线程投递(fire-and-forget 语义不变); ③agent_runner 新增模块内私有 _persist_final(shield薄壳, 包 finalize/update_task 两处终态写防二次cancel, 非公用函数不单列条目)。全部复用 v3.9 atxn 既有薄壳, 零新抽象 | 小欧 |
| v3.9 | 2026-08-24 10:30:00 | 新增 3.3 数据库SDK(app/db/database.py): atxn/_run_txn 异步事务壳(整段 get_conn 进 to_thread 子线程, 将同步 sqlite3 I/O + 锁重试 time.sleep offload 出事件循环, 根治后端卡死); 同步 3.2 已登记落库函数统一经 atxn 调用边界 offload | 小欧 |
| v3.8 | 2026-08-22 14:10:48 | 3.2 新增 fetch_session_user_message_pairs（北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 从 chat_user_message LEFT JOIN chat_tasks 重建"用户消息+其配对AI回答"有序列表, 供 get_session_messages/_load_previous_messages/execution_stream 复用, DRY/复用优先; 不含 execution steps）; 更正 load_execution_steps 描述(v2.0 起不再回退 chat_messages) | 小欧 |
| v3.7 | 2026-08-22 10:40:00 | 新增 九、E2E测试层 章节: 登记 e2e_helpers.verify_db_tool_usage（19个case曾复制粘贴旧action_tool取数块, §10.3模型变更即全量碎裂; 收敛单点校验入口, case瘦身为2行调用, 先查后建禁止重造） | 小欧 |
| v3.6 | 2026-08-20 20:17:29 | 补登记 3.2 步骤存储(storage.py) 11.1 token 四层同构累计公用函数 5 个: query_task_accumulation/query_session_accumulation/query_chain_accumulation/update_task_accumulation/update_session_accumulation（供 react_cycle 每轮即时落库、agent_runner S2、token_usage API 复用；先查后建, 禁止重造） | 小欧 |
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
