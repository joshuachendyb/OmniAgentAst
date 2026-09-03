# -*- coding: utf-8 -*-
"""
【系统层常量】系统常量集中管理 — 小健 2026-05-24

定义：负责 LLM 通信、Agent 循环、API 服务的基础设施层。
文件：app/services/llm/base_service.py、app/utils/sys_error_classifier.py
职责：调 LLM API、处理 LLM 返回结果、管理 Agent 循环、SSE 流
错误分类器：SystemErrorClassifier（按异常消息字符串判断，返回 SystemErrorCategory 枚举）

系统层常量包括：HTTP 协议定义、LLM 客户端配置、Agent 循环参数、共享错误码（ERR_*）等。
与工具层常量文件 tool_constants.py 严格分开，两层互不引用。

分层原则：
  - 本文件（constants.py）：系统层。SYS_HTTP_* 是 HTTP 协议事实定义（如 429=限流），
     供 SystemErrorClassifier 和 LLM 客户端使用。DEFAULT_READ_TIMEOUT 等是 LLM 客户端读超时。
  - tool_constants.py：工具层。TOOL_HTTP_* 是工具自己判断重试用的拷贝，TOOL_TIMEOUTS 等是工具运行参数。

禁止：
  ❌ 本文件引用 tool_constants.py 的任何内容
  ❌ 本文件的 SYS_HTTP_* 被工具层代码直接引用（工具层应引用 tool_constants.py 的 TOOL_HTTP_*）

编辑历史:
# 格式规范: {日期} {署名} {修改内容}
  2026-07-14 小欧 删除死代码RATE_LIMIT_STATUS_CODES(无调用方,限流由error_classifier覆盖,功能零退化)
  2026-07-14 小欧 删除孤儿常量HTTP_RATE_LIMIT(仅被RATE_LIMIT_STATUS_CODES使用,删除后限流仍由error_classifier覆盖,功能零退化)
  2026-07-14 小欧 加回HTTP_RATE_LIMIT=429并供error_classifier引用,消除裸魔法数429(代码变迁遗留,非功能退化)
  2026-07-14 小欧 集中LLM_*/FC_*/TOOL_CACHE_TTL(base_service.py)与MAX_PENDING_CONFIRMATIONS(hitl_confirmation.py)至constants.py(代码变迁遗留,非功能退化,同步改llm_stream/universal_agent/相关测试导入)
  2026-07-15 小欧 常量归一化治理: 删除11个零引用死常量(DEFAULT_*等), 新增系统级 PROJECT_CONTEXT_MAX_CHARS=10000; 现存数值型长度/上限/超时/阈值常量统一标注【使用对象】便于识别废弃
  2026-07-15 老陈裁定+小欧: 删除 HTTP_RATE_LIMIT 常量(429 是 HTTP 状态码, 在 error_classifier 映射中以裸数字与其他状态码并列, 单独常量多余且 HTTP_ 前缀不准), error_classifier 改回裸 429, 功能零退化
  2026-07-16 小欧 新增 LLM_MAX_TOKENS=16384(系统级max_tokens默认值,防LLM无限长输出致长时间静默)+STREAM_TOTAL_TIMEOUT=500(base_service总时长硬超时,弥补httpx idle timeout在连续流式时不触发的缺陷)
  2026-07-17 小沈 FC重命名: LLM_RESPONSE_FALLBACK(原FC_FALLBACK_ENABLED)+LLM_RESPONSE_RETRIES(原FC_MAX_RETRIES)
  2026-07-22 小欧 MAX_CONTEXT_CHARS→MAX_CONTEXT_TOKENS 命名统一（值200000不变），注释同步更新
   2026-07-23 小欧 新增 ACTION_LOG_RESULT_MAX_CHARS=5000(action_handler
        日志result截断长度,防MemoryError); action_handler导入改为
        from app.constants 引用
   2026-08-14 小欧 改名名实相符: model_schemas.py → config_schemas.py(注释同步)
    2026-08-17 小健 常量归属迁移(北京老陈驱动): 压缩/裁剪相关常量(MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_BUFFER/CHARS_PER_TOKEN/TEMP_HISTORY_CHAR_LIMIT) 迁至 app/services/agent/compaction_constants.py(随用方集中到 agent 域), 本源删除, 引用方(start_step/message_builder/compaction 各模块)导入路径同步改
    2026-09-02 小欧 v1.5.13 新增 HITL_CONFIRM_LEAD=10 / BYPASS_AUTO_LEAD=2 两个计时提前量常量(会话信任修复方案5.7.3/5.7.4: 后端唯一计时权威, 前端倒计时=后端窗口−提前量, 消除前后端计时竞态)
    2026-09-03 小欧/北京老陈 新增 HITL_MIN_CONFIRM_TIMEOUT=3 前端倒计时最小值常量(改前三处max(5,bt-LEAD)硬编码5→常量3)
# 注: 本文件数值型长度/上限/超时/阈值常量均标注【使用对象】, 搜全仓无引用的即为候选废弃常量(待清理)
"""

import re
from datetime import timedelta

# ============================================================
# 1. HTTP 状态码与错误码
# ============================================================

# 注: 429 等 HTTP 状态码在 error_classifier.HTTP_STATUS_TO_ERROR_TYPE 中以裸数字映射(与其他状态码并列), 不单独设常量 — 老陈 2026-07-15 裁定(HTTP_ 前缀不准且多余)

# ============================================================
# 2. 重试与限流
# ============================================================

# DEFAULT_MAX_STEPS = 100 仅作 config_schemas.py 请求体默认值(API schema 层), 不参与 Agent 运行循环
# 2026-08-05 小欧 核对说明(北京老陈 2026-08-05 裁定: max_steps 现为调试需要, 不改代码): 运行时 max_steps 由 config.yaml 的 app.max_steps 控制(当前=10000),
# 创建 Agent 链路(openai.py:256 UniversalAgent 不传 max_steps)经 base_agent.py get_max_steps() 取配置; 本常量 100 与配置 10000 不一致系历史遗留, 禁止据其推断循环步数上限
DEFAULT_MAX_STEPS = 100  # 【系统级】使用对象: 仅 config_schemas.py API 请求体默认值
MAX_CONSECUTIVE_CHUNKS = 5  # 【系统级】使用对象: Agent 循环连续 chunk 上限
MAX_CHUNKS_WITHOUT_PROMOTE = 50  # 【系统级】使用对象: Agent 循环无 promote 的 chunk 上限

# ============================================================
# LLM 客户端配置（从 base_service.py 集中迁移 2026-07-14 小欧）
# ============================================================

LLM_TEMPERATURE = 0.7  # 【系统级】使用对象: LLM 客户端采样温度
LLM_TOOL_CHOICE = "auto"  # 【系统级】使用对象: LLM 客户端 tool_choice 模式
LLM_STREAM_MAX_RETRIES = 3  # 【系统级】使用对象: LLM 流式最大重试次数
LLM_STREAM_OPTIONS = {"include_usage": True}  # 【系统级】使用对象: LLM 流式选项
LLM_RESPONSE_FALLBACK = True  # 【系统级】使用对象: LLM响应错误降级开关(FC模式错误→Text降级) — 小沈 2026-07-17
LLM_RESPONSE_RETRIES = 2  # 【系统级】使用对象: LLM响应错误最大重试次数(如空/无效响应) — 小沈 2026-07-17
TOOL_CACHE_TTL = 300  # 【系统级】使用对象: 工具结果缓存 TTL(秒)
LLM_MAX_TOKENS = 16384  # 【系统级】使用对象: LLM 单次调用最大输出 token 数(None=不限)

# ============================================================
# 3. 网络与超时
# ============================================================

DEFAULT_READ_TIMEOUT = 150  # 【系统级】使用对象: LLMClient 读超时兜底(秒)
# LLM 读超时兜底(秒): LLMClient/request_stream 未传 timeout 时使用; 亦为 BaseAIService 默认超时。
# 正常流程 service.py 总传 provider.timeout、base_service 总传 effective_timeout, 故兜底不触发 — 小欧 2026-07-13
DEFAULT_CONNECT_TIMEOUT = 30.0  # 【系统级】使用对象: LLMClient 连接超时(秒)
DEFAULT_WRITE_TIMEOUT = 10.0  # 【系统级】使用对象: LLMClient 写超时(秒)
DEFAULT_POOL_TIMEOUT = 10.0  # 【系统级】使用对象: LLMClient 连接池超时(秒)

LLM_MAX_CONNECTIONS = 10  # 【系统级】使用对象: LLM 客户端连接池最大连接
LLM_MAX_KEEPALIVE = 5  # 【系统级】使用对象: LLM 客户端连接池 keepalive 连接数
STREAM_TOTAL_TIMEOUT = 500  # 【系统级】使用对象: base_service.request_stream 单次LLM流式调用总时长硬超时(秒)
# NETWORK_TOOL_MAX_* 已迁移到 tool_constants.py (NETWORK_MAX_CONNECTIONS/NETWORK_MAX_KEEPALIVE)

# BROWSER_USER_AGENT 已迁移到 tool_constants.py → TOOL_BROWSER_UA

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"  # 【系统级】使用对象: API 服务 CORS 允许源

# ============================================================
# 4. 内容截断与字符限制
# ============================================================

# 压缩/裁剪相关常量(MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_BUFFER/CHARS_PER_TOKEN/TEMP_HISTORY_CHAR_LIMIT)
# 已迁移到 app/services/agent/compaction_constants.py (见 2026-08-17 编辑历史) — 小健 2026-08-17

# 系统级长度常量(2026-07-15 归一化治理): 项目规则文件(OmniAgent.md)注入字符上限 — 小欧
PROJECT_CONTEXT_MAX_CHARS = 10000   # 【系统级】使用对象: 项目规则文件(OmniAgent.md)注入 Prompt 字符上限
ACTION_LOG_RESULT_MAX_CHARS = 5000  # 【系统级】使用对象: action_handler.py(日志 tool_result 截断长度, 防 MemoryError)

# 注: 原 DEFAULT_*(11个) 经验证均为死常量(零引用), 已于 2026-07-15 删除;
#     工具相关长度上限已统一迁至 app/tools/tool_constants.py (OBS_*/SHELL_*/WEB_*/XLSX_*/HTTP_*/DOWNLOAD_*/WRITE_TEXT_*)

# 全部 ERR_* 工具错误码已迁移到 tool_constants.py 第12节

# ============================================================
# 5. 会话与缓存(从 message_saver/display_name_cache 迁移)
# ============================================================

MAX_CACHE_SIZE = 1000  # 【系统级】使用对象: 会话/上下文缓存最大条目数

# ============================================================
# 6. SSE流超时(从 react_sse_wrapper 迁移)
# ============================================================

TASK_TIMEOUT = timedelta(hours=1)  # 【系统级】使用对象: task_registry.cleanup_expired_tasks 过期任务(创建>1h)兜底清理, 防 running_tasks 内存注册表泄漏

# HITL超时(秒) — H-1修复 2026-06-25 小欧
# 2026-09-03 小欧 - 真HITL确认超时已可配置化(security.hitl_timeout, config.yaml优先): 此常量作兜底默认
HITL_TIMEOUT = 120  # 【系统级】使用对象: HITL 确认超时(秒), 可被 config security.hitl_timeout 覆盖
HITL_CONFIRM_LEAD = 10  # v1.5.13(2026-09-02 小欧): 真HITL 前端倒计时比后端 HITL_TIMEOUT 提前的秒数(后端120→前端110)
BYPASS_AUTO_LEAD = 2  # v1.5.13(2026-09-02 小欧): bypass 前端倒计时比后端 S1 提前的秒数(后端5→前端3)
HITL_MIN_CONFIRM_TIMEOUT = 3  # 2026-09-03 小欧/北京老陈: 前端倒计时最小值(后端窗口-LEAD钳制下限, 改前硬编码5→现常量3)

# HITL最大待确认数（从 hitl_confirmation.py 集中迁移 2026-07-14 小欧）
MAX_PENDING_CONFIRMATIONS = 100  # 【系统级】使用对象: HITL 最大待确认数

# ============================================================
# 7. 通用正则常量（从 common_patterns.py 迁入）
# ============================================================

HTML_TAG_PATTERN = re.compile(r'<[^>]+>')  # 【系统级】使用对象: fetch_webpage 等 HTML→纯文本清洗正则
SCRIPT_TAG_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)  # 【系统级】使用对象: fetch_webpage 去除 script 标签正则
STYLE_TAG_PATTERN = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL)  # 【系统级】使用对象: fetch_webpage 去除 style 标签正则
MULTI_WHITESPACE_PATTERN = re.compile(r'\s+')  # 【系统级】使用对象: 多空白压缩正则(fetch_webpage/observation)
UTC_OFFSET_PATTERN = re.compile(r'([+-]\d{2}):?(\d{2})')  # 【系统级】使用对象: 时区偏移解析正则

# ============================================================
# 8. 算法与安全白名单
# ============================================================

SUPPORTED_ALGORITHMS: set[str] = {"md5", "sha1", "sha256", "sha512"}  # 【系统级】使用对象: hash工具+safety/hash_helper 哈希算法白名单 — 从 tools/tool_constants.py 迁入 小沈 2026-08-13


