# -*- coding: utf-8 -*-
"""
settings_registry — 设置页唯一 Schema 源（3.2 铁律1）
key/类型/默认值/值域/存储/生效/来源规则只定一次；key 全局唯一，加载自检重复直接拒启。

编辑历史:
  2026-09-20 - 小沈 - 新建：v4.19 Phase 2 从文档54 9.1.1 逐字落盘
  2026-09-21 - 小欧 - 安全组补 2 项 HITL 参数（auto_confirm_delay, hitl_timeout）+ 新增沙箱组 8 项 + GROUP_ORDER 加 sandbox + app.language 从通用移到外观（UI语言属外观属性，与主题/字号同类）+ 系统参数5项（debug/max_context_tokens/max_history_length/max_rounds/max_steps）从系统组移到通用组 + ai.model_ref 标签改为"当前系统全局使用模型"对齐UI
  2026-09-21 - 小欧 - 删除无意义白/黑名单4项（whitelistEnabled/commandWhitelist/blacklistEnabled/commandBlacklist）：全库无消费方、仅透传保存不生效（北京老陈裁定删除；命令安全由 path_safe_check/tools/security 代码内实现，路径校验才是关键）
  2026-09-21 - 小欧 - v4.20 死配置全清+键名按域收敛（北京老陈裁定）:
    ①删除死配置10项: app.max_context_tokens/app.max_history_length/security.strict_mode/security.contentFilterEnabled/
      security.contentFilterLevel/security.maxFileSize/chat.temperature/chat.top_p/chat.max_tokens/chat.auto_title/
      chat.history_limit/chat.stream(实为12项, 其中chat组6项整体删除) + appearance.density(无消费方)
    ②键名按域收敛: app.project_root→workspace.project_root/app.allowed_dirs→workspace.allowed_dirs/
      app.max_rounds→agent.max_rounds/app.max_steps→agent.max_steps/app.debug→logging.debug
    ③保留: app.language/app.theme(外观域待二期深色) + appearance.fontSize(设置页预览有消费)
  2026-09-21 - 小欧 - 安全/沙箱 12 项补 notice 简明说明（enabled 关闭行为/影子区预演/内存与超时上限等；
    消费点核实：tool_safety_checker enabled=false、executor 预检直通、workspace 影子副本、job_object 内存限制）——
    说明文字从注册表单点下发，前端共用唯一渲染位展示
  2026-09-21 - 小欧 - 追加 6 项 notice：logging.debug(持久化路径分流)、agent.max_rounds/max_steps(单任务轮/步上限)、
    logging.level/max_file_size/backup_count(日志级别与轮转)——消费点核实：logger/config.py、file_persist.py、config.py
  2026-09-21 - 小欧 - logging.debug 说明修正：核心语义为日志(级别强制 DEBUG、明细含文件/行号)，
    文件持久化落点分流为开发期附带惯例不当主解释——消费点核实：get_log_level/shared_handler/api_logger
  2026-09-21 - 小欧 - 系统Tab重组 3 小节：运维日志(logging.*+paths.logs)/工程目录(6 paths.* 只读)/关于；
    工程目录=项目根/项目规则文件/下载/数据库(~/.omniagent)/文件持久化/任务文件目录；
    两级目录中文称呼：「会话目录」=Sion_<会话ID>、「任务目录」=Task_<任务ID>（A/B 记录文件 tool_data_*/conv_hist_*）
    —— 派生值由 settings_service._item_data 实时计算（不落 yaml），前端 SettingsGroup.sectionOf 判定小节
  2026-09-21 - 小欧 - paths.* 说明完整化：每条标注全部状态（project_root 已配置/未配置；ogs 源码/打包；
    files 调试源码/调试打包/正式；task_files 持久化根随状态切换；database 固定含回收站），杜绝只写一种情况
   2026-09-21 - 小欧 - 记录文件两行定稿：工程目录只读收敛为 6 行（项目根/规则文件/下载/数据库/工具结果记录/对话历史记录）；
     删无意义 files 存根行 + 撤 task_files 派生死键（registry 无对应行，仅剩值模板残留）；两条记录文件各写各的互不混杂。
     value 由 settings_service 派生为两级相对目录模板 + 各自文件名（Sion_<会话ID>\\Task_<任务ID>\\xxx.jsonl），
     不写绝对路径（当机值随环境算、无通用语义）；根两态（调试=backend\\files、正式=~\\.omniagent\\files）写 notice。
     北京老陈 2026-09-21 裁定
   2026-09-21 - 小欧 - system 组 96 行下加注释：paths.* 条目与 settings_service._item_data 派生字典一一对应，
     对端漏配抛 KeyError(fail-fast)，两处注释互相指引（北京老陈 2026-09-21 采纳）
   2026-09-22 - 小欧 - 编辑/保存审计修复 S9：logging.level 补 env_key="LOG_LEVEL"——_apply_env_overrides 本就用
     LOG_LEVEL 覆写运行时级别，不标 env_key 致 sources 报 yaml 可编辑可保存却"改了不生效"（假保存）；
     对齐后 env 接管键前端禁改、update_settings 跳过并 warning
    2026-09-22 - 小欧 - 31候选修复 #7：全部无界 int 项补 range_ 上下界（agent.max_rounds/security 延时与超时/
      sandbox 8项/logging 文件大小与备份数）——压缩负数(如 -500MB)曾当合法值落盘，消费方断言非负
      崩溃；range_ 为唯一边界来源，表驱 schema 与 _validate_value 单点校验（fontSize 的 step 见 #8 修复）
  2026-09-23 - 小欧 - [64] LLM补充采样参数: ①general组 agent.max_steps 后追加6条目(llm.sampling.temperature/max_tokens/top_p/frequency_penalty/presence_penalty + llm.context_limit_default); ②OLD_KEY_MAP 加 tuning.llm.temperature→llm.sampling.temperature / tuning.llm.max_tokens→llm.sampling.max_tokens 迁入映射
  2026-09-23 - 小欧 - trim/compaction配置化: ①通用组删 agent.max_rounds（挪入调优·裁剪）; ②tuning组 Agent 循环参数后插 trim 3键(max_rounds/trigger_ratio/compaction_buffer)+compaction 4键(start_enabled/start_trigger_ratio/summary_feed_max_chars/keep_tail)两独立分块; ③OLD_KEY_MAP 加 agent.max_rounds→tuning.trim.max_rounds
  2026-09-23 - 小欧 - 禁止backward还清旧账: 删 OLD_KEY_MAP 3条迁入映射(tuning.llm.temperature/max_tokens、agent.max_rounds，无消费方虚假承诺); live值已手工搬入新键，旧键废弃
  2026-09-23 - 小欧 - 删死配置 tuning.agent.max_consecutive_chunks（should_promote 历史接口全仓零调用，max_consecutive 唯一读取点即该死方法）; max_chunks_without_promote 改名实义 chunk 累积上限+notice重写（单轮未收到完整响应累积50 chunk 即强制失败终止）
   2026-09-23 - 小欧 - 频次惩罚/存在惩罚 label 补英文名: "频次惩罚"→"频次惩罚 (frequency_penalty)"、"存在惩罚"→"存在惩罚 (presence_penalty)" - 小欧-2026-09-23
   2026-09-23 - 小欧 - llm_net 7键 notice 重写(北京老陈指令"描述准确"): 原文案仅同义复述label无解释——
     改为「管什么阶段+超了/超限会怎样」: read=两字节间隙(非总时长,流式断流判死依据)/connect=TCP建连握手/
     write=发完请求体/pool=池满等空位/max_connections=并发上限第N+1排队/max_keepalive=空闲复用保留/
     stream_total=单次流式总闸到点强制截断(与read分工: read管间隙, total管总长) - 小欧-2026-09-23
   2026-09-23 - 小欧 - 连接相关7键 notice 重写(北京老陈指令"一起补充"): stream_max_retries=传输层HTTP重发
     (与response_retries分工: 传输vs内容)/response_fallback=FC耗尽降级Text语义展开/response_retries=L2内容层
     指数退避+不重试元组/soft_pool_wait_timeout=信号量排队超时保底放行(与连接池超时分工)/
     shell_pool_max_per_type=(任务ID,Shell类型)分池槽位/heartbeat_interval=防前端60s判死保活/
     cors_origins=跨域白名单+直连vs proxy场景 —— 消费点核实: base_service.py:344/llm_call.py:230,275/
     client_sdk.py:123,219/shell_engine.py:853/stream_orchestrator.py:574/main.py:92 - 小欧-2026-09-23
   2026-09-23 - 小欧 - 调优组剩余18键 notice 全量重写(北京老陈指令"都是看的稀里糊涂 都优化一下"):
     llm 2键(tool_choice/include_usage)/trim 3键/compaction 4键/stream_task 3键(除heartbeat已改)/
     hitl 4键/content 3键 —— 统一口径「管什么+什么时候触发+超了/关了会怎样+与谁分工」，消灭
     C4/TTL/L2/HITL/bypass/FC轮 等黑话直甩 —— 消费点核实: llm_call.py:89/base_service.py:335/
     message_builder.py:106-108,318,345-366/trigger.py:60/start_step.py:127,137,167/summary.py:61/
     task_registry.py:194/universal_agent.py:42/message_service.py:45/hitl_gateway.py:88-92/
     hitl_confirmation.py:103/project_context.py:45/tool_runner.py:157/chunk_buffer.py:38 - 小欧-2026-09-23
   2026-09-23 - 小欧 - 调优组 notice/label 去开发术语(北京老陈指令"怎么还有开发的代码信息"):
     设置页 notice 是给最终用户看的，禁出现 SSE/HITL/bypass/CORS/Origin/chunk/FC/L2/C4/TTL/
     信号量/request body/ConnectTimeout/PoolTimeout/TCP/DNS/ShellPoolBusy/IDLE_TIMEOUT/Vite
     proxy/action_handler/tool_result/上下文窗口 等代码与内部黑话 —— 全组改纯用户语言
     (「我还活着」「记得更久更费钱」「弹窗一闪来不及点」式口语)，label 同步去术语
     (tool_choice模式→工具调用模式、流式最大重试→传输失败重试、FC响应回退→工具失败转文字、
     响应错误重试→内容错误重试、SSE心跳周期→保活间隔、HITL/bypass倒计时→确认倒计时、
     CORS允许来源→允许访问的页面地址、chunk累积上限→卡死保护上限、软配额等待→排队最多等、
     Shell池槽位→终端会话槽位、裁剪触发比例→裁剪触发水位、开局压缩水位等) ——
     config.yaml.example 注释同步去术语；float 类型键(connect/write/pool/soft_pool)类型值域未动 - 小欧-2026-09-23
   2026-09-23 19:51:21 - 小欧 - 通用组 agent.max_steps label/notice 归位(北京老陈裁定"标签不对，应该是最大轮数"):
     label "最大步数"→"最大轮数"——消费点 react_loop.py:188 while agent.llm_call_count < max_steps 实际限制的是
     LLM 调用轮数(任务条"轮数")，原"步数"标签误导(任务条"步数"=step_count 纯统计无独立上限、被本门限间接封顶)；
     notice 改为轮数门限语义+与"步数"区分说明。键名 agent.max_steps/默认10000/值域[1,10000]/读取链
     config.py:169 get_max_steps→base_agent.py:74 self.max_steps 均不动，只改皮 — 小欧-2026-09-23
   2026-09-23 19:53:20 - 小欧 - tuning.trim.max_rounds notice 修正(北京老陈指正"这个注释不对"):
     原"只记得最近 N 轮问答"语义不准——实际是超限触发裁剪操作，非单纯记忆范围；
     改为"超过 N 轮后执行历史对话信息裁剪，更早的自动忘掉；调大=保留更多的原始信息但更费 token，
     调小=省钱但会忘更早的事" —— 消费点 message_builder.py:358-360 msg_count>max_rounds*2+2 触发裁剪 — 小欧-2026-09-23
"""
from typing import Any, Dict, List, Optional


def _item(key: str, type_: str, label: str, default: Any = None,
          options: Optional[List[Any]] = None, range_: Optional[List[float]] = None,
          step: Optional[float] = None, restart: bool = False, secret: bool = False,
          readonly: bool = False, notice: str = "",
          env_key: Optional[str] = None) -> Dict[str, Any]:
    """单项构造：storage 统一 YAML（4.0/v3.0 单存储），env_key 指定环境变量名时来源判定看 os.environ 是否设了该键。"""
    return {"key": key, "type": type_, "label": label, "default": default,
            "options": options, "range": range_, "step": step, "storage": "YAML",
            "restart": restart, "secret": secret, "readonly": readonly, "notice": notice,
            "env_key": env_key}


GROUPS: Dict[str, Dict[str, Any]] = {
    # 4.1 通用（general，10 项）
    "general": {"label": "通用", "items": [
        _item("workspace.project_root", "text", "项目根目录", "E:\\test_dir"),
        _item("workspace.allowed_dirs", "textarea", "授权目录", "",
              notice="项目根之外额外授权访问的工作目录，多个用换行分隔"),
        _item("logging.debug", "bool", "调试模式", True, restart=True,
              notice="开启后日志按 DEBUG 级别记录，明细含文件/行号"),
        _item("agent.max_steps", "int", "最大轮数", 10000, range_=[1, 10000],
              notice="单任务最多执行的对话轮数（循环门限）：任务条上的『轮数』到顶就强制结束任务；调大=允许跑更久，调小=更早刹车。注意这不是任务条上的『步数』（步数只是自动统计，跟着轮数走，没有单独上限）"),
        # ✅ general 组 agent.max_steps 之后追加 6 条目 — 小欧 2026-09-23
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
        _item("llm.context_limit_default", "int", "默认上下文窗口", 262144, range_=[200000, 2000000],
              notice="模型一次能记住的内容总量默认值（单个模型没单独配置时用这个），约 25.6 万 token"),
    ]},
    # 4.2 模型（model，结构化语义；CRUD 由 model_service 承接，见 9.1.3）
    "model": {"label": "模型", "items": [
        _item("ai.model_ref", "model_ref", "当前系统全局使用模型", None,
              notice="当前选用的模型（哪个服务商+哪个模型）；被环境变量强制指定时整行只读",
              env_key="AI_PROVIDER"),
    ]},
    # 4.3 安全（security，4 项，YAML，即时；命令安全由 path_safe_check/tools/security 代码内实现）
    "security": {"label": "安全", "items": [
        _item("security.enabled", "bool", "安全开关", False,
              notice="关闭后跳过所有安全检查（盘根/项目根等删除硬防线仍生效）"),
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
    # 4.5 系统（system，12 项：3 运维日志配置 + 1 日志目录只读 + 6 工程目录只读 + 2 关于只读）
    #   注意：本小节新增 / 删除 paths.* 条目务必同步 settings_service._item_data 的 paths 派生字典，
    #   二者 keys 一一对应，service 漏配将抛 KeyError(fail-fast 防静默空白) —— 小欧 2026-09-21
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
        # --- 关于（2 只读） ---
        _item("config_path", "readonly", "配置文件路径", None, readonly=True),
        _item("version", "readonly", "当前版本", None, readonly=True),
    ]},
    # 4.6 外观（theme 只读，字号/语言 YAML 即时 + 本地预应用）
    "appearance": {"label": "外观", "items": [
        _item("app.language", "select", "系统语言", "zh-CN",
              options=["zh-CN", "en-US"], restart=True),
        _item("app.theme", "readonly", "主题", "light", readonly=True,
              notice="当前固定浅色；深色二期（需全站 token 化重做硬编码色值）"),
        _item("appearance.fontSize", "range", "字号(px)", 14, range_=[12, 18], step=1),
    ]},
    # 2026-09-22 小欧 - [61] v2.0 第六章 6.2：新增 tuning 调优组（8子组31键，值域来自 constants.py 现值）
    # 2026-09-23 小欧 - 现 10子组35键（[64]剔temperature/max_tokens迁通用+stream_options改bool，trim/compaction配置化加 trim 3键/compaction 4键）
    "tuning": {"label": "调优", "items": [
        # --- llm: LLM 语义参数（5 键，temperature/max_tokens 已迁入 llm.sampling.* 通用组）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.llm.tool_choice", "select", "工具调用模式", "auto",
              options=["auto", "none"], notice="控制模型能不能用工具：auto=正常模式，模型自己决定要不要调用工具；none=禁止用工具，只回纯文字（怀疑工具出问题时用它对照）"),
        _item("tuning.llm.stream_max_retries", "int", "传输失败重试", 3, range_=[0, 10],
              notice="请求中途断线或超时时自动重新发起，最多再试 N 次（每次比上次多等一会）；0=不重试直接失败。与下面「内容错误重试」分工：本项管根本没收到回复，下面管收到了但内容不对"),
        _item("tuning.llm.response_fallback", "bool", "工具失败转文字", True,
              notice="让模型用工具干活时如果一直失败，重试用完后自动改成「不用工具、直接写文字回答」再试一次；关掉则失败就直接报错"),
        _item("tuning.llm.response_retries", "int", "内容错误重试", 2, range_=[0, 5],
              notice="模型返回空回复或明显坏内容时自动重试，最多 N 次，越等越久；配额用完、被限流、请求本身写错这三种情况不走这里。与上面「传输失败重试」分工：本项管内容坏，上面管没收到"),
        _item("tuning.llm.stream_options.include_usage", "bool", "统计 Token 用量", True,
              notice="回答结束后附带本次消耗了多少 token（输入+输出）；关掉后任务统计页的 token 数会显示为 0"),
        # --- llm_net: LLM 网络/超时/连接池（7 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
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
        # --- concurrency: 并发配额（2 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.concurrency.soft_pool_wait_timeout", "float", "排队最多等(秒)", 30.0, range_=[5, 120],
              notice="同时请求达到上限时新请求先排队，最多等这么多秒；等超了就不排了、照样放行（宁可挤一点也不让任务卡死）。与上面「等空闲连接超时」分工：本项管应用层排队，那边管网络连接层"),
        _item("tuning.concurrency.shell_pool_max_per_type", "int", "终端会话槽位", 8, range_=[1, 20],
              notice="同一任务里同一种终端（如 PowerShell）最多同时开几个常驻会话：满了新命令要等空位；调大=并行命令更顺但更占内存"),
        # --- agent: Agent 循环参数（1 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.agent.max_chunks_without_promote", "int", "卡死保护上限", 50, range_=[10, 200],
              notice="模型一直往外吐零碎字却始终不给完整回答，累计吐够这么多次就判定卡死、强制结束任务（防止白白烧配额）"),
        # --- trim: 裁剪 3 键（每轮循环自动执行）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.trim.max_rounds", "int", "保留对话轮数", 100, range_=[1, 10000],
              notice="超过 N 轮后执行历史对话信息裁剪，更早的自动忘掉；调大=保留更多的原始信息但更费 token，调小=省钱但会忘更早的事"),
        _item("tuning.trim.trigger_ratio", "float", "裁剪触发水位", 0.75, range_=[0.1, 0.95],
              notice="对话占到模型记忆容量的百分之多少时开始自动删旧内容（0.75=占到四分之三就删）；调小=删得勤、腾地方快，调大=多记一会但快满时才动手"),
        _item("tuning.trim.compaction_buffer", "int", "给回答留底(字符)", 20000, range_=[1000, 100000],
              notice="删旧内容时故意不删满，给模型写这次回答预留这么多容量，防止删完一点空都没有、模型没地方写"),
        # --- compaction: 压缩 4 键（开局超容时把旧对话压成摘要）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.compaction.start_enabled", "bool", "开局压缩开关", True,
              notice="任务刚开始如果发现以前的对话太长装不下，先自动压成一段摘要再开始干活；关掉则不压、直接硬删"),
        _item("tuning.compaction.start_trigger_ratio", "float", "开局压缩水位", 0.5, range_=[0.1, 0.95],
              notice="开局时旧对话占到记忆容量百分之多少才值得压（0.5=占到一半就压）；只管任务开头这一次，任务跑起来后归上面的「裁剪」管"),
        _item("tuning.compaction.summary_feed_max_chars", "int", "单条截断(字符)", 2000, range_=[100, 10000],
              notice="压成摘要前，单条工具结果超过这么多字先砍掉再给模型看（防超长输出把摘要过程撑爆）；调大=摘要更全但更费"),
        _item("tuning.compaction.keep_tail", "int", "摘要后留几条", 1, range_=[0, 5],
              notice="压成摘要后，再原样保留最近几条消息不压（保住最新对话细节不被摘要抹平）；0=全压成摘要、不留原话"),
        # --- stream_task: 连接保活/任务清理/缓存（4 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.stream_task.heartbeat_interval", "float", "保活间隔(秒)", 25.0, range_=[5, 60],
              notice="任务执行中如果一会儿没新内容，每隔这么多秒主动给页面发一个「我还活着」的信号，防止页面误以为断了自动重连；必须明显小于页面的 60 秒断线判定，否则白保活"),
        _item("tuning.stream_task.task_timeout_hours", "int", "任务保留(小时)", 1, range_=[1, 24],
              notice="已经做完的任务在列表里保留几小时后自动清掉（正在跑的不受影响）；调小=列表干净但翻不了旧任务，调大=能回看更久"),
        _item("tuning.stream_task.tool_cache_ttl", "int", "结果复用时间(秒)", 300, range_=[60, 3600],
              notice="同一工具用同样的参数再查一次时，这么多秒内直接给上次的结果、不再真跑一遍；调小=结果更新鲜但重复查询更慢，调大=更快但可能给到过期结果"),
        _item("tuning.stream_task.max_cache_size", "int", "缓存条数上限", 1000, range_=[100, 10000],
              notice="内部小缓存最多存多少条，超了自动丢最久没用的；一般不用动，调错也没什么感觉"),
        # --- hitl: 人工确认（4 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.hitl.hitl_confirm_lead", "int", "确认倒计时提前(秒)", 10, range_=[0, 60],
              notice="危险操作确认弹窗：页面上的倒计时比后端实际超时（默认120秒）提前这么多秒归零，让你先看到「已超时」提示，而不是弹窗凭空消失；提前量要小于总超时"),
        _item("tuning.hitl.bypass_auto_lead", "int", "自动放行提前(秒)", 2, range_=[0, 10],
              notice="自动确认弹窗：页面倒计时比后端自动放行提前这么多秒归零，保证页面先收好、后端再放行，弹窗不会闪一下才关"),
        _item("tuning.hitl.hitl_min_confirm_timeout", "int", "倒计时最短(秒)", 3, range_=[1, 30],
              notice="确认弹窗倒计时至少显示这么多秒，防止倒计时太短、弹窗一闪而来不及点"),
        _item("tuning.hitl.max_pending_confirmations", "int", "待确认条数上限", 100, range_=[10, 1000],
              notice="同时排队等你确认的操作最多多少条，超了新的直接拒绝（防一次弹出太多窗把页面卡死）"),
        # --- content: 内容截断（3 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.content.project_context_max_chars", "int", "项目规则字数上限", 10000, range_=[1000, 50000],
              notice="项目规则文件(OmniAgent.md)每次带给模型的最大字数，超长部分不带；调大=规则记得全但更占记忆容量，调小=省容量但长规则会被截断"),
        _item("tuning.content.action_log_result_max_chars", "int", "工具结果字数上限", 5000, range_=[1000, 20000],
              notice="工具跑完后写进对话记录的单条结果最多保留多少字，超长截断；防止读了个大文件把整个对话撑爆"),
        _item("tuning.content.temp_history_char_limit", "int", "临时副本字数上限", 50000, range_=[5000, 200000],
              notice="压缩过程中临时存的对话副本最多多少字，超了硬截断；正常用不到，属于防爆保险"),
        # --- network: 网络（1 键）--- notice 2026-09-23 去开发术语重写 — 小欧-2026-09-23
        _item("tuning.network.cors_origins", "text", "允许访问的页面地址",
              "http://localhost:5173,http://127.0.0.1:5173",
              notice="允许访问本服务的页面地址白名单，多个用逗号隔开；换了前端地址或端口要加上新地址，否则页面会被浏览器拦住。默认两个是本机开发地址，一般不用改"),
    ]},
}

GROUP_ORDER = ["general", "model", "security", "sandbox", "tuning", "system", "appearance"]

# registry key → ConfigUpdate 字段映射（旧键走 config_service.update_config，语义不变；
# 未列出的键走通用 region 合并，见 config_helpers.merge_region_patch）
OLD_KEY_MAP: Dict[str, str] = {
    "app.language": "language",
    "workspace.project_root": "project_root",
    "ai.model_ref": "ai_model_ref",
}
# v4.17 修正：安全 10 项全部逐键走通用 region 合并（security.* 逐行 merge，防整块覆盖丢键）。
# 原 SECURITY_KNOWN 整块写 ConfigUpdate.security 的方案撤销——整块替换会覆盖未识别键造成丢数据。
# v4.18 修正：app.max_steps 从 OLD_KEY_MAP 移除，统一走 merge_region_patch（与 app.debug/max_context_tokens/max_history_length/max_rounds 同路径，消除系统参数写路径分裂）；范围校验由 registry range_=[1,10000] + _validate_value 承接。
# v4.20 修正：键名按域收敛后，app.max_steps→agent.max_steps、app.max_rounds→agent.max_rounds、app.debug→logging.debug、
#   app.project_root→workspace.project_root、app.allowed_dirs→workspace.allowed_dirs（OLD_KEY_MAP 同步改）；死配置已全清。
# v4.18 修正：app.theme 从 OLD_KEY_MAP 移除——该键 readonly=True，_validate_value 恒先拒，映射不可达死代码。


def _build_index() -> Dict[str, Dict[str, Any]]:
    """模块加载自检：key 全局唯一，重复直接拒启（3.2 铁律1）。"""
    index: Dict[str, Dict[str, Any]] = {}
    for gname, group in GROUPS.items():
        for item in group["items"]:
            key = item["key"]
            if key in index:
                raise RuntimeError(f"[settings_registry] 重复 key 拒启: {key}")
            index[key] = item
    return index


REGISTRY_INDEX = _build_index()


def get_item(key: str) -> Optional[Dict[str, Any]]:
    """按 key 取 schema 项。"""
    return REGISTRY_INDEX.get(key)


def group_items(group: str) -> List[Dict[str, Any]]:
    """取某组全部 schema 项。"""
    return GROUPS[group]["items"]
