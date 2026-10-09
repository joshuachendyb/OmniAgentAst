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
  2026-10-10 小欧 - general 组新增两项全局 thinking 兜底（北京老陈：通用兜底模型参数区缺思考项）：
    llm.sampling.enable_thinking(bool,默认 True) 与 llm.sampling.reasoning_effort(select,默认 medium,
    四档 minimal/low/medium/high)，单模型没单独配置时用这两个，已在模型 Tab 配了的不受影响。
    group 项数 10 → 12。前端 SettingRow 按 type 渲染(bool→Switch / select→下拉)，零改动 — 小欧-2026-10-10
"""
from typing import Any, Dict, List, Optional

# 注入清单在 app.config（最底层，不能反向依赖本包），一致性由 _build_index 自检
from app.config import ENV_INJECTED_KEYS


def _item(key: str, type_: str, label: str, default: Any = None,
          options: Optional[List[Any]] = None, range_: Optional[List[float]] = None,
          step: Optional[float] = None, restart: bool = False, secret: bool = False,
          readonly: bool = False, notice: str = "",
          env_key: Optional[str] = None, env_inject: bool = False,
          list_of: Optional[str] = None) -> Dict[str, Any]:
    """单项构造：storage 统一 YAML。

    参数 range_ 的尾下划线只避内置 range，与字典键 range 刻意异名（对齐 model_service.add_model）。
    env_key 只决定页面"来源"标记；env_inject=True 另表示 env 值要注入 get_config()，
否则页面显示值≠实际生效值。两者分开：ai.model_ref 是 dict 而 env 是标量，注入会写坏结构。
注入清单在 app.config.ENV_INJECTED_KEYS，双向一致性由 _build_index 启动自检保证。
list_of 声明"本项是某类元素的列表"，落盘前归一+校验，规则见 app/utils/allowlist.py。
"""
    return {"key": key, "type": type_, "label": label, "default": default,
            "options": options, "range": range_, "step": step, "storage": "YAML",
            "restart": restart, "secret": secret, "readonly": readonly, "notice": notice,
            "env_key": env_key, "env_inject": env_inject, "list_of": list_of}


GROUPS: Dict[str, Dict[str, Any]] = {
    # 4.1 通用（general，12 项）
    "general": {"label": "通用", "items": [
        # 默认空：config.get_project_root 靠 `if root:` 判空后回退用户主目录（Path.home()）
        _item("workspace.project_root", "text", "项目根目录", ""),
        _item("workspace.allowed_dirs", "textarea", "授权目录", "",
              notice="项目根之外额外授权访问的工作目录，多个用换行分隔"),
        _item("logging.debug", "bool", "调试模式", True, restart=True,
              notice="开启后日志按 DEBUG 级别记录，明细含文件/行号"),
        _item("agent.max_steps", "int", "最大轮数", 10000, range_=[1, 10000],
              notice="单任务最多执行的对话轮数（循环门限）：任务条上的『轮数』到顶就强制结束任务；调大=允许跑更久，调小=更早刹车。注意这不是任务条上的『步数』（步数只是自动统计，跟着轮数走，没有单独上限）"),
        _item("llm.sampling.temperature", "float", "采样温度", 0.7, range_=[0, 2],
              notice="控制输出随机性：0=完全确定性（每次相同输入输出一致），1=默认随机性，2=最高随机性"),
        _item("llm.sampling.max_tokens", "int", "单次最大 token", 16384, range_=[1, 100000],
              notice="单次 LLM 调用最大输出 token 数，超长截断"),
        _item("llm.sampling.top_p", "float", "核采样 top_p", 1.0, range_=[0, 1],
              notice="核采样阈值：从概率质量前 p 的词中采样；1.0=不筛选；通常与温度二选一调节，同时调易相互抵消"),
        _item("llm.sampling.frequency_penalty", "float", "频次惩罚 (frequency_penalty)", 0, range_=[-2, 2],
              notice="正值减少重复词频（更多样），负值增加重复词频（更聚焦），0=不启用"),
        _item("llm.sampling.presence_penalty", "float", "存在惩罚 (presence_penalty)", 0, range_=[-2, 2],
              notice="正值惩罚已出现过的词（鼓励新话题），负值鼓励重复已出现的词，0=不启用"),
        _item("llm.sampling.enable_thinking", "bool", "思考开关", True,
              notice="全局思考开关默认值（单个模型没单独配置时用这个）：开=模型先思考再回答；关=直接回答。单模型可在模型参数里单独覆盖"),
        _item("llm.sampling.reasoning_effort", "select", "推理深度", "medium",
              options=["minimal", "low", "medium", "high"],
              notice="全局推理深度默认值（单个模型没单独配置时用这个）：minimal最省，high最深。单模型可在模型参数里单独覆盖"),
        _item("llm.context_limit_default", "int", "默认上下文窗口", 262144, range_=[200000, 2000000],
              notice="模型一次能记住的内容总量默认值（单个模型没单独配置时用这个），约 25.6 万 token"),
    ]},
    # 4.2 模型（model，结构化语义；CRUD 由 model_service 承接，见 9.1.3）
    "model": {"label": "模型", "items": [
        _item("ai.model_ref", "model_ref", "当前系统全局使用模型", None,
              notice="当前选用的模型（哪个服务商+哪个模型）；被环境变量强制指定时整行只读",
              env_key="AI_PROVIDER"),
    ]},
    # 4.3 安全（security，YAML，即时；命令安全由 path_safe_check/tools/security 代码内实现）
    #   本组是**操作安全**（要不要拦用户的危险动作）。准入控制（谁能进得来）在 appearance 组首，
    #   两者语义分开，避免误以为"关掉安全开关就不用输口令"。
    "security": {"label": "安全", "items": [
        # 2026-10-05 22:16:38 小欧 - 北京老陈指令：标签「安全开关」改「HTL人工开关」；notice 文案更新。
        #   注意语义：confirmDangerousOps 仍负责操作前的人工确认弹窗，本项管「要不要走人工确认链路」。
        _item("security.enabled", "bool", "HTL人工开关", False,
              notice="关闭后，无需人工确认，无信任，自动延时确认安全检查，（盘根/项目根等删除硬防线仍生效）"),
        _item("security.confirmDangerousOps", "bool", "危险操作确认", True,
              notice="保存时再弹一次确认框（防误触）；后端的安全拦截不依赖这个开关"),
        _item("security.auto_confirm_delay", "int", "自动确认延迟(秒)", 10, range_=[0, 3600],
              notice="自动确认弹窗倒计时（秒），到时没人点就自动放行"),
        _item("security.hitl_timeout", "int", "人工确认超时(秒)", 120, range_=[1, 86400],
              notice="人工确认弹窗最长等你多久（秒），超时按弹窗设定的处理方式收尾"),
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
    ]},
    # 4.5 系统（system，13 项：3 运维日志配置 + 1 日志目录只读 + 6 工程目录只读 + 1 网络 CORS + 2 关于只读）
    #   注意：本小节新增 / 删除 paths.* 条目务必同步 settings_service._item_data 的 paths 派生字典，
    #   二者 keys 一一对应，漏配将抛 KeyError（fail-fast 防静默空白）
    "system": {"label": "系统", "items": [
        # --- 运维日志（3 配置 + 1 目录只读；目录值实时派生见 settings_service._item_data） ---
        _item("logging.level", "select", "日志级别", "INFO",
              options=["DEBUG", "INFO", "WARNING", "ERROR"], restart=True,
              notice="日志记录级别，DEBUG 最详细", env_key="LOG_LEVEL"),
        _item("logging.max_file_size", "int", "日志文件上限(字节)", 10485760, range_=[1024, 1073741824], restart=True,
              notice="单个日志文件大小上限，超限自动轮转"),
        _item("logging.backup_count", "int", "日志备份数", 5, range_=[1, 100], restart=True,
              notice="日志轮转保留的备份文件个数"),
        _item("paths.logs", "readonly", "日志目录", None, readonly=True,
              notice="源码运行=backend\\logs；打包(exe)运行=exe所在目录\\logs；app_日期.log按日期轮转，prompt日志在prompt-logs子目录"),
        # --- 工程目录（6 只读；值实时派生见 settings_service._item_data） ---
        _item("paths.project_root", "readonly", "生效项目根目录", None, readonly=True,
              notice="workspace.project_root 已配置时用配置值；未配置时=用户主目录"),
        _item("paths.omniagent_md", "readonly", "项目规则文件", None, readonly=True,
              notice="项目根目录\\OmniAgent.md；项目根未配置时=用户主目录\\OmniAgent.md"),
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
              notice="允许访问本服务的页面地址白名单，多个用逗号隔开；换了前端地址或端口要加上新地址，否则页面会被浏览器拦住。默认两个是本机开发地址，一般不用改"),
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
        _item("appearance.fontSize", "range", "字号(px)", 14, range_=[12, 18], step=1),
        # 2026-10-05 小欧 - step 渲染显示选项(文档[9] 方案设计 §5.1, 北京老陈裁定两个独立开关):
        #   走前缀 appearance.step_render.*, 不加会被 SettingsGroup.tsx 的"外观"兜底吞掉;
        #   置于 appearance.fontSize 之后, 令 sectionOf 只多一节(§5.11 对齐)
        #   ①思考排版=thought 段(text)是否按 Markdown 语法渲染 ②推理内容=reasoning 段折叠初值, 两者互不干涉
        #   顺序=北京老陈定的「推理内容 在前、思考排版 在后」, 不按文档表格重排 — 小欧-2026-10-05
        _item("appearance.step_render.reasoningVisible", "bool", "推理内容", True,
              notice="推理内容折叠开关：开=每段思考进来就展开；关=新出现的推理段默认只显示标题行，点标题行的箭头可单独展开/收起"),
        _item("appearance.step_render.thoughtMarkdown", "bool", "思考排版", True,
              notice="思考内容(thought)用 Markdown 语法渲染的开关：开=按标题/加粗/列表/代码等语法渲染，关=按纯文本实时显示（效果同加粗）"),
    ]},
    # 2026-09-24 小欧 - 模型库：items 空（schema 仅提供 label 供 Tab 渲染），内容走专用组件分支
    "model_library": {"label": "模型库", "items": []},
    "tuning": {"label": "调优", "items": [
        # --- llm: LLM 语义参数（temperature/max_tokens 在 llm.sampling.* 通用组）---
        _item("tuning.llm.tool_choice", "select", "工具调用模式", "auto",
              options=["auto", "none"], notice="控制模型能不能用工具：auto=正常模式，模型自己决定要不要调用工具；none=禁止用工具，只回纯文字（怀疑工具出问题时用它对照）"),
        _item("tuning.llm.stream_max_retries", "int", "传输失败重试", 3, range_=[0, 10],
              notice="请求中途断线或超时时自动重新发起，最多再试 N 次（每次比上次多等一会）；0=不重试直接失败。与下面「内容错误重试」分工：本项管根本没收到回复，下面管收到了但内容不对"),
        # 2026-10-05 22:16:38 小欧 - 北京老陈指令：设置页「调优」四个标签重命名，更准确反映实际语义。
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
        # --- concurrency: 并发配额（2 键）---
        _item("tuning.concurrency.soft_pool_wait_timeout", "float", "排队最多等(秒)", 30.0, range_=[5, 120],
              notice="同时请求达到上限时新请求先排队，最多等这么多秒；等超了就不排了、照样放行（宁可挤一点也不让任务卡死）。与上面「等空闲连接超时」分工：本项管应用层排队，那边管网络连接层"),
        _item("tuning.concurrency.shell_pool_max_per_type", "int", "PS并发池限额", 8, range_=[1, 20],
              notice="同一任务里同一种终端（如 PowerShell）最多同时开几个常驻会话：满了新命令要等空位；调大=并行命令更顺但更占内存"),
        # --- agent: Agent 循环参数（1 键）---
        _item("tuning.agent.max_chunks_without_promote", "int", "卡死保护上限", 50, range_=[10, 200],
              notice="模型一直往外吐零碎字却始终不给完整回答，累计吐够这么多次就判定卡死、强制结束任务（防止白白烧配额）"),
        # --- trim: 裁剪 3 键（每轮循环自动执行）---
        _item("tuning.trim.max_rounds", "int", "裁剪历史触发轮", 100, range_=[1, 10000],
              notice="超过 N 轮后执行历史对话信息裁剪，更早的自动忘掉；调大=保留更多的原始信息但更费 token，调小=省钱但会忘更早的事"),
        _item("tuning.trim.trigger_ratio", "float", "裁剪触发水位", 0.75, range_=[0.1, 0.95],
              notice="对话占到模型记忆容量的百分之多少时开始自动删旧内容（0.75=占到四分之三就删）；调小=删得勤、腾地方快，调大=多记一会但快满时才动手"),
        _item("tuning.trim.compaction_buffer", "int", "上下文预留空间", 20000, range_=[1000, 100000],
              notice="删旧内容时故意不删满，给模型写这次回答预留这么多容量，防止删完一点空都没有、模型没地方写"),
        # --- compaction: 压缩 4 键（开局超容时把旧对话压成摘要）---
        _item("tuning.compaction.start_enabled", "bool", "开局压缩开关", True,
              notice="任务刚开始如果发现以前的对话太长装不下，先自动压成一段摘要再开始干活；关掉则不压、直接硬删"),
        _item("tuning.compaction.start_trigger_ratio", "float", "开局压缩水位", 0.5, range_=[0.1, 0.95],
              notice="开局时旧对话占到记忆容量百分之多少才值得压（0.5=占到一半就压）；只管任务开头这一次，任务跑起来后归上面的「裁剪」管"),
        _item("tuning.compaction.summary_feed_max_chars", "int", "单条截断(字符)", 2000, range_=[100, 10000],
              notice="压成摘要前，单条工具结果超过这么多字先砍掉再给模型看（防超长输出把摘要过程撑爆）；调大=摘要更全但更费"),
        _item("tuning.compaction.keep_tail", "int", "免压缩原始对话数", 1, range_=[0, 5],
              notice="压成摘要后，再原样保留最近几条消息不压（保住最新对话细节不被摘要抹平）；0=全压成摘要、不留原话"),
        # --- live_front: 连接保活/任务清理/缓存/事件流水保留（5 键；原名 stream_task，改名防与 tuning.llm.stream_* 混淆）---
        _item("tuning.live_front.heartbeat_interval", "float", "保活间隔(秒)", 25.0, range_=[5, 60],
              notice="任务执行中如果一会儿没新内容，每隔这么多秒主动给页面发一个「我还活着」的信号，防止页面误以为断了自动重连；必须明显小于页面的 60 秒断线判定，否则白保活"),
        _item("tuning.live_front.task_timeout_hours", "int", "任务保留(小时)", 1, range_=[1, 24],
              notice="已经做完的任务在列表里保留几小时后自动清掉（正在跑的不受影响）；调小=列表干净但翻不了旧任务，调大=能回看更久"),
        _item("tuning.live_front.tool_cache_ttl", "int", "结果复用时间(秒)", 300, range_=[60, 3600],
              notice="同一工具用同样的参数再查一次时，这么多秒内直接给上次的结果、不再真跑一遍；调小=结果更新鲜但重复查询更慢，调大=更快但可能给到过期结果"),
        _item("tuning.live_front.max_cache_size", "int", "缓存条数上限", 1000, range_=[100, 10000],
              notice="内部小缓存最多存多少条，超了自动丢最久没用的；一般不用动，调错也没什么感觉"),
        _item("tuning.live_front.journal_retention_days", "int", "事件流水保留(天)", 7, range_=[1, 30],
              notice="[63] 事件流水（chat_stream_events）保留几天：只清已完成/已失败/已取消任务的事件，正在跑的任务永不删；调小省磁盘但更早查不到历史回放，调大能回看更久"),
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

GROUP_ORDER = ["general", "model", "security", "sandbox", "tuning", "system", "model_library", "appearance"]

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
    # 边界（勿夸大其词）：本检查只能拦住"**忘记登记**"，拦不住"登记了但写通道其实没实现"——
    #   静态自检无法验证运行时代码路径，那需要集成测试兜底。真正保证写通道可用的是 auth_routes
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
    return index


REGISTRY_INDEX = _build_index()


def get_item(key: str) -> Optional[Dict[str, Any]]:
    """按 key 取 schema 项。"""
    return REGISTRY_INDEX.get(key)


def group_items(group: str) -> List[Dict[str, Any]]:
    """取某组全部 schema 项。"""
    return GROUPS[group]["items"]
