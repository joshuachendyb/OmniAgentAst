
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小沈 - OBS_MAX_DISPLAY_ITEMS/MAX_SEARCH_RESULTS 注释更新(grep上限与条目数统一)
# 2026-07-15 - 小欧 - 常量归一化治理: 新增 B组【系统级】(OBS_SNIPPET/HTML/SYSINFO)与 C组【tool级】(SHELL_OUTPUT/WEB_FETCH/SEARCH_SNIPPET/XLSX/HTTP/DOWNLOAD/WRITE_TEXT), 各常量统一标注【使用对象】便于识别废弃
# 2026-07-15 - 小欧 - HTTP常量归并: HTTPX_TIMEOUT_DEFAULT+TOOL_BROWSER_UA+TOOL_RETRYABLE_HTTP_CODES 从1.1/10节移至第4节(网络工具HTTP常量), 消除散落
# 2026-07-15 - 小欧 - TOOL_RETRY_CONFIG 从 tool_retry_engine.py 迁入第4节, 与 TOOL_RETRYABLE_HTTP_CODES 相邻
# 注: 本文件数值型长度/上限/阈值常量均标注【使用对象】, 搜全仓无引用的即为候选废弃常量(待清理)
# 2026-07-18 - 小欧 - TOOL_TIMEOUTS清理死键(合并的window_maximize/minimize/clipboard_read/write等),补真实注册名(set_window_state/clipboard)
# 2026-07-20 - 小欧 - grep 门限治理:
#   1. 删 MAX_SEARCH_FILE_SIZE(无引用)
#   2. 新增 OBS_GREP_MAX_ROWS=200
#     /OBS_GREP_MAX_ROW_CHARS=150
# 2026-07-20 - 小欧 - shell 门限治理(章6.4):
#   1. 新增 OBS_SHELL_MAX_ROWS=200
#     /OBS_SHELL_MAX_ROW_CHARS=1000
#   2. SHELL_OUTPUT_MAX_CHARS 标记已作废
# 2026-07-20 - 小欧 - find 门限治理(章7.4):
#   1. 新增 OBS_FIND_MAX_ROWS=200
#     /OBS_FIND_MAX_ROW_CHARS=300
#   2. 删 FIND_PAGE_SIZE/MAX_SEARCH_RESULTS
# 2026-07-20 - 小欧 - searchweb 门限治理(章8.4):
#   1. 新增 OBS_SEARCHWEB_MAX_ROWS=100
#     /OBS_SEARCHWEB_MAX_ROW_CHARS=500
#   2. 删 SEARCH/OBS_SNIPPET_MAX_CHARS
# 2026-07-20 - 小欧 - httpget 门限治理(章9.4):
#   1. 新增 OBS_HTTPGET_MAX_ROWS=200
#     /OBS_HTTPGET_MAX_ROW_CHARS=1000
#   2. HTTP_JSON_PREVIEW_MAX_BYTES 改名
#     INER_HTTPGET_JSON_PREVIEW_MAX_BYTES
# 2026-07-20 - 小欧 - fetchpage 门限治理(章10.4):
#   1. 新增 OBS_FETCHPAGE_MAX_ROWS=200
#     /OBS_FETCHPAGE_MAX_ROW_CHARS=500
#   2. 删 WEB_FETCH_MAX_CHARS
#   3. MAX_READ_BYTES/MAX_CONTENT_LENGTH 改名
# 2026-07-20 - 小欧 - readtext 门限治理(章11.4):
#   1. 新增 OBS_READTEXT_MAX_ROWS=200
#     /OBS_READTEXT_MAX_ROW_CHARS=1000
#   2. 去 _select_lines max_line_length 截断
#   3. MAX_READ_SIZE 改名 INER_READTEXT_READ_SIZE
# 2026-07-20 - 小欧 - 门限复查:
#   1. 删僵尸常量 FIND_PAGE_SIZE
#   2. 删 READ_FILE_DEFAULT_LIMIT(无引用)
#   3. 依3.6直接删定义不保留占位
# 2026-07-20 - 小欧 - httpget ②修复:
#   1. 新增 INER_HTTPGET_DATA_PREVIEW_MAX_CHARS
#     =200KB(data内联预览上限)
#   2. INER_HTTPGET_JSON_PREVIEW_MAX_BYTES 下调5MB
# 2026-07-20 - 小欧 - 自然单位治理:
#   1. 新增 OBS_PDF_MAX_ROWS/CHARS
#   2. 新增 OBS_PPTX_MAX_ROWS/CHARS(单页)
#   3. 新增 OBS_TREE_MAX_ROWS/CHILDREN
#   4. 新增 INER_READ_PDF_MAX_PAGES=200
# 2026-07-21 - 小欧 - 第二阶段门限治理:
#   1. TOOL_TIMEOUTS default 120→30(未注册tool缺省超时)
#   2. 新增 OBS_ANALYZE_MAX_ROWS=100/OBS_ANALYZE_MAX_COLS=100(analyze_data行×列收口)
# 2026-07-21 - 小欧 - 字节安全治理: 新增 INER_READ_DOCX_MAX_BYTES/PPTX_MAX_BYTES/XLSX_MAX_BYTES/PDF_MAX_BYTES 常量; 移除 INER_READ_XLSX_MAX_ROWS/INER_READ_PDF_MAX_PAGES(改为参考值,非截断门限)
# 2026-07-22 - 小欧 - OBS_READTEXT_MAX_ROW_CHARS 1000→2000 对齐 opencode-old MaxLineLength
# 2026-07-22 - 小欧 - OBS_LISTDIR_MAX_ROWS 200→500 对齐 opencode-old ls 输出量级
# 2026-07-22 - 小欧 - OBS_READTEXT_MAX_ROWS 200→1000 对标 opencode-old DefaultReadLimit=2000
# 2026-07-23 - 小欧 - 北京老陈驱动: 新增 SHELL_OUTLIMIT_STDOUT_MAX_CHARS=50000
#         /SHELL_OUTLIMIT_STDERR_MAX_CHARS=20000 (shell输出截断)
#         注意: OBS_SHELL_MAX_ROWS×OBS_SHELL_MAX_ROW_CHARS=200K
#         展示上限, tool截断50K目前保守对齐, 试用后调
# 2026-07-23 - 小欧 - 北京老陈驱动: 新增 XLSX_OUTLIMIT_ROWS_MAX=1000
#         /XLSX_OUTLIMIT_CELL_CHARS=500 (xlsx输出截断)
#         注: 多 sheet 结构走 #21 fallback, 不受影响
# 2026-07-23 - 小欧 - 北京老陈驱动: 新增 GREP_OUTLIMIT_MATCHES_MAX=2000
#         /GREP_OUTLIMIT_MATCH_CONTENT_CHARS=2000 (grep输出截断)
# 2026-07-23 - 小欧 - 北京老陈驱动: 硬安全网降配
#    INER_FETCHPAGE_READ_BYTES 5MB→2MB(流式截断)
#    INER_FETCHPAGE_MAX_CONTENT_LENGTH 100MB→10MB(Content-Length拒绝)
#    INER_HTTPGET_JSON_PREVIEW_MAX_BYTES 5MB→2MB(JSON预览截断)
# 2026-07-23 - 小欧 - 北京老陈驱动: INER_前缀两分法重构
#    输入闸门 {TOOL}_INPUT_*: READTEXT/EDITTEXT/READMEDIA/READ_PDF/READ_DOCX/READ_PPTX/READ_XLSX/FETCHPAGE_INPUT_MAX_CONTENT_LENGTH/DOWNLOAD/CLIPBOARD
#    输出截断 {TOOL}_OUTLIMIT_*: SHELL_OUTLIMIT_RAW_BYTES/FETCHPAGE_OUTLIMIT_BODY_BYTES/HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES/HTTPGET_OUTLIMIT_DATA_PREVIEW_CHARS/READ_PDF_OUTLIMIT_DEFAULT_PAGES
# 2026-07-23 - 小欧 - 北京老陈驱动: 删 READTEXT/READ_DOCX/READ_PPTX/READ_PDF_INPUT_MAX_BYTES(字节门→全量读+outlimit截断)
#         新增 READTEXT_OUTLIMIT_CHARS/READ_DOCX_OUTLIMIT_CHARS/READ_PPTX_OUTLIMIT_CHARS=500K
# 2026-07-23 - 小欧 - 北京老陈驱动: 删 SHELL_OUTLIMIT_RAW_BYTES(10MB 读/解码层硬安全网, 50K/20K 存储截断足够, 去掉叠床架屋)
# 2026-07-23 - 小欧 - 三堂会审5bug修复: read_text_file/read_docx outlimit len截断后求值+read_pptx total_slides/notes_data截断同步+删_os_mod死import
# 2026-07-24 - 小欧 - 新增: EXECUTE_SQL_OUTPARM_LIMIT_SQL / QUERY_SQL_OUTPARM_LIMIT_SQL(SQL预览截断) + OBS_QUERY_SQL_PREVIEW_COLUMNS(列名预览)
# 2026-07-24 - 小欧 - 新增: SEARCH_WEB_OUTPARM_LIMIT_RAW / FETCH_WEBPAGE_OUTPARM_LIMIT_DESC / GENERATE_CHART_OUTPARM_LIMIT_DATA / FILTER_DATA_OUTPARM_LIMIT_CONDITIONS / GET_DB_SCHEMA_OUTPARM_LIMIT_TABLES / TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS(魔数→命名常量)
# 2026-07-25 - 小欧 - 新增第2批 outparam/iner 常量: SEND_NOTIFICATION_OUTPARM_LIMIT_MSG / EXECUTE_SHELL_OUTPARM_LIMIT_CMD / WRITETEXT_INER_PREVIEW_CHARS / READTEXT_INER_CJK_SAMPLE / TOOL_SEARCH_INER_RESULTS_TOP / SEARCH_WEB_INER_HTML_PARSE / QUERY_SQL_INER_LOG_SQL
# 2026-07-25 - 小欧 - 三堂会审修复bug×2:
#         ① EXECUTE_SHELL_OUTPARM_LIMIT_CMD误归# fundamental→改# shell
#         ② TOOL_SEARCH_INER_RESULTS_TOP误归# file/internal→改# fundamental/internal
# 2026-07-26 - 小欧 - hint_for_data_error: 前移pandas errors(EmptyDataError/ParserError/OutOfBoundsDatetime)至ValueError前修复截胡bug; 新增MemoryError分类提示
# 2026-07-26 - 小欧 - OOD: 删 READMEDIA_INPUT_MAX_BYTES、READ_XLSX_INPUT_MAX_BYTES 两行
# 2026-07-26 - 小欧 - 迁移: sql_error_hint/hint_for_data_error迁至file_path_checker(同属检查类), 与常量文件解耦
# 2026-07-26 - 小欧 - 注: 上数第2条(hint_for_data_error pandas errors前移)对应函数已迁至file_path_checker, 本文件不再持有
# 2026-07-26 - 小沈 - 超时统一: SUBPROCESS_TIMEOUT_SHORT/DEFAULT 注释修正(涵义准确定位taskkill/命令查找); DEFAULT_TIMEOUT_SEC 注释从"网络工具"扩为"通用工具"
# 2026-07-26 - 小欧 - 常量区块重组: 全文件13节连续编号1-13, 消除空节(原第8节), 消除跳跃(缺第5节), 消除重复(原第4节与第3节重复HTTP常量), 归并可重试码与per-tool配置至第11节(重试), 移动SENSITIVE_FIELDS至第9节(内容质量), 恢复FILE_OPERATION_TOOLS(此前编辑误删)
# 2026-07-29 - 小沈 - TOOL_TIMEOUTS["delete"]=120; 新增TOOL_TIMEOUT_HINTS超时hint字典(仅含无timeout参数tool); TOOL_TIMEOUTS去除有timeout参数tool(shell/httpget/fetchpage/download/compress); listdir注册名对齐(list_directory→listdir),值30→60
# 2026-07-30 - 小沈 - TOOL_TIMEOUT_HINTS加compress: 有timeout参数的tool也可能被保险丝截杀,内部timed_out路径来不及时返回,引擎TIMEOUT路径直接给hint避免LLM收到空串
# 2026-07-30 - 小沈 - 新增 SHELL_POOL_IDLE_TIMEOUT=300: Shell池空闲超时兜底(防孤魂野鬼), 实例release回池后超过此值无人acquire则close
# 2026-08-05 - 小欧 - 设计约定补齐: 移除 TOOL_TIMEOUTS 里的 ping_port(60)
#   【病根】ping_port 的 schema 用 NetworkDiagnoseInput 含 timeout 参数, 属"有 timeout 参数"工具,
#   按约定应移出 TOOL_TIMEOUTS(与 compress/shell/httpget/fetchpage/download 一致), 漏网遗留在表内(60)
#   【影响】移除后 ping_port 未传 timeout 时 base 由显式60变为default 60, 值不变; 内部默认timeout仅5s,
#   保险丝恒远大于内部, 无功能变化 —— 纯设计一致性清理
# 2026-08-12 - 小欧 - 僵尸常量清理: 删除137个全仓无引用的ERR_*僵尸常量(原239个顶层常量→剩102个),
#   逐条按分类小节(文件/Shell/参数/Meta/网络/系统/注册表/桌面/文档/数据/迁移补充)删除, 保留全部活常量;
#   删除后py_compile通过, 全部工具ensure_tools_registered()注册成功, 活常量均有工具真实引用(REF>=1),
#   唯一含已删常量名的backend/scripts/fix_error_codes.py为一次性迁移脚本(FIXES字符串对照表,纯文本替换,不依赖本文件常量)
"""
【工具层常量】— 工具函数运行时常量集中管理 — 北京老陈 2026-05-30

定义：执行具体工具的执行层。
文件：app/tools/network/http_request.py、app/tools/tool_error_classifier.py、
      app/services/agent/tool_retry_engine.py、app/utils/sys_error_classifier.py
职责：执行工具、捕获工具异常、判断工具能否重试
错误分类器：ToolErrorClassifier（不看 HTTP 状态码数字，只看异常类型名。
  HTTPStatusError → 不管 400/429/500 → 统一归为 ToolErrorCategory.NETWORK）

所有工具函数本身运行时需要的常量统一定义在此。
与系统层常量文件 constants.py 严格分开，两层互不引用。

分层原则：
  - 本文件（tool_constants.py）：工具层。TOOL_HTTP_* 是工具自己判断重试用的拷贝，
    TOOL_TIMEOUTS 等是工具运行参数。不引用 constants.py 的系统层 SYS_HTTP_*。
  - constants.py：系统层。SYS_HTTP_* 是 HTTP 协议事实定义，
    供 SystemErrorClassifier 和 LLM 客户端使用。

禁止：
  ❌ 本文件 import constants.py 的任何内容
  ❌ 本文件的常量被系统层代码引用（系统层应引用 constants.py 的 SYS_* 常量）
"""

# ============================================================
# 🕐 1. 工具级保险丝超时（TOOL_TIMEOUTS）— 【工具层】
#     每个工具的"最大允许执行时间"。
#     作用：ToolRetryEngine 用 asyncio.wait_for(timeout=此值) 做保险丝，
#           超时则强制掐断（asyncio.TimeoutError → 重试/报错）。
#     与系统层 SYS_DEFAULT_LLM_TIMEOUT（LLM 客户端超时）完全无关。
#     警告：修改此值会影响重试引擎的超时行为。
# ============================================================

TOOL_TIMEOUT_HINTS = {  # tool 超时时的 LLM hint，指引 LLM 缩小范围重试 — 小沈 2026-07-29 — 小沈 2026-07-30 compress例外加入
    # 原则上只收录「无 timeout 参数」的 tool。compress例外: zf.write()内部I/O卡住时保险丝先于内部timed_out返回,
    # 引擎TIMEOUT路径必须直接给hint,否则LLM收到空串无操作指引。
    "delete": "删除操作超时（120秒），部分文件可能已被删除。建议缩小删除范围：分批删除或指定文件路径后重试。可以先 list_directory 查看剩余文件。",
    "writetext": "文件写入超时，可能内容过大或磁盘繁忙。建议分批写入或检查磁盘状态后重试。",
    "edittext": "文件编辑超时，可能文件过大。建议直接重写整个文件或减小修改范围。",
    "readmedia": "媒体读取超时，可能文件损坏或过大。建议检查文件完整性后重试。",
    "searchweb": "搜索超时，可能搜索服务不稳定。建议简化搜索词后重试。",
    "compress": "压缩超时，目标目录可能过大或包含超大文件。建议：①增大timeout参数重试；②添加exclude_patterns排除大文件；③将大目录分成多个子目录分批压缩。",
}

TOOL_TIMEOUTS = {  # 【tool 级】使用对象: 保险丝超时（ToolRetryEngine 用 asyncio.wait_for 杀整个工具调用）
    # 每个 key=工具注册名, value=最大秒数, 超时整个工具调用被强制终止并走重试/报错。
    # 仅保留真实注册工具名; 已合并的 window_maximize/minimize、clipboard_read/write 等死键删除 — 小欧 2026-07-18
    "listdir": 60,
    "find": 120,
    "grep": 120,
    "readmedia": 60,
    "edittext": 60,
    "tree": 120,
    "session": 60,
    "event_log": 60,
    "searchweb": 60,
    "window_info": 20,
    "window_focus": 20,
    "window_resize": 20,
    "set_window_state": 20,
    "window_restore": 20,
    "window_topmost": 20,
    "window_unpin": 20,
    "mouse_click": 20,
    "mouse_move": 20,
    "mouse_scroll": 20,
    "mouse_position": 10,
    "clipboard": 10,
    "timenow": 10,
    "timeadd": 10,
    "timediff": 10,
    "calendar": 30,
    "timer": 60,
    "timer_set": 10,
    "timer_clear": 10,
    "timer_list": 10,
    "delete": 120,
    "default": 60,
}

# ============================================================
# 🕐 2. 子进程内部操作超时（SUBPROCESS_TIMEOUT_*）— 【工具层】
#     与区块1的区别：区块1杀的是"整个工具调用"（保险丝），这里是杀"工具内部
#     某个具体的 subprocess.run/proc.wait 原子操作"。
#     值必须很小（3~60秒），因为只是等一个原子操作完成，不是等整个工具。
# ============================================================

SUBPROCESS_TIMEOUT_DEFAULT: int = 10    # 【tool 级】使用对象: 通用 subprocess 执行超时, 如 where/which 命令查找
SUBPROCESS_TIMEOUT_SHORT: int = 5       # 【tool 级】使用对象: 短时 subprocess(taskkill 进程树清理、kill 后等待退出)
SUBPROCESS_TIMEOUT_VERY_SHORT: int = 3  # 【tool 级】使用对象: 极短 subprocess(process wait)
SUBPROCESS_TIMEOUT_LONG: int = 60       # 【tool 级】使用对象: 长时 subprocess(文档转换等耗时操作)

# 持久Shell池空闲超时(秒): 实例放回池后超过此值无人acquire则close, 防孤魂野鬼 — 小沈 2026-07-30
SHELL_POOL_IDLE_TIMEOUT: int = 300

# ============================================================
# 🕐 3. HTTP/网络请求超时+默认值（HTTPX/DEFAULT_TIMEOUT）— 【工具层】
#     与区块1/2的区别：
#       区块1：杀整个工具调用（保险丝）
#       区块2：杀 subprocess 内部原子操作（进程等待）
#       区块3：杀 HTTP(S) 网络请求（httpx 超时），以及
#              DEFAULT_TIMEOUT_SEC 作为工具函数 timeout 参数默认值（当用户没传时用）
# ============================================================

# httpx 单次 HTTP 请求超时(秒)
HTTPX_TIMEOUT_DEFAULT: float = 5.0        # 【tool 级】使用对象: 工具内部 httpx.get/post 等请求超时(秒)

# 工具函数参数默认值(秒)，当工具没有收到用户传入的 timeout 参数时使用此值
DEFAULT_TIMEOUT_SEC: float = 30.0             # 【tool 级】使用对象: 工具函数 timeout 参数的默认值(秒), 如 shell/network/数据库等
NETWORK_MAX_CONNECTIONS: int = 100             # 【tool 级】使用对象: network 工具 httpx 连接池最大连接
NETWORK_MAX_KEEPALIVE: int = 20                # 【tool 级】使用对象: network 工具 httpx 连接池 keepalive 连接数

# ============================================================
# 🕐 4. 系统级观察截断（OBS_*）— 【系统级】
#     observation_formatter.py 统一使用的显示域截断常量。
#     与 tool 层面的输入闸门/输出截断相互独立。
#     老陈 2026-07-15 裁定: 因与 tool 输出耦合紧历史置于本文件, 标注【系统级】以区分。
# ============================================================

OBS_MAX_DISPLAY_ITEMS: int = 200       # 【系统级】使用对象: observation_formatter.py(所有 list 类 handler 最大条目数; grep 搜索总开关) — 小沈 2026-07-14
# —— listdir 专属观察截断常量（显示域行×列；Tool 层 LISTDIR_PAGE_SIZE 依3.7作废, listdir 有 offset 可翻页, 显示域截断可恢复） ——
OBS_LISTDIR_MAX_ROWS: int = 500         # 【系统级】使用对象: observation_formatter.py(_format_entries listdir 条目数上限, 匹配型短状态行)
OBS_LISTDIR_MAX_ROW_CHARS: int = 300    # 【系统级】使用对象: observation_formatter.py(_format_entries listdir 单行上限, 深路径保文件名)
OBS_MAX_STRING_LENGTH: int = 1000     # 【系统级】使用对象: observation_formatter.py(单个字符串值最大显示长度)
OBS_DICT_MAX_KEYS: int = 100           # 【系统级】使用对象: observation_formatter.py(_format_key_value 最大键数)
# —— 以下 B 组: 原 observation_formatter.py 内硬编码, 迁入统一(【系统级】) ——
OBS_HTML_SUMMARY_MAX_CHARS: int = 500  # 【系统级】使用对象: observation_formatter.py(HTML→纯文本摘要上限; 原 _extract_html_summary max_len)
OBS_SYSINFO_FIELD_MAX_CHARS: int = 120 # 【系统级】使用对象: observation_formatter.py(sysinfo 每节字段值截断)

# —— grep 专属观察截断常量（显示域行×列；工具输出不做条数/大小限制，唯一收口于此） ——
OBS_GREP_MAX_ROWS: int = 200            # 【系统级】使用对象: observation_formatter.py(_format_matches grep 行数上限)
OBS_GREP_MAX_ROW_CHARS: int = 150       # 【系统级】使用对象: observation_formatter.py(_format_matches grep 单行上限)

# —— shell 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_SHELL_MAX_ROWS: int = 200           # 【系统级】使用对象: observation_formatter.py(_format_shell_result shell 行数上限, 自由文本档)
OBS_SHELL_MAX_ROW_CHARS: int = 1000     # 【系统级】使用对象: observation_formatter.py(_format_shell_result shell 单行上限, 长日志/JSON 自由文本, 禁止150盲截尾部)



# —— find 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_FIND_MAX_ROWS: int = 200            # 【系统级】使用对象: observation_formatter.py(_format_find_results find 行数上限)
OBS_FIND_MAX_ROW_CHARS: int = 300       # 【系统级】使用对象: observation_formatter.py(_format_find_results find 单行上限)

# —— searchweb 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_SEARCHWEB_MAX_ROWS: int = 100       # 【系统级】使用对象: observation_formatter.py(_format_items searchweb 行数上限)
OBS_SEARCHWEB_MAX_ROW_CHARS: int = 500  # 【系统级】使用对象: observation_formatter.py(_format_items searchweb snippet/单行上限)

# —— httpget 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_HTTPGET_MAX_ROWS: int = 200          # 【系统级】使用对象: observation_formatter.py(_format_httpget_result httpget 行数上限, 结构化型保JSON不盲截)
OBS_HTTPGET_MAX_ROW_CHARS: int = 1000    # 【系统级】使用对象: observation_formatter.py(_format_httpget_result httpget 单行上限, 保JSON不盲截)

# —— fetchpage 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_FETCHPAGE_MAX_ROWS: int = 200         # 【系统级】使用对象: observation_formatter.py(_format_fetchpage_result fetchpage 行数上限)
OBS_FETCHPAGE_MAX_ROW_CHARS: int = 500    # 【系统级】使用对象: observation_formatter.py(_format_fetchpage_result fetchpage 单行上限)

# —— readtext 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_READTEXT_MAX_ROWS: int = 1000        # 【系统级】使用对象: observation_formatter.py(_format_readtext_result readtext 行数上限, 对标 opencode-old DefaultReadLimit=2000)
OBS_READTEXT_MAX_ROW_CHARS: int = 2000  # 【系统级】使用对象: observation_formatter.py(_format_readtext_result readtext 单行上限, 对标 opencode-old MaxLineLength=2000)

# —— edittext 专属观察截断常量（显示域行×列；diff 为大文本, Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_EDITTEXT_MAX_ROWS: int = 200        # 【系统级】使用对象: observation_formatter.py(_format_edittext_result edittext 行数上限)
OBS_EDITTEXT_MAX_ROW_CHARS: int = 1000  # 【系统级】使用对象: observation_formatter.py(_format_edittext_result edittext 单行上限, 长行放宽至1000减少截断)

# —— 读取类工具「按被读物自然单位」观察截断常量（2026-07-20 小欧 自然单位治理: PDF=页 / DOCX=段落 / PPTX=幻灯片 / tree=层级 / clipboard=文本行）
#     设计原则: 显示域窗口以介质自然单位为粒度(如 PDF 前几页、PPTX 整本提纲), 非盲目按行数一刀切; 截断均可由原单位取回(page=N/slide=N/进子目录/offset段落)
OBS_PDF_MAX_ROWS: int = 150            # 【系统级】使用对象: observation_formatter.py(_format_pdf_result PDF 显示行数上限, ≈前3页起头, 保留 "--- 第 N 页 ---" 页标记)
OBS_PDF_MAX_ROW_CHARS: int = 1000      # 【系统级】使用对象: observation_formatter.py(_format_pdf_result PDF 单行上限)
#   注: DOCX/clipboard 无页码, 复用 OBS_READTEXT_MAX_ROWS/CHARS(段落/文本行窗口, 与人类读 Word/文本方式一致), 不另增 OBS_DOCTEXT_*(避免死代码)
OBS_PPTX_MAX_ROWS: int = 60            # 【系统级】使用对象: observation_formatter.py(_format_slides PPTX 单张幻灯片正文行数上限, 幻灯片本短, 仅超长单页收口)
OBS_PPTX_MAX_ROW_CHARS: int = 1000     # 【系统级】使用对象: observation_formatter.py(_format_slides PPTX 单行上限)
OBS_TREE_MAX_ROWS: int = 100           # 【系统级】使用对象: observation_formatter.py(_format_tree tree 显示总行数上限, 层级感知: 与 max_depth + 每节点子项封顶配合, 非盲目行数)
OBS_TREE_MAX_CHILDREN: int = 50        # 【系统级】使用对象: observation_formatter.py(_format_tree 每个目录节点最多展示的子项数, 超出标 "…还有 N 个", 类资源管理器)
# —— analyze_data 专属观察截断常量（显示域行×列；转置表格，分组统计结果可能很大） —— 2026-07-21 小欧
OBS_ANALYZE_MAX_ROWS: int = 100        # 【系统级】使用对象: observation_formatter.py(_format_analyze_data 分组显示行数上限)
OBS_ANALYZE_MAX_COLS: int = 100        # 【系统级】使用对象: observation_formatter.py(_format_analyze_data 分组显示列数上限)

# —— query_sql 专属列名预览常量（show columns/top N preview）
OBS_QUERY_SQL_PREVIEW_COLUMNS: int = 5   # 【系统级】使用对象: query_sql.py(列名预览上限, summary + metrics)

# 注: readmedia 的 base64 为二进制编码, 非可读文本, 不按文本行×列处理(章13.4 用户裁定回退为仅元数据+base64字符数摘要),
#     故不新增 OBS_READMEDIA_* 常量(避免死代码); 若后续 readmedia 改返回转写文本, 再补 OBS_READMEDIA_* + 行×列 handler

# ============================================================
# 🕐 5. 工具 输入闸门 / 输出截断 — 小欧 2026-07-23 两分法重构
#     输入闸门 {TOOL}_INPUT_*     — 进门前拒绝(文件太大不读/请求太大不下)
#     输出截断 {TOOL}_OUTLIMIT_*  — tool 返回前截断(format前)
#     内阻常量 {TOOL}_INER_*      — tool 内部使用(预览/采样/日志)
#     (原 INER_ 前缀废弃, 依 3.4→3.5 改名后, 2026-07-23 再按两分法改名)
# ============================================================
# —— 输入闸门 {TOOL}_INPUT_* ——
EDITTEXT_INPUT_MAX_BYTES: int = 10 * 1024 * 1024     # 使用对象: edit_text_file.py(编辑前文件字节上限, 超则拒绝)
FETCHPAGE_INPUT_MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 使用对象: fetch_webpage.py(Content-Length 超阈值拒绝下载)
DOWNLOAD_INPUT_MAX_BYTES: int = 1 * 1024 * 1024 * 1024     # 使用对象: download_file.py(下载文件大小上限, 超则拒绝)
CLIPBOARD_INPUT_MAX_CHARS: int = 200 * 1024          # 使用对象: clipboard_control.py(剪贴板读取最大字符数, 超则截断)

# —— 输出截断 {TOOL}_OUTLIMIT_* ——
# shell
SHELL_OUTLIMIT_STDOUT_MAX_CHARS: int = 50000          # 使用对象: execute_shell_command.py(shell stdout 输出字符上限, 超则截断)
SHELL_OUTLIMIT_STDERR_MAX_CHARS: int = 20000          # 使用对象: execute_shell_command.py(shell stderr 输出字符上限, 超则截断)
# xlsx
XLSX_OUTLIMIT_ROWS_MAX: int = 1000                    # 使用对象: read_xlsx.py(读取 Excel 行数上限, 超此截断)
XLSX_OUTLIMIT_CELL_CHARS: int = 500                   # 使用对象: read_xlsx.py(单格字符串字符上限, 超此截断)
# grep
GREP_OUTLIMIT_MATCHES_MAX: int = 2000                 # 使用对象: grep_file_content.py(匹配条目数上限, 超此截断)
GREP_OUTLIMIT_MATCH_CONTENT_CHARS: int = 2000         # 使用对象: grep_file_content.py(单条匹配 content/before/after 字符串字符上限, 超此截断)
# network
FETCHPAGE_OUTLIMIT_BODY_BYTES: int = 2 * 1024 * 1024 # 使用对象: fetch_webpage.py(流式读取正文上限, 超则截断)
HTTPGET_OUTLIMIT_JSON_PREVIEW_BYTES: int = 2 * 1024 * 1024   # 使用对象: http_request.py(JSON body 预览截断)
HTTPGET_OUTLIMIT_DATA_PREVIEW_CHARS: int = 200 * 1024        # 使用对象: http_request.py(data内联预览字符上限)
# document/text
READTEXT_OUTLIMIT_CHARS: int = 500 * 1024             # 使用对象: read_text_file.py(文本内容字符上限, 超则截断)
READ_DOCX_OUTLIMIT_CHARS: int = 500 * 1024            # 使用对象: read_docx.py(DOCX文本字符上限, 超则截断)
READ_PPTX_OUTLIMIT_CHARS: int = 500 * 1024            # 使用对象: read_pptx.py(PPTX全部幻灯片文本字符上限, 超则截断)
# document
READ_PDF_OUTLIMIT_DEFAULT_PAGES: int = 200            # 使用对象: read_pdf.py(未传page时的默认读取页数, 超则截断)
# sql
EXECUTE_SQL_OUTPARM_LIMIT_SQL: int = 100              # 使用对象: execute_sql.py(SQL params/target 预览截断, 主函数入口统一截断)
QUERY_SQL_OUTPARM_LIMIT_SQL: int = 100                # 使用对象: query_sql.py(SQL params/target 预览截断, 主函数入口统一截断)
# network
SEARCH_WEB_OUTPARM_LIMIT_RAW: int = 200               # 使用对象: search_web.py(raw_text/str(e)日志/error截断)
FETCH_WEBPAGE_OUTPARM_LIMIT_DESC: int = 300            # 使用对象: fetch_webpage.py(metadata描述字段截断)
# chart/data
GENERATE_CHART_OUTPARM_LIMIT_DATA: int = 200           # 使用对象: generate_chart.py(chart data params/detail 预览截断)
FILTER_DATA_OUTPARM_LIMIT_CONDITIONS: int = 200        # 使用对象: filter_data.py(conditions params 预览截断)
# db schema / timer (preview count)
GET_DB_SCHEMA_OUTPARM_LIMIT_TABLES: int = 5            # 使用对象: get_db_schema.py(metrics表名预览数量)
TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS: int = 5            # 使用对象: timer_list.py(params timer_id 预览数量)
# fundamental
SEND_NOTIFICATION_OUTPARM_LIMIT_MSG: int = 50          # 使用对象: send_notification.py(message params预览截断)
# shell
EXECUTE_SHELL_OUTPARM_LIMIT_CMD: int = 50              # 使用对象: execute_shell_command.py(cmd_short命令预览截断)
# file/internal
WRITETEXT_INER_PREVIEW_CHARS: int = 50                 # 使用对象: write_text_file.py(文首文末预览字符数)
READTEXT_INER_CJK_SAMPLE: int = 100                    # 使用对象: read_text_file.py(CJK检测采样字符数)
# fundamental/internal
TOOL_SEARCH_INER_RESULTS_TOP: int = 10                 # 使用对象: tool_search.py(搜索结果top N)
# network/internal
SEARCH_WEB_INER_HTML_PARSE: int = 3000                 # 使用对象: search_web.py(Bing HTML解析片段限制)
# sql/internal
QUERY_SQL_INER_LOG_SQL: int = 50                       # 使用对象: query_sql.py(logger SQL截断)
# file/edit
EDITTEXT_OUTPARM_LIMIT_OLD: int = 80                   # 使用对象: edit_text_file.py(old_string params/detail统一截断)
EDITTEXT_OUTPARM_LIMIT_NEW: int = 50                   # 使用对象: edit_text_file.py(new_string params统一截断)
EDITTEXT_OUTPARM_LIMIT_SAFETY: int = 200               # 使用对象: edit_text_file.py(safety_hint hint统一截断)

# ============================================================
# 🕐 6. 文件工具配置（FILE_OPERATION_TOOLS / BINARY / SKIP_DIRS）— 【工具层】
#     从 file_tools.py / BINARY_EXTENSIONS / SKIP_DIRS 迁移。
#     文件工具运行时的参数，仅工具代码使用。
# ============================================================

FILE_OPERATION_TOOLS: set[str] = {  # 【tool 级】使用对象: 文件操作类工具集合(安全/分批判定)
    "readtext", "writetext", "edittext",
    "move", "copy", "delete", "rename",
    "compress", "extract",
}

# 注: LISTDIR_PAGE_SIZE(原 listdir 分页每页条目数) 依3.7作废删除(2026-07-20 章18): Tool 层条数截断违反3.7, 改由 Format 层 OBS_LISTDIR_* 行×列收口; listdir 有 offset 可翻页, 显示域截断可恢复(区别于 read_xlsx 无offset)
# 注: FIND_PAGE_SIZE/READ_FILE_DEFAULT_LIMIT 依门限复查(2026-07-20)删除: 全代码检索仅定义处存在, 无任何工具引用(僵尸常量);
#      find 分页已由 OBS_FIND_MAX_ROWS 取代、file 读取默认行数已由 INER_READTEXT_READ_SIZE/INER_EDITTEXT_READ_SIZE 取代, 二者均不再使用

# 二进制文件扩展名 — 小健 2026-06-24 更新：补充媒体扩展名
BINARY_EXTENSIONS: set[str] = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.tif', '.svg',
    '.heic', '.heif',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4a', '.ogg',
    '.flac', '.aac', '.wma', '.mid', '.midi', '.webm',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
    '.exe', '.msi', '.dll', '.so', '.dylib',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf',
    '.odt', '.ods', '.odp', '.rtf',
}  # 【tool 级】使用对象: 文本工具(readtext/writetext/edittext)拒绝二进制文件扩展名集合

SKIP_DIRS: frozenset[str] = frozenset({
    'node_modules', 'bower_components',
    '.git', '.svn', '.hg', '__pycache__',
    '.next', '.nuxt', 'dist', 'build', 'target', 'out',
    'vendor', '.venv', 'venv', '.env', 'env',
    '.idea', '.vscode', '.yarn', '.pnp', 'coverage',
    '.terraform', '.serverless',
})  # 【tool 级】使用对象: grep/list_directory 遍历时跳过目录集合 — 小欧 2026-07-19

# ============================================================
# 🕐 7. 工具注册模块映射(从 lazy_loader.py 迁移) — 【工具层】
# ============================================================

CATEGORY_MODULES: dict[str, tuple[str, str]] = {  # 【tool 级】使用对象: ToolRegistry 各分类→注册函数模块映射
    "file": ("app.tools.file", "_register_file_tools"),
    "shell": ("app.tools.shell", "_register_shell_tools"),
    "network": ("app.tools.network", "_register_network_tools"),
    "system": ("app.tools.system", "_register_system_tools"),
    "desktop": ("app.tools.desktop", "_register_desktop_tools"),
    "document": ("app.tools.document", "_register_document_tools"),
    "dataanalysis": ("app.tools.dataanalysis", "_register_dataanalysis_tools"),
    "fundamental": ("app.tools.fundamental", "_register_fundamental_tools"),
    "win_registry": ("app.tools.win_registry", "_register_registry_tools"),
    "timer": ("app.tools.timer", "_register_timer_tools"),
}

# ============================================================
# 🕐 8. 注册表工具映射(从 reg_tools.py 迁移) — 【工具层】
# ============================================================

# 【tool 级】使用对象: win_registry 注册表 hive 名称映射
HIVE_MAP: dict[str, str] = {  
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

# ============================================================
# 🕐 9. 工具内容质量(从 content_quality.py 迁移) — 【工具层】
# ============================================================

SELF_REF_KEYWORDS: list[str] = [  # 【tool 级】使用对象: content_quality 自检词关键词集合
    '已成功', '需要继续', '现在需要', '接下来将', '按照要求',
    '继续创建', '已完成', '已创建', '写入成功', '已经写入',
    '已成功创建', '内容已写入', '成功写入', '已成功写入',
    '现在应该', '接下来需要', '需要先', '然后需要',
]

CODE_EXTENSIONS: set[str] = {'.py', '.js', '.ts', '.java', '.go', '.c', '.cpp', '.rs', '.rb', '.swift', '.kt', '.scala'}  # 【tool 级】使用对象: content_quality/代码类工具判定代码文件扩展名
DOC_EXTENSIONS: set[str] = {'.txt', '.md', '.doc', '.docx', '.csv', '.log', '.ini', '.cfg', '.yml', '.yaml', '.json', '.xml', '.html', '.htm', '.css', '.scss', '.less'}  # 【tool 级】使用对象: 文档类工具判定文档扩展名

SELF_REF_THRESHOLD_NORMAL: float = 0.6       # 【tool 级】使用对象: content_quality 自检词比例阈值(正常文本)
SELF_REF_THRESHOLD_SHORT: float = 0.4         # 【tool 级】使用对象: content_quality 自检词比例阈值(短文本)
SHORT_CONTENT_LENGTH: int = 50                 # 【tool 级】使用对象: content_quality 短文本判定长度

# 【tool 级】使用对象: 敏感字段脱敏/红框判定集合
SENSITIVE_FIELDS: set[str] = {"password", "token", "api_key", "secret", "authorization", "credential"}  

# ============================================================
# 🕐 10. 工具日期/哈希辅助(从 date_helper/hash_helper 迁移) — 【工具层】
# ============================================================

QINGMING_DATES: dict[int, tuple[int, int]] = {  # 【tool 级】使用对象: 节日/日期相关工具判定清明日期
    2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
    2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
    2031: (4, 5), 2032: (4, 4), 2033: (4, 4), 2034: (4, 5), 2035: (4, 5),
}

SUPPORTED_ALGORITHMS: set[str] = {"md5", "sha1", "sha256", "sha512"}  # 【tool 级】使用对象: hash 工具支持的算法集合

# ============================================================
# 🕐 11. 工具重试配置(从 tool_config.py 迁移 + HTTP 可重试状态码归并) — 【工具层】
#    工具重试引擎（ToolRetryEngine）运行时参数。
#     与系统层的 LLM 熔断/重试策略完全分开。
#     含 TOOL_RETRYABLE_HTTP_CODES（旧存第4节·网络常量）和 TOOL_RETRY_CONFIG（旧存第4节·per-tool配置）
# ============================================================

TOOL_RETRY_BACKOFF: dict[str, float] = {  # 【tool 级】使用对象: ToolRetryEngine 重试退避系数(秒)
    "default": 2.0,
}

# 工具层 HTTP 可重试状态码 — 从旧第4节(网络常量)归并至此
TOOL_RETRYABLE_HTTP_CODES: set[int] = {429, 500, 502, 503, 504}  # 【tool 级】使用对象: httpget 等 network 工具判断是否抛异常给 ToolRetryEngine 重试

# 工具层 per-tool 重试配置 — 从旧第4节(网络常量)+tool_retry_engine.py 迁入
# 不在字典中的 tool → max_retries=0（不重试）
# 格式: {tool名: {"max_retries": int, "retryable": list[str]}}
# retryable 列表中的字符串必须与 ToolErrorCategory.value 完全匹配
TOOL_RETRY_CONFIG: dict[str, dict] = {
    "httpget": {"max_retries": 2, "retryable": ["timeout", "connect", "network", "protocol"]},
    "download": {"max_retries": 2, "retryable": ["timeout", "connect", "network", "protocol"]},
    "fetchpage": {"max_retries": 2, "retryable": ["timeout", "connect", "network", "protocol"]},
    "searchweb": {"max_retries": 2, "retryable": ["timeout", "connect", "network"]},
    "ping_port": {"max_retries": 2, "retryable": ["timeout", "connect"]},
}  # 【tool 级】使用对象: ToolRetryEngine per-tool 重试参数

# 工具层错误码(从 constants.py 迁入) — 小欧 2026-06-30
# 使用对象: 各工具 build_error/build_warning 返回码(用途明确, 本组 ERR_* 不再逐条标注使用对象)
# 用途：ToolRetryEngine 构建重试耗尽错误返回。
ERR_TOOL_NOT_FOUND = "ERR_TOOL_NOT_FOUND"
ERR_MISSING_PARAM = "ERR_MISSING_PARAM"
ERR_INVALID_PARAMS = "ERR_INVALID_PARAMS"
ERR_UNKNOWN = "ERR_UNKNOWN"

# ============================================================
# 🕐 12. 系统敏感路径黑名单常量 — Safety层(path_safe_check)消费
# ============================================================

FORBIDDEN_PATHS_EXACT: set[str] = {  # 【tool 级】使用对象: 文件安全禁用路径(精确匹配)
    "/etc/shadow",
    "/etc/sudoers",
}

FORBIDDEN_PATHS_PREFIX: set[str] = {  # 【tool 级】使用对象: 文件安全禁用路径(前缀匹配)
    "/proc",
    "/sys",
}

FORBIDDEN_PATHS_WINDOWS_EXACT: set[str] = {  # 【tool 级】使用对象: Windows 禁用路径(精确匹配)
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Windows\System32\config\SAM",
    r"C:\Windows\System32\config\SYSTEM",
    r"C:\Windows\System32\config\SECURITY",
    r"C:\Windows\System32\config\SOFTWARE",
    r"C:\Windows\System32\config\DEFAULT",
}

FORBIDDEN_PATHS_WINDOWS_PREFIX: set[str] = {  # 【tool 级】使用对象: Windows 禁用路径(前缀匹配)
    r"C:\Windows\System32\config",
    r"C:\Windows\WinSxS",
}

# ============================================================
# 🕐 13. 工具错误码(从 constants.py 整节迁入) — 小欧 2026-06-30
#     命名规范: ERR_{MODULE}_{PROBLEM}
#     MODULE: DOC/FILE/SHELL/META/SYSTEM/DESKTOP/NETWORK/DB/REG/TIMER/TASK/WIN/SYS_ENV/SYS_REG
#     所有工具返回的错误码统一定义在此,消除散落和命名不一致
# ============================================================

# --- 文件操作类 ---
ERR_FILE_READ_FAILED = "ERR_FILE_READ_FAILED"
ERR_FILE_WRITE_FAILED = "ERR_FILE_WRITE_FAILED"
ERR_FILE_REPLACE_FAILED = "ERR_FILE_REPLACE_FAILED"
ERR_FILE_SEARCH_FAILED = "ERR_FILE_SEARCH_FAILED"
ERR_FILE_RENAME_FAILED = "ERR_FILE_RENAME_FAILED"

# --- Shell/命令执行类 ---
ERR_SHELL_TIMEOUT = "ERR_SHELL_TIMEOUT"
ERR_SHELL_COMMAND_NOT_FOUND = "ERR_SHELL_COMMAND_NOT_FOUND"
ERR_SHELL_EXEC = "ERR_SHELL_EXEC"
ERR_SHELL_FIND_COMMAND = "ERR_SHELL_FIND_COMMAND"
ERR_SHELL_INJECTION = "ERR_SHELL_INJECTION"
ERR_SHELL_EXCEPTION = "ERR_SHELL_EXCEPTION"

# --- 参数/输入校验类 ---
ERR_PARAM_INVALID = "ERR_PARAM_INVALID"
ERR_PARAMETER_INVALID = "ERR_PARAMETER_INVALID"
ERR_PARAMETER_EMPTY = "ERR_PARAMETER_EMPTY"

# --- Meta/任务/时间类 ---
ERR_TASK_CREATE = "ERR_TASK_CREATE"
ERR_TASK_DELETE = "ERR_TASK_DELETE"
ERR_TASK_EMPTY = "ERR_TASK_EMPTY"
ERR_TASK_LIST = "ERR_TASK_LIST"
ERR_TASK_NOT_FOUND = "ERR_TASK_NOT_FOUND"
ERR_TIMER_SET = "ERR_TIMER_SET"
ERR_TIMER_CLEAR = "ERR_TIMER_CLEAR"
ERR_TIMER_LIST = "ERR_TIMER_LIST"
ERR_TIME_ADD = "ERR_TIME_ADD"
ERR_TIME_DATE = "ERR_TIME_DATE"
ERR_TIME_DIFF = "ERR_TIME_DIFF"
ERR_TIME_NOW = "ERR_TIME_NOW"

# --- 网络/URL类 ---
ERR_INVALID_URL = "ERR_INVALID_URL"
ERR_NETWORK_TIMEOUT = "ERR_NETWORK_TIMEOUT"

# --- 系统/进程/服务类 ---
ERR_SYSTEM_TIMEOUT = "ERR_SYSTEM_TIMEOUT"
ERR_SYSTEM_INFO = "ERR_SYSTEM_INFO"
ERR_SYSTEM_EVENT_LOG = "ERR_SYSTEM_EVENT_LOG"

# --- 系统环境变量/注册表类 ---
ERR_REG_READ_FAILED = "ERR_REG_READ_FAILED"
ERR_REG_WRITE_FAILED = "ERR_REG_WRITE_FAILED"
ERR_REG_DELETE_FAILED = "ERR_REG_DELETE_FAILED"

# --- 桌面/GUI类 ---
ERR_FOCUS_WINDOW = "ERR_FOCUS_WINDOW"
ERR_WINDOW_LIST = "ERR_WINDOW_LIST"
ERR_WINDOW_NOT_FOUND = "ERR_WINDOW_NOT_FOUND"
ERR_WINDOW_RESIZE = "ERR_WINDOW_RESIZE"
ERR_WINDOW_SET_STATE = "ERR_WINDOW_SET_STATE"
ERR_SCREENSHOT = "ERR_SCREENSHOT"
ERR_SCREEN_SNAPSHOT = "ERR_SCREEN_SNAPSHOT"

# --- 数据库/SQL类 ---
ERR_SQL_EXEC = "ERR_SQL_EXEC"
ERR_DB_CONNECTION = "ERR_DB_CONNECTION"

# --- 数据格式解析类 ---
ERR_WRITE_DOCX = "ERR_WRITE_DOCX"
ERR_WRITE_XLSX = "ERR_WRITE_XLSX"
ERR_WRITE_PDF = "ERR_WRITE_PDF"

# --- 数据分析类 ---
ERR_SCHEMA_FAILED = "ERR_SCHEMA_FAILED"
ERR_FILTER_INVALID = "ERR_FILTER_INVALID"

# --- 其他 ---
ERR_INVALID_ACTION = "ERR_INVALID_ACTION"
ERR_INVALID_MODE = "ERR_INVALID_MODE"

# --- 迁移自动补充 ---
ERR_DESKTOP_CLIPBOARD = "ERR_DESKTOP_CLIPBOARD"
ERR_DESKTOP_GET_MOUSE_POSITION = "ERR_DESKTOP_GET_MOUSE_POSITION"
ERR_DESKTOP_GET_WINDOW_INFO = "ERR_DESKTOP_GET_WINDOW_INFO"
ERR_DESKTOP_MOUSE_CLICK = "ERR_DESKTOP_MOUSE_CLICK"
ERR_DESKTOP_MOUSE_MOVE = "ERR_DESKTOP_MOUSE_MOVE"
ERR_DESKTOP_MOUSE_SCROLL = "ERR_DESKTOP_MOUSE_SCROLL"
ERR_DESKTOP_NOTIFICATION = "ERR_DESKTOP_NOTIFICATION"
ERR_DESKTOP_PLATFORM_NOT_SUPPORTED = "ERR_DESKTOP_PLATFORM_NOT_SUPPORTED"
ERR_DOC_ANALYZE_DATA = "ERR_DOC_ANALYZE_DATA"
ERR_DOC_CHART_GENERATE = "ERR_DOC_CHART_GENERATE"
ERR_DOC_DB_TABLE_NOT_FOUND = "ERR_DOC_DB_TABLE_NOT_FOUND"
ERR_DOC_NO_OPENPYXL = "ERR_DOC_NO_OPENPYXL"
ERR_DOC_NO_PPTX = "ERR_DOC_NO_PPTX"
ERR_DOC_QUERY_EMPTY = "ERR_DOC_QUERY_EMPTY"
ERR_DOC_READ_DOCX = "ERR_DOC_READ_DOCX"
ERR_DOC_READ_PDF = "ERR_DOC_READ_PDF"
ERR_DOC_READ_PPTX = "ERR_DOC_READ_PPTX"
ERR_DOC_READ_XLSX = "ERR_DOC_READ_XLSX"
ERR_DOC_WRITE_PPTX = "ERR_DOC_WRITE_PPTX"
ERR_FILE_COMPRESS_FAILED = "ERR_FILE_COMPRESS_FAILED"
ERR_FILE_CONTENT_SEARCH_FAILED = "ERR_FILE_CONTENT_SEARCH_FAILED"
ERR_FILE_COPY_FAILED = "ERR_FILE_COPY_FAILED"
ERR_FILE_DELETE_FAILED = "ERR_FILE_DELETE_FAILED"
ERR_FILE_EDIT_FAILED = "ERR_FILE_EDIT_FAILED"
ERR_FILE_EXTRACT = "ERR_FILE_EXTRACT"
ERR_FILE_LIST_DIR_FAILED = "ERR_FILE_LIST_DIR_FAILED"
ERR_FILE_MOVE_FAILED = "ERR_FILE_MOVE_FAILED"
ERR_KEYBOARD_SHORTCUT = "ERR_KEYBOARD_SHORTCUT"
ERR_KEYBOARD_TYPE = "ERR_KEYBOARD_TYPE"
ERR_KEY_COMBO = "ERR_KEY_COMBO"
ERR_NETWORK_CONNECTION_ERROR = "ERR_NETWORK_CONNECTION_ERROR"
ERR_NETWORK_CREATE_DIR = "ERR_NETWORK_CREATE_DIR"
ERR_NETWORK_DNS_ERROR = "ERR_NETWORK_DNS_ERROR"
ERR_NETWORK_DOWN = "ERR_NETWORK_DOWN"
ERR_NETWORK_HTTP_ERROR = "ERR_NETWORK_HTTP_ERROR"
ERR_NETWORK_INVALID_HOST = "ERR_NETWORK_INVALID_HOST"
ERR_NETWORK_INVALID_PARAM = "ERR_NETWORK_INVALID_PARAM"
ERR_NETWORK_INVALID_PATH = "ERR_NETWORK_INVALID_PATH"
ERR_NETWORK_INVALID_PORT = "ERR_NETWORK_INVALID_PORT"
ERR_NETWORK_JS_RENDER = "ERR_NETWORK_JS_RENDER"
ERR_NETWORK_REQUEST_ERROR = "ERR_NETWORK_REQUEST_ERROR"
ERR_NETWORK_WRITE_FILE = "ERR_NETWORK_WRITE_FILE"
ERR_NET_UNKNOWN = "ERR_NET_UNKNOWN"
ERR_NO_PYAUTOGUI = "ERR_NO_PYAUTOGUI"

# --- 迁移自动补充 ---
ERR_NO_WIN10TOAST = "ERR_NO_WIN10TOAST"
ERR_NO_WIN32GUI = "ERR_NO_WIN32GUI"

# ============================================================
# 🕐 14. 工具层浏览器 User-Agent — 【工具层】
# ============================================================

TOOL_BROWSER_UA: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"  # 【tool 级】使用对象: network 工具(fetch_webpage 等) HTTP 请求 User-Agent


