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
    # 4.1 通用（general，5 项）
    "general": {"label": "通用", "items": [
        _item("workspace.project_root", "text", "项目根目录", "E:\\test_dir"),
        _item("workspace.allowed_dirs", "textarea", "授权目录", "",
              notice="项目根之外额外授权访问的工作目录，多个用换行分隔"),
        _item("logging.debug", "bool", "调试模式", True, restart=True,
              notice="开启后日志按 DEBUG 级别记录，明细含文件/行号"),
        _item("agent.max_rounds", "int", "最大轮数", 100, range_=[1, 10000],
              notice="单个任务最大执行轮数，超限结束任务"),
        _item("agent.max_steps", "int", "最大步数", 10000, range_=[1, 10000],
              notice="单任务最大执行步数，超限中止"),
    ]},
    # 4.2 模型（model，结构化语义；CRUD 由 model_service 承接，见 9.1.3）
    "model": {"label": "模型", "items": [
        _item("ai.model_ref", "model_ref", "当前系统全局使用模型", None,
              notice="与后端 DTO 同形的 {provider, model} 结构；env 接管时整行只读",
              env_key="AI_PROVIDER"),
    ]},
    # 4.3 安全（security，4 项，YAML，即时；命令安全由 path_safe_check/tools/security 代码内实现）
    "security": {"label": "安全", "items": [
        _item("security.enabled", "bool", "安全开关", False,
              notice="关闭后跳过所有安全检查（盘根/项目根等删除硬防线仍生效）"),
        _item("security.confirmDangerousOps", "bool", "危险操作确认", True,
              notice="保存二次确认 Modal（UX 层）；后端安全门禁独立生效"),
        _item("security.auto_confirm_delay", "int", "自动确认延迟(秒)", 10, range_=[0, 3600],
              notice="HITL 自动确认倒计时（秒），到时未操作自动放行"),
        _item("security.hitl_timeout", "int", "人工确认超时(秒)", 120, range_=[1, 86400],
              notice="HITL 人工确认最大等待（秒），超时按策略处理"),
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
              notice="workspace.project_root 已配置时用配置值；未配置时=用户主目录（2026-09-22 小欧：label 与 workspace.project_root 去重，保证 SearchBox 跳转无歧义）"),
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
    "tuning": {"label": "调优", "items": [
        # --- llm: LLM 语义参数（7 键） ---
        _item("tuning.llm.temperature", "float", "采样温度", 0.7, range_=[0, 2],
              notice="LLM 采样温度，0=确定性，2=高随机"),
        _item("tuning.llm.tool_choice", "select", "tool_choice 模式", "auto",
              options=["auto", "none"], notice="auto=模型自主选择工具，none=纯文本模式"),
        _item("tuning.llm.max_tokens", "int", "单次最大 token", 16384, range_=[1, 100000],
              notice="LLM 单次调用最大输出 token 数"),
        _item("tuning.llm.stream_max_retries", "int", "流式最大重试", 3, range_=[0, 10],
              notice="LLM 流式调用最大重试次数"),
        _item("tuning.llm.response_fallback", "bool", "FC 响应回退", True,
              notice="FC 模式错误时降级为 Text 模式重试"),
        _item("tuning.llm.response_retries", "int", "响应错误重试", 2, range_=[0, 5],
              notice="LLM 响应错误（空/无效）最大重试次数"),
        _item("tuning.llm.stream_options", "textarea", "流式选项(JSON)", '{"include_usage": true}',
              notice="LLM 流式请求 stream_options 字段，JSON 格式"),
        # --- llm_net: LLM 网络/超时/连接池（7 键） ---
        _item("tuning.llm_net.read_timeout", "int", "读超时(秒)", 150, range_=[10, 600],
              notice="LLM 客户端读超时兜底(秒)"),
        _item("tuning.llm_net.connect_timeout", "float", "连接超时(秒)", 30.0, range_=[5, 120],
              notice="LLM 客户端连接超时(秒)"),
        _item("tuning.llm_net.write_timeout", "float", "写超时(秒)", 10.0, range_=[5, 120],
              notice="LLM 客户端写超时(秒)"),
        _item("tuning.llm_net.pool_timeout", "float", "连接池超时(秒)", 10.0, range_=[5, 120],
              notice="LLM 客户端连接池超时(秒)"),
        _item("tuning.llm_net.max_connections", "int", "池最大连接", 10, range_=[1, 50],
              notice="LLM 客户端连接池最大连接数"),
        _item("tuning.llm_net.max_keepalive", "int", "keepalive 连接", 5, range_=[0, 20],
              notice="LLM 客户端连接池 keepalive 连接数"),
        _item("tuning.llm_net.stream_total_timeout", "int", "流总硬超时(秒)", 500, range_=[60, 3600],
              notice="单次 LLM 流式调用总时长硬超时(秒)"),
        # --- concurrency: 并发配额（2 键） ---
        _item("tuning.concurrency.soft_pool_wait_timeout", "float", "软配额等待(秒)", 30.0, range_=[5, 120],
              notice="LLM 软配额排队等待上限(秒)，超时保底放行"),
        _item("tuning.concurrency.shell_pool_max_per_type", "int", "Shell 池槽位", 8, range_=[1, 20],
              notice="同 key Shell 池最大并发实例数"),
        # --- agent: Agent 循环参数（3 键） ---
        _item("tuning.agent.default_max_steps", "int", "Agent 最大步数", 100, range_=[10, 500],
              notice="API 请求体默认 max_steps（config.yaml agent.max_steps 为运行时上限）"),
        _item("tuning.agent.max_consecutive_chunks", "int", "连续 chunk 上限", 5, range_=[1, 20],
              notice="Agent 循环连续 chunk 上限，超出触发 promote"),
        _item("tuning.agent.max_chunks_without_promote", "int", "无 promote 上限", 50, range_=[10, 200],
              notice="Agent 循环无 promote 的 chunk 上限，超出强制停止"),
        # --- stream_task: 流/任务/缓存（4 键） ---
        _item("tuning.stream_task.heartbeat_interval", "float", "SSE 心跳周期(秒)", 25.0, range_=[5, 60],
              notice="SSE keep-alive 心跳周期(秒)，须 < 前端 IDLE_TIMEOUT=60s"),
        _item("tuning.stream_task.task_timeout_hours", "int", "任务过期(小时)", 1, range_=[1, 24],
              notice="已结束任务超过 N 小时自动清理"),
        _item("tuning.stream_task.tool_cache_ttl", "int", "工具缓存 TTL(秒)", 300, range_=[60, 3600],
              notice="工具结果缓存 TTL(秒)"),
        _item("tuning.stream_task.max_cache_size", "int", "缓存条目上限", 1000, range_=[100, 10000],
              notice="会话/上下文缓存最大条目数"),
        # --- hitl: 人工确认（4 键） ---
        _item("tuning.hitl.hitl_confirm_lead", "int", "HITL 倒计时提前量(秒)", 10, range_=[0, 60],
              notice="前端倒计时比后端 HITL_TIMEOUT 提前的秒数"),
        _item("tuning.hitl.bypass_auto_lead", "int", "bypass 提前量(秒)", 2, range_=[0, 10],
              notice="bypass 前端倒计时比后端提前的秒数"),
        _item("tuning.hitl.hitl_min_confirm_timeout", "int", "倒计时最小值(秒)", 3, range_=[1, 30],
              notice="前端倒计时最小值，不低于后端窗口减提前量"),
        _item("tuning.hitl.max_pending_confirmations", "int", "待确认上限", 100, range_=[10, 1000],
              notice="HITL 最大待确认请求数"),
        # --- content: 内容截断（3 键） ---
        _item("tuning.content.project_context_max_chars", "int", "上下文注入上限(字符)", 10000, range_=[1000, 50000],
              notice="项目规则文件(OmniAgent.md)注入 Prompt 字符上限"),
        _item("tuning.content.action_log_result_max_chars", "int", "日志截断(字符)", 5000, range_=[1000, 20000],
              notice="action_handler 日志 tool_result 截断长度"),
        _item("tuning.content.temp_history_char_limit", "int", "临时历史字符上限", 50000, range_=[5000, 200000],
              notice="compaction 临时历史字符上限"),
        # --- network: 网络（1 键） ---
        _item("tuning.network.cors_origins", "text", "CORS 允许来源",
              "http://localhost:5173,http://127.0.0.1:5173",
              notice="API CORS 允许来源，多个用逗号分隔"),
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
