# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小沈 - OBS_MAX_DISPLAY_ITEMS/MAX_SEARCH_RESULTS 注释更新(grep上限与条目数统一)
# 2026-07-15 - 小欧 - 常量归一化治理: 新增 B组【系统级】(OBS_SNIPPET/HTML/SYSINFO)与 C组【tool级】(SHELL_OUTPUT/WEB_FETCH/SEARCH_SNIPPET/XLSX/HTTP/DOWNLOAD/WRITE_TEXT), 各常量统一标注【使用对象】便于识别废弃
# 2026-07-15 - 小欧 - HTTP常量归并: HTTPX_TIMEOUT_DEFAULT+TOOL_BROWSER_UA+TOOL_RETRYABLE_HTTP_CODES 从1.1/10节移至第4节(网络工具HTTP常量), 消除散落
# 2026-07-15 - 小欧 - TOOL_RETRY_CONFIG 从 tool_retry_engine.py 迁入第4节, 与 TOOL_RETRYABLE_HTTP_CODES 相邻
# 注: 本文件数值型长度/上限/阈值常量均标注【使用对象】, 搜全仓无引用的即为候选废弃常量(待清理)
# 2026-07-18 - 小欧 - TOOL_TIMEOUTS清理死键(合并的window_maximize/minimize/clipboard_read/write等),补真实注册名(set_window_state/clipboard)
# 2026-07-20 - 小欧 - 删 MAX_SEARCH_FILE_SIZE(grep 搜索单文件大小不再设上限, 对齐 rg 无文件大小限制, 因无引用删除); 新增 OBS_GREP_MAX_ROWS=200/OBS_GREP_MAX_ROW_CHARS=150(grep 专属行×列, 显示域截断收口)
# 2026-07-20 - 小欧 - shell 门限治理(章6.4): 新增 OBS_SHELL_MAX_ROWS=200/OBS_SHELL_MAX_ROW_CHARS=1000(shell 专属行×列, 显示域截断收口); SHELL_OUTPUT_MAX_CHARS 标记【已作废】由 OBS_SHELL_MAX_ROW_CHARS 取代
# 2026-07-20 - 小欧 - find 门限治理(章7.4): 新增 OBS_FIND_MAX_ROWS=200/OBS_FIND_MAX_ROW_CHARS=300(find 专属行×列, 显示域截断收口); FIND_PAGE_SIZE/MAX_SEARCH_RESULTS 已删除(由 OBS_FIND_MAX_ROWS 取代, find 返回全部匹配, deadline 超时保护)
# 2026-07-20 - 小欧 - searchweb 门限治理(章8.4): 新增 OBS_SEARCHWEB_MAX_ROWS=100/OBS_SEARCHWEB_MAX_ROW_CHARS=500(searchweb 专属行×列, 显示域截断收口); SEARCH_SNIPPET_MAX_CHARS/OBS_SNIPPET_MAX_CHARS 已删除(由 OBS_SEARCHWEB_MAX_ROW_CHARS 取代, searchweb 返回完整snippet)
# 2026-07-20 - 小欧 - httpget 门限治理(章9.4): 新增 OBS_HTTPGET_MAX_ROWS=200/OBS_HTTPGET_MAX_ROW_CHARS=2000(httpget 专属行×列, 显示域截断收口); HTTP_JSON_PREVIEW_MAX_BYTES 依3.5改名 INER_HTTPGET_JSON_PREVIEW_MAX_BYTES(保留为3.4硬安全网防OOM, 触发置 _truncated+_reason)
# 2026-07-20 - 小欧 - fetchpage 门限治理(章10.4): 新增 OBS_FETCHPAGE_MAX_ROWS=200/OBS_FETCHPAGE_MAX_ROW_CHARS=500(fetchpage 专属行×列, 显示域截断收口); WEB_FETCH_MAX_CHARS 已删除(fetchpage 返回完整正文, 截断收口于 OBS_FETCHPAGE); MAX_READ_BYTES/MAX_CONTENT_LENGTH 依3.5改名 INER_FETCHPAGE_READ_BYTES/INER_FETCHPAGE_MAX_CONTENT_LENGTH(保留为3.4硬安全网防OOM/巨文件下载)
# 2026-07-20 - 小欧 - readtext 门限治理(章11.4): 新增 OBS_READTEXT_MAX_ROWS=200/OBS_READTEXT_MAX_ROW_CHARS=1000(readtext 专属行×列, 显示域截断收口); read_text_file 去除 _select_lines max_line_length 单行截断(Tool 层零限制); MAX_READ_SIZE 依3.5改名 INER_READTEXT_READ_SIZE(各 tool 独立不公用, readtext 自有; 保留为3.4硬安全网, 文件过大拒绝, 不截断)
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
# 1. 工具超时配置(从 tool_meta.py 迁移) — 【工具层】
#    用于工具内部校验 deadline、ToolRetryEngine 保险丝超时。
#    与系统层的 SYS_DEFAULT_LLM_TIMEOUT（LLM 客户端超时）完全无关。
# ============================================================

TOOL_TIMEOUTS = {  # 【tool 级】使用对象: 各工具 deadline 校验与 ToolRetryEngine 超时配置
    # 双重用途：
    # 1. 工具内部校验 deadline / subprocess.run 超时
    # 2. ToolRetryEngine 用 asyncio.wait_for(timeout=此值) 做保险丝，
    #    防止工具卡死不返回。详见 tool_retry_engine.py 第95行。
    # 警告：修改此值会影响重试引擎的超时行为。
    # 仅保留真实注册工具名; 已合并的 window_maximize/minimize、clipboard_read/write 等死键删除 — 小欧 2026-07-18
    "list_directory": 30,
    "find": 120,
    "grep": 120,
    "readmedia": 60,
    "edittext": 60,
    "shell": 120,
    "tree": 120,
    "session": 60,
    "event_log": 60,
    "searchweb": 60,
    "httpget": 60,
    "download": 120,
    "fetchpage": 60,
    "ping_port": 60,
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
    "compress": 300,
    "default": 120,
}

# ============================================================
# 1.1 Subprocess超时配置(从各工具文件硬编码迁移)— 北京老陈 2026-05-31
# 【工具层】工具执行 subprocess 的硬超时阈值。httpx 超时移至第4节网络常量。
# ============================================================

# subprocess执行超时(秒)
SUBPROCESS_TIMEOUT_DEFAULT: int = 10    # 【tool 级】使用对象: 通用 subprocess 执行超时(秒)
SUBPROCESS_TIMEOUT_SHORT: int = 5       # 【tool 级】使用对象: 短时 subprocess(shell communicate、代码执行)
SUBPROCESS_TIMEOUT_VERY_SHORT: int = 3  # 【tool 级】使用对象: 极短 subprocess(process wait)
SUBPROCESS_TIMEOUT_LONG: int = 60       # 【tool 级】使用对象: 长时 subprocess(文档转换等耗时操作)

# ============================================================
# 2. 文件工具配置(从 file_tools.py 迁移) — 小欧 2026-06-18 新增FILE_OPERATION_TOOLS
# 【工具层】文件工具运行时的参数。仅工具代码使用。
# ============================================================

FILE_OPERATION_TOOLS: set[str] = {  # 【tool 级】使用对象: 文件操作类工具集合(安全/分批判定)
    "readtext", "writetext", "edittext",
    "move", "copy", "delete", "rename",
    "compress", "extract",
}

READ_FILE_DEFAULT_LIMIT: int = 500          # 【tool 级】使用对象: file 工具(readtext/edittext 等)读取默认行数上限
LISTDIR_PAGE_SIZE: int = 500                  # 【tool 级】使用对象: listdir 分页每页条目数
FIND_PAGE_SIZE: int = 500                     # 【tool 级】使用对象: find 分页每页条目数 — 【已作废】2026-07-20 小欧 find 改行×列返回全部匹配(OBS_FIND_MAX_ROWS), FIND_PAGE_SIZE 不再使用

# ============================================================
# 【系统级】观察截断常量（observation_formatter.py 统一使用）— 小欧 2026-07-04
#     常量集中管理，便于后续统一调整。
#     与 tool 层面的截断上限（如 READ_FILE_DEFAULT_LIMIT）相互独立。
#     老陈 2026-07-15 裁定: OBS_* 逻辑属系统级(observation 统一截断层), 因与 tool 输出耦合紧历史置于本文件, 标注【系统级】以区分【tool 级】常量。
# ============================================================
OBS_MAX_DISPLAY_ITEMS: int = 500       # 【系统级】使用对象: observation_formatter.py(所有 list 类 handler 最大条目数; grep 搜索总开关) — 小沈 2026-07-14
OBS_MAX_STRING_LENGTH: int = 10000     # 【系统级】使用对象: observation_formatter.py(单个字符串值最大显示长度)
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
OBS_HTTPGET_MAX_ROW_CHARS: int = 2000    # 【系统级】使用对象: observation_formatter.py(_format_httpget_result httpget 单行上限, 保JSON不盲截)

# —— fetchpage 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_FETCHPAGE_MAX_ROWS: int = 200         # 【系统级】使用对象: observation_formatter.py(_format_fetchpage_result fetchpage 行数上限)
OBS_FETCHPAGE_MAX_ROW_CHARS: int = 500    # 【系统级】使用对象: observation_formatter.py(_format_fetchpage_result fetchpage 单行上限)

# —— readtext 专属观察截断常量（显示域行×列；Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_READTEXT_MAX_ROWS: int = 200        # 【系统级】使用对象: observation_formatter.py(_format_readtext_result readtext 行数上限)
OBS_READTEXT_MAX_ROW_CHARS: int = 1000  # 【系统级】使用对象: observation_formatter.py(_format_readtext_result readtext 单行上限, 长行不多放宽至1000减少截断)

# —— edittext 专属观察截断常量（显示域行×列；diff 为大文本, Tool 输出不截断, 仅显示域按行×列收口） ——
OBS_EDITTEXT_MAX_ROWS: int = 200        # 【系统级】使用对象: observation_formatter.py(_format_edittext_result edittext 行数上限)
OBS_EDITTEXT_MAX_ROW_CHARS: int = 1000  # 【系统级】使用对象: observation_formatter.py(_format_edittext_result edittext 单行上限, 长行放宽至1000减少截断)

# 注: readmedia 的 base64 为二进制编码, 非可读文本, 不按文本行×列处理(章13.4 用户裁定回退为仅元数据+base64字符数摘要),
#     故不新增 OBS_READMEDIA_* 常量(避免死代码); 若后续 readmedia 改返回转写文本, 再补 OBS_READMEDIA_* + 行×列 handler

# ============================================================
# 【tool 级】工具读取/输出上限 — 老陈 2026-07-15 归一化治理
#     与 tool 紧密相关的长度/上限常量集中于此(便于查看对比检查),
#     每个常量注释使用对象。FILE/MEDIA 读取上限依3.5改名 INER_ 前缀(私有内部常量, 各 tool 独立不公用): INER_READTEXT_READ_SIZE(readtext)/INER_EDITTEXT_READ_SIZE(edittext)/INER_READMEDIA_READ_SIZE(媒体类)。
# ============================================================
# —— 以下为工具文件读取/搜索上限(【tool 级】) ——
INER_READTEXT_READ_SIZE: int = 10 * 1024 * 1024   # 【tool 级/私有内部常量】使用对象: read_text_file.py(读取文本文件字节上限防 OOM, 3.4 硬安全网; 原 MAX_READ_SIZE; 依 3.5 改名 INER_READTEXT_ 前缀, 各 tool 独立不公用)
INER_EDITTEXT_READ_SIZE: int = 10 * 1024 * 1024   # 【tool 级/私有内部常量】使用对象: edit_text_file.py(编辑前读取文件字节上限防 OOM, 3.4 硬安全网; 原 MAX_READ_SIZE; 依 3.5 改名 INER_EDITTEXT_ 前缀, 各 tool 独立不公用)
INER_READMEDIA_READ_SIZE: int = 50 * 1024 * 1024   # 【tool 级/私有内部常量】使用对象: read_media_file.py(读取媒体文件字节上限防 OOM, 3.4 硬安全网; 原 MAX_MEDIA_READ_SIZE; 依 3.5 改名 INER_READMEDIA_ 前缀, 各 tool 独立不公用)
MAX_BATCH_FILE_COUNT: int = 100                 # 【tool 级】使用对象: 批量文件操作单次文件数上限
# SHELL_OUTPUT_MAX_CHARS 已作废(2026-07-20 小欧 shell 改行×列, Tool 层不再截断; 由 OBS_SHELL_MAX_ROW_CHARS 取代) — 原值 20000
INER_SHELL_OUTPUT_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 【tool 级/私有内部常量】使用对象: shell_engine.py(引擎读 shell 临时输出文件防 OOM, 3.4 硬安全网; 原 _MAX_OUTPUT_SZ / SHELL_OUTPUT_FILE_MAX_BYTES; 依 3.5 改名 INER_ 前缀)
INER_FETCHPAGE_READ_BYTES: int = 5 * 1024 * 1024  # 【tool 级/私有内部常量】使用对象: fetch_webpage.py(流式读取正文硬截断防 OOM, 3.4 硬安全网; 原 MAX_READ_BYTES=5_242_880; 依 3.5 改名 INER_ 前缀)
INER_FETCHPAGE_MAX_CONTENT_LENGTH: int = 100 * 1024 * 1024  # 【tool 级/私有内部常量】使用对象: fetch_webpage.py(Content-Length 超阈值拒绝下载防 OOM, 3.4 硬安全网; 原 MAX_CONTENT_LENGTH=100MB; 依 3.5 改名 INER_ 前缀)
XLSX_MAX_ROWS: int = 10000             # 【tool 级】使用对象: read_xlsx.py(单次读取最大行数; 原 max_rows=10000)
INER_HTTPGET_JSON_PREVIEW_MAX_BYTES: int = 10 * 1024 * 1024  # 【tool 级/私有内部常量】使用对象: http_request.py(JSON body 预览截断, 3.4 硬安全网防响应体撑爆OOM/序列化溢出; 原 HTTP_JSON_PREVIEW_MAX_BYTES/_MAX_JSON_SIZE; 依 3.5 改名 INER_ 前缀)
DOWNLOAD_MAX_BYTES: int = 100 * 1024 * 1024  # 【tool 级】使用对象: download_file.py(下载文件大小上限; 原 _MAX_FILE_SIZE)
# 注: WRITE_TEXT_MAX_CHARS(原 max_length=10000) 依3.6作废删除(入参长度限制属多余叠加); 2026-07-20 用户裁定写结果预览恢复 Tool 层 _build_content_preview(文首50+文末50), 不新增 OBS_WRITETEXT_*(避免死代码); writetext 仍走 #21 fallback(_format_scalar_data)

# 二进制文件扩展名 — 小健 2026-06-24 更新：补充媒体扩展名
# 用途：read_text_file/write_text_file/edit_text_file等文本工具拒绝二进制文件
# 说明：包含所有二进制格式（包括系统不支持的.rar/.7z），用于防止文本工具误操作二进制文件
BINARY_EXTENSIONS: set[str] = {  # 【tool 级】使用对象: 文本工具(readtext/writetext/edittext)拒绝二进制文件扩展名集合
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.tif', '.svg',
    '.heic', '.heif',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4a', '.ogg',
    '.flac', '.aac', '.wma', '.mid', '.midi', '.webm',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
    '.exe', '.msi', '.dll', '.so', '.dylib',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf',
    '.odt', '.ods', '.odp', '.rtf',
}

# 【tool 级】使用对象: grep/list_directory 遍历时跳过目录集合 — 小欧 2026-07-19
SKIP_DIRS: frozenset[str] = frozenset({
    'node_modules', 'bower_components',
    '.git', '.svn', '.hg', '__pycache__',
    '.next', '.nuxt', 'dist', 'build', 'target', 'out',
    'vendor', '.venv', 'venv', '.env', 'env',
    '.idea', '.vscode', '.yarn', '.pnp', 'coverage',
    '.terraform', '.serverless',
})

# ============================================================
# 3. 工具注册模块映射(从 lazy_loader.py 迁移) — 【工具层】
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
# 4. 网络工具HTTP常量(从各节归并) — 【工具层】
#     所有 HTTP/网络相关常量集中于此，消除散落。
#     与系统层的 LLM_MAX_CONNECTIONS（LLM 客户端）分开。
# ============================================================

# httpx请求超时(秒)
HTTPX_TIMEOUT_DEFAULT: float = 5.0        # 【tool 级】使用对象: 通用 httpx 请求超时(秒)

# 网络工具默认超时(秒)
DEFAULT_TIMEOUT_SEC: float = 30.0             # 【tool 级】使用对象: network 工具默认超时(秒)
NETWORK_MAX_CONNECTIONS: int = 100             # 【tool 级】使用对象: network 工具 httpx 连接池最大连接
NETWORK_MAX_KEEPALIVE: int = 20                # 【tool 级】使用对象: network 工具 httpx 连接池 keepalive 连接数

# 工具层浏览器 User-Agent
TOOL_BROWSER_UA: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"  # 【tool 级】使用对象: network 工具(fetch_webpage 等) HTTP 请求 User-Agent

# 工具层 HTTP 可重试状态码
TOOL_RETRYABLE_HTTP_CODES: set[int] = {429, 500, 502, 503, 504}  # 【tool 级】使用对象: httpget 等 network 工具判断是否抛异常给 ToolRetryEngine 重试

# 工具层 per-tool 重试配置 — 从 tool_retry_engine.py 迁入
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

# ============================================================
# 6. 注册表工具映射(从 reg_tools.py 迁移) — 【工具层】
# ============================================================

HIVE_MAP: dict[str, str] = {  # 【tool 级】使用对象: win_registry 注册表 hive 名称映射
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

# ============================================================
# 7. 工具内容质量(从 content_quality.py 迁移) — 【工具层】
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

# ============================================================
# 8. 工具安全模式(从 shell_helper/exec_helper 迁移) — 【工具层】
# ============================================================

# DANGEROUS_PATTERNS 已于 2026-06-27 删除
# 原因：execute_code改用execute_code_safety.py的分级检查(RISK_CHECK_RULES)，
#        tool_safety_checker改用execute_shell_command_safety.py的分级检查(SHELL_DANGEROUS_PATTERNS)，
#        DANGEROUS_PATTERNS（Python模式）无人引用，删除。

# SHELL_DANGEROUS_PATTERNS 已于 2026-06-27 迁出到 execute_shell_command_safety.py
# 原因：规则与检查逻辑内聚（对齐execute_code_safety.py设计原则），不再放在全局常量文件



# ============================================================
# 9. 工具日期/哈希辅助(从 date_helper/hash_helper 迁移) — 【工具层】
# ============================================================

QINGMING_DATES: dict[int, tuple[int, int]] = {  # 【tool 级】使用对象: 节日/日期相关工具判定清明日期
    2024: (4, 4), 2025: (4, 4), 2026: (4, 5),
    2027: (4, 5), 2028: (4, 4), 2029: (4, 5), 2030: (4, 5),
    2031: (4, 5), 2032: (4, 4), 2033: (4, 4), 2034: (4, 5), 2035: (4, 5),
}

SUPPORTED_ALGORITHMS: set[str] = {"md5", "sha1", "sha256", "sha512"}  # 【tool 级】使用对象: hash 工具支持的算法集合

# ============================================================
# 10. 工具重试配置(从 tool_config.py 迁移) — 【工具层】
#    工具重试引擎（ToolRetryEngine）运行时参数。
#    与系统层的 LLM 熔断/重试策略完全分开。
# ============================================================

TOOL_RETRY_BACKOFF: dict[str, float] = {  # 【tool 级】使用对象: ToolRetryEngine 重试退避系数(秒)
    "default": 2.0,
}

# 工具层错误码(从 constants.py 迁入) — 小欧 2026-06-30
# 使用对象: 各工具 build_error/build_warning 返回码(用途明确, 本组 ERR_* 不再逐条标注使用对象)
# 用途：ToolRetryEngine 构建重试耗尽错误返回。
ERR_TOOL_NOT_FOUND = "ERR_TOOL_NOT_FOUND"
ERR_MISSING_PARAM = "ERR_MISSING_PARAM"
ERR_INVALID_PARAMS = "ERR_INVALID_PARAMS"
ERR_UNKNOWN = "ERR_UNKNOWN"

SENSITIVE_FIELDS: set[str] = {"password", "token", "api_key", "secret", "authorization", "credential"}  # 【tool 级】使用对象: 敏感字段脱敏/红框判定集合

# ============================================================
# 11. 系统敏感路径黑名单常量 — Safety层(path_safe_check)消费
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
# 12. 工具错误码(从 constants.py 整节迁入) — 小欧 2026-06-30
#     命名规范: ERR_{MODULE}_{PROBLEM}
#     MODULE: DOC/FILE/SHELL/META/SYSTEM/DESKTOP/NETWORK/DB/REG/TIMER/TASK/WIN/SYS_ENV/SYS_REG
#     所有工具返回的错误码统一定义在此,消除散落和命名不一致
# ============================================================

# --- 文档/格式类 ---
ERR_DOC_FORMAT_NOT_SUPPORTED = "ERR_DOC_FORMAT_NOT_SUPPORTED"
ERR_DOC_READ_JSON = "ERR_DOC_READ_JSON"
ERR_DOC_PARSE_FAILED = "ERR_DOC_PARSE_FAILED"

# --- 文件操作类 ---
ERR_FILE_NOT_FOUND = "ERR_FILE_NOT_FOUND"
ERR_FILE_EXISTS = "ERR_FILE_EXISTS"
ERR_FILE_PATH_INVALID = "ERR_FILE_PATH_INVALID"
ERR_FILE_PATH_NOT_DIR = "ERR_FILE_PATH_NOT_DIR"
ERR_FILE_DIRECTORY_NOT_FOUND = "ERR_FILE_DIRECTORY_NOT_FOUND"
ERR_FILE_READ = "ERR_FILE_READ"
ERR_FILE_READ_FAILED = "ERR_FILE_READ_FAILED"
ERR_FILE_READ_BINARY_FILE = "ERR_FILE_READ_BINARY_FILE"
ERR_FILE_READ_TOO_LARGE = "ERR_FILE_READ_TOO_LARGE"
ERR_FILE_WRITE_FAILED = "ERR_FILE_WRITE_FAILED"
ERR_FILE_REPLACE_FAILED = "ERR_FILE_REPLACE_FAILED"
ERR_FILE_SEARCH_FAILED = "ERR_FILE_SEARCH_FAILED"
ERR_FILE_RENAME_FAILED = "ERR_FILE_RENAME_FAILED"

# --- Shell/命令执行类 ---
ERR_SHELL_TIMEOUT = "ERR_SHELL_TIMEOUT"
ERR_SHELL_COMMAND_NOT_FOUND = "ERR_SHELL_COMMAND_NOT_FOUND"
ERR_SHELL_NOT_FOUND = "ERR_SHELL_NOT_FOUND"
ERR_SHELL_EXEC = "ERR_SHELL_EXEC"
ERR_SHELL_EXEC_EMPTY_CODE = "ERR_SHELL_EXEC_EMPTY_CODE"
ERR_SHELL_EXEC_INVALID_DIR = "ERR_SHELL_EXEC_INVALID_DIR"
ERR_SHELL_EXEC_NODE_NOT_FOUND = "ERR_SHELL_EXEC_NODE_NOT_FOUND"
ERR_SHELL_EXEC_PYTHON_NOT_FOUND = "ERR_SHELL_EXEC_PYTHON_NOT_FOUND"
ERR_SHELL_FIND_COMMAND = "ERR_SHELL_FIND_COMMAND"
ERR_SHELL_GET_CWD = "ERR_SHELL_GET_CWD"
ERR_SHELL_INJECTION = "ERR_SHELL_INJECTION"
ERR_SHELL_CHECK_PATH = "ERR_SHELL_CHECK_PATH"
ERR_SHELL_CHECK_RUNNING = "ERR_SHELL_CHECK_RUNNING"
ERR_SHELL_EXCEPTION = "ERR_SHELL_EXCEPTION"
ERR_SHELL_VALIDATE_COMMAND = "ERR_SHELL_VALIDATE_COMMAND"

# --- 参数/输入校验类 ---
ERR_PARAM_INVALID = "ERR_PARAM_INVALID"
ERR_PARAM_MISSING = "ERR_PARAM_MISSING"
ERR_PARAM_CONFLICT = "ERR_PARAM_CONFLICT"
ERR_PARAMETER_INVALID = "ERR_PARAMETER_INVALID"
ERR_PARAMETER_EMPTY = "ERR_PARAMETER_EMPTY"
ERR_PARAMETER_MISSING = "ERR_PARAMETER_MISSING"

# --- Meta/任务/时间类 ---
ERR_META_NO_ACTIVE_TASK = "ERR_META_NO_ACTIVE_TASK"
ERR_META_INVALID_FORMAT = "ERR_META_INVALID_FORMAT"
ERR_TASK_CREATE = "ERR_TASK_CREATE"
ERR_TASK_DELETE = "ERR_TASK_DELETE"
ERR_TASK_EMPTY = "ERR_TASK_EMPTY"
ERR_TASK_LIST = "ERR_TASK_LIST"
ERR_TASK_NOT_FOUND = "ERR_TASK_NOT_FOUND"
ERR_TIMER_SET = "ERR_TIMER_SET"
ERR_TIMER_CLEAR = "ERR_TIMER_CLEAR"
ERR_TIMER_LIST = "ERR_TIMER_LIST"
ERR_TIMER_PARAM = "ERR_TIMER_PARAM"
ERR_TIMESTAMP_TO_TIME = "ERR_TIMESTAMP_TO_TIME"
ERR_TIME_ADD = "ERR_TIME_ADD"
ERR_TIME_DATE = "ERR_TIME_DATE"
ERR_TIME_DIFF = "ERR_TIME_DIFF"
ERR_TIME_NOW = "ERR_TIME_NOW"
ERR_TIME_TO_TIMESTAMP = "ERR_TIME_TO_TIMESTAMP"
ERR_TIME_TZ = "ERR_TIME_TZ"

# --- 网络/URL类 ---
ERR_INVALID_URL = "ERR_INVALID_URL"
ERR_NETWORK_REQUEST = "ERR_NETWORK_REQUEST"
ERR_NETWORK_TIMEOUT = "ERR_NETWORK_TIMEOUT"
ERR_NETWORK_DNS = "ERR_NETWORK_DNS"
ERR_NETWORK_CONNECT = "ERR_NETWORK_CONNECT"

# --- 系统/进程/服务类 ---
ERR_SYSTEM_TIMEOUT = "ERR_SYSTEM_TIMEOUT"
ERR_SYSTEM_PROCESS_LIST = "ERR_SYSTEM_PROCESS_LIST"
ERR_SYSTEM_PROCESS_KILL = "ERR_SYSTEM_PROCESS_KILL"
ERR_SYSTEM_COMMAND_NOT_FOUND = "ERR_SYSTEM_COMMAND_NOT_FOUND"
ERR_SYSTEM_INFO = "ERR_SYSTEM_INFO"
ERR_SYSTEM_EVENT_LOG = "ERR_SYSTEM_EVENT_LOG"
ERR_SYSTEM_NET_CONN = "ERR_SYSTEM_NET_CONN"
ERR_SERVICE_LIST = "ERR_SERVICE_LIST"
ERR_SERVICE_NOT_FOUND = "ERR_SERVICE_NOT_FOUND"
ERR_SERVICE_START = "ERR_SERVICE_START"
ERR_SERVICE_STOP = "ERR_SERVICE_STOP"

# --- 系统环境变量/注册表类 ---
ERR_SYS_ENV_GET = "ERR_SYS_ENV_GET"
ERR_SYS_ENV_INVALID_ACTION = "ERR_SYS_ENV_INVALID_ACTION"
ERR_SYS_ENV_INVALID_NAME = "ERR_SYS_ENV_INVALID_NAME"
ERR_SYS_ENV_INVALID_SCOPE = "ERR_SYS_ENV_INVALID_SCOPE"
ERR_SYS_ENV_INVALID_VALUE = "ERR_SYS_ENV_INVALID_VALUE"
ERR_SYS_ENV_LIST = "ERR_SYS_ENV_LIST"
ERR_SYS_REG_INVALID_ROOT_KEY = "ERR_SYS_REG_INVALID_ROOT_KEY"
ERR_SYS_REG_KEY_NOT_FOUND = "ERR_SYS_REG_KEY_NOT_FOUND"
ERR_SYS_REG_KEY_NOT_EMPTY = "ERR_SYS_REG_KEY_NOT_EMPTY"
ERR_SYS_REG_CANNOT_DELETE_ROOT = "ERR_SYS_REG_CANNOT_DELETE_ROOT"
ERR_REG_READ_FAILED = "ERR_REG_READ_FAILED"
ERR_REG_WRITE_FAILED = "ERR_REG_WRITE_FAILED"
ERR_REG_DELETE_FAILED = "ERR_REG_DELETE_FAILED"
ERR_REG_INVALID_PARAM = "ERR_REG_INVALID_PARAM"
ERR_REG_UNSUPPORTED_TYPE = "ERR_REG_UNSUPPORTED_TYPE"
ERR_REG_VALIDATE_FAILED = "ERR_REG_VALIDATE_FAILED"

# --- 桌面/GUI类 ---
ERR_DESKTOP_NOT_FOUND = "ERR_DESKTOP_NOT_FOUND"
ERR_FOCUS_WINDOW = "ERR_FOCUS_WINDOW"
ERR_GUI_CALL = "ERR_GUI_CALL"
ERR_WINDOW_LIST = "ERR_WINDOW_LIST"
ERR_WINDOW_NOT_FOUND = "ERR_WINDOW_NOT_FOUND"
ERR_WINDOW_RESIZE = "ERR_WINDOW_RESIZE"
ERR_WINDOW_SET_STATE = "ERR_WINDOW_SET_STATE"
ERR_SCREENSHOT = "ERR_SCREENSHOT"
ERR_SCREEN_RECORD = "ERR_SCREEN_RECORD"
ERR_SCREEN_SNAPSHOT = "ERR_SCREEN_SNAPSHOT"

# --- 数据库/SQL类 ---
ERR_SQL_EXEC = "ERR_SQL_EXEC"
ERR_DB_CONNECTION = "ERR_DB_CONNECTION"

# --- 数据格式解析类 ---
ERR_PARSE_YAML = "ERR_PARSE_YAML"
ERR_PARSE_TOML = "ERR_PARSE_TOML"
ERR_PARSE_INI = "ERR_PARSE_INI"
ERR_PARSE_XML = "ERR_PARSE_XML"
ERR_PARSE_JSON = "ERR_PARSE_JSON"
ERR_PARSE_PROPERTIES = "ERR_PARSE_PROPERTIES"
ERR_INVALID_JSON = "ERR_INVALID_JSON"
ERR_WRITE_YAML = "ERR_WRITE_YAML"
ERR_WRITE_TOML = "ERR_WRITE_TOML"
ERR_WRITE_JSON = "ERR_WRITE_JSON"
ERR_WRITE_DOCX = "ERR_WRITE_DOCX"
ERR_WRITE_XLSX = "ERR_WRITE_XLSX"
ERR_WRITE_PDF = "ERR_WRITE_PDF"

# --- 数据分析类 ---
ERR_DATA_ANALYSIS = "ERR_DATA_ANALYSIS"
ERR_STATISTICS_FAILED = "ERR_STATISTICS_FAILED"
ERR_SCHEMA_FAILED = "ERR_SCHEMA_FAILED"
ERR_FILTER_INVALID = "ERR_FILTER_INVALID"

# --- Agent/工具执行类 ---
ERR_TOOL_DEPRECATED = "ERR_TOOL_DEPRECATED"
ERR_UNSAFE_CODE = "ERR_UNSAFE_CODE"

# --- 其他 ---
ERR_INVALID_ACTION = "ERR_INVALID_ACTION"
ERR_INVALID_DIRECTION = "ERR_INVALID_DIRECTION"
ERR_INVALID_MODE = "ERR_INVALID_MODE"
ERR_INVALID_STEP = "ERR_INVALID_STEP"

# --- 迁移自动补充 ---
ERR_DESKTOP_CHECK_SCREEN_SIZE = "ERR_DESKTOP_CHECK_SCREEN_SIZE"
ERR_DESKTOP_CHECK_TESSERACT = "ERR_DESKTOP_CHECK_TESSERACT"
ERR_DESKTOP_CHECK_WINDOW = "ERR_DESKTOP_CHECK_WINDOW"
ERR_DESKTOP_CLIPBOARD = "ERR_DESKTOP_CLIPBOARD"
ERR_DESKTOP_GET_MOUSE_POSITION = "ERR_DESKTOP_GET_MOUSE_POSITION"
ERR_DESKTOP_GET_WINDOW_INFO = "ERR_DESKTOP_GET_WINDOW_INFO"
ERR_DESKTOP_GET_WINDOW_POSITION = "ERR_DESKTOP_GET_WINDOW_POSITION"
ERR_DESKTOP_MOUSE_CLICK = "ERR_DESKTOP_MOUSE_CLICK"
ERR_DESKTOP_MOUSE_MOVE = "ERR_DESKTOP_MOUSE_MOVE"
ERR_DESKTOP_MOUSE_SCROLL = "ERR_DESKTOP_MOUSE_SCROLL"
ERR_DESKTOP_NOTIFICATION = "ERR_DESKTOP_NOTIFICATION"
ERR_DESKTOP_NOT_WINDOWS = "ERR_DESKTOP_NOT_WINDOWS"
ERR_DESKTOP_NO_DEPENDENCY = "ERR_DESKTOP_NO_DEPENDENCY"
ERR_DESKTOP_PLATFORM_NOT_SUPPORTED = "ERR_DESKTOP_PLATFORM_NOT_SUPPORTED"
ERR_DOC_ANALYZE_DATA = "ERR_DOC_ANALYZE_DATA"
ERR_DOC_CHART_GENERATE = "ERR_DOC_CHART_GENERATE"
ERR_DOC_CONVERT_FAILED = "ERR_DOC_CONVERT_FAILED"
ERR_DOC_DATA_FORMAT_FAILED = "ERR_DOC_DATA_FORMAT_FAILED"
ERR_DOC_DB_TABLE_NOT_FOUND = "ERR_DOC_DB_TABLE_NOT_FOUND"
ERR_DOC_FORMAT_NOT_DETECTED = "ERR_DOC_FORMAT_NOT_DETECTED"
ERR_DOC_NO_OPENPYXL = "ERR_DOC_NO_OPENPYXL"
ERR_DOC_NO_PPTX = "ERR_DOC_NO_PPTX"
ERR_DOC_QUERY_EMPTY = "ERR_DOC_QUERY_EMPTY"
ERR_DOC_READ_CSV = "ERR_DOC_READ_CSV"
ERR_DOC_READ_DOCX = "ERR_DOC_READ_DOCX"
ERR_DOC_READ_PDF = "ERR_DOC_READ_PDF"
ERR_DOC_READ_PPTX = "ERR_DOC_READ_PPTX"
ERR_DOC_READ_XLSX = "ERR_DOC_READ_XLSX"
ERR_DOC_WRITE_PPTX = "ERR_DOC_WRITE_PPTX"
ERR_EXEC_FAILED = "ERR_EXEC_FAILED"
ERR_EXEC_JS = "ERR_EXEC_JS"
ERR_EXEC_PYTHON = "ERR_EXEC_PYTHON"
ERR_EXEC_TIMEOUT = "ERR_EXEC_TIMEOUT"
ERR_FILE_BACKUP = "ERR_FILE_BACKUP"
ERR_FILE_CALCULATE_DISTRIBUTION = "ERR_FILE_CALCULATE_DISTRIBUTION"
ERR_FILE_CHECKSUM_FAILED = "ERR_FILE_CHECKSUM_FAILED"
ERR_FILE_CHECKSUM_TIMEOUT = "ERR_FILE_CHECKSUM_TIMEOUT"
ERR_FILE_CHECK_PERMISSION = "ERR_FILE_CHECK_PERMISSION"
ERR_FILE_COMPRESS_FAILED = "ERR_FILE_COMPRESS_FAILED"
ERR_FILE_CONTENT_BLOCKED = "ERR_FILE_CONTENT_BLOCKED"
ERR_FILE_CONTENT_SEARCH_FAILED = "ERR_FILE_CONTENT_SEARCH_FAILED"
ERR_FILE_COPY_FAILED = "ERR_FILE_COPY_FAILED"
ERR_FILE_CREATE_DIR = "ERR_FILE_CREATE_DIR"
ERR_FILE_DELETE_FAILED = "ERR_FILE_DELETE_FAILED"
ERR_FILE_EDIT_FAILED = "ERR_FILE_EDIT_FAILED"
ERR_FILE_ENCODING = "ERR_FILE_ENCODING"
ERR_FILE_EXTRACT = "ERR_FILE_EXTRACT"
ERR_FILE_HASH = "ERR_FILE_HASH"
ERR_FILE_INFO = "ERR_FILE_INFO"
ERR_FILE_LIST_DIR_FAILED = "ERR_FILE_LIST_DIR_FAILED"
ERR_FILE_METADATA = "ERR_FILE_METADATA"
ERR_FILE_MIME_TYPE = "ERR_FILE_MIME_TYPE"
ERR_FILE_MOVE_FAILED = "ERR_FILE_MOVE_FAILED"
ERR_FILE_MOVE_TRASH = "ERR_FILE_MOVE_TRASH"
ERR_FILE_PATH_EXISTS = "ERR_FILE_PATH_EXISTS"
ERR_FILE_PATH_NOT_FILE = "ERR_FILE_PATH_NOT_FILE"
ERR_KEYBOARD_SHORTCUT = "ERR_KEYBOARD_SHORTCUT"
ERR_KEYBOARD_TYPE = "ERR_KEYBOARD_TYPE"
ERR_KEY_COMBO = "ERR_KEY_COMBO"
ERR_META_CALENDAR_NEXT_N_WORKDAY = "ERR_META_CALENDAR_NEXT_N_WORKDAY"
ERR_META_INVALID_CHECK_TYPE = "ERR_META_INVALID_CHECK_TYPE"
ERR_META_TIME_CONVERT = "ERR_META_TIME_CONVERT"
ERR_META_TIME_FORMAT = "ERR_META_TIME_FORMAT"
ERR_MISSING_TOOL = "ERR_MISSING_TOOL"
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
ERR_NO_DOCX = "ERR_NO_DOCX"
ERR_NO_IMAGEIO = "ERR_NO_IMAGEIO"
ERR_NO_LIBREOFFICE = "ERR_NO_LIBREOFFICE"
ERR_NO_MATCH = "ERR_NO_MATCH"
ERR_NO_MATPLOTLIB = "ERR_NO_MATPLOTLIB"
ERR_NO_NUMPY = "ERR_NO_NUMPY"
ERR_NO_PANDAS = "ERR_NO_PANDAS"
ERR_NO_PDFPLUMBER = "ERR_NO_PDFPLUMBER"
ERR_NO_PYAUTOGUI = "ERR_NO_PYAUTOGUI"
ERR_NO_PYZIPPER = "ERR_NO_PYZIPPER"
ERR_NO_PYYAML = "ERR_NO_PYYAML"
ERR_NO_RECORD_LIB = "ERR_NO_RECORD_LIB"
ERR_NO_REPORTLAB = "ERR_NO_REPORTLAB"
ERR_NO_SCREENSHOT_LIB = "ERR_NO_SCREENSHOT_LIB"
ERR_NO_TESSERACT = "ERR_NO_TESSERACT"
ERR_NO_TOMLI = "ERR_NO_TOMLI"
ERR_NO_TOMLI_W = "ERR_NO_TOMLI_W"
ERR_OCR = "ERR_OCR"
ERR_PARAM_MISMATCH = "ERR_PARAM_MISMATCH"
ERR_PATH_INVALID = "ERR_PATH_INVALID"
ERR_PATH_NOT_FILE = "ERR_PATH_NOT_FILE"
ERR_PERMISSION_DENIED = "ERR_PERMISSION_DENIED"
ERR_PIPELINE_FAILED = "ERR_PIPELINE_FAILED"
ERR_PIPELINE_STOPPED = "ERR_PIPELINE_STOPPED"
ERR_PIPELINE_TIMEOUT = "ERR_PIPELINE_TIMEOUT"
ERR_QUERY_FAILED = "ERR_QUERY_FAILED"
ERR_READ_CSV_BASIC = "ERR_READ_CSV_BASIC"
ERR_READ_CSV_DATAFRAME = "ERR_READ_CSV_DATAFRAME"
ERR_READ_EXCEL_DATAFRAME = "ERR_READ_EXCEL_DATAFRAME"
ERR_READ_ONLY_VIOLATION = "ERR_READ_ONLY_VIOLATION"
ERR_REG_PERMISSION_DENIED = "ERR_REG_PERMISSION_DENIED"

# --- 迁移自动补充 ---
ERR_DESKTOP_NO_PYWIN32 = "ERR_DESKTOP_NO_PYWIN32"
ERR_NO_WIN10TOAST = "ERR_NO_WIN10TOAST"
ERR_NO_WIN32GUI = "ERR_NO_WIN32GUI"


def sql_error_hint(e: Exception) -> str:
    """根据SQL异常消息生成更精确的hint — 小欧 2026-07-08"""
    msg = str(e).lower()
    if "no such column" in msg or "has no column" in msg:
        return "请先使用 get_db_schema 查看表结构确认列名是否正确"
    if "no such table" in msg:
        return "请先使用 get_db_schema 查看所有表确认表名是否正确"
    if "syntax error" in msg or "unrecognized token" in msg or "near " in msg:
        return "SQL语法错误，请检查关键字拼写和语句结构"
    if "ambiguous column" in msg:
        return "列名存在歧义，请使用 表名.列名 方式限定"
    if "no such function" in msg:
        return "函数名不存在，请检查SQL函数拼写"
    return "请检查SQL语法"


def hint_for_data_error(e: Exception) -> str:
    """根据数据处理异常类型返回诚实、准确的 hint — 小欧 2026-07-12

    原则（与 file_path_checker.hint_for_read/write_error 一致）：
    - 可识别异常给精准提示；
    - 未知异常如实报出异常类型，由 detail 承载真实信息；
    - 绝不编造与真实原因无关的提示（如对权限异常谎称"检查数据"）。
    """
    import sqlite3 as _sqlite3
    if isinstance(e, _sqlite3.Error):
        return sql_error_hint(e)
    if isinstance(e, PermissionError) or (isinstance(e, OSError) and getattr(e, "errno", None) == 13):
        return "无文件读取/写入权限，请检查文件权限后重试"
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
        return "磁盘空间不足，请清理磁盘后重试"
    if isinstance(e, OSError):
        return f"文件操作失败({e.strerror or type(e).__name__})，详见错误明细"
    if isinstance(e, ValueError):
        return "数据或参数格式异常，请检查输入数据"
    if isinstance(e, (TypeError, KeyError)):
        return "数据结构异常，请检查字段和格式"
    if isinstance(e, ImportError):
        return "所需库未安装，请安装缺失依赖"
    return f"处理失败({type(e).__name__})，详见错误明细"
