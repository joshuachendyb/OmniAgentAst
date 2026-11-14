# -*- coding: utf-8 -*-
"""
settings_registry — 设置页唯一 Schema 源：key/类型/默认值/值域/存储/来源规则只定一次，
key 全局唯一，加载自检重复直接拒启。

编辑历史:
  2026-09-20 小沈 - 新建（Phase 2 落盘）。
  2026-09-21 小欧 - 补 HITL 参数/沙箱组；app.language 移入外观；删白名单4项与死配置10项；
    键名按域收敛（app.project_root→workspace.*、app.max_steps→agent.max_steps 等）；
    系统 Tab 重组为 运维日志/工程目录/关于，paths.* 为派生只读值（由 settings_service 实时算）。
  2026-09-22 小欧 - logging.level 补 env_key（否则标 yaml 可编辑却"改了不生效"= 假保存）；
    无界 int 项补 range（负数曾当合法值落盘致消费方崩溃）。
  2026-09-23 小欧 - 补 LLM 采样/裁剪/压缩/网络参数；notice 全量重写为用户语言
    （禁出现 SSE/HITL/信号量等内部黑话）；cors_origins 迁入 system 组并去 tuning 前缀。
  2026-09-24 小欧 - tuning.stream_task→live_front（与 LLM 流式撞名易误读）；新增 model_library 组。
  2026-09-26 小欧 - 新增 security.access_token（secret，拒经 /settings 写，唯一写入口 auth/token）
    与 security.access_token_allowlist，置于 appearance 组最前。
  2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}（后端一次生成，前端纯回显）。
  2026-09-27 小欧 - 修 workspace.project_root 默认值 "E:\test_dir" → ""（原值非空使
    `if root:` 恒真、永不回退用户主目录）。另精简本文件冗长编辑历史（410→285 行，只留决策不留过程）。
  2026-09-27 小欧 - 根因修复：_item 增 env_inject（取代 config.py 手写注入清单，键名只此一处）
    与 list_of（白名单落盘前归一+校验）；appearance label「外观」→「前端」
  2026-09-27 小欧 - 同轮再精简：_item docstring 与 security/appearance 分组注释去重（原"只有三处"
    那类会腐烂的清单改为直接指向唯一真源 app/config.py::_apply_env_overrides）。
  2026-09-28 小欧 - 字典键 range_→range 全链路统一（DTO/前端本就叫 range，Pydantic 静默丢弃
    range_ 致响应 range 恒 null：值域不显示、InputNumber 失 min/max、字号滑块回落 0~100）。
    参数名 range_ 保留（避内置 range，同 model_service.add_model）。
  2026-10-05 小欧 - appearance 组加两个独立 bool: step_render.thoughtMarkdown「思考排版」(thought块
    Markdown渲染) + step_render.reasoningVisible「推理内容」(reasoning块折叠初值), 默认皆开; 置于
    fontSize 之后(sectionOf 只比相邻项), 不加 restart/secret/env_key。缺键由 get_group 回填默认值。
  2026-10-05 22:16:38 小欧 - 指人后监下调优与安全的四个标签/notice 修正（更准确、更贴近实际语义）：
    tuning.llm.response_fallback「工具失败转文字」→「响应无工具转文本」；
    tuning.llm.response_retries「内容错误重试」→「响应内容错重试限额」；
    tuning.concurrency.shell_pool_max_per_type「终端会话槽位」→「PS并发池限额」；
    security.enabled「安全开关」→「HTL人工开关」，notice 同步为"关闭后，无需人工确认，
    无信任，自动延时确认安全检查，（盘根/项目根等删除硬防线仍生效）"。
    仅改展示文案与说明，不改 key、默认值与域，旧配置文件不受影响。
  2026-10-10 小欧 - general 组新增两项全局 thinking 缺省值（通用模型参数区缺思考项）:
    llm.sampling.enable_thinking(bool,默认 True) 与 llm.sampling.reasoning_effort(select,默认 medium,
    四档 minimal/low/medium/high)，单模型没单独配置时用这两个，已在模型 Tab 配了的不受影响。
    group 项数 10 → 12。前端 SettingRow 按 type 渲染(bool→Switch / select→下拉)，零改动 — 小欧-2026-10-10
  2026-10-12 小欧 - sandbox 组新增「工具 › 语法检测」8 项(沙箱页原仅 8 项偏空, 工具类设置挂此处):
    1 个总开关 sandbox.tool.syntax_check.enabled + 7 个语言独立开关(python/json/yaml/toml/xml/
    javascript/typescript), 全部 bool、默认 True、restart=False。
    判定单点落在 syntax_validator.validate_syntax(新 _syntax_enabled), write/edit 调用方零改动;
    前端 SettingsGroup.sectionOf 加 sandbox 分支拆「运行控制/工具/语法检测」三节。
    刻意不加 env_inject(会触发 _build_index 双向一致性自检, 不同步即拒启动) — 小欧-2026-10-12
  2026-10-18 小欧 - 键名 security.enabled → security.hitl_enabled: 该项只决定是否走人工确认链路, 危险防护
    (删根/系统目录/自杀/危险命令)无条件生效。改名后与同段 hitl_timeout/auto_confirm_delay 前缀一致。
    同步点: config_service.DEFAULT_SECURITY、config.yaml、config.yaml.example、前端 SettingsPage 硬编码键、
    path_tool_safety_checker 读点。不保留旧键别名 — 小欧-2026-10-18
  2026-10-18 小欧 - security 组按子命名空间重组(上一条的 hitl_enabled 形态随之作废):
    security.system.confirm_dangerous_ops  系统级要不要拦
    security.hitl.enabled / .auto_confirm_delay / .timeout / .shell_readonly_prefixes  人工确认链路
    security.trust.ttl_days  会话信任时长
    键名不再是"security.XXX"平铺, 而是按前缀定归属; 前端 sectionOf 同步按前缀拆
    「系统 / HTL人工确认 / 信任」三节, 展示名不写业务细节, 由 DANGER_LABELS 供二次确认文案。
    前缀即可识别归属, 故未引入新的分组注册机制(两三个前缀, if 直判即可)。
  2026-10-18 小欧 - 新增 shell_readonly_prefixes(list_of, 默认展示值取安全层内置清单) 接入设置页:
    原为纯硬编码, 收紧须改代码发版; 接入后仅需改配置, 且清单在设置页可见可审计。
    注释精简冗余标注, 技术说明原样保留。
  2026-10-19 小欧 - security 组新增 9 项。
    security.system 段 6 项(硬拦类): enabled(总闸) / forbidden_system_path_block /
    forbidden_non_system_path_block / white_list_block / shell_danger_block / shell_risk_block;
    security.hitl 段 4 项(确认类): write_confirm / delete_confirm / dual_path_confirm / shell_path_confirm。
    全部 bool 默认 True(缺键按"开", fail-closed 方向); 键名按前缀自动归入「系统 / HTL人工确认」两节, 前端零改动。
   2026-10-20 小欧 - 新增路径工具四类归类名单只读展示(security.hitl.tool_lists.read/write/delete/dual):
     紧随 shell_readonly_prefixes; readonly=True, 取值直接来自 tool_constants 判定名单(展示与实判同源),
     设置页显示为可复制文本、不可编辑; 改动归类仍须改代码, 避免配置面改写安全判定口径。
    2026-10-24 小欧 - reasoning_effort options 移除 minimal: OpenAI 官方文档明确 "Not all reasoning
      models support every value"，minimal 是少数派值(agnes-2.5-flash 不认→HTTP 400)，全局兜底只留
      low/medium/high 三个所有推理模型都支持的核心值；notice 同步更新说明少数派值需 per-model 配置 — 小欧-2026-10-24
   2026-10-25 小欧 - tuning.trim 3 键→5 键: keep_recent_rounds(int,5-20,默认5,裁剪时最近 N 个 FC 工具步
      不参与裁剪)、tools_token_reserve(int,5000-80000,默认30000,tools schema 输入 token 预留防超窗 400);
      同批同步 config.yaml.example(trim 块) 与 config/config.yaml(本地副本); 并立 _item 前铁规注释:
      加参数必须先同步 config.yaml.example, 严禁只在 registry 加 — 小欧-2026-10-25
   2026-10-31 小欧 - llm.context_limit_default 默认值 262144 魔法数字改引 app.constants.DEFAULT_CONTEXT_LIMIT
      (常量自 compaction_constants 迁入 app/constants.py, 设置项默认值与 runtime 兜底同一真源, 值不变) — 小欧-2026-10-31
   2026-11-03 小欧 - system 组新增 system.chat_retention_days(对话历史保留天数, int 0-3650, restart=True,
      0=关闭; 启动期清理超期会话, 配合设置页系统tab「数据治理」分组渲染) — 小欧-2026-11-03

   2026-11-03 17:40 小欧 - 三堂会审修复: line 324 注释「归 tuning.live_front 命名空间」改「归 system 命名空间」
      (实际 key=system.chat_retention_days, 注释与代码对齐) — 小欧-2026-11-03

   2026-11-03 小欧 - general 组新增 logging.console_level(select, 默认 WARNING, 放 logging.debug 之后):
      控制台(黑窗口)显示阈值与文件日志解耦, 默认 WARNING 零行为变化; 消费方 _get_console_level
      (logger/config+shared_handler), restart=False 走热重载10s生效。同轮同步 config.yaml.example
      与 config/config.yaml(铁规三处同步), general 12→13 项 — 小欧-2026-11-03
   2026-11-03 小欧 - 两级日志名副其实+归位: logging.level→logging.file_level(标签「文件日志级别」)移入 general 紧随调试模式;
      debug/level 的 restart 纠正为 False(10s 热重载实测生效), 「调试模式」notice 补全真实作用域 — 小欧-2026-11-03
   2026-11-03 21:30 小欧 - 设置项 notice 订正: 「调试模式」删去不存在的「删除类硬阻断豁免」(与 hitl 两项
       「硬防线仍生效」自相矛盾); max_file_size/backup_count 恢复 restart=True — 小欧-2026-11-03
   2026-11-03 21:35 小欧 - 更正 L86 表述: console_level 消费方已收口为 LogConfig.get_console_level_int()
      (logger/config 唯一换算点, shared_handler 与 log_and_print 共用), 私有 _get_console_level 已删除 — 小欧-2026-11-03
   2026-11-03 21:40 小欧 - console_level 语义改「精确档位」: 控制台只显示 == 所选级别的记录(log_and_print 与
      ConsoleMirrorHandler 同口径), notice 同步改写; 文件通道仍为 >= 阈值 — 小欧-2026-11-03
   2026-11-03 21:56 小欧 - 两档位独立(北京老陈令): 删 _get_gate_level()=min(文件,控制台), 总闸恒定 DEBUG;
      两项 notice 均补「互不影响」表述 — 小欧-2026-11-03
   2026-11-03 22:20 小欧 - 再撤销双键(北京老陈令: 一个值即可, 拆两个是画蛇添足): console_level 整项删除,
      general 14→13 项; 键回单一 logging.level(标签「日志级别」, 默认 WARNING), notice 写明一值两用法 —
      控制台只显示 == 该值的行, 日志文件按原逻辑记 >= 该值; debug true 时文件强制 DEBUG、控制台不受影响 — 小欧-2026-11-03
    2026-11-08 小欧 - media 组补齐: 「转发图片外链」notice 的条数上限改引 app.constants.MAX_REMOTE_IMAGES(与 vision 截断同源),
      并补「被拒会留一行说明」; 与内联/压缩四项 notice 的语义对齐 — 小欧-2026-11-08
    2026-11-09 小欧 - 上架就地配置: 外链检测项登记为 hidden(hidden=True 仅组内不渲染, 键仍可读写), 迁到设置页②实测行就地显示;
      默认值定为 Wikimedia Commons 公网 PNG — 小欧-2026-11-09
    2026-11-09 小欧 - 默认检测图换 cn.bing.com/favicon.ico: wikimedia 对 agnes 厂商146s连接超时必失败(实测定性),
      Bing favicon 走厂商外链腿 30s 过(image_tokens=64), 微软全球CDN可达性最好 — 小欧-2026-11-09
    2026-11-09 小欧 - 「转发图片外链」notice 补准(逐句对 vision.py 会审): 裸链接?参数原样保留(同批修
      _BARE_IMAGE_RE 丢参)、超出4个静默不转发、未实测模型链接整个忽略不留说明、内网改「内网/保留地址」 — 小欧-2026-11-09
    2026-11-10 小欧 - tuning.agent 新增 disabled_tools(禁用工具名单, textarea 可编辑): 原 tools_alias_mapper
      .UNAVAILABLE_OFFICIAL_TOOLS 硬编码五元组; 命中即提示「禁止使用」并点明生效全组, 只影响未注册工具
      措辞、不拦已注册工具; 键存在即配置为真值——清空=不禁用任何工具(不兜底), 仅缺键/异常形状回落内置;
      运行时消费口 get_disabled_official_tools/is_disabled_tool(get_config 热读)。
      同批同步 config.yaml.example 与 config/config.yaml(铁规三处同步) — 小欧-2026-11-10
    2026-11-11 小欧 - 新增 media.probe_video_url / media.probe_audio_url(输入能力验证视频/音频素材地址, hidden 仅组内不渲染, 键可读写; 默认值=实测择优公网小文件) — 小欧-2026-11-11
    2026-11-11 小欧 - 三个验证素材地址(probe_image_url/probe_video_url/probe_audio_url)由 hidden 回媒体页直接显示:
      原 probe_image_url 迁②Image_URL 行就地配置、probe_video_url/probe_audio_url 无就地入口致"无处可配"(既不在媒体页也不在就地行);
      现统一去掉 hidden 回 media 组「外链图片」小节直接编辑(SettingRow text 渲染, 走组保存), 与 remote_url_passthrough 同节 — 小欧-2026-11-11
    2026-11-13 商量 - 新增后台命令 3 项: tuning.concurrency.shell_max_background(并发上限) +
      tuning.shell_bg_log_max_mb(输出文件轮转阈值) + tuning.shell_bg_result_retain_hours(结果保留时长) — 商量-2026-11-13
    2026-11-13 商量 - 复核撤销 shell_bg_log_max_mb(轮转从未实现, 纯假配置; 保留 shell_bg_result_retain_hours),
      后台命令配置项实为 2 项 — 商量-2026-11-13
    2026-11-13 商量 - 三堂会审补 tuning.shell_bg_max_output_mb(输出上限, 超限杀进程防磁盘写满),
      后台命令配置项 3 项 — 商量-2026-11-13
    2026-11-13 商量 - 10轮三堂会审: 后台输出上限默认值定为 512MB(并发5条峰值2.5GB, 守住系统级红线;
      原 2048MB 峰值 10GB 与"防磁盘写满"初衷相悖), 并发上限提示补"需重启生效" — 商量-2026-11-13

"""
from typing import Any, Dict, List, Optional

# 注入清单在 app.config（最底层，不能反向依赖本包），一致性由 _build_index 自检
from app.config import ENV_INJECTED_KEYS

# 2026-10-31 小欧 - llm.context_limit_default 默认值引系统级常量(单一真源, 消魔法数字 262144):
#   与 runtime 兜底(lifecycle/service.parse_model_params)同源, 改值只改一处
# 2026-11-08 小欧 - 外链条数上限引系统级常量: notice 文案与 vision 截断同源, 改值只改一处
from app.constants import DEFAULT_CONTEXT_LENGTH, MAX_REMOTE_IMAGES

# 只读免确认白名单的**默认展示值**取自安全层内置清单(services→safety 依赖方向合法, 与本包
# security_docs 引 SYSTEM_PROTECTED_DIR_NAMES 同款)。取内置而非空串: 该清单命中即免弹窗+免沙箱,
# 设页若显示空白则等于"用户看不见它存在" —— 正是本项要消除的问题, 故直接把生效清单亮出来。
from app.safety.shell_readonly import SHELL_READONLY_PREFIXES as _READONLY_PREFIXES
from app.tools.tool_constants import (
    DELETE_PATH_TOOLS as _DELETE_PATH_TOOLS,
)
from app.tools.tool_constants import (
    DUAL_PATH_TOOLS as _DUAL_PATH_TOOLS,
)

# 2026-10-20 小欧 - 路径工具四类名单(只读展示, 与判定同源): 直接取 tool_constants 判定名单,
#   不另抄一份, 避免设置页展示与实判漂移
from app.tools.tool_constants import (
    READ_PATH_TOOLS as _READ_PATH_TOOLS,
)
from app.tools.tool_constants import (
    WRITE_PATH_TOOLS as _WRITE_PATH_TOOLS,
)

# 2026-11-10 小欧 - 禁用工具名单默认展示值取自 tools_alias_mapper 内置五件套(与运行时回落同一真源,
#   展示与实判不漂移); 生效值=config tuning.agent.disabled_tools, 缺键回落此清单, 清空=不禁用任何工具，工具名称逗号分隔
from app.tools.tools_alias_mapper import UNAVAILABLE_OFFICIAL_TOOLS as _UNAVAILABLE_OFFICIAL

# ============================================================
# !! 铁规（北京老陈 2026-10-25 令）：新增 _item 必须同步 config.yaml.example
# !!
# !! 步骤（缺一不可）：
# !!   1. backend/config.yaml.example  — git 跟踪的唯一模板（必须）
# !!   2. settings_registry.py         — 本文件（必须）
# !!   3. config/config.yaml           — 本地运行时副本（gitignore，仅本机生效）
# !!
# !! 严禁只在本文件加 _item 而不同步 config.yaml.example：代码兜底默认值虽能生效，
# !! 但模板缺键即配置面永久缺失该参数、发版后新装机不可见；registry 与 example
# !! 脱节无法被任何自检捕获。
# !! 严禁只加 config/config.yaml（本地副本）而漏 template 与本文件。
# ============================================================


def _item(key: str, type_: str, label: str, default: Any = None,
          options: Optional[List[Any]] = None, range_: Optional[List[float]] = None,
          step: Optional[float] = None, restart: bool = False, secret: bool = False,
          readonly: bool = False, notice: str = "",
          env_key: Optional[str] = None, env_inject: bool = False,
          list_of: Optional[str] = None, hidden: bool = False) -> Dict[str, Any]:
    """单项构造：storage 统一 YAML。

    参数 range_ 的尾下划线只避内置 range，与字典键 range 刻意异名（对齐 model_service.add_model）。
    env_key 只决定页面"来源"标记；env_inject=True 另表示 env 值要注入 get_config()，
否则页面显示值≠实际生效值。两者分开：ai.model_ref 是 dict 而 env 是标量，注入会写坏结构。
注入清单在 app.config.ENV_INJECTED_KEYS，双向一致性由 _build_index 启动自检保证。
list_of 声明"本项是某类元素的列表"，落盘前归一+校验，规则见 app/utils/allowlist.py。
hidden=True 的项仍在注册表(可读写)，但设置页组内不再渲染——它已迁到具体功能行就地配置 — 小欧-2026-11-09
"""
    return {"key": key, "type": type_, "label": label, "default": default,
            "options": options, "range": range_, "step": step, "storage": "YAML",
            "restart": restart, "secret": secret, "readonly": readonly, "notice": notice,
            "env_key": env_key, "env_inject": env_inject, "list_of": list_of, "hidden": hidden}


GROUPS: Dict[str, Dict[str, Any]] = {
    # 4.1 通用（general，13 项）
    "general": {"label": "通用", "items": [
        # 默认空：config.get_project_root 靠 `if root:` 判空后回退用户主目录（Path.home()）
        _item("workspace.project_root", "text", "项目根目录", ""),
        _item("workspace.allowed_dirs", "textarea", "授权目录", "",
              notice="项目根之外额外授权访问的工作目录，多个用换行分隔"),
        _item("logging.debug", "bool", "调试模式", True,
              notice="全局调试开关（不止日志）：开=日志强制 DEBUG 且带文件名行号、开放调试接口（/echo、/tool/*）、文件落盘到 backend\\files（打包运行=程序目录 files）；关=按「日志级别」记录、文件落盘到用户目录 ~/.omniagent\\files、调试接口关闭。改动后约 10 秒自动生效，无需重启"),
        # 2026-11-03 小欧 - 撤销双键(北京老陈令: 一个值即可, 拆两个是画蛇添足): 单键 logging.level,
        #   控制台只显示 == 该值的行, 日志文件按原逻辑记 >= 该值; 调试模式开时文件强制 DEBUG(控制台不受影响)
        _item("logging.level", "select", "日志级别", "WARNING",
              options=["DEBUG", "INFO", "WARNING", "ERROR"],
              notice="一个值两种用法：后端控制台（黑窗口）只显示「等于所选级别」的日志，不连带其他级别（例如选 WARNING 只显警告行，选 DEBUG 只显调试行）；日志文件（位置见下方「日志目录」）按常规方式记录「该级别及以上」。上方「调试模式」开启时日志文件被强制为 DEBUG，控制台不受影响。改动后约 10 秒自动生效，无需重启", env_key="LOG_LEVEL"),
        _item("agent.max_steps", "int", "最大轮数", 10000, range_=[1, 10000],
              notice="单任务最多执行的对话轮数（循环门限）：任务条上的『轮数』到顶就强制结束任务；调大=允许跑更久，调小=更早刹车。注意这不是任务条上的『步数』（步数只是自动统计，跟着轮数走，没有单独上限）"),
        _item("llm.sampling.temperature", "float", "采样温度", 0.7, range_=[0, 2],
              notice="全局默认:控制输出随机性：0=完全确定性（每次相同输入输出一致），1=默认随机性，2=最高随机性"),
        _item("llm.sampling.max_tokens", "int", "最大输出Token", 16384, range_=[1, 100000],  # 2026-11-01 小欧 原名「单次最大 token」含糊, 用户指令改
              notice="全局默认:最大输出 token 数(输出封顶)，超长截断；与厂商声明/厂商级上限取最小"),
        _item("llm.sampling.top_p", "float", "核采样 top_p", 1.0, range_=[0, 1],
              notice="全局默认:核采样阈值：从概率质量前 p 的词中采样；1.0=不筛选；通常与温度二选一调节，同时调易相互抵消"),
        _item("llm.sampling.frequency_penalty", "float", "频次惩罚 (frequency_penalty)", 0, range_=[-2, 2],
              notice="全局默认:正值减少重复词频（更多样），负值增加重复词频（更聚焦），0=不启用"),
        _item("llm.sampling.presence_penalty", "float", "存在惩罚 (presence_penalty)", 0, range_=[-2, 2],
              notice="全局默认:正值惩罚已出现过的词（鼓励新话题），负值鼓励重复已出现的词，0=不启用"),
        _item("llm.sampling.enable_thinking", "bool", "思考开关", True,
              notice="全局默认:思考开关默认值（单个模型没单独配置时用这个）：开=模型先思考再回答；关=直接回答。单模型可在模型参数里单独覆盖"),
        _item("llm.sampling.reasoning_effort", "select", "推理深度", "medium",
              options=["low", "medium", "high"],
              notice="全局推理深度默认值，只列所有推理模型都支持的三个核心值(low/medium/high)。"
                     "少数派值(none/minimal/xhigh/max)各模型支持不同，放全局会导致切模型时HTTP 400，"
                     "需在模型参数里单独配置"),
        _item("llm.context_length_default", "int", "默认上下文窗口", DEFAULT_CONTEXT_LENGTH, range_=[200000, 2000000],
              notice="全局默认:模型一次能记住的内容总量默认值（单个模型没单独配置时用这个），约 25.6 万 token"),
    ]},
    # 4.2 模型（model，结构化语义；CRUD 由 model_service 承接，见 9.1.3）
    "model": {"label": "模型", "items": [
        _item("ai.model_ref", "model_ref", "当前系统全局使用模型", None,
              notice="当前选用的模型（哪个服务商+哪个模型）；被环境变量强制指定时整行只读",
              env_key="AI_PROVIDER"),
    ]},
    # 媒体（media）：图片送进模型的上限与压缩参数，只管"怎么送"，不管"能不能看" —
    #   能不能看图由 vision.supports_image_input 判定(实测优先, 无实测回落 input_modalities) — 小欧-2026-11-08
    "media": {"label": "媒体", "items": [
        _item("media.inline_limit_mb", "int", "内联图片上限(MB)", 2, range_=[1, 20],
              notice="内联 = 图片字节经 base64 编进请求体随消息发送。按原始文件大小算，单张超过这个值就不直接发，先按下面三项压缩（压缩开关关掉则直接不发）。外链（只传图片地址、由厂商自己抓取）不走这条，不受本项限制"),
        _item("media.compress_enabled", "bool", "超限自动压缩", True,
              notice="超限的内联图片先在本机等比缩小再编码（JPEG/PNG），原文件不动。关掉则超限图片一律不发，只在对话里留一行说明"),
        _item("media.compress_max_edge", "int", "压缩长边(像素)", 2048, range_=[256, 4096],
              notice="压缩后长边的像素上限，等比缩放。调小更省流量、细节更少；调大更清晰，但可能压不到上限以内而放弃发送"),
        _item("media.compress_jpeg_quality", "int", "JPEG 质量", 85, range_=[1, 95],
              notice="压缩成 JPEG 时的量化质量。85 对照片基本看不出差别；截图、图表、含小字的图建议 92 以上，否则文字边缘发糊。带透明通道的图压缩后存 PNG（无量化损失，但仍会等比缩小），本项对它不生效"),
        _item("media.remote_url_passthrough", "bool", "转发图片外链", True,
              notice=f"在消息里明确写出的公网图片地址转给模型：不下载、不转码，请求体里只放地址，由厂商自己抓取。只认两种写法：Markdown 图片 ![](https://…)，或带 .png/.jpg/.jpeg/.gif/.webp/.bmp 后缀的裸链接（?查询参数原样保留）；单条消息最多 {MAX_REMOTE_IMAGES} 个，超出的静默不转发；本机地址、内网/保留地址、以及 .pdf/.html/.zip 等非图片后缀一律不转发，被拒的会在对话里留一行说明。且只有「模型库」实测出外链可用的模型才会真收到，未实测的按外链不可用处理、链接整个忽略不留说明（外链没通时转发会导致整轮请求被拒）。关掉则只发内联"),
        _item("media.probe_image_url", "text", "图片输入检测外链素材地址",
              "https://www.baidu.com/img/flexible/logo/pc/result.png",
              notice="「实测」时用来测外链腿的那张公网图片地址（内联腿用内置的 8×8 PNG，不依赖本项）。留空 = 只测内联，外链不写结论；地址会原样交给厂商自己抓取，别用带隐私参数的链接"),
        # 2026-11-11 小欧 - 视频/音频输入验证素材地址(默认值=本机实测可达性/速度/体积择优的全球 CDN
        #   小文件(视频 test-videos.co.uk, 音频 runoob; 与图片外链地址同口径) — 小欧-2026-11-11
        _item("media.probe_video_url", "text", "视频输入检测外链素材地址",
              "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4",
              notice="「视频输入能力验证」腿用的公网视频地址（约 991KB 的 mp4，全球 CDN），原样交给厂商接口抓取。留空 = 用内置默认地址；换成私有地址时保证厂商侧可直连 GET"),
        _item("media.probe_audio_url", "text", "音频输入检测外链素材地址",
              "https://www.runoob.com/try/demo_source/horse.mp3",
              notice="「音频输入能力验证」腿用的公网音频地址（约 29KB 的 mp3），后端先下载再 base64 内联发送。留空 = 用内置默认地址"),
    ]},
    # 4.3 安全（security，YAML，即时；命令安全由 path_safe_check/tools/security 代码内实现）
    #   本组是**操作安全**（要不要拦用户的危险动作）。准入控制（谁能进得来）在 appearance 组首，
    #   两者语义分开，避免误以为"关掉安全开关就不用输口令"。
    #   2026-10-18 小欧 - 按使用者视角分三段，**组名进键名前缀**（分节由前端 sectionOf 按前缀切，
    #   与 sandbox.tool.* 同一机制，零新增渲染逻辑）:
    #     security.system.* 系统   —— 硬拦类：要不要拦
    #     security.hitl.*   人工确认 —— 确认类：要不要问
    #     security.trust.*  信任   —— 会话信任
    #   现有 6 项按此重排并改键名，禁 backward 不留旧键别名。
    "security": {"label": "安全", "items": [
        # ── 系统段 ──
        # 2026-10-05 22:16:38 小欧 - 标签「安全开关」改「HTL人工开关」；notice 文案更新。
        #   注意语义：confirmDangerousOps 仍负责操作前的人工确认弹窗，本项管「要不要走人工确认链路」。
        _item("security.system.confirm_dangerous_ops", "bool", "保存设置时二次确认", True,
              notice="保存时再弹一次确认框（防误触）；后端的安全拦截不依赖这个开关"),
        # 2026-10-19 小欧 - 系统段 5 项硬拦类开关(要不要拦)
        #   security.system.enabled 为总闸, 关闭后整个安全层放行(实现: 折入 app/safety/safety_switch.py)
        _item("security.system.enabled", "bool", "安全模块启用", True,
              notice="关闭后不再做路径与命令的权限判定，工具直接执行；参数合法性初查（空路径/路径穿越等）与工具直调兜底仍生效"),
        _item("security.system.forbidden_system_path_block", "bool", "禁区系统目录拦截", True,
              notice="关闭后不再拦截磁盘根与系统保护目录。此项不影响禁区非系统目录拦截与 bash 危险命令拦截"),
        _item("security.system.forbidden_non_system_path_block", "bool", "禁区非系统目录拦截", True,
              notice="关闭后不再拦截代码目录及其内部子级、允许根集自身及其上级。此项不影响禁区系统目录拦截"),
        _item("security.system.white_list_block", "bool", "白名单外路径拦截", True,
              notice="关闭后白名单档不判：白名单外路径的写/删/递归删均直接放行。禁区系统/非系统目录仍由各自开关控制"),
        _item("security.system.shell_danger_block", "bool", "bash 危险命令拦截", True,
              notice="关闭后不再拦截高危命令（磁盘写入/关机/执行等）。此项不影响中风险命令确认"),
        _item("security.system.shell_risk_block", "bool", "bash 风险命令拦截", True,
              notice="关闭后不再对中风险命令发起人工确认。此项不影响高危命令拦截与路径判定"),
        # ── HTL人工确认段 ──
        # 2026-10-18 - 小欧 - 键名 security.enabled → security.hitl_enabled → security.hitl.enabled:
        #   该项只决定是否走人工确认链路, 危险防护(删根/系统目录/自杀/危险命令)不受其影响。
        #   两次改名后与同段 hitl.timeout / hitl.auto_confirm_delay 同前缀。禁 backward。
        _item("security.hitl.enabled", "bool", "人工确认总开关", True,
              notice="关闭后，无需人工确认，无信任，自动延时确认安全检查，（盘根/项目根等删除硬防线仍生效）。默认开启：缺键时按『开』处理，缺配置不会悄悄放松安全等级"),
        # 2026-10-19 小欧 - 确认段 4 项(要不要问); 只关"问不问", 硬拦不受影响
        _item("security.hitl.write_confirm", "bool", "写操作确认", True,
              notice="关闭后写入需授权的路径不再弹窗，直接放行。危险写入拦截不受本项影响"),
        _item("security.hitl.delete_confirm", "bool", "删除操作确认", True,
              notice="关闭后删除需授权的路径不再弹窗，直接放行。递归删除允许根集外目录的硬拦不受本项影响"),
        _item("security.hitl.dual_path_confirm", "bool", "双路径操作确认", True,
              notice="关闭后 copy/move 等双路径工具的授权请求不再弹窗，直接放行"),
        _item("security.hitl.shell_path_confirm", "bool", "shell 命令确认", True,
              notice="关闭后 bash 命令内的路径授权不再判定、直接放行。中风险命令确认与危险命令拦截均不受本项影响"),
        _item("security.hitl.auto_confirm_delay", "int", "自动确认倒计时(秒)", 10, range_=[0, 3600],
              notice="自动确认弹窗倒计时（秒），到时没人点就自动放行"),
        _item("security.hitl.timeout", "int", "人工确认超时(秒)", 120, range_=[1, 86400],
              notice="人工确认弹窗最长等你多久（秒），超时按弹窗设定的处理方式收尾"),
        # 2026-10-18 小欧 - 本项原先是无配置面的硬编码白名单: 命中即**同时**跳过 HITL 确认与沙箱预检
        #   (safety_gate / sandbox.executor / execute_shell_command 三个消费点), 设置页完全不可见。
        #   内置默认 30 条(含 tasklist/systeminfo/netstat/ipconfig /all 等信息展示类, 以及 get- 这类宽前缀)。
        _item("security.hitl.shell_readonly_prefixes", "textarea", "只读命令免确认白名单",
              ", ".join(_READONLY_PREFIXES),
              notice="当前生效的完整清单(共 %d 条, 逗号分隔), 命中的命令**免弹窗且免沙箱预检**, 直接执行。删掉某项=该前缀不再豁免(收紧); 整框清空=回退内置默认清单。新增前缀请自行确保是纯只读命令 —— 写操作前缀等于开后门" % len(_READONLY_PREFIXES)),
        # 2026-10-20 小欧 - 路径工具四类归类名单(北京老陈令: 按只读命令白名单的形式在设置页可见)。
        #   只读展示, 不支持设置页修改 —— 真值源是 tool_constants 判定名单, 展示与判定同源;
        #   若放开编辑会让"展示归类"与"实际放行/拦截"两套口径漂移, 故 readonly=True 且取值不做插值。
        # 2026-10-20 小欧 - 显示样式统一(北京老陈令): type 由 readonly 改 textarea + 保留 readonly=True,
        #   前端按"禁用 textarea"渲染(与只读命令白名单同外观不可编辑); 后端 _item_data readonly 分支
        #   不受 type 影响(仍返 comma-joined 同源值), update_settings 仍因 readonly 不生效。
        _item("security.hitl.tool_lists.read", "textarea", "只读工具名单",
              ", ".join(sorted(_READ_PATH_TOOLS)),
              notice="当前代码内置的只读工具归类(共 %d 条, 逗号分隔), 仅供查看与审计; 修改需改 backend/app/tools/tool_constants.py 的 READ_PATH_TOOLS" % len(_READ_PATH_TOOLS)),
        _item("security.hitl.tool_lists.write", "textarea", "写入工具名单",
              ", ".join(sorted(_WRITE_PATH_TOOLS)),
              notice="当前代码内置的写入工具归类(共 %d 条, 逗号分隔), 仅供查看与审计; 修改需改 backend/app/tools/tool_constants.py 的 WRITE_PATH_TOOLS" % len(_WRITE_PATH_TOOLS)),
        _item("security.hitl.tool_lists.delete", "textarea", "删除工具名单",
              ", ".join(sorted(_DELETE_PATH_TOOLS)),
              notice="当前代码内置的删除工具归类(共 %d 条, 逗号分隔), 仅供查看与审计; 修改需改 backend/app/tools/tool_constants.py 的 DELETE_PATH_TOOLS" % len(_DELETE_PATH_TOOLS)),
        _item("security.hitl.tool_lists.dual", "textarea", "双动作工具名单",
              ", ".join(sorted(_DUAL_PATH_TOOLS)),
              notice="当前代码内置的双动作工具归类(共 %d 条, 逗号分隔), 仅供查看与审计; 修改需改 backend/app/tools/tool_constants.py 的 DUAL_PATH_TOOLS" % len(_DUAL_PATH_TOOLS)),
        # ── 信任段 ──
        # 2026-10-18 小欧 - 本项此前只有代码侧读取(trust_db._ttl_expiry 读 security.trust.ttl_days,
        #   默认 90), 本表未注册, 设置页无从展示/修改。补注册后该项可见可改。
        _item("security.trust.ttl_days", "int", "会话信任有效期(天)", 90, range_=[1, 3650],
              notice="弹窗里勾了『信任此操作』后, 该信任在多少天后自动失效(同一会话内免弹窗)。到期后同类操作会重新弹窗询问。调小=更频繁询问, 调大=更少打扰但风险窗口更长"),
    ]},
    # 4.4 沙箱（sandbox，8 项，运行时参数）
    "sandbox": {"label": "沙箱", "items": [
        _item("sandbox.enabled", "bool", "沙箱开关", True, restart=True,
              notice="关闭后取消沙箱预检，命令/文件操作直通执行"),
        _item("sandbox.backend", "select", "沙箱后端", "job_object",
              options=["job_object"], restart=True,
              notice="当前仅支持 job_object（Windows 进程 Job 隔离）"),
        _item("sandbox.max_concurrent_sandboxes", "int", "最大并发沙箱数", 3, range_=[1, 128],
              notice="同时运行的沙箱并发数，超出排队等待"),
        _item("sandbox.max_workspace_mb", "int", "工作区上限(MB)", 500, range_=[1, 1048576],
              notice="工作区真实磁盘占用上限（MB）"),
        _item("sandbox.max_shadow_mb", "int", "影子区上限(MB)", 100, range_=[1, 1048576],
              notice="高危文件操作（删除/复制/移动）预演副本上限（MB）"),
        _item("sandbox.process_memory_limit_mb", "int", "进程内存上限(MB)", 2048, range_=[1, 1048576],
              notice="沙箱内进程内存上限（MB），超限终止（误杀时调大）"),
        _item("sandbox.default_timeout_sec", "int", "默认超时(秒)", 60, range_=[1, 86400],
              notice="命令未指定超时时的默认超时（秒）"),
        _item("sandbox.max_timeout_sec", "int", "最大超时(秒)", 300, range_=[1, 3600],
              notice="单次执行最大超时（秒），超出截断转裁决"),
        # 工具 › 语法检测(2026-10-12: 沙箱页偏空, 工具类设置挂此处; 总开关 + 每语言独立开关)
        #   判定单点落在 syntax_validator.validate_syntax, write/edit 调用方零改动;
        #   勿加 env_inject(会触发 _build_index 双向一致性校验, 不同步直接拒启动)
        _item("sandbox.tool.syntax_check.enabled", "bool", "语法检测总开关", True,
              notice="写代码文件时做语法检测.开-检出问题只告警不阻断写入；关-不检测任何语言,目前支持的tool是 Write和Edit"),
        _item("sandbox.tool.syntax_check.python", "bool", "Python", True,
              notice="检测 .py / .pyw / .pyi代码文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.json", "bool", "JSON", True,
              notice="检测 .json代码文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.yaml", "bool", "YAML", True,
              notice="检测 .yaml / .yml文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.toml", "bool", "TOML", True,
              notice="检测 .toml（如 pyproject.toml）代码文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.xml", "bool", "XML", True,
              notice="检测 .xml代码文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.javascript", "bool", "JavaScript(JSX)", True,
              notice="检测 .js / .mjs / .cjs / .jsx代码文件开关.开-支持检测,关-不检查"),
        _item("sandbox.tool.syntax_check.typescript", "bool", "TypeScript(TSX)", True,
              notice="检测 .ts / .tsx代码文开关.开-支持检测,关-不检查"),
    ]},
    # 4.5 系统（system，13 项：2 运维日志配置 + 1 日志目录只读 + 6 工程目录只读 + 1 网络 CORS + 1 数据治理 + 2 关于只读）
    #   注意：本小节新增 / 删除 paths.* 条目务必同步 settings_service._item_data 的 paths 派生字典，
    #   二者 keys 一一对应，漏配将抛 KeyError（fail-fast 防静默空白）
    "system": {"label": "系统", "items": [
        # --- 运维日志（2 配置 + 1 目录只读；目录值实时派生见 settings_service._item_data） ---
        #   2026-11-03 小欧 - 「日志级别」已移至通用组(单键, 兼管控制台精确显示与文件阈值), 紧随调试模式 — 小欧-2026-11-03
        #   2026-11-03 小欧 - 恢复 restart=True: maxBytes/backupCount 只在 SafeRotatingFileHandler 构造期读取,
        #     refresh_log_levels 不重刷 → 改完必须重启, 不能标"免重启" — 小欧-2026-11-03
        _item("logging.max_file_size", "int", "日志文件上限(字节)", 10485760, range_=[1024, 1073741824], restart=True,
              notice="单个日志文件大小上限，超限自动轮转（需重启生效）"),
        _item("logging.backup_count", "int", "日志备份数", 5, range_=[1, 100], restart=True,
              notice="日志轮转保留的备份文件个数（需重启生效）"),
        _item("paths.logs", "readonly", "日志目录", None, readonly=True,
              notice="源码运行=backend\\logs；打包(exe)运行=exe所在目录\\logs；app_日期.log按日期轮转，prompt日志在prompt-logs子目录"),
        # --- 工程目录（6 只读；值实时派生见 settings_service._item_data） ---
        _item("paths.project_root", "readonly", "生效项目根目录", None, readonly=True,
              notice="workspace.project_root 已配置时用配置值；未配置时=用户主目录"),
        _item("paths.omniagent_md", "readonly", "项目规则文件", None, readonly=True,
              notice="代码根目录\\OmniAgent.md；文件名大小写不敏感；不存在时自动创建空文件"),
        _item("paths.download", "readonly", "下载目录", None, readonly=True,
              notice="项目根目录\\download；项目根未配置时=用户主目录\\download；download.dest 相对本目录"),
        _item("paths.database", "readonly", "数据库目录", None, readonly=True,
              notice="固定 ~\\.omniagent 无配置项；chat_history.db/monitoring.db 等多库与回收站 recycle_bin 同根"),
        _item("paths.record_tool", "readonly", "工具结果文件", None, readonly=True,
              notice="根：调试=backend\\files、正式=~\\.omniagent\\files；tool_data_<短任务ID>_<消息ID>_<时间去冒号>.jsonl，1块=1工具结果"),
        _item("paths.record_conv", "readonly", "对话历史文件", None, readonly=True,
              notice="根：调试=backend\\files、正式=~\\.omniagent\\files；conv_hist_<短任务ID>_<消息ID>_<时间去冒号>.jsonl，1块=1消息"),
        # --- 网络（1 键，自 tuning 组迁入；键名 network.cors_origins 顶层，main.py 消费方同步）---
        _item("network.cors_origins", "url", "允许访问的页面地址",
              "http://localhost:5173,http://127.0.0.1:5173",
              notice="仅跨域部署时生效（如前端独立CDN、E2E代理）；打包版同源运行无需配置"),
        # --- 对话历史保留（1 键，归 system 命名空间，启动时清理超期会话）---
        _item("system.chat_retention_days", "int", "对话历史保留天数", 0,
              range_=[0, 3650], restart=True,
              notice="保留近 N 天的对话历史（0=关闭，不删用户历史）；>0 时启动时清理超期会话（级联 tasks/steps/events），建议先备份 chat_history.db"),
        # --- 关于（2 只读） ---
        _item("config_path", "readonly", "配置文件路径", None, readonly=True),
        _item("version", "readonly", "当前版本", None, readonly=True),
    ]},
    # 4.8 前端（appearance）：前两项是准入控制，键名沿用 security.*（前缀只表命名空间）
    #   Tab 显示名 2026-09-27 由「外观」改「前端」（本组实含准入 + 外观两块）
    "appearance": {"label": "前端", "items": [
        # 访问口令（secret → 读掩码；写路径被显式拒绝，改口令走 auth_routes 专用端点）
        _item("security.access_token", "secret", "访问口令", None, secret=True,
              env_key="OMNIAGENT_ACCESS_TOKEN", env_inject=True,
              notice="局域网访问本服务用的口令（暗号）。除本机与白名单外，访问任何接口都要它；泄露了改成新的，旧的立即作废"),
        # 免口令 IP 白名单（非 secret：白名单不是机密，需在设置页可维护）
        _item("security.access_token_allowlist", "textarea", "免口令 IP 白名单", "",
              env_key="OMNIAGENT_ACCESS_TOKEN_ALLOWLIST", env_inject=True, list_of="ip_cidr",
              notice="这些 IP/网段访问本服务免口令。每行一条，也可用逗号分隔，支持 CIDR（如 192.168.1.0/24）。本机(127.0.0.1/::1)免口令。⚠️白名单内等于无鉴权，可读全部密钥，只放可信网段"),
        _item("app.language", "select", "系统语言", "zh-CN",
              options=["zh-CN", "en-US"], restart=True),
        _item("app.theme", "readonly", "主题", "light", readonly=True,
              notice="当前固定浅色；深色二期（需全站 token 化重做硬编码色值）"),
        # 2026-11-12 小欧 - **阅读区字号**(文档[31] §4.2/§4.3/§7.1 定案):
        #   label 明确「阅读区」, notice 写清作用范围(只管长文阅读区, 不影响流水线正文与任务卡);
        #   range 收窄为 [12,16] step 2 —— 三档全落在全局字号阶梯上, 不产生 13/15 这类游离半档
        #   (13px 当年被废正是因半档游离)。已存的越界/非阶梯值由读取侧钳制(夹紧 + 向下吸附)。
        _item("appearance.fontSize", "range", "阅读区字号(px)", 14, range_=[12, 16], step=2,
              notice="长文阅读区的正文档位（文件预览的 Markdown 美显、设置页说明弹框），可选 12 / 14 / 16 三档。不影响流水线正文与任务卡回复区（那两处是信息流，节奏固定）。"),
        # 2026-11-12 小欧 - **界面密度**(文档[31] §4.2/§7.1 定案): 全局密度, 管控件高与排布松紧。
        #   此前前端 useSettings 引用了 appearance.density 但 registry 无此键 → 彻底死分支(永不触发);
        #   本次正式注册, 前端写入侧零改动即自动生效(键名沿用 localStorage 的 density 字段)。
        _item("appearance.density", "select", "界面密度", "comfortable",
              options=["comfortable", "compact"],
              notice="全局排布松紧：紧凑 = 控件更矮、阅读区间距更紧；舒适 = 默认。字号与流水线正文节奏不受此影响。"),
        # 2026-10-05 小欧 - step 渲染显示选项(两个独立开关):
        #   走前缀 appearance.step_render.*, 不加会被 SettingsGroup.tsx 的"外观"归组吞掉;
        #   置于 appearance.fontSize 之后, 令 sectionOf 只多一节
        #   思考排版=thought 段(text)是否按 Markdown 语法渲染; 思考内容=reasoning 段折叠初值, 两者互不干涉
        #   顺序=思考内容 在前、思考排版 在后 — 小欧-2026-10-05
        # 2026-11-14 商量 - 标签「推理内容」→「思考内容」, 与流水线标题行文案统一(思考内容... 同名同义)
        _item("appearance.step_render.reasoningVisible", "bool", "思考内容", True,
              notice="思考内容折叠开关：开=每段思考进来就展开；关=新出现的思考段默认只显示标题行，点标题行的箭头可单独展开/收起"),
        _item("appearance.step_render.thoughtMarkdown", "bool", "思考排版", True,
              notice="思考排版开关：thought 段用 Markdown 语法渲染；开=按标题/加粗/列表/代码等语法渲染，关=按纯文本实时显示（效果同加粗）"),
        _item("appearance.step_render.contentRender", "bool", "Content渲染", True,
              notice="步骤内容(content)渲染开关：开=正常渲染步骤内容，关=隐藏步骤内容"),
        _item("appearance.step_render.diffRender", "bool", "Diff渲染", True,
              notice="Diff渲染开关：开=显示代码变更对比，关=隐藏Diff视图"),
    ]},
    # 2026-09-24 小欧 - 模型库：items 空（schema 仅提供 label 供 Tab 渲染），内容走专用组件分支
    "model_library": {"label": "模型库", "items": []},
    "tuning": {"label": "调优", "items": [
        # --- llm: LLM 语义参数（temperature/max_tokens 在 llm.sampling.* 通用组）---
        _item("tuning.llm.tool_choice", "select", "工具调用模式", "auto",
              options=["auto", "none"], notice="控制模型能不能用工具：auto=正常模式，模型自己决定要不要调用工具；none=禁止用工具，只回纯文字（怀疑工具出问题时用它对照）"),
        _item("tuning.llm.stream_max_retries", "int", "传输失败重试", 3, range_=[0, 10],
              notice="请求中途断线或超时时自动重新发起，最多再试 N 次（每次比上次多等一会）；0=不重试直接失败。与下面「内容错误重试」分工：本项管根本没收到回复，下面管收到了但内容不对"),
        # 2026-10-05 22:16:38 小欧 - 设置页「调优」四个标签重命名，更准确反映实际语义。
        _item("tuning.llm.response_fallback", "bool", "响应无工具转文本", True,
              notice="让模型用工具干活时如果一直失败，重试用完后自动改成「不用工具、直接写文字回答」再试一次；关掉则失败就直接报错"),
        _item("tuning.llm.response_retries", "int", "响应内容错重试限额", 2, range_=[0, 5],
              notice="模型返回空回复或明显坏内容时自动重试，最多 N 次，越等越久；配额用完、被限流、请求本身写错这三种情况不走这里。与上面「传输失败重试」分工：本项管内容坏，上面管没收到"),
        _item("tuning.llm.stream_options.include_usage", "bool", "统计 Token 用量", True,
              notice="回答结束后附带本次消耗了多少 token（输入+输出）；关掉后任务统计页的 token 数会显示为 0"),
        # --- llm_net: LLM 网络/超时/连接池（7 键）---
        _item("tuning.llm_net.read_timeout", "int", "等待回复间隔(秒)", 150, range_=[10, 600],
              notice="两次收到模型回字之间的最大间隔：超过这个秒数没动静就认为连接断了。不是总时长——模型一直有字吐出来就不算超。与下面「单次总时长」分工：本项管字与字的间隔，下面管从头到尾总时间"),
        _item("tuning.llm_net.connect_timeout", "float", "连上服务器超时(秒)", 30.0, range_=[5, 120],
              notice="发起请求到连上模型服务器的最大等待：网络不通或地址解析失败时，最多等这么多秒就报错。调大=弱网多等会，调小=更快发现连不上"),
        _item("tuning.llm_net.write_timeout", "float", "发送请求超时(秒)", 10.0, range_=[5, 120],
              notice="把你的问题完整发出去的最大等待：请求内容很大或上行网速很慢时用到，超时报错"),
        _item("tuning.llm_net.pool_timeout", "float", "等空闲连接超时(秒)", 10.0, range_=[5, 120],
              notice="并发连接用满时，排队等一条空闲连接的最大时间：等到就接着发，等不到就报错。与上面「并发连接上限」配套——上限决定排多少人，本项决定排多久"),
        _item("tuning.llm_net.max_connections", "int", "同时最多连接数", 10, range_=[1, 50],
              notice="同时向模型服务器发起的请求最多几条：超出的排队等空位（排多久由上面「等空闲连接超时」管）。调大=并行任务更顺但更占资源"),
        _item("tuning.llm_net.max_keepalive", "int", "空闲保留连接", 5, range_=[0, 20],
              notice="请求结束后先留着不断开的连接条数，下次请求直接复用、省去重新连的时间；0=用完就断（更省资源，但下次会慢一点）"),
        _item("tuning.llm_net.stream_total_timeout", "int", "单次总时长上限(秒)", 500, range_=[60, 3600],
              notice="一次回答从开始到结束的总时间上限，到点强制掐断（防模型卡住永远不出结果）。与上面「等待回复间隔」分工：本项管总时长，上面管字与字的间隔"),
        # --- concurrency: 并发配额（3 键）---
        _item("tuning.concurrency.soft_pool_wait_timeout", "float", "排队最多等(秒)", 30.0, range_=[5, 120],
              notice="同时请求达到上限时新请求先排队，最多等这么多秒；等超了就不排了、照样放行（宁可挤一点也不让任务卡死）。与上面「等空闲连接超时」分工：本项管应用层排队，那边管网络连接层"),
        _item("tuning.concurrency.shell_max_processes", "int", "shell并发进程上限", 10, range_=[2, 64],
              notice="同时执行的 shell 子进程总数上限（每个约40MB内存）：到顶后新命令排队等空位，等不到就提示稍后重试。每条命令跑完即销毁，不常驻"),
        _item("tuning.concurrency.shell_max_background", "int", "后台命令并发上限", 5, range_=[1, 32],
              notice="后台运行的命令最多同时几条；到顶后新后台命令直接拒绝并提示稍后。后台命令无超时，完成后自动通知并续跑。（改本项需重启服务生效）"),
        _item("tuning.shell_bg_max_output_mb", "int", "后台输出上限(MB)", 512, range_=[0, 8192],
              notice="单条后台命令输出文件最多写多少 MB；超过即强制终止该命令，防日志狂写把磁盘写满拖垮系统。默认512MB（并发5条时峰值约2.5GB）。0=不限制（不建议）"),
        _item("tuning.shell_bg_result_retain_hours", "int", "后台结果保留(小时)", 24, range_=[1, 720],
              notice="后台命令结束后结果文件保留多久；到期在新后台命令启动时顺带清理"),
        # --- agent: Agent 循环参数（2 键）---
        _item("tuning.agent.max_chunks_without_promote", "int", "卡死保护上限", 50, range_=[10, 200],
              notice="模型一直往外吐零碎字却始终不给完整回答，累计吐够这么多次就判定卡死、强制结束任务（防止白白烧配额）"),
        # 2026-11-10 小欧 - 官方13件套禁用名单配置化(原 tools_alias_mapper 硬编码五元组):
        #   只影响未注册工具被拒时的措辞(禁用提示+点明全组), 拦不住已注册工具;
        #   键存在即配置为真值——清空=不禁用任何工具, 仅缺键/异常形状回落内置(用户拍板, 不兜底)。
        _item("tuning.agent.disabled_tools", "textarea", "禁用工具名单",
              ", ".join(_UNAVAILABLE_OFFICIAL),
              notice="模型调用这些工具时提示「禁止使用」并点明整个名单，防反复试错；不影响已注册正常工具。清空=不禁用任何工具"),
        # --- trim: 裁剪 5 键（loop 每轮评估）— 小欧-2026-10-25
        _item("tuning.trim.max_rounds", "int", "裁剪历史触发轮", 100, range_=[1, 10000],
              notice="用于计算消息数上限(msg_ceiling=max_rounds×2+5)，超出即触发裁剪；调大保留更多原始信息，调小更早裁旧"),
        _item("tuning.trim.trigger_ratio", "float", "裁剪阈值调节系数", 0.8, range_=[0.5, 0.95],
              notice="裁剪入口阈值=budget_base×系数(一次方)；裁剪出口队列预算=budget_base×系数²(二次方)；调小更早触发且队列预算更小，调大更晚触发且队列预算更大"),
        _item("tuning.trim.compaction_buffer", "int", "上下文预留空间", 20000, range_=[1000, 100000],
              notice="裁剪预算中扣除的输出预留；不足则裁完 messages 已逼近 context_length"),
        _item("tuning.trim.keep_recent_rounds", "int", "最近轮硬保护", 5, range_=[5, 20],
              notice="裁剪时最近 N 个 FC 工具步(assistant.tool_calls+tool)不参与裁剪，第 N+1 步起按预算整轮裁"),
        _item("tuning.trim.tools_token_reserve", "int", "tools 定义预留", 30000, range_=[5000, 80000],
              notice="tools schema 占用的输入 token 预留；不足则 messages 裁至预算仍会超 context_length 致LLM报400错误"),
        # --- compaction: 压缩 4 键（开局超容时把旧对话压成摘要）---
        _item("tuning.compaction.start_enabled", "bool", "开局压缩开关", True,
              notice="任务刚开始如果发现以前的对话太长装不下，先自动压成一段摘要再开始干活；关掉则不压、直接硬删"),
        _item("tuning.compaction.start_limit_ratio", "float", "压缩摘要限制系数", 0.5, range_=[0.1, 0.95],
              notice="压缩摘要的限制系数（0.5=占到一半就压）：开局时旧对话占到记忆容量这个比例才值得压；只管任务开头这一次，任务跑起来后归上面的「裁剪」管"),
        _item("tuning.compaction.summary_feed_max_chars", "int", "单条截断(字符)", 2000, range_=[100, 10000],
              notice="压成摘要前，单条工具结果超过这么多字先砍掉再给模型看（防超长输出把摘要过程撑爆）；调大=摘要更全但更费"),
        _item("tuning.compaction.keep_tail", "int", "免压缩原始对话数", 1, range_=[0, 5],
              notice="[暂时无用]压成摘要后，再原样保留最近几条消息不压（保住最新对话细节不被摘要抹平）；0=全压成摘要、不留原话"),
        # --- live_front: 连接保活/任务清理/缓存/事件流水保留（5 键；原名 stream_task，改名防与 tuning.llm.stream_* 混淆）---
        _item("tuning.live_front.heartbeat_interval", "float", "保活间隔(秒)", 25.0, range_=[5, 25],
              notice="任务执行中如果一会儿没新内容，每隔这么多秒主动给页面发一个「我还活着」的信号，防止页面误以为断了自动重连；必须明显小于页面的 60 秒断线判定，也要小于顶栏状态灯的 30 秒静默判据，否则白保活（上限 25 秒 = 60 秒窗口内至少 2 次心跳，且留 5 秒余量给状态判据）"),
        _item("tuning.live_front.task_timeout_hours", "int", "任务保留(小时)", 1, range_=[1, 24],
              notice="已经做完的任务在列表里保留几小时后自动清掉（正在跑的不受影响）；调小=列表干净但翻不了旧任务，调大=能回看更久"),
        _item("tuning.live_front.tool_cache_ttl", "int", "结果复用时间(秒)", 300, range_=[60, 3600],
              notice="同一工具用同样的参数再查一次时，这么多秒内直接给上次的结果、不再真跑一遍；调小=结果更新鲜但重复查询更慢，调大=更快但可能给到过期结果"),
        _item("tuning.live_front.max_cache_size", "int", "缓存条数上限", 1000, range_=[100, 10000],
              notice="内部小缓存最多存多少条，超了自动丢最久没用的；一般不用动，调错也没什么感觉"),
        _item("tuning.live_front.journal_retention_days", "int", "事件流水保留(天)", 7, range_=[1, 30],
              notice="事件流水（chat_stream_events）保留几天：只清已完成/已失败/已取消任务的事件，正在跑的任务永不删；调小省磁盘但更早查不到历史回放，调大能回看更久"),
        # --- hitl: 人工确认（4 键）---
        _item("tuning.hitl.hitl_confirm_lead", "int", "确认倒计时提前(秒)", 10, range_=[0, 60],
              notice="危险操作确认弹窗：页面上的倒计时比后端实际超时（默认120秒）提前这么多秒归零，让你先看到「已超时」提示，而不是弹窗凭空消失；提前量要小于总超时"),
        _item("tuning.hitl.bypass_auto_lead", "int", "自动放行提前(秒)", 2, range_=[0, 10],
              notice="自动确认弹窗：页面倒计时比后端自动放行提前这么多秒归零，保证页面先收好、后端再放行，弹窗不会闪一下才关"),
        _item("tuning.hitl.hitl_min_confirm_timeout", "int", "倒计时最短(秒)", 3, range_=[1, 30],
              notice="确认弹窗倒计时至少显示这么多秒，防止倒计时太短、弹窗一闪而来不及点"),
        _item("tuning.hitl.max_pending_confirmations", "int", "待确认条数上限", 100, range_=[10, 1000],
              notice="同时排队等你确认的操作最多多少条，超了新的直接拒绝（防一次弹出太多窗把页面卡死）"),
        # --- content: 内容截断（3 键）---
        _item("tuning.content.project_context_max_chars", "int", "项目规则字数上限", 10000, range_=[1000, 50000],
              notice="项目规则文件(OmniAgent.md)每次带给模型的最大字数，超长部分不带；调大=规则记得全但更占记忆容量，调小=省容量但长规则会被截断"),
        _item("tuning.content.action_log_result_max_chars", "int", "工具结果字数上限", 5000, range_=[1000, 20000],
              notice="工具跑完后写进对话记录的单条结果最多保留多少字，超长截断；防止读了个大文件把整个对话撑爆"),
        _item("tuning.content.temp_history_char_limit", "int", "临时副本字数上限", 50000, range_=[5000, 200000],
              notice="压缩过程中临时存的对话副本最多多少字，超了硬截断；正常用不到，属于防爆保险"),
    ]},
}

GROUP_ORDER = ["general", "model", "media", "security", "sandbox", "tuning", "system", "model_library", "appearance"]

# 声明"registry 静态 secret 键中哪些的写路径已接好"的唯一权威集合：新增 secret 项必须在此登记，
# 未登记则模块加载即拒启（fail-fast，防半吊子）。位置须在 _build_index 之前。
# 键须与 registry 完整 key 一致。security.access_token 的写路径是专用 auth 端点（与 provider 通道同构）。
# 2026-09-26 小欧 - 删原集合里的裸 "api_key"：registry 无任何键含 api_key（provider 的 api_key 是
#   ProviderConfig 专属动态项，不在静态表），属死数据且与"须登记完整 key"自相矛盾。
_SECRET_WRITTEN_BY_PROVIDER_CHANNEL = frozenset({"security.access_token"})


def _build_index() -> Dict[str, Dict[str, Any]]:
    """模块加载自检：key 全局唯一，重复直接拒启（3.2 铁律1）。"""
    index: Dict[str, Dict[str, Any]] = {}
    for gname, group in GROUPS.items():
        for item in group["items"]:
            key = item["key"]
            if key in index:
                raise RuntimeError(f"[settings_registry] 重复 key 拒启: {key}")
            index[key] = item
    # secret 项自检（2026-09-26 小欧）。
    # secret=True 的项其写路径必须已接好（provider 通道或专用 auth 端点），否则 settings 通用通道
    #   又显式拒绝写它，该项就变成"写不进也读不出掩码"的半吊子。此处开发期即拒启。
    # 边界（勿夸大其词）：本检查只能拦住"忘记登记"，拦不住"登记了但写通道其实没实现"——
    #   静态自检无法验证运行时代码路径，那需要集成测试覆盖。真正保证写通道可用的是 auth_routes
    #   与 model_service 各自的 TDD 用例。
    for key, item in index.items():
        if item.get("secret") and key not in _SECRET_WRITTEN_BY_PROVIDER_CHANNEL:
            raise RuntimeError(
                f"[settings_registry] secret 项未接 provider 通道写路径，拒启: {key}。"
                f"secret 项须在 _SECRET_WRITTEN_BY_PROVIDER_CHANNEL 登记"
                f"（当前已登记: {sorted(_SECRET_WRITTEN_BY_PROVIDER_CHANNEL)}）"
            )
    # env_inject 与 config.ENV_INJECTED_KEYS 双向核对，不一致即拒启。
    # 原手写清单在键改名时漏改 → env 注入旧键、页面读新键得 None；漏改从此是启动失败而非静默脱节。
    for key, item in index.items():
        if item.get("env_inject") and ENV_INJECTED_KEYS.get(key) != item.get("env_key"):
            raise RuntimeError(
                f"[settings_registry] env_inject 与 app.config.ENV_INJECTED_KEYS 不一致，拒启: {key}；"
                f"声明 env_key={item.get('env_key')!r}，注入清单={ENV_INJECTED_KEYS.get(key)!r}"
            )
    for key, env_name in ENV_INJECTED_KEYS.items():
        item = index.get(key)
        if item is None:
            raise RuntimeError(
                f"[settings_registry] ENV_INJECTED_KEYS 的 {key}={env_name} 在 registry 无对应项，拒启"
            )
        if not item.get("env_inject") or item.get("env_key") != env_name:
            raise RuntimeError(
                f"[settings_registry] ENV_INJECTED_KEYS 与 registry 声明不一致，拒启: {key}={env_name}；"
                f"registry env_inject={bool(item.get('env_inject'))} env_key={item.get('env_key')!r}"
            )
    # 分组两处声明(GROUPS 定义 / GROUP_ORDER 定 Tab 顺序)必须一一对应:
    #   漏登记只会让该组静默消失, 故加载即拒启 — 小欧-2026-11-08
    if set(GROUP_ORDER) != set(GROUPS):
        raise RuntimeError(
            f"[settings_registry] GROUP_ORDER 与 GROUPS 不一致，拒启: "
            f"缺 {sorted(set(GROUPS) - set(GROUP_ORDER))} 多 {sorted(set(GROUP_ORDER) - set(GROUPS))}"
        )
    return index


REGISTRY_INDEX = _build_index()


def get_item(key: str) -> Optional[Dict[str, Any]]:
    """按 key 取 schema 项。"""
    return REGISTRY_INDEX.get(key)


def group_items(group: str) -> List[Dict[str, Any]]:
    """取某组全部 schema 项。"""
    return GROUPS[group]["items"]
