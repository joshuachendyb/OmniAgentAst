# [68] delegateagent 与 AgentConfig 多 Agent 委托机制设计

> 文档名称: delegateagent与AgentConfig多Agent委托机制设计-小欧-2026-11-27

版本历史:
- v1.0 2026-11-27 小欧 初版创建
- v1.1 2026-11-27 小欧 代码契约核验后修订：补子 Agent 独立事件缓冲；修正空集合语义反转、工具过滤双重失效、ContextVar token 模式、工具返回体契约、摘要提取字段；删除未消费字段；补 system_prompt 注入、并行上限落点、取消联动与临时授权约束
- v1.2 2026-11-27 小欧 主名称定为 delegateagent，其它生态名（subagent/delegate_task/delegate_to_agent/call_agent）经工具名别名层归一到本名；Schema 同步更名；新增 wait 参数，P0 同步、P1 异步；补别名映射改动清单
- v1.3 2026-11-27 小欧 §7 扩为通信交互与数据流总览：补主 Agent 四条通信通道（LLM/工具层/前端/子 Agent）与三条设计约束，明确子 Agent 结果经 FinalStep.response → summary → observation 回灌父 Agent 的路径
- v1.4 2026-11-27 小欧 明确执行模型：子 Agent 是同进程同事件循环的协程任务（非子进程/子线程），靠 ContextVar 副本做逻辑隔离；补入 §7.1 与架构边界约束、§1.2 设计约束、§9 决策记录
- v1.5 2026-11-27 小欧 明确子 Agent 复用主 Agent 同一 `react_loop.run_react_cycle`（零重写），差异全在配置/注入；补入 §2.6 与 §5.3
- v1.6 2026-11-27 小欧 `AgentConfig.model` 配置层扩展位：默认 None 继承父 Agent 的 LLM，非 None 时新建独立 llm_client（用完归还），不入工具参数；新增 §2.8 OCP 扩展点总表（13 个开放口 + 未列扩展点的封闭理由 + 灵活/可靠/高效三性）；补入 §2.1、§2.6、§6.2、§8、§9
- v1.7 2026-11-27 小欧 全文通读一致性修订：回调签名/工具描述补 wait、并行措辞统一到 tool_runner、旧名 delegate() 改正、§8 P0 model 行归位、§4.3 连接池补独立 client 说明、去"A+"口语化引用
- v1.8 2026-11-27 小欧 三堂会审逐条对码复核后的修订：①`AgentConfig.model` 路径原写 `agent.llm_client.api_key`，该类只有 `_api_key`（client_sdk.py:441），照写必 AttributeError；补只读 `api_key` property 并复用父 httpx 客户端（`shared_client`）；②递归防护原只靠"AGENT 分类不在工具集"，但 `auto_inject_from_search` 会按 searchtool 结果 `load_category` 把 AGENT 整类灌回子 Agent（`_retry_engine._tools` 与 `_tools_dict` 同一 dict 引用），改为 fail-closed：委托深度 ContextVar + 子作用域清空委托回调；③子 Agent 的 HITL/交互无出口（确认正文走 interact 帧进子私有 buffer、用户不可见，`wait_for_confirmation_result` 120s 后按拒处理），P0 定为只读子 Agent（拒绝清单 + 构造后确认工具校验）；④并行共享 `llm_client` 时 `_current_response` 单槽互相覆盖，取消改以 Task.cancel 为准；⑤P1 异步回灌原来写 notice/SSE，父 LLM 读不到，改走既有 inbox（`inject_system_notice` → `drain_inbox` → 对话历史）；⑥新增守卫协程：墙钟超时 + 父取消联动，且取消/超时时先把子任务收干净再回收 buffer；⑦工具描述改由注册表动态生成（`description` 支持 callable），新增 Agent 零改代码；⑧`agent_id` 校验、`AgentConfig.__post_init__` 校验、Registry `unregister/reset`；⑨删死参数 `parallel`（框架按 `len(all_calls)>1` 决定并行）、`output_format` 改自由文本 `output_instruction`；⑩`subagent` 别名与 `UNAVAILABLE_OFFICIAL_TOOLS`/`tuning.agent.disabled_tools` 冲突，不收录；⑪补插件扫描器文件与启动调用点；⑫子 Agent 不落 `tasks` 台账（`track_task=False`）
- v1.9 2026-11-27 小欧 复核后落实全文一致性：①§4.2 补"继承≠可用：子 Agent 必须只读"三条对码事实（确认正文只走 interact 帧 / `wait_for_confirmation_result` 120s 按拒 / 交互事件只写本地 buffer）与"三道同源约束 + 构造后元数据校验"；②§4.3 资源保护表重写（`timeout_s` 墙钟 P0 生效、取消改父侧轮询联动、buffer 先收子任务再回收、台账 `track_task=False`）；③§5.1 补 `plugin_loader.py`、`agent_config.py` 落 tools 层并说明归层理由；§5.2 补 `client_sdk.py`/`base_agent.py`/`tool_loader.py`/`universal_agent.py`/`registry.py`/`tool_description.py` 及行数订正；§5.3 移除已被修改的 `base_agent.py`/`tool_loader.py`/`universal_agent.py`，补 `hitl_confirmation.py` 不改理由；④§6.2 字段同步 `output_instruction`/`timeout_s` 并说明插件不可指定 `track_task`/`allow_delegate`；⑤§6.3 改为 `_register_agent_tools()` 内扫描、目录取 `tuning.agent.plugins_dir`（默认 `get_code_root()/plugins`）、只需早于工具列表构建；⑥§7.1 由四条通道扩为五条，新增"⑤ 异步回灌（P1）"= `inject_system_notice` → `drain_inbox` → 对话历史；§7.2 数据流按 `run_delegate` 实际步骤重画；§7.3 约束由三条扩为四条（改走 inbox + 子 Agent 不得依赖"人"）；⑦§8 把并行上限/超时/只读/深度校验/`api_key` property 上移 P0，`subagent` 收编列 P2；⑧§9 补 9 条决策（fail-closed、只读、守卫协程、`api_key`+`shared_client`、并行共享单槽风险、删 `parallel`、`output_instruction`、`subagent` 冲突、归层、callable 描述、`track_task`）
- v2.0 2026-11-27 小欧 对码核实整改（契约时态与位置口径）：①§3.2 原写"复用 `init_tools(initial_categories, excluded_tools)`"与"`to_openai_tools(exclude=...)` 都读它"均与代码不符——`init_tools` 实签为 `(self, initial_categories=None)`、`to_openai_tools` 实签为 `(registry, categories, tool_names, strict)` 无 `exclude`，改为标注"须 §5.2 改造后成立"并列出三处改造前提；②点明 `UniversalAgent`/`BaseAgent` 现为 `**kwargs` 只收不校验，漏改即静默失效，故改造须显式形参 + 启动期 fail-fast；③§4.3 台账行原写"`BaseAgent.__init__` 不再 `tracker.create_task`"与事实相反（当前无条件建行、无 `track_task` 形参），改为"须实装门控"并写清未改后果；④§2.6 构造代码注释标注两参数"改造后生效"；⑤§3.2 与 §4.2 重复的"三处同源"收敛为 §4.2 引用 §3.2；⑥`MAX_DELEGATE_DEPTH` 位置口径统一——留 runner 模块常量（仅本模块使用），仅 `MAX_PARALLEL_SUB_AGENTS` 进 `tool_constants.py`；⑦§5.2 清单同步：`tool_description.py` 增 `exclude` 形参、`base_agent.py` 去 `**kwargs` 静默吞、`tool_executor.py` 删误写的 `excluded_tools` 透传；⑧§5.3 补 `hitl_confirmation.py` 真实路径 `services/task/`；⑨§7.1 补第 4 条架构边界（子 Agent 工具集须落在异步 I/O 或已下沉宿主/线程池的工具上，CPU 密集类会阻塞全局事件循环、受害面为全部会话）；⑩§8 增"契约前置改造"P0 项、§9 增 fail-fast 决策
- v2.1 2026-11-27 小欧 章节结构重组：①§2 小节合并——原 2.4(ContextVar)+2.5(入口层注入)合并为新 2.4"注入机制"；原 2.6(运行器)+2.7(并行模式)合并为新 2.5"子 Agent 运行器"；原 2.8 顺延为新 2.6"OCP 扩展点总表"；②原 §4 防递归与安全防护整体前置并入新 2.7"安全与递归防护"（原 4.1/4.2/4.3 内容不变，仅降级为 2.7.x）；③原 §7 通信交互与数据流总览提前为新 §3；④原 §3 与现有代码的集成顺延为新 §4；⑤原 §6 插件/Skill Manifest 格式并入新 §2.1 作为子节（2.1.x 插件 manifest 加载），不再独立成章；⑥原 §5/§8/§9 顺延为新 §5/§6/§7；⑦全文交叉引用章节号同步更新
- v2.2 2026-11-27 小欧 设计决策记录由文末移至 §1.4（概述阶段先给决策全貌，读者不必翻到末尾）；修正 §1.3 与 §1.4 之间缺空行、标题多余空格、文末悬空分隔线
- v2.3 2026-11-27 小欧 补执行模型与并行前提两处口径：①§1.4 增两条决策——子 Agent 前台阻塞+可并行（不做后台 fire-and-forget）的理由、子 Agent 价值定位在上下文隔离；②§2.5.1 增"并行的真实前提"（`delegateagent` 不在 `_has_conflict` 三类工具集内 → 恒无冲突恒可并行，属结构性巧合，加路径参数会静默退化为串行）与"前台阻塞 ≠ 串行等待"，并标注 `MAX_PARALLEL_SUB_AGENTS` 当前代码尚无、为 §5.2 新增项；③§3.1 增"前台/后台"与"串行/并行"两维度独立说明；④§6 P0 并行上限行补常量新增
- v2.4 2026-11-27 20:03:59 小欧 逐条对码后的收口整改：①删 `AgentConfig.allow_delegate` 死字段（全仓无消费方，没人读的开关即假开关）及 manifest 加载 kwarg，§2.1.1/§2.7.1 口径同步为 P1 再引入；②`DELEGATE_DENY_CATEGORIES` 增 `SYSTEM`（`create_task`/`delete_task` 能删父任务台账行）与 `MEDIA`（生成即落盘并计费）并逐类注理由，§1.2/§2.6/§2.7.1/§2.7.2 同步；③`_find_unattended_blocker` 覆盖面订正——只拦 AGENT 分类与声明 `needs_confirmation`/`confirm_fn` 的工具，FILE 写类因 `file_register.py:246 CONFIRMATION_MAP = {}` 不声明确认（delete 的确认在 `check_delete_permission` 执行期产出），唯一防线是 `DELEGATE_DENY_TOOLS`，原"新工具自动兜底"的措辞属高估；④`run_delegate` 增 `wait=False` 显式拒绝（静默当同步跑等于谎报已后台执行）；⑤`UniversalAgent(...)` 构造包 try/except + `_close_quietly`，修构造失败时独立 client 泄漏（原 `try/finally` 尚未开始）；⑥取消路径改有界：新增 `_CANCEL_GRACE_S = 5.0`，`finally` 内 `asyncio.wait(..., timeout=)` 后仍未退出则记 error 并放弃等待，避免父任务被无界挂住，同步删 `import contextlib`；⑦§4.1 补 `tool_methods["delegateagent"]` 注册步骤（漏此步工具根本不 register）；⑧§4.2/§5.2 补可见性传参链 `tool_cache_manager.get_openai_tools`（`tool_cache_manager.py:29` 现只传 `categories`）→ `registry.to_openai_tools` → `tool_description.to_openai_tools`，清单新增 `tool_cache_manager.py`；⑨§2.5.1 补"上限校验必须在工具名归一之后"（`tool_runner.py:54-59` 重写 `c["tool_name"]`，否则别名绕过 6 路上限）；⑩§3.1 ⑤ 通道载体改模块级 `task_registry.inject_system_notice`、参数名 `content`（原写 `TaskRegistry.` 方法与 `text`）；§3.2 数据流第 6 步 `track_task=False` 改 `track_task=config.track_task`；⑪§4.1 注意 2 补 callable 描述的全部落点（`tool_description.py:54`、`registry.py:374`、`register(description=...)` 类型放宽、`tool_cache_manager.py:54` 亦直读 `.description`）；⑫§3.1 架构边界第 4 条改为 `DATAANALYSIS`/`DOCUMENT` 仍属待复核 CPU 类（`SYSTEM`/`MEDIA` 已被拒绝分类覆盖）；⑬§5.2 `base_agent.py` 改为删掉 `**kwargs` 由 Python 原生 `TypeError` fail-fast（比手写校验少一层代码）
- v2.6 2026-11-27 OmniAgent 追加 2026 Agent 趋势增量章节：①§7「A2A 开放委托层」——把子 Agent"来源维度"从进程内注册表扩到 A2A/MCP 开放协议（Agent Card/Task/Artifact 映射到现有 AgentConfig/委托/回传，保留 fail-closed 可靠性内核），定位 P2+ 增量、不推翻 §1-§6；②§8「其他 2026 趋势增量」——agent RL 兼容声明、会话内自演化记忆槽、测试时 effort 预算档、按需图编排开关（默认 KISS 关闭）；③§6 里程碑表新增 P2+ 开放委托层行。原 §1-§6 正文与可靠性内核不变
- v2.7 2026-11-27 小欧 趋势增量章节收敛：①§8 整章删除——8.1 agent RL 兼容声明融入 §1.4 决策表（纯声明零代码改动，原文本就指定落点），8.4 按需图编排开关融入 §1.2「不引入 DAG」约束行（本就是该约束的破例条件），8.2 记忆槽/8.3 effort 预算档移入 §7 成为 7.2/7.3；②§7 更名「远期增量与开放生态（P2+）」，原 7.1-7.3 降为 7.1.1-7.1.3 归到 7.1 A2A 开放委托层下，全文 8 章收敛为 7 章；③§2.6 OCP 总表补「Agent 来源」行（原漏项，指向 §7.1）；④§6 P2+ 行与文末说明同步新章节号，消除对已删除 §8 的引用
- v2.8 2026-11-27 小欧 补齐实施代码（对码核实后把"只描述未给码"的缺口落码）：①§2.1.1 补 `plugin_loader.py` 完整扫描器实现 + 调用点；②§2.4.2 把 delegate 回调注入改为嵌入现有 try/finally 的真实结构（含 token 守卫理由），usage 合并交叉引用 §4.3 避免重复；③§2.5.1 把并行上限伪代码替换为可落地完整实现，并点明 `_active_calls` 取号前移的隐藏改动点；④§2.7.3 补 `base_agent` 的 `track_task` 门控代码 + 遥测归属取舍（子 Agent 不 finalize，token 经 accumulated_usage 回灌父）；⑤§4.2 补前置改造全套代码（`tool_loader`/`universal_agent`/`tool_description`/`registry`/`tool_cache_manager`/`client_sdk.api_key` 六项），并补 §5.2 清单里 `registry.to_openai_tools` 增 `exclude` 的漏项；⑥修正描述性不符：OCP 扩展口 17→18、`_find_unattended_blocker` 覆盖面措辞（全仓 needs_confirmation=True 零命中，bash/execute_sql 靠 confirm_fn）
- v2.9 2026-11-27 小欧 实施清单与里程碑逐项对齐：①§5.1/§5.2 每个文件补「修改要点（落码位置）」列，点名改哪个函数、改什么、代码在哪一节，消除"只列文件名不知改什么"；②§5.2 补原清单遗漏的 `config/config.yaml`（P1 新增 `tuning.agent.plugins_dir` 配置项）与 `stream_orchestrator.py`（P2 改 `_SSE_FORWARD_TYPES`）；③§5.3 补 `task_registry.py`（`inject_system_notice`/`drain_inbox` 已存在，P1 直接复用）、`tools/agent/__init__.py`（已存在）不改理由，并标注 `react_loop.py` 的 P2 事件 sink 例外；④§6 每阶段增「涉及文件（新增/修改）」列，逐阶段点名代码落点，工期不变
- v2.10 2026-11-27 小欧 全章交叉核查修正（逐章互相核查）：①§5.1 `load_from_manifest` 职责归属纠正——它是 `AgentRegistry` 的方法（`agent_config.py:195`），非 `plugin_loader.py` 的；`plugin_loader.py` 只做 `load_plugins()` 扫描 + 逐 manifest 调 `registry.load_from_manifest()`，行数 ~50 改 ~30（与 §2.1.1 一致）；②§5.1 `agent_config.py` 补 `load_from_manifest` 与 `get_agent_registry`/`reset_agent_registry`（模块级函数，非 Registry 方法）落点；③§5.2 `agent_register.py` 修改要点由"三张分类/依赖表"改为"三张表（描述/入参/示例）+ `tool_methods` 注册循环"（与 §4.1 四张表口径一致）；④§5.2 `stream_orchestrator.py` 预估列改"P2（暂缓）"；⑤§6 P1 插件行 `plugin_loader.py` 由"改"改"新增"（§5.1 已列为新增文件）
- v2.11 2026-11-27 22:39:03 小欧 §6 由单张优先级表扩为两节：原表收为 §6.1「优先级总表」；新增 §6.2「阶段实施方案」，把 P0 拆为 S0-S5 六个可独立验收的串行阶段、P1/P2/P2+ 各一阶段，逐阶段给出目标/改动面/验收清单/退出标准/失败回退，并补 §6.2.11 验收门禁与记录规则（每阶段一记录、红项不出阶段、安全项与能力同阶段验收）；同时纠正 §2.5.1 上限校验落点的错误前提——`execute_tools` 开头逐 call 的修正实为文件扩展名纠错（`_auto_correct_file_tool`，不查 `TOOL_NAME_ALIASES`），别名归一在下游 `registry.get_tool` 才发生，故计数必须自行调 `normalize_tool_name`，同步改 §2.5.1 代码与 §5.2 `tool_runner.py` 行、§6.2.7 验收第 2 项
- v2.12 2026-11-28 00:04:29 小欧 S0 落码后的口径校正（对码实测）：①§6.2.2 改动面由 7 个文件改 9 个——补 `tool_types.py`（`description` 放宽 + `resolved_description()` 唯一解析点）与 `tool_search.py`（BM25 索引与结果回填两处直读 `.description`，不改则 callable 描述在检索期抛 TypeError），并说明原表按 `exclude` 传参链列文件、漏了 callable 描述链路的两个读取点；②描述取值统一表述为 `resolved_description()`，不再写 `meta.description() if callable(...)` 的内联写法（单一解析点，六处读取点一处收口）；③验收第 2 项补"快照须取自真实改造前代码（`git archive HEAD backend` + 同一探针），不得用复算等价代替"；④验收第 7 项与 §6.2.11 第 2 条把"单测全绿"改为可执行的"失败集合与改造前基线同一集合，新增一条即失败"（实测基线存量 52 条红项，全绿不可达，原措辞会把每个阶段都卡死）
- v2.13 2026-11-28 06:32:54 小欧 全文再核（S0 已落码后的一致性收口）：①§6.1/§6.2.1/§5.2 三处文件清单与 §6.2.2 的 9 文件对齐——补 `tool_types.py`/`tool_search.py`，§6.2.2 失败回退"7 个文件"订正为 9；②§6.2.2 增注「表中『现 :N』指 S0 改造前位置」，避免落码后行号下移被误读；「全仓 6 处读取点」改为不计数表述，并订正 v2.12 的该计数——实测 ToolMetadata 直读点为 5 处（`tool_description.py:54`/`registry.py:374`/`tool_cache_manager.py:54`/`tool_search.py:110`、`:294`）；③§4.1 注意点 2 由"各 +1 行内联解析 callable"改为"只在一处解析"：`tool_types.resolved_description()` 为唯一解析点，补 `tool_search` 两处直读，说明散落写法会在检索期抛 TypeError；④§4.2 ①～⑥ 由"形参当前不存在"改为"S0 前不存在 / S0 已落码"（`init_tools(excluded_tools)`、`to_openai_tools(exclude)`、`registry`/`tool_cache_manager` 传参链、`api_key` property），③ 代码样例 `meta.description() if callable(...)` 改 `meta.resolved_description()`；⑤§1.4 与 §2.7.3 台账/`**kwargs` 两处口径由"当前无条件建台账、现有 kwargs 不校验"改为"S0 前如此，S0 已门控/已删"，台账行与门控代码块标注 S0 已落码；⑥工具侧 ContextVar 清单三处不一致（§2.7.2 七组、§2.6 九项含 depth、§3.1 八项缺 task_id）统一为"10 个，清单见 §2.7.2"，清单按 `app/tools/context.py` 实测（task_id/hooks/text_task/notice/question/generate/precheck/session_id/delegate/depth）；⑦§6.2.5 第 16 项原用"传非法 sub_task_id（含空格）"触发构造失败——该 id 由 runner 内部生成、`UniversalAgent` 只校验非空，此路不通，改为故障注入（临时替换构造器）并断言独立 client 已关闭；⑧§3.2 第 9 步把"delegate 回调置空"从 `_delegate_scope` 移到第 10 步子任务内（实际在 `_child()` 内 set）；⑨§7.2 台账引用 §5.3（不改的文件）改 §2.7.3；§7.3 effort 校验落点由 §4.1（工具注册）改 §2.2 Schema + §2.3 工具实现
- v2.14 2026-11-28 07:30:29 小欧 S0 验收补测与订正：①§6.2.2 第 1 项补服务级冒烟实测（`start_dev.ps1 watch` 真起进程 → `GET /health` 200、`status/db_status=healthy`），并写明 import 探针覆盖不到启动期建库/挂路由/构造 Agent；②第 4 项订正 `BaseAgent` 是 ABC，"无 `**kwargs`"须用 `inspect.signature` 断言 `VAR_KEYWORD`，直接实例化抛的 `TypeError` 来自抽象类、不能作证据；③第 7 项补定向回归实测（63 文件，基线 15 失败/1635 通过 vs 改造后 15/1635，失败集合逐条相同、新增 0）与 E2E-P0-03b 实测（PASSED，31.1s，5 次 LLM 调用，22 步）；④新增"补测发现并修复的静默失效点"表（5 点：`excluded_tools` 传 str 被拆单字符、别名不归一、`exclude`/`tool_names` 子串判定、`track_task` 传字符串当真有、`api_key` 返回 None），并订正 `write_file` 并非别名表键、原判断不成立；⑤新增开发启动器崩溃自愈记录（watchfiles 只在文件变更时重启子进程，补守护进程上溯清理 + 孤儿链清理 + 端口看护，实测 25s 自愈）；⑥§6.2.11 第 2 条订正回归基线取法——`git archive` 在本仓取不到测试（435 个 `test_*.py` 全部未入库），改为改动文件逐字节回退 + sha256 校验恢复，并说明全量 pytest 因 300s 超时不可用、改用定向集
- v2.15 2026-11-28 08:55:59 小欧 §6.2.3 S1 补 TDD 测试要求：新增 A–E 五组共 30 条用例设计（构造校验 / 集合语义与拒绝清单 / 注册表与单例 / manifest 容错 / 分层）、8 轮红绿节奏、可运行探针代码 `backend/tests/probe_delegate_s1_config.py` 与运行退出判据；并列出相对 §2.1 的四处字段类型收紧（`max_steps`/`timeout_s`/`tool_categories`/`track_task` 禁止隐式强转，沿用 S0 静默失效教训），`load_from_manifest` 的 `int()/float()` 解析保持不变
- v2.16 2026-11-28 09:07:41 小欧 §6.2.3 S1 按 TDD 落码完成：新增 `backend/app/tools/agent/agent_config.py`（构造即校验含四处类型收紧、拒绝清单同源、注册表六方法、单例与内置 3 Agent、manifest 容错）；探针 `backend/tests/probe_delegate_s1_config.py` 首轮导入红 → 骨架断言红 51/22 → 全绿 73 passed，ruff 全过；§6.2.3 末尾补实施记录，并产出 `notes/阶段验收记录-S1-delegateagent-小欧-2026-11-28.md`
- v2.17 2026-11-28 09:19:41 小欧 §6.2.4 S2 TDD 与落码完成：测试要求写入文档（A 失败收口与透传 / B ContextVar 隔离 / C Schema / D 分层，T01–T12），新增 `backend/tests/probe_delegate_s2_channel.py` 与两个设计内新文件 `delegateagent_schema.py`/`delegateagent.py`，`context.py` 追加 §2.4.1 原样代码；首轮导入红 → 12 passed / 0 failed，ruff 全过；澄清深度只按参考代码提供 `get_delegate_depth()`，不新增设计外包装函数；§6.2.4 末尾补实施记录，产出 `notes/阶段验收记录-S2-delegateagent-小欧-2026-11-28.md`
- v2.18 2026-11-28 09:34:08 小欧 §6.2.5 S3 补 TDD 实施方法：新增 A 同步成功与显式拒绝 / B 只读与递归防护 / C 资源与收口 / D 台账·SSE·授权隔离 / E client 与构造失败共 16 条用例设计（T01–T16，逐条对应 16 项验收），明确「真实 LLM/工具/SQLite，只做观测型 spy + 唯一构造故障注入」的打点边界、8 轮红绿节奏与可运行探针 `backend/tests/probe_delegate_s3_runner.py`；不改本阶段验收口径与失败回退口径
- v2.18 2026-11-28 09:33:49 小欧 三堂会审违规整改：①`agent_id` 正则由 `$` 锚点改全串 `fullmatch`，堵住结尾换行 fail-open，补 T02c 回归；②清除本次新增代码注释与参考代码块中的章节号/阶段号（`§6.2.3`/`S0`/`§2.7.2`/`§2.4.1`/`§2.5`/`§4.3`/`§2.2`/`§2.3`），只保留技术描述；③S1/S2 实施记录改为指向正文、不再指向阶段验收记录文件（按用户要求不再产出该类文件）；④整改后两探针 88 passed、定向回归 130 passed、ruff 全过、代码注释违规命中 0
- v2.19 2026-11-28 10:54:57 小欧 §6.2.6 S4 补 TDD 实施说明（只写测试与实施口径，不改本阶段验收口径）：新增 A 注册与描述 / B 注入与复位 / C 别名归一 / D usage 合并与终态记账 / E 全链路 E2E / F 回归共六组用例（T01–T08b + T03d）、打点边界、8 轮红绿节奏与可运行探针 `backend/tests/probe_delegate_s4_wiring.py`；对码发现并写明三处实施口径：`build_delegate_tool_description()` 尚未实现须在 S4 新增、usage 合并须同时落 `task_accumulated_tokens` 并写 DB 方能达成验收第 6 项、注入与合并判据改用 `normalize_tool_name` 防直调别名漏注入；同步把 §2.4.2 与 §4.3 的参考代码对齐这三处口径，消除新旧实现分歧
- v2.20 2026-11-28 11:00:11 小欧 §6.2.7 S5 补 TDD 实施说明（只写测试与实施口径，不改本阶段验收口径）：新增 A 上限拦截 / B 索引与取号 / C 并行不退化 / D 回归与静态契约四组用例（T01–T09）、打点边界、6 轮红绿节奏与可运行探针 `backend/tests/probe_delegate_s5_parallel_cap.py`；对码发现并写明四处实施口径：常量当前零命中须新增、`_active_calls` 改造须同步三分支且取号用 `_active_indices[pos]+1`（`make_fp_callback` 按 `exec_calls[_tno-1]` 取原始参数串）、被拒结果体用 `build_error` 空 data、别名计数须写回主名（`tool_retry_engine._prepare_execution` 裸名查表）；同步把 §2.5.1 的写回口径从"可选增强"订正为"必做"
- v2.21 2026-11-28 11:26:42 小欧 §6.2.8 S6 补 TDD 实施方法（四个子阶段逐个先红后绿，只写测试与实施口径，不改原验收要点与退出标准）：对码核实四处缺口——异步回灌通道已存在但 `wait=False` 仍显式拒绝、插件扫描器与配置项不存在、`tool_names` 字段与构造前过滤/参数别名缺失、`allow_delegate`/`provider`/`api_base` 字段与深度上限配置化缺失；新增 S6.1–S6.4 四组用例表（各 T01–T05）、打点边界、9 轮红绿节奏与四个可运行探针代码；明确 S6.1 必须证明父 LLM 经 inbox 真读到结果
- v2.22 2026-11-28 11:31:16 小欧 §6.2.6 S4 按 TDD 真实落码完成（红线→最小实现→全绿）：四处改动全部落地——`agent_config.py` 新增动态描述、`agent_register.py` 四张表+注册循环+插件占位、`tool_executor.py` 归一名注入+token 守卫 reset+四层 usage 合并写 DB、`tools_alias_mapper.py` 四别名；探针首轮 ImportError 红，逐组推进后离线用例 A/C/D 组共 15 条全绿、定向回归 101 passed、`ruff` 无新增错误。B/E 组真实 LLM 用例（T03/T03b/T03c/T03d/T04c/T04d/T07）受服务端账户级 429 速率限制（每 3 分钟 1 次、Retry-After 等待 >工具 60s 保险丝）本环境不可验证，如实标注、不宣称全绿；探针落盘两处实测修正：共享事件循环（避免跨 loop 异常）、`temp_config` 改 `setdefault` 覆盖语义（文档参考代码同步修正）
- v2.22 2026-11-28 11:29:17 小欧 补记 S4/S5 实施记录（不产出独立阶段验收记录文件，按用户要求写回正文）：S4 代码对码核实与参考代码 0 处差异、探针与 E2E 未落盘不宣称全绿；S5 探针完整 9 passed、修两处用例设计错误、429 限流下只锁真实执行与拒绝契约不放宽上限断言、ruff F 类零命中但有 8 条存量 W29x、定向回归未执行故不宣称 D 组全过
- v2.23 2026-11-28 11:43:57 小欧 §6.2.8 S6 TDD 实施方法合规修正（四个子阶段的验收要点与退出标准不变）：①对码订正 `to_openai_tools(tool_names=...)` 语义为「额外包含」而非「精确白名单」，S6.3 须新增真正的白名单过滤路径，不能靠透传达成；②S6.1 T02/T04 改为可真正变红的用例——T02 真跑 `_absorb_inbox` 并断言 `message_builder.conversation_history` 含 `delegate_id`，T04 先确认 `sub-` 委托已创建再取消并断言清退，使退出判据可验证；③S6.3 明确 `UniversalAgent.__init__` 新增 `tool_names` 形参并写入 R5，runner 构造子 Agent 处透传 `config.tool_names`；④S6.4 补 T04 子池关闭断言、`shared_client` 改为显式传参校验；⑤对齐用例表／探针／红绿节奏／退出判据的编号与条数，并标注别名与两层成功在 429 限流下的锁定位；⑥订正对码行号（`delegateagent_runner.py:785` → 221-223）、插件目录配置语义（配置项即插件目录，缺省回落 `get_code_root()/plugins`）、清理探针内冗余 import；⑦T05 口径改为同步回归，把 tool_call 配对不破并入 T02 的历史条数断言，消除用例表与探针不符
- v2.24 2026-11-28 12:56:23 小欧 修正 S6 实施中发现的 manifest 隐式强转缺陷：`agent_config.load_from_manifest` 去掉 `int()/float()`，原值交 `__post_init__` 统一校验，非法 manifest 由外层跳过+warning（原 v2.15 与正文"保持不变、解析后仍走严格校验"的口径不成立：强转发生在校验前，会把 `true`/`"8"`/`8.5` 洗白成合法 int/float）；同步订正正文该说明，不改字段语义与默认值
- v2.25 2026-11-28 14:03:57 小欧 对 P0 逐项对码核查并在对应代码小节标注实施状态与偏差（已实施/未实施/偏差）；先核查 P0，附 P1/P2 对码结果；本次实测 S0+S1+S2 探针 118 passed，S3–S5 静态对码不重跑真实 LLM；偏差含 track_task 硬编码、DELEGATE_ALLOW_TOOLS 白名单、_find_unattended_blocker 跳过 visible_to_llm、allow_delegate 嵌套委托未打通、wait=false 返回体处理、§4.5 别名措辞等
- v2.26 2026-11-28 14:39:20 小欧 整改最重要差异：wait=false `status=running` 不再返回 error；`allow_delegate` 真正放行精确嵌套委托且深度≤2；`track_task=config.track_task` 透传；usage 合并 `_safe_int` + 非 dict no-op + 异步记账；只读白名单保留 fail-closed 且兼容 read 元数据；`provider/api_base` 不再依赖 model；新增可选 `api_key` 不入插件 manifest；`exclude/tool_names` 已注册名归一；更新对应代码节标注；实测 S0+S1+S2 118 passed、S6.2-S6.4 13 passed、`wait=false`/usage/allow 路径最小核验；未重跑真实 LLM 长链路


---

## 1 概述

### 1.1 目标

为 OmniAgent 引入**多 Agent 委托能力**：主 Agent 通过一个 tool（`delegateagent`）创建独立子 Agent，子 Agent 拥有独立上下文、独立工具子集、有界 ReAct 循环，完成后回传摘要和 token 用量。

### 1.2 设计约束

| 约束 | 说明 |
|------|------|
| **不引入框架** | 不引入 LangGraph、AutoGen 等外部编排框架 |
| **不引入 DAG** | 不做多 Agent 图编排，保持"一个 tool 调一个有界子循环"；仅当真实出现"条件分支+循环回边+并行汇聚"任务时，才加默认关闭的图模式开关（图只是配置数据，执行仍走 `run_react_cycle`） |
| **不引入消息总线** | 不另立独立消息总线；P0 同步 `await`，P1 异步复用现成的完成通知通道回灌，不新增总线设施 |
| **协程而非进程/线程** | 子 Agent 是同一事件循环上的协程 Task，靠 ContextVar 副本隔离上下文；不新建 OS 执行单元（见 §3.1） |
| **复用 UniversalAgent** | 子 Agent 实例化复用现有 `UniversalAgent`，不新增 Agent 子类 |
| **工具层零越层** | 子 Agent 创建/运行通过 ContextVar 回调注入，工具内不 import services |
| **递归防护 fail-closed** | 不靠"工具看不见"当唯一防线：委托深度 ContextVar 硬顶 + 子作用域内清空委托回调（即使工具被动态灌回也调不动） |
| **子 Agent 只读** | P0 子 Agent 不得持有需要人工确认/交互/写盘的工具：拒绝分类（AGENT/SYSTEM/MEDIA/WIN_REGISTRY/DESKTOP/TIMER）+ 拒绝名单（写/删/双路径/bash/交互工具）为主防线；构造后再按工具元数据 `needs_confirmation`/`confirm_fn` 校验（只覆盖声明了确认的工具，如 bash/execute_sql），命中即拒绝委托 |
| **并行有界** | 单轮最多 6 个并行子 Agent，上限校验 P0 就落在 `tool_runner.execute_tools`（唯一持有 `all_calls` 全量的一层）；常量 `MAX_PARALLEL_SUB_AGENTS` 须同批新增（§2.5.1） |
| **耗时有界** | 每个子 Agent 有墙钟超时（`AgentConfig.timeout_s`，默认 300s）与父任务取消联动，两者都由 §2.5 的守卫协程收口 |

### 1.3 适用场景

| 场景 | 子 Agent 工具子集 | 特点 |
|------|-------------------|------|
| 独立并行搜索 | NETWORK + FUNDAMENTAL | 不同关键词同时搜，各回传摘要 |
| 独立审查验证 | FUNDAMENTAL + FILE | 干净上下文审查代码/方案 |
| 工具专精 | 按需分配 | 限定工具域的专用 Agent |
| 插件/Skill | manifest 声明 | 可注册的 AgentConfig 包 |
| 知识库多域对照 | FILE + FUNDAMENTAL | 隔离上下文避免膨胀 |

### 1.4 设计决策

| 决策 | 理由 |
|------|------|
| 子 Agent 复用 `UniversalAgent` 而非新 Agent 子类 | KISS-DIRECT：现有类已支持 `initial_categories`，无需新抽象 |
| 不走 `agent_runner.run_agent_in_background` | 子 Agent 是同步子过程不是用户任务；完整 runner 的台账/取消/重连/统计属用户任务语义，套上去是类别错误 |
| 私有纯内存 buffer 而非改 runner 加开关 | 复用 `create_task_stream_buffer(..., journal_sink=None)` 现成纯内存模式；框架零改动、SSE/DB 天然隔离 |
| 上下文副本（`copy_context` + `create_task(context=)`） | `clear_temp_auth`、`set/reset_current_task_id`、工具侧各 ContextVar 回调都是 ContextVar 操作，副本天然隔离父子，优于手工保存恢复 |
| 递归防护 fail-closed（深度 + 清空回调）而非只看工具可见性 | `auto_inject_from_search` 会按 searchtool 结果把 AGENT 整类灌回（`_retry_engine._tools` 与 `_tools_dict` 同一 dict），"看不见"不是防线；只有"拿不到回调"才是 |
| 子 Agent 只读（拒绝分类 + 拒绝名单 + 元数据校验） | HITL 确认正文只走 interact 帧，子 Agent 的确认/问询落在私有 buffer，用户不可见；`wait_for_confirmation_result` 120s 后按拒处理。开写权限等于给用户一个静默超时的黑洞 |
| 守卫协程 `_run_child_guarded` 统一收口超时与取消 | 子 Agent 不注册 `running_tasks`，框架内 `is_cancel_requested(子task_id)` 恒 False；超时/取消只能由父侧轮询 + `Task.cancel` 实现，且必须先 cancel+await 再回收 buffer，否则 publish 撞已回收 buffer |
| `LLMClient.api_key` 补只读 property，并传 `shared_client` | 该类只有 `_api_key`（`client_sdk.py:441`），照"`agent.llm_client.api_key`"写必 AttributeError；传 `shared_client` 后子 client `_owns_client=False`，`close()` 为 no-op，连接池天然并发安全 |
| 并行子 Agent 不强绑独立 `llm_client` | 共享 client 时 `_current_response` 是单槽（`client_sdk.py:686/723`），并发会互相覆盖；故 P0 并行默认只共享连接池、不共享可变响应状态，且不承诺 per-call 结果隔离 |
| 删掉工具参数 `parallel` | 并行由框架判 `is_parallel = len(all_calls) > 1`（`action_input_parser.py:96`）；工具再声明一遍是双重真相，且 LLM 会拿它当开关乱用 |
| `output_format` 改为自由文本 `output_instruction` | 枚举值只会退化成 if/else 分支；自由文本直接拼进子 Agent 的 task 描述，扩展零成本 |
| `subagent` 不入 `TOOL_NAME_ALIASES` | 它在 `UNAVAILABLE_OFFICIAL_TOOLS` 内，且 `tuning.agent.disabled_tools` 可能按此名屏蔽；收进来会与"未注册即禁用"判定打架（P2 再处理） |
| `AgentConfig`/`AgentRegistry` 放 `backend/app/tools/agent/` | `agent_register.py`（tools 层）要读注册表生成描述；放 services 会形成"工具层 import services"的越层（`shell_background.set_notify_router` 是既有合规范式） |
| 工具描述由注册表动态生成（`description` 支持 callable） | OCP：新增 Agent 只注册配置，不改描述代码；描述文本永远与 `list_configs()` 同源，不会漂移 |
| 子 Agent `track_task=config.track_task`，`AgentConfig.track_task` 默认 `False` | 它不是用户任务：默认不该占 `tasks` 台账、不该被启动期超时扫描当僵尸任务、也不该让 `_finalize_cycle` 去写用户可见状态；仅显式 `track_task=True` 才建行。**门控已在 `BaseAgent.__init__` 实装** `if track_task:`，非 bool `TypeError`；插件 manifest 不能开启 `track_task` |
| 改造项一律"显式形参 + 启动期 fail-fast"，不接受 `**kwargs` 兜底 | `UniversalAgent`/`BaseAgent` 在 S0 前用 `**kwargs` 只接收不校验（S0 已删，见 §4.2 改造前提），`excluded_tools`/`track_task` 漏改时无任何报错：sub 拿到全量工具（只读承诺失效）、sub 建台账行（幽灵任务）。安全类承诺若走静默降级，测试不红、日志不报，只能靠线上发现 |
| P0 只做分类粒度工具集，名粒度 `tool_names` 精确放行白名单 | `ToolLoader.init_tools(tool_names=)` 在 `ToolRetryEngine` 构造前筛 + `to_openai_tools`/`tool_cache_manager` 可见性同源；`to_openai_tools(tool_names=)` 本身仍是“额外包含”，精确白名单用后过滤实现；名粒度不得扩大只读面 |
| 主名称定为 `delegateagent`，其它生态名走别名归一 | 名称唯一、零重复注册；复用 `TOOL_NAME_ALIASES`/`normalize_tool_name` 现成能力，注册表 `get_tool`/`resolve_registered_tool` 已内置归一调用，零改调用点 |
| `wait` 默认 True（P0 同步）/ False（P1 异步） | P0 先跑通同步直线路径；异步复用既有 inbox 通道回灌，不在父轮次结束后硬改 `conversation_history` |
| 子 Agent 前台阻塞 + 可并行，不做后台 fire-and-forget | "前台/后台"与"串行/并行"是两个独立维度：子 Agent 是父 `await` 的协程任务（前台），但同轮多个委托经 `asyncio.gather` 同时跑（并行）。后台化要求父循环有"挂起态"，而 `react_loop` 是无挂起态的同步 while 循环、`AgentStatus` 五态里也没有挂起态；且前台并行已拿到 `max(t_i)` 耗时，后台化收益为零 |
| 子 Agent 的价值是上下文隔离，不是"后台干活" | 父 `conversation_history` 只多一行摘要，子 Agent 的 reasoning 与工具原始输出全部留在子域（§3.2）。这是 `tuning.trim.keep_recent_rounds` 之外的第二道上下文防线：装不下的事在子域内消化，不挤占父的裁剪预算 |
| 模型线独立演进，scaffolding 不变 | 外层脚手架（`delegateagent` + 注册表 + prompt + fail-closed）是纯 scaffolding，天然兼容 agent RL 底座（Qwen3-Coder/GPT-5 等）；底座变强时脚手架顺势变薄，本设计零改动 |


---

## 2 核心设计

### 2.1 AgentConfig 数据类

> **【核查】实施状态：已实施（P0，S1 已落码；探针 probe_delegate_s1_config.py 本次实测 73/73，与 S0/S2 合计 118 passed）。偏差如下：**
> - 代码：`backend/app/tools/agent/agent_config.py`
> - 字段比设计多 `tool_names`、`allow_delegate`、`provider`、`api_base`、`api_key`；`tool_names` P1 已消费；`allow_delegate` 已真正放行精确嵌套委托且深度≤2；`provider`/`api_base` 不再依赖 `model`；`api_key` 可选且 `repr=False`、不进入 manifest 插件装载；`track_task` 透传。设计正文 `§5.1` 字段清单与之不符但行为已按本版核查。
> - `__post_init__` 比设计更严：`max_steps`/`timeout_s`/`track_task` 类型不符抛 `TypeError`、`tool_categories` 必须 `Set[ToolCategory]`、`tool_names` 必须集合、`allow_delegate` 必须 bool；`description` 要求 `str`；`agent_id` 全串 `fullmatch`；`system_prompt` 必须 `str`、`output_instruction/model/api_key` 必须字符串或 None；`provider/api_base` 字符串或 None。设计正文用 `int()/float()` 的口径已被代码否决。
> - `load_from_manifest` 比设计更严：去掉 `int()/float()` 强转，原值交 `__post_init__`；`description` 非字符串直接拒绝；`system_prompt` 非字符串回落空串；分类形状非法回落 `fundamental`；`tool_names` 形状非法回落空集；`track_task` 强制 `False`；读取 `provider`/`api_base`；不读取 `api_key`；不读取 `allow_delegate`。
> - `reset_agent_registry` 存在（设计 `reset`）；`register(..., replace=)`、`unregister`、`list_configs`、`list_available`、模块级 `get_agent_registry` 齐备；唯一构造点 `get_agent_registry`；不 import `app.services`。
> - `DELEGATE_DENY_CATEGORIES == {AGENT,SYSTEM,MEDIA,WIN_REGISTRY,DESKTOP,TIMER}`；`DELEGATE_DENY_TOOLS` 含 `WRITE_PATH_TOOLS∪DELETE_PATH_TOOLS∪DUAL_PATH_TOOLS∪{bash,question,schedule,delegateagent}`，与设计一致；`query_sql`/`read`/`find`/`searchweb` 不在拒绝名单（但另有运行器白名单收窄，见安全节）。

**文件位置**：`backend/app/tools/agent/agent_config.py`

> 分层说明：`AgentConfig`/`AgentRegistry` 只是"某个子 Agent 是什么能力"的声明，放 tools 层；运行器（services 层）向上 import 它。反过来放 services 层，会让 `agent_register.py`（tools 层）为生成工具描述而 import services，违反"工具层零越层"（§1.2）。

```python
# -*- coding: utf-8 -*-
"""
agent_config — Agent 配置数据类 + AgentRegistry

小欧 2026-11-27
"""
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.logger import logger
from app.tools.tool_constants import DELETE_PATH_TOOLS, DUAL_PATH_TOOLS, WRITE_PATH_TOOLS
from app.tools.tool_types import ToolCategory

# 子 Agent 禁止持有的工具分类:
#   AGENT       — 用户交互（question/schedule），子 Agent 没有前端出口，也不得自行提问
#   SYSTEM      — create_task/delete_task 会动任务台账，子 Agent 能删掉父任务行
#   MEDIA       — 生成即落盘并计费，属"写"+花钱，不该出现在只读子 Agent 里
#   WIN_REGISTRY/DESKTOP/TIMER — 宿主副作用，与"干净上下文只做分析"无关
DELEGATE_DENY_CATEGORIES: Set[ToolCategory] = {
    ToolCategory.AGENT, ToolCategory.SYSTEM, ToolCategory.MEDIA,
    ToolCategory.WIN_REGISTRY, ToolCategory.DESKTOP, ToolCategory.TIMER,
}

# 子 Agent 禁止持有的工具名: 直接复用算子层既有的写/删/双路径分类表(DRY), 再补 bash 与显式交互工具。
# 新增写类工具只要进 PATH_* 表, 这里自动生效, 不需要改本文件。
# 注意: PATH_* 已含 execute_sql/screen_capture/download/generate_chart, 故一并被拒。
DELEGATE_DENY_TOOLS: Set[str] = (
    set(WRITE_PATH_TOOLS) | set(DELETE_PATH_TOOLS) | set(DUAL_PATH_TOOLS)
    | {"bash", "question", "schedule", "delegateagent"}
)

# 全串匹配：不用 $ 锚点（会放过结尾换行），交给 fullmatch 判定
_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")


@dataclass
class AgentConfig:
    """子 Agent 配置 — 定义一个可委托的 Agent 实例的全部参数"""
    agent_id: str                          # 唯一标识，如 "researcher" / "reviewer" / "kb_analyst"
    description: str                       # 一句话说明（给 LLM 看，帮助主 Agent 选择委托目标）
    system_prompt: str = ""                # 子 Agent 的 system prompt（注入方式见 §2.5）
    tool_categories: Set[ToolCategory] = field(default_factory=lambda: {ToolCategory.FUNDAMENTAL})
    tool_names: Set[str] = field(default_factory=set)  # 精确放行白名单；空集=按分类+拒绝清单；不能扩大只读面
    allow_delegate: bool = False              # 精确多层委托：默认1层；True 放宽到≤2层，只放行 delegateagent
    provider: Optional[str] = None            # 跨 provider 子 client provider
    api_base: Optional[str] = None            # 跨 provider 子 client 端点
    output_instruction: Optional[str] = None  # 输出约束（自由文本；None=默认摘要要求，见 §2.5）
    model: Optional[str] = None            # 指定模型（None=继承父 Agent 的 LLM，见 §2.5）
    api_key: Optional[str] = None            # 跨 provider 可选凭据；repr=False；不进入 manifest 插件装载
    max_steps: int = 8                     # 子 Agent 最大 ReAct 步数（有界）
    timeout_s: float = 300.0               # 墙钟超时（秒），由 §2.5 守卫协程强制执行
    track_task: bool = False               # 是否在 tasks 台账建行（默认不建；仅显式配置才建）

    def __post_init__(self) -> None:
        """构造即校验 — 非法配置在注册/委托之前失败，不留到运行期"""
        if not isinstance(self.agent_id, str) or not _ID_RE.fullmatch(self.agent_id):
            raise ValueError(f"agent_id 非法: {self.agent_id!r}（要求小写字母开头，[a-z0-9_]）")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(f"agent_id={self.agent_id}: description 不能为空（LLM 靠它路由）")
        # 小欧 2026-11-28 - 可选字符串字段构造期收口，避免运行期字符串拼接/模型构造失败
        if not isinstance(self.system_prompt, str):
            raise TypeError(...)
        if self.output_instruction is not None and not isinstance(self.output_instruction, str):
            raise TypeError(...)
        if self.model is not None and not isinstance(self.model, str):
            raise TypeError(...)
        # 类型显式：bool 是 int 子类，必须单独排除；禁止 int()/float() 隐式强转
        if not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool):
            raise TypeError(...)
        if not 1 <= self.max_steps <= 30:
            raise ValueError(f"agent_id={self.agent_id}: max_steps={self.max_steps} 越界（1..30）")
        if not isinstance(self.timeout_s, (int, float)) or isinstance(self.timeout_s, bool):
            raise TypeError(...)
        if not 5 <= self.timeout_s <= 1800:
            raise ValueError(f"agent_id={self.agent_id}: timeout_s={self.timeout_s} 越界（5..1800）")
        if not isinstance(self.tool_categories, (set, frozenset)) or not all(isinstance(c, ToolCategory) for c in self.tool_categories):
            raise TypeError(...)
        if not self.tool_categories:
            raise ValueError(f"agent_id={self.agent_id}: tool_categories 不能为空")
        self.tool_categories = set(self.tool_categories)   # 拷贝成独立集合，防调用方共享可变对象
        if not isinstance(self.tool_names, (set, frozenset)) or not all(isinstance(n, str) for n in self.tool_names):
            raise TypeError(...)
        self.tool_names = set(self.tool_names)
        if not isinstance(self.allow_delegate, bool):
            raise TypeError(...)
        if self.provider is not None and not isinstance(self.provider, str):
            raise TypeError(...)
        if self.api_base is not None and not isinstance(self.api_base, str):
            raise TypeError(...)
        if self.api_key is not None and not isinstance(self.api_key, str):
            raise TypeError(...)
        if not isinstance(self.track_task, bool):
            raise TypeError(...)

    def effective_categories(self) -> Set[ToolCategory]:
        """实际生效的分类 — 拒绝分类在配置层先扣一遍（运行期还有工具元数据校验兜底）"""
        return set(self.tool_categories) - DELEGATE_DENY_CATEGORIES


class AgentRegistry:
    """AgentConfig 注册表 — 管理所有可委托的子 Agent 配置"""

    def __init__(self):
        self._configs: Dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig, *, replace: bool = False) -> None:
        """注册一个 AgentConfig — 重名默认报错（插件覆盖同名 Agent 必须显式 replace=True）"""
        if config.agent_id in self._configs and not replace:
            raise ValueError(f"agent_id 已存在: {config.agent_id}（覆盖需 replace=True）")
        self._configs[config.agent_id] = config

    def unregister(self, agent_id: str) -> bool:
        """注销一个 Agent — 插件卸载/热重载用；不存在的 id 返回 False"""
        return self._configs.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> Optional[AgentConfig]:
        """按 agent_id 获取配置"""
        return self._configs.get(agent_id)

    def list_configs(self) -> List[AgentConfig]:
        """列出全部配置 — 供工具描述动态生成（§4.1），新增 Agent 不需要改描述代码"""
        return list(self._configs.values())

    def list_available(self) -> List[str]:
        """列出所有可用 agent_id（供 LLM 看）"""
        return list(self._configs.keys())

    def load_from_manifest(self, path: str) -> Optional[AgentConfig]:
        """从插件 manifest.json 加载 AgentConfig（见 §2.1.1）— 任何不合法都返回 None 并 warning，不抛"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[AgentRegistry] 读取 manifest 失败({path}): {e}")
            return None

        categories: Set[ToolCategory] = set()
        for name in data.get("tool_categories", ["fundamental"]):
            try:
                categories.add(ToolCategory(str(name)))
            except ValueError:
                logger.warning(f"[AgentRegistry] 未知工具分类 {name!r}，跳过")
        try:
            config = AgentConfig(
                agent_id=str(data["name"]),
                description=str(data.get("description", "")),
                system_prompt=str(data.get("system_prompt", "")),
                tool_categories=categories or {ToolCategory.FUNDAMENTAL},
                output_instruction=data.get("output_instruction"),
                model=data.get("model"),
                max_steps=int(data.get("max_steps", 8)),
                timeout_s=float(data.get("timeout_s", 300)),
                track_task=False,
            )
        except Exception as e:     # 缺 name / 类型错 / __post_init__ 校验不过 → 跳过该插件
            logger.warning(f"[AgentRegistry] manifest 不合法已跳过({path}): {e}")
            return None
        try:
            self.register(config)
        except ValueError as e:
            logger.warning(f"[AgentRegistry] 与已有 Agent 冲突已跳过({path}): {e}")
            return None
        return config


# 全局单例（P0 单例；测试用 reset_agent_registry 复位，避免 E2E 用例之间串态）
_agent_registry: Optional[AgentRegistry] = None

def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
        _register_builtin_agents(_agent_registry)
    return _agent_registry

def reset_agent_registry() -> None:
    """丢弃单例（连同已加载插件配置）— 仅供测试与插件热重载使用"""
    global _agent_registry
    _agent_registry = None


def _register_builtin_agents(registry: AgentRegistry) -> None:
    """内置 Agent 注册（P0 阶段 3 个内置子 Agent）"""
    registry.register(AgentConfig(
        agent_id="researcher",
        description="独立搜索研究员：用网络搜索工具多路并行搜索，回传结构化摘要",
        tool_categories={ToolCategory.NETWORK, ToolCategory.FUNDAMENTAL},
        max_steps=10,
        timeout_s=240,
    ))
    registry.register(AgentConfig(
        agent_id="reviewer",
        description="独立审查员：用文件读取+搜索工具在干净上下文中审查代码/方案，回传结论",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        output_instruction="按「结论 / 依据 / 风险 / 建议」四段输出，逐条列明出处（文件:行号）",
        max_steps=12,
        timeout_s=300,
    ))
    registry.register(AgentConfig(
        agent_id="kb_analyst",
        description="知识库分析师：检索知识库做多域对照分析，回传结论摘要",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        max_steps=10,
        timeout_s=240,
    ))
```

#### 2.1.1 插件/Skill Manifest 格式

> **【核查】实施状态：已实施，但属 P1 而非 P0（S6.2 落码）。**
> - 代码：`backend/app/tools/agent/plugin_loader.py`、`agent_register._register_agent_tools()` 调 `load_plugins()`；`agent_config.AgentRegistry.load_from_manifest`。
> - `load_plugins()` 扫 `tuning.agent.plugins_dir`（缺省 `get_code_root()/plugins`）下 `*/manifest.json`，`sorted`，目录不存在/空静默跳过；逐 manifest 调 `load_from_manifest`；单个非法仅 warning；重名跳过。
> - `config/config.yaml` 是否含 `tuning.agent.plugins_dir` 键：本次未核验该键落点（代码有 `get_config().get(...,"")` 缺省回落，不依赖键存在）。
> - 与设计差异：设计扫描器注释说 `track_task` 不允许指定（恒 False，代码一致）；`tool_names` 读入并消费（设计 §2.1.1 表说 P0 读入不消费、P1 精确放行，代码已 P1 消费）。

##### 目录结构

```
plugins/
├── web-researcher/
│   ├── manifest.json
│   └── (可选) prompt.md    # system_prompt 全文（比 manifest 内联更长时放这里）
├── code-reviewer/
│   ├── manifest.json
└── kb-analyst/
    └── manifest.json
```

##### manifest.json 字段

```json
{
  "name": "web-researcher",
  "description": "多源并行网络搜索，回传结构化摘要",
  "system_prompt": "你是一个专业的网络研究员，擅长多源信息搜索与交叉验证...",
  "tool_categories": ["network", "fundamental"],
  "tool_names": null,
  "model": null,
  "max_steps": 12,
  "timeout_s": 300,
  "output_instruction": "按「结论 / 证据 / 存疑」三段输出，不要罗列原始网页"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | agent_id，全局唯一，须匹配 `^[a-z][a-z0-9_]{0,31}$` |
| `description` | 是 | 一句话（给 LLM 路由用，进工具描述，见 §4.1） |
| `system_prompt` | 否 | 子 Agent 的 system prompt（空则用默认） |
| `tool_categories` | 否 | 工具分类列表（默认 `["fundamental"]`；拒绝分类会被 `effective_categories()` 扣掉） |
| `tool_names` | 否 | P1 工具名粒度（null=用分类，P0 读入但不消费，留给 P1 精确放行） |
| `model` | 否 | 指定模型（null=继承父 Agent 的 LLM；非 null 时新建独立 client） |
| `max_steps` | 否 | 最大步数（默认 8，上限 30） |
| `timeout_s` | 否 | 墙钟超时秒数（默认 300，5..1800） |
| `output_instruction` | 否 | 输出约束自由文本（缺省时用内置摘要要求，见 §2.5） |

> 字段集与 `AgentConfig` 一一对应，`load_from_manifest` 只读上面这些键；`track_task` 不允许由插件指定（恒 False），插件也不能给自己开写权限（由 `DELEGATE_DENY_*` 决定）或再委托权限（由 `MAX_DELEGATE_DEPTH` 硬顶决定）。

##### 加载时机

扫描与注册在 `_register_agent_tools()` 内完成，即 `ensure_tools_registered()` 遍历 `CATEGORY_MODULES` 时同步发生：先 `plugin_loader.load_plugins()` 注册插件 Agent，再注册 `delegateagent` 工具本身。顺序要求只有一个——**必须早于任何 Agent 实例构建工具列表**（`to_openai_tools`），否则插件 Agent 不会出现在工具描述里。

目录来源：`Config.get("tuning.agent.plugins_dir", default)`，默认 `get_code_root()/plugins`（`config.get_code_root()` 返回代码库根）。目录不存在或为空则静默跳过，不报错。

容错：`load_from_manifest` 对未知 `tool_categories` 值逐项 warning 跳过并回落 `["fundamental"]`，`AgentConfig.__post_init__` 的校验异常由扫描器捕获；JSON 格式错/字段缺失/重名冲突一律仅 warning 跳过该目录，不阻塞启动。重名需覆盖时插件侧无法自助，只能由内置注册显式 `replace=True`。

**扫描器实现**（新增 `backend/app/tools/agent/plugin_loader.py`，~30 行）：

```python
# -*- coding: utf-8 -*-
"""
plugin_loader — plugins/ 目录扫描 + manifest 容错加载
小欧 2026-11-27
"""
from pathlib import Path
from typing import List

from app.config import get_code_root, get_config
from app.logger import logger
from app.tools.agent.agent_config import get_agent_registry


def load_plugins() -> List[str]:
    """扫描 plugins_dir 下所有 manifest.json，逐个加载注册；返回成功加载的 agent_id 列表

    容错：目录不存在/为空静默跳过；单个 manifest 非法由 load_from_manifest 内部 warning 跳过，
    不阻塞启动；重名冲突由注册表 register 抛 ValueError 后 load_from_manifest 跳过。
    """
    configured = get_config().get("tuning.agent.plugins_dir", "")
    root = Path(configured) if configured else Path(get_code_root()) / "plugins"
    if not root.is_dir():
        return []
    registry = get_agent_registry()
    loaded: List[str] = []
    for manifest in sorted(root.glob("*/manifest.json")):
        cfg = registry.load_from_manifest(str(manifest))
        if cfg is not None:
            loaded.append(cfg.agent_id)
            logger.info(f"[plugin_loader] 已加载插件 Agent: {cfg.agent_id} ({manifest})")
    return loaded
```

**调用点**（`agent_register.py` 的 `_register_agent_tools()` 内，注册 `delegateagent` 之前）：

```python
from app.tools.agent.plugin_loader import load_plugins
load_plugins()   # 必须在构建工具列表之前，插件 Agent 才能进 callable 描述
```

### 2.2 delegateagent 工具 Schema

> **【核查】实施状态：已实施（P0，S2 已落码）。**
> - 代码：`backend/app/tools/agent/delegateagent_schema.py`。
> - `DelegateAgentInput`：`agent_id`/`task` 必填；`task` `min_length=1,max_length=500`；`context: Optional[Dict]`；`wait` 默认 `True`；无 `parallel`。
> - `wait=False` 在 schema 注释标 P1；实际 `delegateagent` 透传、`run_delegate` 已 P1 异步；`status=running` 现作为成功启动返回 `delegate_id`，完成走 inbox。

**文件位置**：`backend/app/tools/agent/delegateagent_schema.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent_schema — delegateagent 工具参数模型
小欧 2026-11-27
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DelegateAgentInput(BaseModel):
    """delegateagent 工具入参 — LLM 侧看到的参数结构"""
    agent_id: str = Field(
        ...,
        description="目标子Agent ID（取值见工具描述里动态列出的可用列表）"
    )
    task: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="委托给子Agent的任务描述（自包含，含必要背景，≤500字）"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="附加上下文（文件路径/数据片段/约束条件等，按需传入）"
    )
    wait: bool = Field(
        True,
        description="是否同步等待结果（True=本轮直接返回摘要+用量，P0 已实现；False=立即返回 delegate_id，后台跑完自动回灌，P1）"
    )
```

**设计说明**：

- `agent_id`：取值由 `AgentRegistry.list_available()` 决定，工具描述在每次构建工具列表时从注册表动态生成（§4.1），新增 Agent 不改代码也不改描述字面量。
- `task`：自包含任务描述。子 Agent **不继承父 Agent 的完整对话历史**，只接收这里传入的任务描述 + context。这是上下文隔离的核心。
- `context`：可选结构化附加信息（如文件路径、代码片段、约束条件）。
- **没有 `parallel` 参数**：并行与否由框架决定，不由工具声明——`action_input_parser` 以 `is_parallel = len(all_calls) > 1` 定并行（`tool_runner.execute_tools` 的 B'/C 分支），
  单个工具参数既改变不了分组，还会诱导 LLM 传一个无效开关。要并行就"同一轮发多个 `delegateagent` 调用"，上限由 `tool_runner` 校验（§2.5）。
- `wait`：同步/异步开关（默认 True）。
  - `True`（**P0 已实现**）：同步 `await` 子 Agent，本轮 observation 直接带摘要 + usage，父 Agent 继续 ReAct——即 §2.5 的同步委托路径。
  - `False`（**P1**）：`create_task` 后立即返回 `delegate_id` + `status=running`，子 Agent 跑完后经**既有 inbox 通道**回灌父任务（`inject_system_notice` → 父 Agent 下一轮 LLM 调用前 `drain_inbox` 并入对话历史，见 §3.3），父不轮询。结果携带 `delegate_id` 以区分并发的多个异步委托；父任务取消时未完成的后台委托一并终止。

### 2.3 delegateagent 工具实现

> **【核查】实施状态：已实施（P0 同步），与设计有细节偏差。**
> - 代码：`backend/app/tools/agent/delegateagent.py`。
> - 工具层零越层（不 import services）；取 `get_current_delegate_callback()`；未注入返回 `build_error`；回调异常收口为 `build_error`；不外抛。
> - 成功返回 `data={agent_id,summary,usage,steps}`、`other_data.duration_ms`；失败也带 `data.usage`/`steps`。
> - 细节：① 额外 `if not isinstance(result, dict): raise TypeError`→error；② `_summary = result.get("summary") or ""`；`detail=result.get("summary") or "未知原因"`；③ 已整改 `status=="running"` 成功分支返回 `delegate_id`，不再返回 error；④ 回调非 `async` 函数会 `await` 失败被收口，契约要求 async。

**文件位置**：`backend/app/tools/agent/delegateagent.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent — 子Agent委托工具实现
小欧 2026-11-27

核心逻辑：
  1. 从 ContextVar 取 delegate_callback（入口层注入）
  2. 调 callback(agent_id, task, context, wait)
  3. callback 内部：查 AgentRegistry → 创建子 Agent → 跑 ReAct → 回传摘要 + usage（P0 同步 / P1 异步）
  4. 工具层零越层：不 import services/agent，只消费 ContextVar 回调
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_delegate_callback
from app.tools.tool_response import build_error, build_success


async def delegateagent(
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    wait: bool = True,
) -> Dict[str, Any]:
    """委托子 Agent 执行任务 — 工具入口"""
    start = time.time()

    # 取回调（tool_executor 入口层注入）
    callback = get_current_delegate_callback()
    if callback is None:
        return build_error(llm_data={
            "summary": "delegateagent，失败：委托通道未注入",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": "无可用 delegate_callback",
                       "hint": "请确认当前运行环境支持多 Agent 委托"},
        })

    try:
        result = await callback(agent_id=agent_id, task=task, context=context, wait=wait)
    except Exception as e:
        return build_error(llm_data={
            "summary": f"delegateagent，失败：子 Agent 执行异常 {e}",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": f"子 Agent 内部错误: {e}",
                       "hint": "可换其他 agent_id 重试或自行处理"},
        })

    duration_ms = int((time.time() - start) * 1000)

    # result 结构由 callback 保证: {"summary", "usage", "status", "steps"}，llm_data 统一走项目契约
    status = result.get("status", "failed")
    if status == "success":
        _summary = result.get("summary", "")
        return build_success(
            data={
                "agent_id": agent_id,
                "summary": _summary,
                "usage": result.get("usage", {}),
                "steps": result.get("steps", 0),
            },
            llm_data={
                "summary": f"委托子Agent({agent_id})完成: {_summary[:120]}",
                "action": {"tool": "delegateagent", "tool_zh": "委托子Agent",
                           "params": {"agent_id": agent_id}},
                "status": {"exec_code": "success", "message": "成功"},
            },
            other_data={"duration_ms": duration_ms},
        )
    else:
        # 失败也带上 usage：子 Agent 可能已烧掉几步 token，父侧仍要记账
        return build_error(
            data={
                "agent_id": agent_id,
                "usage": result.get("usage", {}),
                "steps": result.get("steps", 0),
            },
            llm_data={
                "summary": f"delegateagent，失败：子Agent({agent_id})执行未成功",
                "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
                "status": {"exec_code": "error", "message": "失败",
                           "detail": result.get("summary", "未知原因"),
                           "hint": "可检查任务描述是否清晰后重试，或自行处理"},
            },
            other_data={"duration_ms": duration_ms},
        )
```

### 2.4 注入机制（ContextVar 定义 + 入口层注入）

#### 2.4.1 ContextVar 定义（工具层零越层）

> **【核查】实施状态：已实施（P0）。**
> - 代码：`backend/app/tools/context.py`。
> - `_current_delegate_callback`（签名 `async (agent_id, task, context, wait)->Dict`，默认 None）+ `get/set/reset_current_delegate_callback`（token 模式）；`_current_delegate_depth`（默认 0）+ `get_delegate_depth()`；深度 set/reset 直接操作 ContextVar，**无 `set_delegate_depth`/`reset_delegate_depth` 包装**（与设计一致）。
> - ContextVar 而非模块全局，6 路并发各算各的（S2 T05–T08 实测）。

**文件位置**：`backend/app/tools/context.py`（扩展）

```python
# 2026-11-27 小欧 - 新增 _current_delegate_callback ContextVar
# 签名: async (agent_id, task, context, wait) -> Dict
# 入口层(tool_executor)持 agent + AgentRegistry 注入; 工具层零越层, 未注入返回 None 自行降级
_current_delegate_callback: ContextVar[Optional[object]] = ContextVar(
    "current_delegate_callback", default=None
)

# 委托深度: 主 Agent 作用域为 0, 子 Agent 内部为 1。深度用 ContextVar 而非模块全局,
# 才能在并发委托时各算各的(模块全局会被 6 路并发互相污染)。
_current_delegate_depth: ContextVar[int] = ContextVar("current_delegate_depth", default=0)

def get_current_delegate_callback():
    return _current_delegate_callback.get()

def set_current_delegate_callback(callback):
    """返回 token 供 reset 恢复上一作用域值（与 hooks/notice/question 同模式）"""
    return _current_delegate_callback.set(callback)

def reset_current_delegate_callback(token) -> None:
    _current_delegate_callback.reset(token)

def get_delegate_depth() -> int:
    return _current_delegate_depth.get()
```

> 为什么要有深度变量：递归防护如果只靠"子 Agent 工具集里没有 AGENT 分类"，会被 `auto_inject_from_search` 绕过——searchtool 命中后按结果里的 category 调 `load_category`，而 `ToolRetryEngine` 持有的是同一个 `_tools_dict` 对象引用，动态灌回即意味着可执行（§2.7）。深度是**不看工具可见性**的硬约束。

#### 2.4.2 入口层注入（tool_executor 扩展）

> **【核查】实施状态：已实施（P0）。**
> - 代码：`backend/app/services/agent/tool_executor.py::execute_tool`。
> - `set_current_delegate_callback` 在 `_session_token = set_current_session_id(...)` 之后、`try` 之前；**按 `normalize_tool_name(tool_name)=="delegateagent"` 归一名判据**（直调别名不漏注入）；`_delegate_token` 非 None 守卫 `reset_current_delegate_callback`；`run_delegate` 惰性 import；嵌进同一个 `try/finally`；usage 合并在 `return result` 之前（见 usage 合并节）。
> - `auto_inject_from_search` 仅 `if tool_name == "searchtool"`（裸名，`searchtool` 无别名，不影响委托只读防线，因 `load_category` 同源过滤）。

**文件位置**：`backend/app/services/agent/tool_executor.py`（扩展 `execute_tool` 的 ContextVar 注入段）

在 `execute_tool` 函数中，与现有的 hooks/text_task/notice/question/generate/precheck/session_id 注入同层，新增。现有结构是"注入段 → `try:` 执行 → `finally:` 逐个 reset → 末尾 `return result`"，delegate 回调必须**嵌进同一个 try/finally**，不能另起一个（否则子 Agent 跑完回调未 reset，会泄漏到后续工具）：

```python
# import 段补（与现有 set_current_* 同一 import 块）：
#   set_current_delegate_callback, reset_current_delegate_callback
# 另需 normalize_tool_name：判据用归一名，直调别名也不漏注入 — 小欧 2026-11-28

# execute_tool 内，在 _session_token = set_current_session_id(...) 之后、try 之前：
_delegate_token = None
if normalize_tool_name(tool_name) == "delegateagent":
    from app.services.agent.delegateagent_runner import run_delegate
    async def _delegate_cb(**kwargs):
        return await run_delegate(agent=agent, **kwargs)
    _delegate_token = set_current_delegate_callback(_delegate_cb)

# 现有 finally 段（reset_current_session_id 之后）补：
if _delegate_token is not None:
    reset_current_delegate_callback(_delegate_token)

# 现有 return result 之前补 usage 合并（完整实现见 usage 合并段落）：
if normalize_tool_name(tool_name) == "delegateagent":
    ...  # 完整实现见 usage 合并段落
```

> 为什么用 `_delegate_token is not None` 守卫而不是无条件 reset：非 delegate 工具从未 set，token 为 None，`ContextVar.reset(None)` 会抛 `ValueError`。这与现有 `_text_token`/`_notice_token` 的守卫写法同源（`tool_executor.py:176-183`）。

> 为什么在 `if normalize_tool_name(tool_name) == "delegateagent"` 内才注入：其它工具不消费 delegate 回调，无条件注入等于每个工具调用都多一次 set/reset，且 `run_delegate` 的 import 会提前触发模块加载。按需注入符合 KISS-DIRECT 的"默认零开销"；用归一名而非裸名判据，是为了直调别名时也不漏注入。

### 2.5 子 Agent 运行器（核心）

> **【核查】实施状态：P0 同步核心已实施；与设计有偏差，且 P1 `wait=False` 已部分落码。**
> - 代码：`backend/app/services/agent/delegateagent_runner.py`。
> - 已实施（P0）：复用同一 `react_loop.run_react_cycle`（零重写）；`_delegate_scope` 私有纯内存 buffer（`journal_sink=None`/无 `persist_sink`）+ `contextvars.copy_context()`；`_run_child_guarded` 守卫协程（墙钟 `timeout_s` + 父 `is_cancel_requested` 轮询 `_POLL_S=1.0` + `task.cancel()` + `_CANCEL_GRACE_S=5.0` 有界等待 + 先收子任务再回收 buffer）；`_find_unattended_blocker`；`_close_quietly`；`_extract_summary`（`FinalStep.response`→`error_message`→`reasoning`→末步 `get_content()`）；`_build_sub_task`；深度硬顶；`track_task` 不落台账；model 分支。
> - 已整改 `track_task`：`track_task=config.track_task` 透传；`AgentConfig.track_task` 默认 `False`、插件强制 `False`、`BaseAgent` 非 bool `TypeError`；P0 默认子 Agent 不落台账；仅显式配置才建行。
> - 已整改只读白名单：保留 fail-closed；`_excluded = DELEGATE_DENY_TOOLS ∪ (已注册全集 - 只读放行集)`；显式 `DELEGATE_ALLOW_TOOLS` + `meta.action_kind=="read"` 均可放行；拒绝分类/拒绝名单/需人工确认/未注册/不可见仍拒；精确 `allow_delegate` 只额外放行 `delegateagent`，不放行 `question/schedule`。实测当前注册 68 工具、默认子 Agent 可用 20 个只读工具。
> - `_find_unattended_blocker`：额外 `if not meta.visible_to_llm: continue`；`meta is None→拦截`；`allow_delegate=True` 时 `delegateagent` 例外；AGENT 下其它工具仍拒。
> - `_parent_http_client`（取 `client`→`ensure_client_pool()`→`_shared_client`）；生产父 `BaseAIService`；`_close_quietly`；构造失败 `_close_quietly`；`shared_client=agent.llm_client.client` 口径已收敛为父池获取。
> - `_build_sub_task` 额外**键名截断 100**（`_k[:100]`）。
> - `wait=false`：`wait=False` 走后台 `_execute_delegate` + `_background_delegates`，完成 `inject_system_notice` → inbox；`delegateagent` `status=running` 成功分支返回 `delegate_id`；异步完成 usage 经 `_merge_delegate_usage` 合并；inbox notice 不依赖记账成功。

> 注入只发生在主 Agent 的每次工具调用期间；子 Agent 作用域内先 `set_current_delegate_callback(None)`；默认子 Agent 不含 `delegateagent`。精确 `allow_delegate=True` 时只放行 `delegateagent`，子 Agent 实际调用时入口层重新注入，仍受深度硬顶≤2。非精确放行的 `delegateagent` 若被 searchtool 动态灌回，仍被 `_excluded` + `_find_unattended_blocker` 拒绝。

**引擎复用（关键架构决策）**：子 Agent **不另写 ReAct 循环**，调用的是主 Agent 同一个引擎——`sub_agent.run_react_cycle(...)` 继承自 `BaseAgent`，内部只做一层薄转发（`base_agent.py:133-138`：`return await _run(self, ...)`，`_run` 即 `react_loop.run_react_cycle`）。父子跑的是同一个函数，子 Agent 自动获得 LLM 调用与重试、安全门/沙箱/HITL、`execute_tools` 三分支、observation 回灌、StepEmitter、终态判定与全局清理等全套机制。

父子差异全在**配置与注入**，不在循环本身：`initial_categories`（工具子集）、`max_steps`（步数）、实例覆盖 `_get_system_prompt`（角色）、`_delegate_scope`（私有事件总线 + 上下文副本）、`_build_sub_task`（自包含任务描述）。即"同一个引擎，换配置、换上下文、换总线"，不是另写一台发动机。

**文件位置**：`backend/app/services/agent/delegateagent_runner.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent_runner — 子 Agent 创建与运行
小欧 2026-11-27

职责：
  1. 查 AgentRegistry 获取 AgentConfig
  2. 创建子 UniversalAgent（独立 task_id、工具子集）
  3. 组装子 Agent 的 task 描述（父传入的 task + context + 输出格式约束）
  4. 在私有事件总线 + 克隆上下文中跑有界 run_react_cycle
  5. 从 FinalStep.response 提取结果 + accumulated_usage，组装返回值

事件总线（关键设计）：
  run_react_cycle 入口强制 get_stream_buffer(task_id) 非空，否则抛 RuntimeError。
  子 Agent 在 delegate_scope 内用 create_task_stream_buffer(sub_task_id, "") 领一张
  纯内存通行证（无 journal_sink / persist_sink）：不进父 SSE、不落 chat_task_steps。
  上下文副本使 clear_temp_auth(以及 task_id 等 set/reset 类操作)只作用于子作用域，父零污染。
  不用走 run_agent_in_background：那是用户任务语义（台账/取消/重连/统计），
  子过程是同步计算，套完整 runner 属类别错误。

递归防护（fail-closed，三层）：
  1. 配置层：子 Agent 分类先扣拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用），看不到 delegateagent
  2. 运行层：子作用域内 set_current_delegate_callback(None) → 工具即使被动态灌回也拿不到回调
  3. 深度层：_current_delegate_depth 硬顶（P0 上限 1 层），run_delegate 入口校验
  注：第 1 层单独不够 —— auto_inject_from_search 会按 searchtool 结果 load_category 把 AGENT
  整类灌回子 Agent，而 ToolRetryEngine 持有同一个 _tools_dict 引用（§2.7）。
"""
import asyncio
import contextvars
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from app.logger import logger
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_state import (
    create_task_stream_buffer,
    is_cancel_requested,
    reclaim_memory_buffer,
)
from app.tools.agent.agent_config import DELEGATE_DENY_TOOLS, AgentConfig, get_agent_registry
from app.tools.context import (
    _current_delegate_depth,
    reset_current_delegate_callback,
    set_current_delegate_callback,
)
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

MAX_DELEGATE_DEPTH = 1        # P0 只允许 1 层委托；P1 引入 allow_delegate 字段时改配置驱动
_POLL_S = 1.0                 # 取消/超时轮询步长（异步等待，不阻塞事件循环）
_CANCEL_GRACE_S = 5.0         # 取消后等待子任务真正退出的上限；超时即放弃等待并留错误日志


@asynccontextmanager
async def _delegate_scope(sub_task_id: str):
    """私有事件总线 + 克隆上下文：子 Agent 的框架准入与全局状态隔离收口于此

    约束：返回的 ctx 只能交给一个 asyncio.create_task 使用 —— 同一个 Context 不能被两个
    任务同时进入（否则 RuntimeError: cannot enter context）。
    """
    create_task_stream_buffer(sub_task_id, "")   # journal_sink=None → 纯内存，无 SSE/DB sink；session_id 空串仅占位(不落库故无意义) — 小欧 2026-11-27
    ctx = contextvars.copy_context()
    try:
        yield ctx
    finally:
        # 走到这里时子任务必须已结束（成功/异常/取消都在 _run_child_guarded 收口），
        # 否则回收后子任务仍会往空 buffer 写 → publish/ask_question 抛 RuntimeError。
        reclaim_memory_buffer(sub_task_id)


async def _run_child_guarded(sub_agent, sub_task: str, max_steps: int, scope_ctx,
                              *, parent_task_id: str, timeout_s: float) -> None:
    """在子作用域内跑子 Agent：递归 fail-closed + 墙钟超时 + 父取消联动，收口在一处

    为什么不用 `await asyncio.create_task(...)` 直等：父任务被取消时，等的一方抛
    CancelledError 但**不会**取消被等的任务，子任务会继续跑；而 _delegate_scope 的
    finally 已经回收了 buffer → 子任务下一次 publish/ask_question 直接 RuntimeError。
    所以必须显式持有句柄：取消 → cancel() → 有界等待它真的结束 → 才允许回收
    （宽限期 `_CANCEL_GRACE_S` 内未退出则放弃等待并留错误日志，见 finally）。
    """
    async def _child():
        # 运行层 fail-closed：子作用域内清空委托回调。即使 searchtool 把 AGENT 分类
        # 动态灌回子 Agent、或将来配置泄漏，delegateagent 工具也只会拿到 None 而立即失败。
        _cb_token = set_current_delegate_callback(None)
        _d_token = _current_delegate_depth.set(_current_delegate_depth.get() + 1)
        try:
            await sub_agent.run_react_cycle(task=sub_task, max_steps=max_steps)
        finally:
            _current_delegate_depth.reset(_d_token)
            reset_current_delegate_callback(_cb_token)

    task = asyncio.create_task(_child(), context=scope_ctx, name=f"delegate:{sub_agent.task_id}")
    deadline = time.monotonic() + float(timeout_s)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=_POLL_S)
            if task in done:
                task.result()                    # 子 Agent 的异常原样抛出（含 CancelledError）
                return
            if is_cancel_requested(parent_task_id):
                raise asyncio.CancelledError(f"父任务 {parent_task_id} 已取消，终止子Agent")
            if time.monotonic() >= deadline:
                raise asyncio.TimeoutError(f"子Agent超时({timeout_s}s)已强制终止")
    finally:
        if not task.done():
            task.cancel()
            # 有界等待：cancel() 只是"请求取消"，子任务若正卡在同步工具里，取消要等工具返回才生效。
            # 无界 await 会把父任务的超时/取消一起拖长（违背"耗时有界"），故设二次上限。
            _done, _ = await asyncio.wait({task}, timeout=_CANCEL_GRACE_S)
            if task not in _done:
                # 放弃等待：buffer 会被上层回收，子任务后续 publish 会抛 RuntimeError 并被任务自身吞进
                # "Task exception was never retrieved" 日志。这是"宁可留日志也不挂死父任务"的取舍。
                logger.error(
                    f"[delegateagent_runner] 子Agent {sub_agent.task_id} 取消后 {_CANCEL_GRACE_S}s 仍未退出，"
                    f"放弃等待（其后续输出将因 buffer 已回收而报错）"
                )


def _find_unattended_blocker(sub_agent) -> Optional[str]:
    """剩余工具里出现"需人工确认/交互"者即返回其名 — 子 Agent 没有前端出口，宁可拒绝委托

    覆盖面（别高估）：AGENT 分类工具 + 靠 confirm_fn 声明确认的工具（现为 bash、execute_sql，
    分别见 fundamental_register.py:144 / dataanalysis_register.py:178）；全仓 needs_confirmation=True 零命中，
    故 needs_confirmation 分支实际不触发。FILE 写类工具不声明确认——
    delete 的确认由 check_delete_permission(R3-R6) 在执行期产出（file_register.py:246 CONFIRMATION_MAP 为空），
    所以 write/delete/move 这类只能靠 DELEGATE_DENY_TOOLS 拦，本函数兜不住。
    这也正是拒绝清单必须真落地的原因：一旦 excluded_tools 被静默吞掉，delete 会漏进子 Agent，
    然后在不可见的 HITL 上空转 120s 后拿到"拒绝"。
    """
    for name in list(sub_agent._tools_dict.keys()):
        meta = tool_registry.get_tool(name)
        if meta is None:
            return f"{name}(未注册)"
        if meta.category is ToolCategory.AGENT or meta.needs_confirmation or meta.confirm_fn is not None:
            return name
    return None


async def _close_quietly(client) -> None:
    if client is None:
        return
    try:
        await client.close()
    except Exception as e:
        logger.warning(f"[delegateagent_runner] 关闭子 client 失败: {e}")


def _usage_of(sub_agent) -> Dict[str, int]:
    return dict(getattr(sub_agent, "accumulated_usage", {}) or {})


async def run_delegate(
    agent,              # 父 Agent 实例（提供 llm_client / task_id）
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    wait: bool = True,  # P0 恒 True 同步；P1 False 走后台任务 + inbox 回灌（§3.3）
) -> Dict[str, Any]:
    """执行一次子 Agent 委托"""
    from app.services.agent.status_table import AgentStatus

    # 深度硬顶：不看工具可见性，只看当前调用栈深度（P0 上限 1 层）
    depth = _current_delegate_depth.get()
    if depth >= MAX_DELEGATE_DEPTH:
        return {"status": "error",
                "summary": f"委托深度超限(当前 {depth}，上限 {MAX_DELEGATE_DEPTH})，子Agent不可再委托"}

    registry = get_agent_registry()
    config = registry.get(agent_id)
    if config is None:
        available = registry.list_available()
        return {
            "status": "error",
            "summary": f"未知 agent_id '{agent_id}'，可用: {available}",
        }

    # 父任务已取消 → 不启动子 Agent（运行中的子 Agent 由 _run_child_guarded 轮询联动）
    if is_cancel_requested(agent.task_id):
        return {"status": "error", "summary": "父任务已取消，跳过委托"}

    # P0 只实现同步路径：wait=False 必须显式拒绝，不能静默当同步跑——
    # 谎报"已后台执行"比直接说"未实现"更坏（LLM 会据此继续推进错误假设）。
    if not wait:
        return {"status": "error",
                "summary": "异步委托(wait=False)属 P1 能力，当前版本未实现；请用 wait=True 同步等待结果"}

    # 分类层：配置的 categories 再扣一遍拒绝分类（配置可能来自 manifest，不可信）。
    # 显式传集合：空集就是零工具；不可写 `or None` —— 那会回落到
    # UniversalAgent._INITIAL_CATEGORIES（含 AGENT），把刚剔除的分类工具又装回来。
    sub_categories = config.effective_categories()

    # 创建子 Agent（独立 task_id；默认继承父 llm_client，零新建池）
    sub_task_id = f"sub-{agent.task_id}-{agent_id}-{uuid.uuid4().hex[:6]}"
    _sub_client = None
    if config.model:
        # OCP 扩展位：指定模型 → 新建 client，但复用父的连接池与凭据（默认零开销继承父）。
        # P0 限制：只支持"同 provider / 同 api_base 换模型"（ModelRef 沿用父的 provider/api_base）；
        #          跨 provider 需 AgentConfig 增 provider/api_base 字段（P1），否则共享池 base_url 不对。
        from app.db.models.chat_models import ModelRef
        from app.llm.client_sdk import create_llm_client
        _parent_model = agent.llm_client.llm_model
        _model_ref = ModelRef(provider=_parent_model.provider, model=config.model,
                              api_base=_parent_model.api_base)
        _sub_client = create_llm_client(
            llm_model=_model_ref,
            api_key=agent.llm_client.api_key,        # 只读 property（client_sdk 需补，见 §5.2）
            shared_client=agent.llm_client.client,   # 复用父 httpx 池，不新建连接池
        )
        _llm_client = _sub_client
    else:
        _llm_client = agent.llm_client

    try:
        sub_agent = UniversalAgent(
            llm_client=_llm_client,
            task_id=sub_task_id,
            max_steps=config.max_steps,
            initial_categories=sub_categories,
            excluded_tools=DELEGATE_DENY_TOOLS,   # 只读：写/删/双路径/bash/交互工具不进子 Agent（需 §5.2 改造后生效，见 §4.2）
            track_task=config.track_task,          # 子过程默认不落 tasks 台账（需 §5.2 改造后生效，见 §2.7.3）
        )
    except Exception as e:
        # 构造失败（task_id 非法/依赖缺失等）必须在这里收口：下面的 try/finally 还没开始，
        # 独立 client 否则永远不关（共享 client 时 close 是 no-op，但独立池会漏）。
        await _close_quietly(_sub_client)
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 构造失败: {e}")
        return {"status": "error", "summary": f"子Agent构造失败: {e}"}

    # 配置层已扣分类，这里按工具元数据兜底：剩余工具若有需确认/交互者，直接拒绝委托
    _blocked = _find_unattended_blocker(sub_agent)
    if _blocked:
        await _close_quietly(_sub_client)
        return {"status": "error",
                "summary": f"agent_id={agent_id} 的工具集含需人工确认/交互工具 {_blocked}，"
                           f"子Agent无交互出口，已拒绝委托"}

    # system_prompt 注入：initialize_run_state 每轮以 _get_system_prompt() 重写 _sys_prompt，
    # 故必须在实例上覆盖该方法，直接设 _sys_prompt 会被下一轮覆盖。
    if config.system_prompt:
        sub_agent._get_system_prompt = lambda: (
            config.system_prompt + "\n\n" + sub_agent.prompts.build_full_system_prompt()
        )

    sub_task = _build_sub_task(config, task, context)

    # P0：wait=True 同步等，本轮 observation 直接带结果。
    # P1：wait=False 不 await，句柄存 _background_delegates[delegate_id]，立即返回
    #     {"status":"running","delegate_id":...}；完成经 inbox 回灌（§3.3，结果带 delegate_id）。
    # 私有事件总线 + 克隆上下文：子 Agent 的终态清理（clear_temp_auth 等）与工具回调
    # set/reset 全落在副本，父作用域零污染。
    try:
        async with _delegate_scope(sub_task_id) as scope_ctx:
            await _run_child_guarded(
                sub_agent, sub_task, config.max_steps, scope_ctx,
                parent_task_id=agent.task_id, timeout_s=config.timeout_s,
            )
    except asyncio.TimeoutError as e:
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 超时: {e}")
        return {"status": "error", "summary": str(e), "usage": _usage_of(sub_agent),
                "steps": sub_agent.llm_call_count}
    except asyncio.CancelledError:
        raise                                   # 父任务取消：继续向上取消，终态由父侧收口
    except Exception as e:
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 异常: {e}")
        return {"status": "error", "summary": f"子Agent执行异常: {e}",
                "usage": _usage_of(sub_agent), "steps": sub_agent.llm_call_count}
    finally:
        await _close_quietly(_sub_client)       # 独立 client 归还（异常/取消路径同样清理）

    success = getattr(sub_agent, "status", None) == AgentStatus.COMPLETED
    summary = _extract_summary(sub_agent)
    usage = dict(sub_agent.accumulated_usage)  # 由 tool_executor 合并进父 Agent

    logger.info(
        f"[delegateagent_runner] 子Agent {agent_id} 完成: "
        f"status={'success' if success else 'failed'}, steps={sub_agent.llm_call_count}, "
        f"usage={usage}"
    )

    return {
        "status": "success" if success else "failed",
        "summary": summary,
        "usage": usage,
        "steps": sub_agent.llm_call_count,
    }


def _build_sub_task(config: AgentConfig, task: str, context: Optional[Dict[str, Any]]) -> str:
    """组装子 Agent 的 task 描述（自包含，不继承父历史，长度有界且截断留痕）"""
    _task = task[:500]
    if len(task) > 500:
        logger.warning(f"[delegateagent_runner] task 超长已截断: {len(task)}→500 字")
    parts = [f"## 任务\n{_task}"]
    if context:
        items = list(context.items())
        if len(items) > 20:
            logger.warning(f"[delegateagent_runner] context 键过多已截断: {len(items)}→20")
        lines = []
        for k, v in items[:20]:                            # 键数上限，防塞满
            _v = str(v)
            if len(_v) > 200:
                logger.warning(f"[delegateagent_runner] context[{k}] 超长已截断: {len(_v)}→200 字")
                _v = _v[:200]
            lines.append(f"- {k}: {_v}")                   # 单值上限，防大段文本
        if lines:
            parts.append("## 附加上下文\n" + "\n".join(lines))
    # 输出要求：配置给自由文本就用配置，否则用默认摘要要求（不再有封闭枚举 + if/else）
    parts.append("## 输出要求\n" + (
        config.output_instruction or "请输出简洁摘要（≤300字），包含关键发现和结论"
    ))
    return "\n\n".join(parts)


def _extract_summary(sub_agent) -> str:
    """从子 Agent 终态提取结果：FinalStep.response 是正文，reasoning 只是推理轨迹"""
    steps = getattr(sub_agent, "steps", []) or []
    for step in reversed(steps):
        if getattr(step, "TYPE", "") == "final":
            return (getattr(step, "response", "") or getattr(step, "error_message", "")
                    or getattr(step, "reasoning", "") or "")
    return steps[-1].get_content() if steps else ""      # 无终态时降级取末步正文
```

#### 2.5.1 并行模式

> **【核查】实施状态：已实施（P0，S5 已落码）。**
> - 代码：`backend/app/services/agent/tool_runner.py::execute_tools`、`backend/app/tools/tool_constants.py::MAX_PARALLEL_SUB_AGENTS=6`。
> - 无 `parallel` 参数；`is_parallel=len(all_calls)>1`；`_has_conflict` 三类集合（`FILE_OPERATION_TOOLS`/`WINDOW_TARGET_TOOLS`/`_SQL_TOOLS`）不含 `delegateagent`；B' 分组并行 + `asyncio.gather`。
> - 上限校验在扩展名纠错循环之后、三分支之前；计数前 `normalize_tool_name`；命中委托写回主名 `delegateagent`；超出第 6 个之后的委托 `build_error`（"上限 6"）；`_active_calls`/`_active_indices`；三分支统一 `_active_indices[pos]+1` 取号；末尾按原索引回填，长度不变。
> - 与设计差异：设计说 `MAX_PARALLEL_SUB_AGENTS` "当前代码中尚不存在"；实际已新增单点常量。`_SQL_TOOLS` 含 `query_sql`，但 `delegateagent` 不在其中，不影响并行前提。

**机制**：主 Agent 在同一轮 LLM 响应中发出多个 `delegateagent` 工具调用（每个不同 `agent_id` 或不同 `task`）。并行的判据由框架给，不由工具给：`action_input_parser` 产出 `is_parallel = len(all_calls) > 1`（`action_input_parser.py:96`），`tool_runner.execute_tools` 走 B' 分组并行（无冲突组 `asyncio.gather`）。所以 `delegateagent` 作为普通 tool 参与即可，**没有 `parallel` 参数**。

**并行的真实前提（易被误读，实施时不得破坏）**：并行能否生效，取决于 `delegateagent` 是否被 `_has_conflict` 判为冲突工具。该函数只对三类工具记冲突键——`FILE_OPERATION_TOOLS`、`WINDOW_TARGET_TOOLS`、`_SQL_TOOLS`（`conflict_detector.py:161-166`）；`delegateagent` 不在其中任何一类，因此**恒判无冲突、恒可并行**。这是当前"6 路并行"成立的唯一依据，属**结构性结果而非显式声明**：若后续给 `delegateagent` 增加路径类参数（如工作目录）并把它并入 `FILE_OPERATION_TOOLS`，`_partition_calls` 会把同路径的委托并成一组，并行将**静默退化为串行**——不报错、日志只多一行"串行"，测试也不易红。故 P0 须在运行器注释中写明这条依赖，禁止未经评估把 `delegateagent` 加入上述三类工具集。

**前台阻塞 ≠ 串行等待（两个维度互相独立）**：

| 维度 | P0 取值 | 由谁决定 |
|------|---------|----------|
| 前台 / 后台 | 前台阻塞：父 `await` 子 Agent 返回 | 架构决定，不可配（理由见 §1.4） |
| 串行 / 并行 | 取决于父一轮发出几个 `delegateagent` | LLM 决定（发几个 tool_call） |

父在 `await` 上等的是"全部子任务完成"，不是"逐个完成"：发 3 个委托即 3 个子 Agent 同时跑，总耗时 ≈ `max(t_i)`；发 1 个才是串行。子 Agent 的价值在上下文隔离（§1.4、§3.2），与是否后台无关。

**约束**：
- 单轮并行子 Agent 数 ≤ 6（P0 就校验，不是 P1）；常量 `MAX_PARALLEL_SUB_AGENTS` **当前代码中尚不存在**（`app/` 下零命中），须按 §5.2 在 `tool_constants.py` 新增，否则上限仅是纸面约束、无人拦截
- 子 Agent 内部**串行**（每个子 Agent 自身是单线程 ReAct 循环）
- 默认共享父 Agent 的 `llm_client`：`httpx.AsyncClient` 本身并发安全，但 `LLMClient._current_response` 是**单槽**（`client_sdk.py:686`），多路流式会互相覆盖，`cancel()` 因此可能关到别人的响应。故**取消以 `Task.cancel()` 为准**（§2.5 守卫协程），不依赖 `llm_client.cancel()`；`AgentConfig.model` 非 None 时新建 client 但共用同一个 httpx 池
- 单轮总 token 风险：6 个子 Agent × `max_steps` × 单步上下文，需要 `timeout_s` 兜底（§2.5）

**LLM 侧感知**：主 Agent 看到多个 `delegateagent` 的 observation 同时返回（各带摘要 + usage），自行整合。

**上限校验落点**：必须在 `tool_runner.execute_tools` —— 它是唯一持有 `all_calls` 全量的一层。
`delegateagent()` 与 `tool_executor.execute_tool()` 都是单工具粒度，放在那里看不到同轮其它调用，校验无效。

位置还有第二个硬约束：**计数前必须自己做别名归一**。`execute_tools` 开头那段逐 call 的 `c["tool_name"] = _corrected`（`tool_runner.py:53-60`）实际只做**文件扩展名纠错**（`_auto_correct_file_tool`，仅对 `read*`/`write*` 且带 `path` 的调用生效），**不查 `TOOL_NAME_ALIASES`**；别名归一发生在下游 `registry.get_tool`/`resolve_registered_tool`，属单工具粒度、晚于本处。也就是说 `delegate_task`/`call_agent` 进到 `execute_tools` 时名字仍是别名，若直接 `c.get("tool_name") == "delegateagent"` 计数，别名会全部绕过上限。正确做法是**计数时对每个 call 调一次 `normalize_tool_name`**，并且**命中委托的必须把主名原地写回 `c["tool_name"]`**（不是可选增强）：`tool_retry_engine._prepare_execution` 用 `self._tools.get(action)` 裸名查表，别名不写回则前 6 个虽被正确放行，仍会在执行层报"工具未找到"。写回只针对归一后为 `delegateagent` 的调用，不动其它工具的别名路径。插入点是扩展名纠错循环结束、`if len(all_calls) == 1` 分支之前。

```python
# tool_constants.py
MAX_PARALLEL_SUB_AGENTS = 6

# tool_runner.py import 段补：
from app.tools.tool_constants import MAX_PARALLEL_SUB_AGENTS
from app.tools.tool_response import build_error
from app.tools.tools_alias_mapper import normalize_tool_name

# execute_tools 内、扩展名纠错循环之后 / if len(all_calls) == 1 之前：
# 计数自带归一：all_calls 里的 tool_name 此时可能仍是 delegate_task/call_agent 等别名
# 命中委托即写回主名：执行层裸名查表，别名不写回会"工具未找到" — 小欧 2026-11-28
for c in all_calls:
    if normalize_tool_name(c.get("tool_name", "")) == "delegateagent":
        c["tool_name"] = "delegateagent"
_delegate_idx = [i for i, c in enumerate(all_calls)
                 if c.get("tool_name") == "delegateagent"]
_over = set(_delegate_idx[MAX_PARALLEL_SUB_AGENTS:])
_rejected: Dict[int, Any] = {}
if _over:
    for i in _over:
        _rejected[i] = build_error(llm_data={
            "summary": f"delegateagent，失败：单轮并行子Agent上限 {MAX_PARALLEL_SUB_AGENTS}",
            "status": {"exec_code": "error", "message": "失败",
                       "detail": f"本轮共 {len(_delegate_idx)} 个委托，超出部分未执行",
                       "hint": "请分批委托：本轮先处理这些，下一轮再发其余"},
        })
    _active_indices = [i for i in range(len(all_calls)) if i not in _over]
    _active_calls = [all_calls[i] for i in _active_indices]
else:
    _active_indices = list(range(len(all_calls)))
    _active_calls = all_calls

# 原三分支（A 单工具 / B' 分组并行 / C 顺序）一律改用 _active_calls 执行：
#   if len(_active_calls) == 1: ...
#   elif is_parallel: groups = _partition_calls(_active_calls) ...
#   else: ...
# 三分支产出记为 _active_results（长度 == len(_active_indices)）。

# 末尾按原索引回填，保持 results 长度与 all_calls 一致（预览/observation 不错位）：
results = [None] * len(all_calls)
for _pos, _i in enumerate(_active_indices):
    results[_i] = _active_results[_pos]
for _i, _err in _rejected.items():
    results[_i] = _err
```

> **隐藏改动点（易漏）**：原三分支内部用 `all_calls[i]` 的全局下标给 `on_attempt_recorded(indices[0]+1)` 取号（`tool_runner.py:75/102/109/117/146`）。改用 `_active_calls` 后，被拒委托之前的调用取号不变，但**被拒委托之后的调用取号会前移**（`_active_calls` 里下标变小）。必须统一用 `_active_indices[pos] + 1` 取号：A 分支 `_active_indices[0]+1`（不再硬写 1）、B' 分支 `_active_indices[indices[0]]+1` 与 `_active_indices[_gi]+1`、C 分支 `_active_indices[_pos]+1`，末尾回填同样按 `_active_indices[_i]` 定位原下标。
>
> **为什么不是"序号难看"而是数据错误**：`handle_action` 传入的工厂是 `make_fp_callback(agent, step, _exec_calls)`，`file_persist.py:268` 按 `exec_calls[_tno - 1]` 取 `params_raw_str` 写文件A。取号回退会让被拒调用之后的工具把**别人的原始参数串**写进排查文件。三分支的分组/组内取数/回填/取号四处须一起改，只删校验保留 `_active_calls` 属半成品，必须整段回退重做。

### 2.6 开放封闭原则（OCP）扩展点总表

> **【核查】实施状态：绝大多数扩展点已实施；个别口径与代码不符。**
> - `agent_register` + `load_from_manifest` + `load_plugins`；`tool_categories` + P1 `tool_names`；`model` + `provider`/`api_base` + `shared_client`；`system_prompt` 实例覆盖 `_get_system_prompt`；`output_instruction`；`max_steps`/`timeout_s`/`track_task`；4 别名；`description` callable + `resolved_description`；10 ContextVar；`_delegate_scope`；`react_loop.run_react_cycle`；`MAX_PARALLEL_SUB_AGENTS=6`；`DELEGATE_DENY_*`；`register/unregister/reset_agent_registry`。
> - 已整改：`track_task` 配置驱动透传；只读写工具拒绝 + `DELEGATE_ALLOW_TOOLS`/read 元数据白名单；跨 provider + `api_key`；`provider/api_base` 不再依赖 `model`；`tool_names` P1 已实现；`allow_delegate` 精确嵌套已实现。

架构的价值在于**对扩展开放、对修改封闭**。本设计的扩展点分布在配置层（不变代码即可扩展）与注入层（换实现不改调用方），逐项如下：

| 扩展点 | 默认行为 | 扩展方式（开放口） | 阶段 | 修改封闭性 |
|--------|----------|-------------------|------|-----------|
| 子 Agent 类型/能力 | 内置 3 个 | `AgentRegistry.register(AgentConfig)` / manifest 扫描 | P0 | 新增 Agent 不改运行器、不改工具描述 |
| 工具集 | `AgentConfig.tool_categories` | 配置字段 + P1 `tool_names` | P0/P1 | 不加入参，避免权限交给 LLM |
| **LLM 模型** | 继承父 `llm_client` | `AgentConfig.model` → 新 client 复用父连接池 | P0 | 不入工具参数；默认零开销 |
| system_prompt | 默认 PromptBuilder | `AgentConfig.system_prompt` + 实例覆盖 `_get_system_prompt` | P0 | 不改 UniversalAgent |
| 输出要求 | 默认摘要指令 | `AgentConfig.output_instruction`（自由文本） | P0 | 配置驱动，无枚举分支 |
| 步数/超时/台账 | 8 步 / 300s / 不建台账 | `max_steps` / `timeout_s` / `track_task` | P0 | 配置驱动 |
| 名称/别名 | `delegateagent` 唯一 | `TOOL_NAME_ALIASES` 增条目 → `normalize_tool_name` | P0 | 不另注册工具、不改调用点 |
| 工具描述内容 | 注册表快照动态生成 | 描述支持 callable（`to_openai_tools` 取值时调用） | P0 | 新增 Agent 不改描述字面量 |
| 工具回调通道 | 入口层注入 | `ContextVar` set/reset（10 个，清单见 §2.7.2） | P0 | 工具层零越层，新增回调不动工具代码 |
| 事件总线 | 私有纯内存 buffer | `_delegate_scope` 可换 sink（P2 `agent.event_sink` 注入） | P0/P2 | 不改 react_loop/runner |
| ReAct 引擎 | `react_loop.run_react_cycle` | 共用同一引擎，差异全在配置 | P0 | 子 Agent 零重写 |
| 并行上限 | 6 | `tool_constants.MAX_PARALLEL_SUB_AGENTS` | P0 | 常量单点，校验落 tool_runner |
| 子 Agent 拒绝清单 | 拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用）+ 写/删/双路径/bash 名单 | `agent_config.DELEGATE_DENY_*` + 工具元数据校验 | P0 | 新增写类工具只要进 PATH_* 表即自动拦截 |
| 同步/异步 | `wait=True` 同步 | `wait` 参数切 P1 异步 + inbox 回灌 | P0/P1 | 不新增工具，参数复用 |
| 完成回灌通道 | inbox（`inject_system_notice`） | 经既有 inbox 注入，可换实现 | P1 | 不改 conversation_history 装配 |
| 插件/Skill | 内置注册 | `plugins/*/manifest.json` + `load_from_manifest` | P1 | 新增插件不放代码 |
| 注册表生命周期 | 进程内单例 | `register/unregister/reset_agent_registry` | P0 | 热插拔/测试复位不改单例内部 |
| Agent 来源 | `local`（进程内注册表） | `agent_source`（`a2a_endpoint`/`mcp_server`）→ 来源解析器转本地 AgentConfig（§7.1） | P2+ | 注册结构不变，只多一个数据来源 |

**未列为扩展点（有意封闭，理由充分）**：工具集/模型/权限**不入工具参数**——这三类是"这个 agent 是谁"的配置属性，交给 LLM 入参会破坏递归防护与能力承诺（见 §2.2、§3.3）；ReAct 循环本身封闭——父子共用同一引擎，不允许子 Agent 定制循环逻辑，避免分叉出难以维护的多套实现。

**扩展代价（可核对的数字）**：
- 新增一个子 Agent：**0 个文件改动**（`register(...)` 一行，或放一个 `manifest.json`）。
- 新增一类工具给子 Agent 用：工具注册后按分类可用；只读 `read` 工具可自动进入子 Agent，写/未知工具自动拒绝；显式 `DELEGATE_ALLOW_TOOLS` 仍需审计。
- 换模型：**0 个文件改动**（`AgentConfig.model`；`provider/api_base/api_key` 可选；跨 provider 独立池）。
- 改并行上限/超时/步数：**0 个文件改动**（常量或配置字段）。
- 换事件总线/换引擎：需要动 1 处（`_delegate_scope`）或明确不开放（引擎）。

**架构三性**：
- **灵活**：上表 18 个扩展口均为"配置字段 / 注册表条目 / ContextVar 回调 / 策略参数 / 工具元数据"，新增能力不改调用链主干。
- **可靠**：每个扩展位都有明确默认值（继承父、内存 buffer、同步 wait），缺配置即走零开销默认路径；异常/取消/超时路径统一在 `_run_child_guarded` + `finally` 收口（子任务先收干净、buffer 后回收、client 归还、token reset）；递归防护三层且最后一层不依赖工具可见性。
- **高效**：默认路径不新建进程/线程/client/池（§3.1），扩展时才付额外成本，符合"按需付费"。

### 2.7 安全与递归防护

#### 2.7.1 递归防护

> **【核查】实施状态：P0 fail-closed 已实施；精确 `allow_delegate` 已真正实施，P0/P1 边界与原 v2.4 文本仍有口径差异。**
> - `effective_categories()` 扣拒绝分类；`excluded_tools` 三处同源（装载/动态注入/可见性）；`delegateagent` 默认在拒绝名单；`_find_unattended_blocker` 整单拒绝；`_current_delegate_depth` 硬顶；子作用域 `set_current_delegate_callback(None)`；`max_steps` + `timeout_s`。
> - `MAX_DELEGATE_DEPTH=1`（默认）；`allow_delegate=True` 时 `max_depth=2`，只放行 `delegateagent`，深度≤2；源子 Agent `_allow_delegate` 或目标 `config.allow_delegate` 满足即进入第2层；第2层再委托被深度硬顶拒绝；子作用域先清空再由入口层对 `delegateagent` 重新注入；非精确放行的 `delegateagent` 被 `_excluded`/`_find_unattended_blocker` 拒绝。
> - 设计 v2.4 曾说 P0 不预留 `allow_delegate`、P1 再引入；现行代码已加入并实现，仍保留 P1 定位；`MAX_DELEGATE_DEPTH` 仍为 runner 常量，但可通过 `allow_delegate` 放宽到2。
> - **附加白名单：** `_excluded` 叠加 `DELEGATE_ALLOW_TOOLS` + read 元数据只读放行（见运行器节），未知/写工具仍拒；与设计“拒绝名单 + 元数据校验”不矛盾但更严。

| 防护层 | 机制 | 是否依赖 LLM/工具可见性 |
|--------|------|------------------------|
| **配置层** | `effective_categories()` 扣掉拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用）；拒绝名单再扣 `delegateagent` | 是最外层，但**单独不成立**（见下） |
| **运行层（决定性）** | 子作用域内 `set_current_delegate_callback(None)`：工具就算被注入也拿不到回调，`delegateagent` 立即返回"委托通道未注入" | 否（不看可见性） |
| **深度层** | `_current_delegate_depth` 硬顶，`MAX_DELEGATE_DEPTH=1`（P0）；入口 `run_delegate` 先查 | 否 |
| **硬顶** | 子 Agent `max_steps` 有界（默认 8）+ `timeout_s` 墙钟兜底 | 否 |

**为什么"配置层 + 实例层"不够（实测路径）**：`tool_executor.auto_inject_from_search` 在工具返回后按 `matches[].category` 调 `agent._tool_loader.load_category(cat)`，把整类工具灌进 `_tools_dict`；而 `ToolRetryEngine` 持有的是**同一个 dict 对象**（`tool_retry_engine.py:275-276`），所以灌进来的 `delegateagent` 立刻可执行。仅靠"初始分类里没有 AGENT"，一条 searchtool 结果就能把防线拆掉。

> 粒度说明：P0 用"整类 + 名单"粗粒度就够（子 Agent 本就不该交互/写入）；P1 引入 `AgentConfig.allow_delegate` 与可配深度时，改为按工具名精确放行（见 §4.2），`MAX_DELEGATE_DEPTH` 从常量换成配置字段。P0 不预留该字段——没人读的开关是假开关。

#### 2.7.2 安全继承与作用域隔离

> **【核查】实施状态：已实施（P0）。**
> - `contextvars.copy_context()` + `create_task(context=ctx)`；子 `set/reset` 落副本，父零污染；`clear_temp_auth` 仅清副本；子继承父 `_authorized_paths`；10 个工具侧 ContextVar；`delegate` 子启动前置 None；`DefaultToolSecurityHooks` 照常；沙箱读侧照常。
> - 子 Agent 只读四道：拒绝分类 + 拒绝名单三处同源 + `delegateagent` 自身 + `_find_unattended_blocker`；FILE 写类仅靠拒绝名单（`CONFIRMATION_MAP={}`）；加 **`DELEGATE_ALLOW_TOOLS` 白名单**。
> - `_find_unattended_blocker` 跳过 `visible_to_llm=False`（实际增强）。

子 Agent 跑在 `contextvars.copy_context()` 的副本里（见 §2.5），副本继承父作用域的全部 ContextVar：

- `DefaultToolSecurityHooks`：安全确认/拒绝照常生效
- 沙箱预检：读文件类工具（`reviewer` 允许 FILE 分类里的读侧）同样走路径校验；bash/写侧在 P0 已被拒绝清单挡住，P1 放开时也只会经过同一套安全门，不会因为"子 Agent"而放宽
- 临时授权（ `_authorized_paths` 是 ContextVar）：子 Agent 继承父的授权映射；其 `clear_temp_auth()` 只清副本，**父 Agent 的授权不受影响**
- 全部 10 个工具侧 ContextVar（`task_id`/`hooks`/`text_task`/`notice`/`question`/`generate`/`precheck`/`session_id`/`delegate`/`depth`，定义见 `app/tools/context.py`）在副本内 set/reset，父子互不干扰；其中 `delegate` 在子任务启动前被显式置 `None`（§2.7.1 运行层）

> 不采用"手工保存/恢复授权"：ContextVar 本就是为这种作用域隔离设计的，克隆即用，零额外 API。

**继承 ≠ 可用：子 Agent 必须只读**

副本隔离只保证父子互不污染，**不保证子 Agent 的"人要确认"能传到人面前**。三条对码事实：

| 事实 | 代码依据 | 后果 |
|------|----------|------|
| 确认请求只播信封，正文在 interact 帧 | `hitl_confirmation.create_confirmation` 只 `publish` `hitl_pending` 事件 | 子 Agent 的确认 UI 落在子私有 buffer，父 task 的 SSE 与前端都收不到，用户无从点按 |
| 等待确认超时按拒绝处理 | `wait_for_confirmation_result(..., timeout=120)` 超时返回拒绝 | 子 Agent 空转到 120s 后拿到"拒绝"，纯浪费上下文与时间 |
| 问询/交互事件只写本地 buffer | `ask_question`、`step_emitter.emit_interact` 写 `agent_streams[子task_id]` | 无人消费，等于黑洞 |

所以 P0 定为 **子 Agent 只读**：不持有写入/删除/bash/AGENT 交互类工具。落地是"三道同源约束 + 一道构造后校验"：

1. `DELEGATE_DENY_CATEGORIES` 在 `effective_categories()` 里扣掉整类（§2.1）；
2. `DELEGATE_DENY_TOOLS` 名单经 `excluded_tools` 在「装载 / 动态注入 / 可见性」三处同源过滤（三处落点与改造前提见 §4.2，此处不重述）；
3. `delegateagent` 自身也在拒绝名单内（§2.7.1 配置层）；
4. 构造子 Agent 后**再按工具元数据校验一遍**：遍历实际拿到的工具，凡 `needs_confirmation=True` 或带 `confirm_fn` 的，一律判定"子 Agent 不可用"，**整单拒绝委托并回传原因**。不做"跳过该工具继续跑"——半只读的子 Agent 会跑到半途卡在确认上，比直接拒绝更难排查。
   > 覆盖面必须说清：这道校验只拦 AGENT 分类和声明了 `needs_confirmation`/`confirm_fn` 的工具（现为 `bash`、`execute_sql`）。**FILE 写类工具故意不声明 `needs_confirmation`**（`file_register.py:246` 的 `CONFIRMATION_MAP = {}`，delete 的确认在 `check_delete_permission` 里按 R3-R6 执行期产出），所以 `write`/`delete`/`move`/`copy`/`rename`/`edit` 的唯一防线是第 2 条的 `DELEGATE_DENY_TOOLS`。把这道校验当成"新写工具自动兜底"是误判——它也解释不了为什么 `excluded_tools` 的契约改造必须 fail-fast 而不能静默降级。

#### 2.7.3 资源保护

> **【核查】实施状态：已实施（P0）；`track_task` 已整改。**
> - token 预算 `max_steps` + 不继承父历史；并行 ≤6；`timeout_s=300` 墙钟 `_run_child_guarded` + `_CANCEL_GRACE_S=5.0`；连接池共享父 `httpx`（`shared_client`→`_owns_client=False`→`close()` no-op）；model/跨 provider/自定义端点/自定义 api_key 独立 client `finally` 关闭；取消联动父侧轮询 + `Task.cancel`；私有 buffer 先 cancel+有界等待再 `reclaim_memory_buffer`；子 `TaskTelemetry` 不 finalize，token 经 `accumulated_usage` 回灌父。
> - `track_task=config.track_task` 透传；`AgentConfig.track_task` 默认 `False`、插件强制 `False`；`BaseAgent.__init__ track_task:bool=True` + `if track_task:` 门控 + 非 bool `TypeError`；默认主 Agent 不变；子 Agent 默认不落台账，仅显式配置才建行。
> - `StepEmitter` 对 `_task_tracker=None` 守卫，不报错不落行；不写 `chat_tasks`/`chat_task_steps`/`tasks`（`sub-%` 0 行）。

| 保护 | 机制 |
|------|------|
| token 预算 | 子 Agent `max_steps` 有界（默认 8）+ 不继承父对话历史（初始上下文只有 task 描述与 system_prompt） |
| 并行数 | 单轮 ≤ 6 个子 Agent（`MAX_PARALLEL_SUB_AGENTS`，在 `tool_runner.execute_tools` 按 `len(all_calls)` 校验，见 §2.5） |
| 总耗时 | `AgentConfig.timeout_s`（默认 300s）墙钟硬顶，由 `_run_child_guarded` 计时；超时即 `task.cancel()` + 宽限期内等收敛后按失败回传，P0 即生效。取消后子任务超过 `_CANCEL_GRACE_S` 仍未退出则放弃等待并留 error 日志——宁可留残留日志，也不把父任务拖成无界等待 |
| 连接池 | 默认共享父 Agent 的 `httpx` 客户端（`create_llm_client(..., shared_client=...)` 使 `_owns_client=False`，子实例 `close()` 为 no-op）；`AgentConfig.model` 非 None 才新建独立 client，finally 关闭 |
| 取消联动 | 子 Agent 不注册进 `running_tasks`，框架内 `is_cancel_requested(子task_id)` 恒为 False，故联动只能由父侧轮询：`_run_child_guarded` 按 `_POLL_S` 周期查 `is_cancel_requested(父task_id)`，命中即 `task.cancel()` 并等待收敛 |
| 事件总线 | 私有纯内存 buffer；回收顺序必须是"先 cancel + 有界等待子任务收干净，再 `reclaim_memory_buffer`"，反序会让子任务 publish 撞上已回收 buffer 抛 RuntimeError |
| 任务台账 | 子 Agent `track_task=config.track_task`，默认 `AgentConfig.track_task=False`；`BaseAgent` `if track_task:` 门控 + 非 bool `TypeError`；P0 默认无 `sub-` 台账行；仅显式配置才建行 |
| 遥测归属 | `react_loop.run_react_cycle` 内部会建 `TaskTelemetry` 并 `on_start`（`react_loop.py:197-205`），但 `finalize()` 由 `agent_runner` 收尾路径调用；子 Agent 不跑完整 runner（§5.3），故**子 Agent 的 telemetry 无人 finalize**——P0 取舍：**不 finalize**，子 Agent 的 token 只经 `accumulated_usage` 回灌父 Agent（§4.3）统一记账，不单独落 `task_metrics`（子 task_id 不在 `chat_tasks` 里，强落会外键失败）。P0 验证时须确认 `TaskTelemetry` 未 finalize 不会在 `react_loop` 结尾抛异常或留悬挂资源 |

**台账门控改造**（`base_agent.py`，§5.2 前置改造的一部分，S0 已落码）：

```python
def __init__(self, llm_client, task_id, max_steps=None,
             track_task: bool = True,      # 新增；默认 True 保持主 Agent 行为不变
             ):                            # 删掉 **kwargs → 漏改即 TypeError 在构造时炸出
    ...
    if track_task:                         # 门控 tracker.create_task
        self._task_tracker = None
        try:
            from app.services.task import get_tracker
            tracker = get_tracker()
            tracker.create_task(task_id=self.task_id,
                                agent_id=self.__class__.__name__, description="")
            self._task_tracker = tracker
        except Exception as _e:
            logger.debug(f"[TaskTracker] 创建任务失败: {_e}")
```

> 子 Agent 传 `track_task=config.track_task`（默认 `AgentConfig.track_task=False`），默认走 `if` 之外的分支，`self._task_tracker` 保持 None；后续 `StepEmitter.complete_task`/`record_operation` 对 None tracker 已有守卫（`step_emitter.py:219`），不报错、不落行。

---

## 3 通信交互与数据流总览

### 3.1 主 Agent 的五条通信通道

主 Agent 同时与五个对象通信，各有独立载体，互不串扰：

| 通道 | 对象 | 载体 | 谁消费 |
|------|------|------|--------|
| ① LLM 回路 | LLM | `message_builder.conversation_history`（内存消息列表） | 仅 LLM |
| ② 工具层 | 各工具实现 | `ContextVar` 回调注入（10 个，清单见 §2.7.2） | 工具实现 |
| ③ 前端 | 浏览器 SSE | `StreamBuffer.event_log`（`agent_streams[task_id]`） | `stream_reader` → SSE 帧 |
| ④ 子 Agent | 子会话 | `delegate_callback` + 返回字典 | 父 Agent 的 conversation_history |
| ⑤ 异步回灌（P1） | 父 Agent 自己 | `task_registry.inject_system_notice` → `drain_inbox` → 对话历史 | 父 ReAct 下一轮 |

- **① LLM 回路**：每轮 `react_step._process_single_step` → `call_llm_with_fallback` 把 `conversation_history` 发给模型；LLM 回 `action`(tool_calls) 或 `answer`。工具结果经 `build_observation` → `message_builder.add_tool_result(tool_call_id, content)` 以 `role=tool` 消息追加回历史，与 `add_assistant_tool_call` 按 `tool_call_id` 配对，下一轮 LLM 带上完整历史。
- **② 工具层**：`tool_executor.execute_tool` 调工具前把闭包注入 ContextVar，工具内部只消费、不 import services；finally 按 token reset。`delegateagent` 就走这条已验证通道。
- **③ 前端**：所有 Step 经 `StepEmitter` → `buffer.publish()` 写入 `event_log`；`stream_reader(buffer, task_id, after_seq)` 按 seq 读并转 SSE。该通道只给前端，也是断线重连回放源。
- **④ 子 Agent**：见 §3.2。
- **⑤ 异步回灌（P1）**：`wait=False` 时父轮次早已结束，无法用工具返回值回灌；唯一"LLM 真能读到"的路径是既有 inbox——`inject_system_notice(task_id, content)` 写入任务收件箱，父 Agent 下一轮 `react_step` 入口 `drain_inbox()` 取出并作为对话历史的一条消息注入。**不新造总线**。

> 关键边界：**LLM 只看 conversation_history**，看不到 SSE、看不到前端、看不到子 Agent 内部步骤；**SSE 只给前端**，两条通道完全独立。⑤ 之所以成立，是因为它最终也汇入 ①——inbox 只是"延迟写 ①"的转账方式，不是第二条 LLM 通道。

**执行模型定位（本设计的核心架构模式）**：子 Agent **不是子进程，也不是宿主的子线程**，而是同一 Python 进程、同一 OS 线程、同一 asyncio 事件循环上的一个协程任务（`asyncio.create_task`），靠 `copy_context()` 复制 ContextVar 做**逻辑隔离**。这是本设计的架构选择——用"不创建 OS 执行单元"换取零框架改动与轻量上下文隔离。

| 层次 | 执行单元 | 依据 |
|------|----------|------|
| 子 Agent 的 ReAct 循环 | 事件循环上的协程 Task | `asyncio.create_task(..., context=scope_ctx)`；`run_react_cycle` 全程 `async def` |
| LLM 调用 | 同一事件循环的异步 I/O | `httpx.AsyncClient` + 共享池（`_SharedClientPool`/`ConnectionScope`）+ `asyncio.Semaphore` 排队 |
| 同步工具实现 | 线程池（有界 WorkerPool / `asyncio.to_thread`） | `tool_retry_engine._execute_tool_once` |
| shell / 文件预演 | 真正的 OS 子进程（`subprocess.Popen` + Job Object） | `sandbox/backend.py`、`SandboxExecutor` |

即：**控制流全程是协程；只有工具执行才可能突破到线程/进程边界**。子 Agent 本身不另起进程或线程。

由此还有一个常被混淆的口径：**"前台/后台"与"串行/并行"是两个独立维度**，P0 的定位是"前台阻塞 + 可并行"（父 `await` 全部子任务完成，而非逐个等待）；判据、前提与不可破坏的依赖见 §2.5.1，此处不重述。

由此产生的架构边界（P0 接受，后续阶段按需升级）：

1. **无资源隔离**：父子共享进程内存、`llm_client`、事件循环；子 Agent 的 CPU 密集操作会阻塞父 Agent，不是"互不影响的子任务"。
2. **I/O 并发非 CPU 并行**：多个子 Agent 靠 `asyncio.gather` 交错执行，只在 I/O 等待时切换；token/连接池共享（信号量排队）。
3. **隔离唯一手段是 ContextVar 副本**：凡绕过 ContextVar 读写模块级全局状态（`agent_streams`、`_last_heal_attempt`）者，父子会串味——这是全局清理反噬问题（§2.7.2）的根源。
4. **子 Agent 工具集受事件循环形状约束**：本系统已把 shell/文件预演下沉到独立进程宿主（`app/proc`，主进程零 `CreateProcessW`），目的正是避免重活压住主事件循环。子 Agent 不另起执行单元，因此**其工具集必须整体落在"异步 I/O 或已下沉线程池/宿主"的工具上**：CPU 密集型（`DATAANALYSIS`/`DOCUMENT` 等）若进子 Agent 工具集，6 路并行会同时阻塞全局事件循环，受害面是**全部会话**而非仅父任务。（`SYSTEM`/`MEDIA` 已在 `DELEGATE_DENY_CATEGORIES` 里被整体拒绝，见 §2.1。）P0 落地时仍须逐个复核 `AgentConfig.tool_categories` 所指工具的执行体形态，必要时把 CPU 类也补进拒绝分类。

### 3.2 委托数据流

```
主 Agent LLM 回路（① conversation_history）
  │  LLM 决定调用 delegateagent(agent_id="researcher", task="...")
  ▼
tool_executor.execute_tool()
  │  注入 delegate_callback ContextVar（② 工具层通道）
  │  并行分支: 框架按 len(all_calls)>1 走 gather，无 per-call parallel 参数
  ▼
tools/agent/delegateagent.py (工具函数)
  │  取 callback → await callback(agent_id, task, context, wait)
  ▼
delegateagent_runner.run_delegate(agent=父agent, agent_id, task, context, wait)
  │  1. 深度校验: _current_delegate_depth.get() >= MAX_DELEGATE_DEPTH → 直接拒绝
  │  2. 查 AgentRegistry.get(agent_id) → AgentConfig；未知 id 回传可用列表
  │  3. 父任务已取消（is_cancel_requested(父task_id)）→ 不启动
  │  4. 分类层: effective_categories() 扣掉 DELEGATE_DENY_CATEGORIES
  │  5. model 非 None → create_llm_client(..., shared_client=父client)；否则继承父 client
  │  6. 创建 UniversalAgent(excluded_tools=DELEGATE_DENY_TOOLS, track_task=config.track_task)
  │  7. 只读校验: _find_unattended_blocker 扫到需确认/交互工具 → 整单拒绝
  │  8. system_prompt 覆盖 _get_system_prompt；组装 sub_task（task≤500 / 单值≤200）
  │  9. _delegate_scope: 建 sub_task_id 纯内存 buffer + copy_context()（回调置空在子任务内做，见 10）
  │ 10. _run_child_guarded: create_task(..., context=副本) 跑 run_react_cycle
  │     · 墙钟 timeout_s 到点 → task.cancel() → 收敛 → 抛 TimeoutError
  │     · 每 _POLL_S 查 is_cancel_requested(父task_id) → task.cancel() → 收敛 → 抛 CancelledError
  │     · 先 cancel + await 子任务收干净，再由作用域退出时 reclaim_memory_buffer
  │ 11. 从 FinalStep.response 提取结果 + accumulated_usage
  ▼
返回 {"status", "summary", "usage", "steps"}（④ 子 Agent 通道；失败/超时也带 usage/steps）
  │  summary 来源：_extract_summary 取子 Agent 的 FinalStep.response（任务总结正文）；
  │               失败时回落 error_message / reasoning；无终态时降级取末步 get_content()
  ▼
工具层 build_success → llm_data={"summary", "action", "status": {"exec_code":"success"}}
  │
  ▼
observation_formatter._format_llm_data → observation 文本：
  │   "工具执行: 委托子Agent 调用工具-delegateagent - 执行结果: 成功\n观察: <summary>"
  ▼
message_builder.add_tool_result(tool_call_id, observation_text)  → 父 conversation_history（①）
  │
  ├─ tool_executor: 按 data.usage 是否存在合并到 agent.accumulated_usage（成功/失败都算）
  └─ 父 Agent LLM 下一轮看到 observation（摘要+用量）→ 继续 ReAct 循环
```

子 Agent 内部步骤写入私有 buffer（§4.4），既不进父 SSE（③），也不进父 conversation_history（①）；只在日志中留痕。

### 3.3 通信交互对委托设计的四条约束

1. **结果回灌的唯一入口是 conversation_history**：父 LLM 只看①，看不到子 Agent 内部步骤。因此 `_extract_summary` 取出的 `FinalStep.response` 直接决定父 Agent 看到什么——摘要字段必须准确（见 §2.5 修复后的 `_extract_summary`）。

2. **SSE 与 LLM 上下文是两条独立通道**：子事件写私有 buffer，既不到父 SSE（前端不可见），也不到父 conversation_history（LLM 不可见），这是 §4.4 隔离目标的机制保证。

3. **P1 异步完成通知走⑤（inbox）而非直接改①**：父 Agent 此刻可能正等其它工具结果，直接写 `conversation_history` 会破坏 tool_call 的 assistant/tool 配对。改走既有 `inject_system_notice(task_id, content)` → 父 ReAct 下一轮 `drain_inbox()` 取件注入历史；通知携带 `delegate_id` 以区分并发异步委托（见 §2.2 `wait=False` 说明）。注意 notice 事件本身只到前端（③），**不能直接喂给 LLM**——落到 inbox 才是 LLM 能读到的唯一异步路径。

4. **子 Agent 不得依赖"人"**：子 Agent 的确认/问询事件只能写进自己的私有 buffer，前端和父任务都收不到（§2.7.2 三条实测依据）。所以委托契约必须是"输入自包含、输出纯文本"，任何需要临场澄清的任务都不该交给子 Agent。

---

## 4 与现有代码的集成

### 4.1 工具注册（agent_register.py 扩展）

> **【核查】实施状态：已实施（P0）。**
> - `agent_register._register_agent_tools`：`AGENT_TOOL_DESCRIPTIONS["delegateagent"]=build_delegate_tool_description`（callable）；`AGENT_INPUT_MODELS["delegateagent"]=DelegateAgentInput`；`AGENT_TOOL_EXAMPLES`；`tool_methods["delegateagent"]=delegateagent` 进注册循环；`category=AGENT`；`hide_from_steps` 不加；`visible_to_llm`；`version`。
> - `build_delegate_tool_description()` 实时 `get_agent_registry().list_configs()`，空→`（注册表为空）`；`meta.resolved_description()` 唯一解析点；`register(description=Union[str,Callable])`；读取点 `tool_description`/`registry.list_tools`/`tool_cache_manager`/`tool_search`(BM25+回填) 均走 `resolved_description()`。
> - `load_plugins()` 在注册 `delegateagent` 之前（P1）。

在 `_register_agent_tools()` 中增加 `delegateagent` 注册。**描述不写字面量**，由注册表动态生成——否则每加一个 Agent 都要回来改代码（原设计把 3 个 agent_id 写死在描述里，是 OCP 破口）：

```python
# agent_config.py（tools 层，与注册表同文件）
def build_delegate_tool_description() -> str:
    """工具描述动态生成 — 可用 agent 列表来自注册表（新增 Agent 零改代码）"""
    items = "；".join(f"{c.agent_id}({c.description})" for c in get_agent_registry().list_configs())
    return (
        "委托子Agent执行独立任务。子Agent拥有独立上下文与只读工具子集（不能写文件、不能执行命令、不能向用户提问）。"
        "适用于：并行搜索不同来源、独立审查验证、工具专精任务、知识库多域对照分析。"
        "参数：agent_id(见下) + task(自包含任务描述，≤500字) + context(可选附加信息) + wait(默认同步等待结果)。"
        "子Agent完成后回传摘要和token用量，父Agent整合结果继续。"
        f"可用agent_id：{items or '（注册表为空）'}。"
    )

# agent_register.py 扩展
from app.tools.agent.agent_config import build_delegate_tool_description
from app.tools.agent.delegateagent import delegateagent
from app.tools.agent.delegateagent_schema import DelegateAgentInput

AGENT_TOOL_DESCRIPTIONS["delegateagent"] = build_delegate_tool_description
# ↑ 传 callable 而不是字符串：to_openai_tools / list_tools 取值时调用，
#   插件在启动后加载进来的 Agent 也能立刻出现在描述里（工具缓存按 TTL 刷新，见 tool_cache_manager）。
AGENT_INPUT_MODELS["delegateagent"] = DelegateAgentInput
AGENT_TOOL_EXAMPLES["delegateagent"] = [
    {
        "agent_id": "researcher",
        "task": "搜索 2026年 Windows 桌面 Agent 框架的最新进展，重点关注上下文隔离和工具子集设计",
        "context": {"focus": "上下文隔离", "time_range": "2026"},
    }
]
# hide_from_steps 不加：delegateagent 是业务工具，前端步骤流可见

# ⚠ 只加上面三张表还不够 —— _register_agent_tools() 的注册循环用的是函数内的 tool_methods，
#   漏了这一步，描述/入参/示例都齐了但工具根本没 register（工具列表里查不到 delegateagent）：
def _register_agent_tools():
    tool_methods = {"question": question, "schedule": schedule, "delegateagent": delegateagent}
    # ... 其余不动
```

注意两点：

1. `delegateagent` **不加入** `AGENT_HIDE_FROM_STEPS`（它是有业务产出的工具，前端步骤流应展示"正在委托 researcher 子Agent..."）。
2. `ToolMetadata.description` 需支持 callable，且**解析只在一处**：S0 把字段放宽为 `Union[str, Callable[[], str]]` 并在 `tool_types.py` 新增 `resolved_description()`（解析异常按空串返回 + warning），所有取值方一律走它——`tool_description.to_openai_tools`、`registry.list_tools`、`tool_cache_manager._get_original_search_desc`、`tool_search` 的 BM25 索引与结果回填。**不要在调用方各自写 `callable(x) and x()`**：5 个直读点各写一遍等于把同一判据复制 5 份，漏一处就把函数对象塞进 schema、或在检索期抛 TypeError（S0 落码前正是这种散落写法）。`register(description=...)` 的形参标注同步放宽。

### 4.2 工具子集注入

> **【核查】实施状态：契约前置改造已落码（S0）；子 Agent 只读实现比设计更严但已收敛。**
> - `ToolLoader.init_tools(initial_categories, excluded_tools, tool_names)`；`agent._excluded_tools` 单一权威；`load_category` 同源；`to_openai_tools(...,exclude=...)`；`registry.to_openai_tools` 透传；`tool_cache_manager.get_openai_tools` 透传 `_excluded_tools`；`UniversalAgent`/`BaseAgent` 显式形参删 `**kwargs`；`ToolMetadata.description` callable + `resolved_description`；`LLMClient.api_key` 只读 property。
> - `tool_cache_manager` 额外 `_names` 过滤（P1 `tool_names` 同源）。
> - `_excluded=DELEGATE_DENY_TOOLS ∪ (已注册全集 - 只读放行集)` + `tool_names=config.tool_names`；`track_task=config.track_task`；`LLMClient.api_key` `or ""`；`exclude/tool_names` 已注册名 `normalize_tool_name`；`to_openai_tools(tool_names=)` 保留“额外包含”，P1 精确白名单后过滤；精确 `allow_delegate` 只额外放行 `delegateagent`。

子 Agent 的工具注入走 `ToolLoader.init_tools`。**`excluded_tools` 形参在 S0 前并不存在**（原签名 `init_tools(self, initial_categories=None)`，`tool_loader.py:28`）；S0 已落码为 `init_tools(self, initial_categories=None, excluded_tools=None)`（`:30`），下段代码按此写：

> 改造前提（S0，已落码）：下文「三处同源」列的每个落点都要改造才生效（`init_tools`/`load_category` 增 `excluded_tools`、`to_openai_tools` 增 `exclude` 形参并经 `registry`/`tool_cache_manager` 打通、两个构造器改显式形参并删掉 `**kwargs`）。**S0 前 `UniversalAgent.__init__` 与 `BaseAgent.__init__` 都是 `**kwargs` 接收后不消费、不报错**（`universal_agent.py:56`、`base_agent.py:57`），漏改任何一项都表现为"参数被吞掉、程序照跑"，不会在启动期暴露；S0 已删 `**kwargs`，此后再漏改由 Python 原生 `TypeError` 在构造时炸出来。

```python
# delegateagent_runner.py 中
sub_agent = UniversalAgent(
    llm_client=_llm_client,
    task_id=sub_task_id,
    max_steps=config.max_steps,
    initial_categories=sub_categories,    # AgentConfig.effective_categories()
    excluded_tools=_excluded,             # 只读拒绝清单 + 已注册非只读工具；精确 allow_delegate 仅放行 delegateagent
    track_task=config.track_task,
    tool_names=config.tool_names,
)
```

**拒绝清单必须三处同源**（漏一处就有一条暗道）：

1. `init_tools` 装载时跳过被拒工具（`_tools_dict` 不含它）；
2. `load_category` 动态注入时同样跳过（否则 searchtool 一命中又灌回来）；
3. `get_openai_tools`/`to_openai_tools` 生成可见列表时同样跳过（否则 LLM 看得见但调不通，白耗轮次）。

实现口径：`ToolLoader.init_tools(..., excluded_tools)` 把清单存成 `agent._excluded_tools`（单一权威），`load_category` 读它过滤动态注入。**可见性侧在 S0 前无法直接传 `exclude`**：原签名 `to_openai_tools(registry, categories=None, tool_names=None, strict=False)`（`tool_description.py:27`）没有该形参；S0 已增 `exclude`（`:29-31`），`registry.to_openai_tools` 与 `tool_cache_manager.get_openai_tools` 同步透传，`_excluded_tools` 因此才真正生效。写入点只有 `UniversalAgent.__init__`（`excluded_tools=None` 保持既有行为）。

> 传参链要一次打通，缺一环拒绝清单在 LLM 眼里就等于不存在：`tool_cache_manager.get_openai_tools(agent)`（S0 前只传 `categories=agent._loaded_categories`；S0 已补 `exclude=getattr(agent, "_excluded_tools", None)`）→ `registry.to_openai_tools(..., exclude=agent._excluded_tools)` → `tool_description.to_openai_tools(...)`。三者任一漏传，子 Agent 会"看得见但调不通"，白耗一轮。

**前置改造完整代码**（§5.2 清单逐项落地；`base_agent.py` 的 `track_task` 门控见 §2.7.3，`tool_executor.py` 的注入见 §2.4.2，此处不重述）：

① `tool_loader.py` —— `init_tools`/`load_category` 增 `excluded_tools`，单一权威存 `agent._excluded_tools`：

```python
def init_tools(self, initial_categories=None, excluded_tools=None):
    self.agent._excluded_tools = set(excluded_tools or ())   # 单一权威
    self.agent._tools_dict = {}
    # ... 原装载循环内加：if name in self.agent._excluded_tools: continue
    self.agent._loaded_categories = set(initial_categories or ())
    return self.agent._tools_dict

def load_category(self, category: ToolCategory) -> bool:
    # ... 原动态注入循环内加：
    # for name in names:
    #     if name in getattr(self.agent, "_excluded_tools", ()): continue
```

② `universal_agent.py` —— 显式形参 + 删 `**kwargs`：

```python
def __init__(self, llm_client, task_id, max_steps=None,
             initial_categories=None,
             excluded_tools=None,      # 新增显式形参
             track_task=True,          # 新增显式形参
             ):                        # 删掉 **kwargs → 漏改即 TypeError
    ...
    self._tool_loader.init_tools(initial_categories=initial_categories,
                                 excluded_tools=excluded_tools)
    super().__init__(llm_client=llm_client, task_id=task_id,
                     max_steps=max_steps, track_task=track_task)
```

③ `tool_description.py` —— `to_openai_tools` 增 `exclude` 形参 + callable 描述解析（§4.1 注意点2）：

```python
def to_openai_tools(registry, categories=None, tool_names=None,
                    strict=False, exclude: Optional[Set[str]] = None) -> list:
    _exclude = exclude or set()
    ...
    for name, meta in sorted(registry._tools.items(), key=lambda x: x[0]):
        if name in _exclude:                       # 新增：可见性过滤
            continue
        ...
        "description": meta.resolved_description(),   # 唯一解析点（tool_types.py），不在调用方各写一份
```

④ `registry.py` —— `to_openai_tools` 增 `exclude` 并透传（§5.2 清单原漏此项，补上）：

```python
def to_openai_tools(self, categories=None, tool_names=None,
                    exclude: Optional[Set[str]] = None) -> list:
    return to_openai_tools(self, categories=categories,
                           tool_names=tool_names, exclude=exclude)
```

> `list_tools`（`registry.py:374` 附近）、`register(description=...)` 的形参标注、`tool_search` 的两处直读也须同步：取值一律走 `resolved_description()`，后者放宽为 `Union[str, Callable[[], str]]`（§4.1 注意点2）。

⑤ `tool_cache_manager.py` —— 补传 `exclude`：

```python
tools = tool_registry.to_openai_tools(
    categories=agent._loaded_categories,
    exclude=getattr(agent, "_excluded_tools", None),   # 新增
)
```

⑥ `client_sdk.py` —— `LLMClient` 补只读 `api_key` property（§2.5 model 分支用 `agent.llm_client.api_key`；该类 S0 前仅有 `_api_key`，`client_sdk.py:441`；S0 已加 property）：

```python
@property
def api_key(self) -> str:
    """公开已清洗的 API Key（只读）— 小欧 2026-11-27
    不提供 setter，避免绕过 __init__ 的 strip 清洗口径。"""
    return self._api_key
```

**P0 是"分类粒度 + 名字级拒绝清单"**：`initial_categories` 一次传到位（`ToolLoader.init_tools` 同时写 `_tools_dict` 与 `_loaded_categories`），拒绝清单在装载/动态注入/可见性三处同源过滤（见上）。

**P1 再加"名字级允许清单 `tool_names`"**——它比黑名单更严，且**不能**在 `init_tools` 之后改 `_tools_dict` 实现，两头都不靠：

- LLM 可见性由 `_loaded_categories` 决定（`tool_cache_manager.get_openai_tools` 以 `categories=agent._loaded_categories` 调 `to_openai_tools`），改 `_tools_dict` 不影响 LLM 看到什么；
- 可执行性由 `_retry_engine._tools` 决定（`UniversalAgent.__init__` 用 `ToolRetryEngine(self._tools_dict)`，引擎持有 `self._tools = tools` 同一 dict 引用），构造后**重新赋值** `_tools_dict` 不会更新引擎，被"过滤掉"的工具照样能执行。

P1 正确做法：过滤发生在 `ToolRetryEngine` 构造之前（把筛完的字典传进去），并让可见性同源（`get_openai_tools` 接 `tool_names`，`to_openai_tools` 已原生支持该形参）。

### 4.3 usage 合并

> **【核查】实施状态：已实施（P0）。**
> - `tool_executor._merge_delegate_usage`；`if normalize_tool_name(tool_name)=="delegateagent"`；判据 `data.usage` 存在性非 `is_success`；成功/失败都记；`keys=(prompt,completion,total)`；`_safe_int` 脏数值->0 + `None/空->0` + 数字字符串 + `1e3` + inf/NaN->0；非 dict `data/usage` no-op；四层 `accumulated_usage`+`task_accumulated_tokens`+`session_accumulated_tokens`(基线+task，不叠加)+`chain_accumulated_tokens`；`db.atxn("chat",_write,retry_locked=3)`；`storage.update_task_accumulation`+`update_session_accumulation(sid)`；空 usage no-op；非 delegate 不记；异步 `wait=false` 完成后同样 `_merge_delegate_usage`，记账失败不阻断 inbox。
> - 与设计差异：import 为 `from app.db import db`（非 `app.db.database`）；运行器**不自行合并父账**（仅返回 `usage`，由 `tool_executor` 合并）。设计开头"不自动合并"与下文"设计决策合并"自相矛盾，以下文+代码为准。

子 Agent 完成后，`run_delegate` 返回的 `usage` 字典（`accumulated_usage` 快照）由父 Agent 在 observation 中看到；运行器自身**不自行合并父账**，但父 Agent 的 `accumulated_usage` **由 `tool_executor` 自动合并**；异步 `wait=false` 完成后同样合并，父 LLM 可经 inbox 读到完成通知。

**设计决策**：usage 合并放在父 Agent 侧——`tool_executor.execute_tool` 完成后累加。两条硬要求：

1. **不分成功失败，有 usage 就记账**：子 Agent 跑了 6 步才失败，那 6 步的 token 是真实花费。故 §2.3 的失败分支也把 `usage` 放进 `data`。
2. **判据用 `data.usage` 存在性，不用 `is_success`**：`is_success` 读的是 `llm_data.status.exec_code`（工具"是否成功"），与"是否产生 token"是两件事。

需在 `tool_executor.py` 增 `db`（`app.db`）、`storage`（`app.services.chat`）与 `normalize_tool_name` 三个 import。合并落点为工具执行完成后；判据用归一名，避免直调别名漏合并。

```python
# tool_executor.py — 小欧 2026-11-28：四层合并 + DB 落账，失败委托同样记账
async def _merge_delegate_usage(agent, sub_usage: dict) -> None:
    if not sub_usage or not isinstance(sub_usage, dict):
        return
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    delta = {k: _safe_int(sub_usage.get(k)) for k in keys}
    for k in keys:
        agent.accumulated_usage[k] += delta[k]
        agent.task_accumulated_tokens[k] += delta[k]
    # session/chain 是基线 + 当前任务累计的派生值，合并时不再叠加基线（否则下轮双计）
    zero = {k: 0 for k in keys}
    s_base = getattr(agent, "_session_acc_base", None) or zero
    c_base = getattr(agent, "_chain_acc_base", None) or zero
    agent.session_accumulated_tokens = {k: s_base[k] + agent.task_accumulated_tokens[k] for k in keys}
    agent.chain_accumulated_tokens = {k: c_base[k] + agent.task_accumulated_tokens[k] for k in keys}
    # DB 权威列必须落子用量：react_step 每轮只记本次 LLM 调用，取不到 delegate 的消耗
    sid = (getattr(agent, "_start_meta", None) or {}).get("session_id")

    def _write(conn):
        storage.update_task_accumulation(conn, task_id=agent.task_id, llm_call_count_token=delta)
        if sid:
            storage.update_session_accumulation(conn, session_id=sid, llm_call_count_token=delta)

    await db.atxn("chat", _write, retry_locked=3)


if normalize_tool_name(tool_name) == "delegateagent":
    await _merge_delegate_usage(agent, (result.get("data") or {}).get("usage") or {})
```

这样父 Agent 的 `FinalStep` 终态输出里已包含子 Agent 的 token 消耗（失败委托也计入），DB 的 `chat_tasks.task_accumulated_tokens` 也不漏账。

### 4.4 SSE 隔离（P0 已实现）

> **【核查】实施状态：已实施（P0）。**
> - `_delegate_scope` 为 `sub_task_id` 建纯内存 StreamBuffer（`journal_sink=None`/无 `persist_sink`）；父 SSE 读父 buffer；子步骤写子 buffer；`reclaim_memory_buffer(sub_task_id)` 在子任务收干净后；不写 `chat_task_steps`/`chat_tasks`；不产生 `sub-` 幽灵行；`_task_tracker=None`；`publish_for_task(EVENT_TASK_ENDED...)` 仍发但子 `task_id` 不在父 SSE 消费。
> - P2 嵌套透传/`stream_orchestrator` 未改（暂缓）。

子 Agent 的步骤**不透传**到父 Agent 的 SSE 流。父 Agent 步骤流中只看到：

```
Step N: delegateagent(researcher, "搜索...") → observation: 摘要
```

**隔离机制**：`_delegate_scope` 为子 Agent 创建 `sub_task_id` 对应的**纯内存 StreamBuffer**（`journal_sink=None`，无 `persist_sink`）。`stream_reader(buffer, task_id)` 的 buffer 是参数传入的——父 SSE 读的是父 buffer 对象，子事件写入子 buffer，天然不可见；同时不写 `chat_task_steps` / `chat_tasks`，不产生幽灵任务行。循环结束 `reclaim_memory_buffer(sub_task_id)` 回收。

子 Agent 内部步骤只在日志中记录（`logger.debug`），前端不可见。

P2 阶段可考虑（暂不实施）：
- 父 Agent 步骤中嵌套显示子 Agent 的步骤（折叠/展开）
- 显式把子 Agent 的 StepEmitter 事件经父级 SSE 转发（需改 `stream_orchestrator._SSE_FORWARD_TYPES` 白名单与嵌套渲染）

### 4.5 名称归一：其它生态名 → delegateagent

> **【核查】实施状态：已实施（P0）；设计正文与代码块口径有一处不一致。**
> - `TOOL_NAME_ALIASES.update` 4 条：`delegate_task`/`delegate_to_agent`/`call_agent`/`invoke_agent`→`delegateagent`（与设计代码块一致）；`normalize_tool_name`；`registry.get_tool`/`resolve_registered_tool` 内归一；不另注册；`subagent` 不收，留 `UNAVAILABLE_OFFICIAL_TOOLS`；`assistant`/`worker` 不收；`UNAVAILABLE_OFFICIAL_TOOLS` 不改。
> - **P1 `PARAM_ALIASES["delegateagent"].prompt→task` 已实现**（设计标 P1 可选）。
> - **不一致：** 设计开篇/§6.1 说"4 条大众名（subagent/delegate_task/delegate_to_agent/call_agent）、subagent 不收"，但设计代码块与代码实际是 `delegate_task/delegate_to_agent/call_agent/invoke_agent`。

主名称唯一：`delegateagent`。其它生态的叫法不另注册工具，而是走工具名别名层归一——复用现成的 `tools_alias_mapper.TOOL_NAME_ALIASES` 与 `normalize_tool_name`，零重复定义、零歧义。

**文件位置**：`backend/app/tools/tools_alias_mapper.py`（扩展 `TOOL_NAME_ALIASES`）

```python
# tools_alias_mapper.py — TOOL_NAME_ALIASES 新增条目（大众生态名 → 本系统主名）
# 已有 normalize_tool_name() 在 registry.get_tool / resolve_registered_tool 内被调用，
# 别名自动生效，无需改任何调用点。
TOOL_NAME_ALIASES.update({
    "delegate_task":    "delegateagent",  # CrewAI/MetaGPT 概念名
    "delegate_to_agent":"delegateagent",  # 社区 Multi-Agent 教程常见名
    "call_agent":       "delegateagent",  # 通用动宾叫法
    "invoke_agent":     "delegateagent",  # 企业生态叫法
})
```

**为什么刻意不收录 `subagent`**：`subagent` 在 `UNAVAILABLE_OFFICIAL_TOOLS = ("skill","subagent","patch","execute")`（`tools_alias_mapper.py:428`）里，也是 `tuning.agent.disabled_tools` 的默认禁用项，未注册时会被明确反馈"已禁用"。把它别名到已注册的 `delegateagent`，等于**静默放开用户显式禁用的名字**——设置页写着"禁用 subagent"，实际调用却通了。要么收编、要么保留禁用，不能两头都占；本版选择保留禁用（收编需同批删禁用名单、改设置页说明，属产品决策，见 §6 P2）。

**归链**：LLM 生成任一别名 → `normalize_tool_name` 命中 → 返回 `delegateagent` → 查注册表得到唯一工具实现。工具列表只暴露 `delegateagent` 一个，不浪费 token；参数名不变（`agent_id`/`task`/`context`/`wait`），schema 校验天然兼容。

**可选参数别名（P1，仅当 LLM 按 OpenCode 习惯传参时）**：OpenCode 的 `subagent` 用 `prompt` 传任务描述，本系统用 `task`，可在 `PARAM_ALIASES["delegateagent"]` 加 `{"prompt": "task"}`；`description` 无对应字段则按 `PARAM_DROP` 丢弃，避免白废一轮。

**YAGNI 边界**：只收录真实存在的高频大众名，不自造别名；新增别名需有调用实证。

---

## 5 实施文件清单

> **【核查】实施状态：本节为清单；逐项代码落点与偏差已在对应代码节标注。**
> - 新增文件 `agent_config.py`/`delegateagent_runner.py`/`delegateagent.py`/`delegateagent_schema.py`/`plugin_loader.py` 全部存在；`delegateagent_runner.py` 实际 352 行（估 ~230）。
> - `agent_config.py` 字段与 §5.1 不符（多 `tool_names`/`allow_delegate`/`provider`/`api_base`）。
> - **§5.1 `delegateagent` 写 `wait=False` 显式拒绝（P1 再放开）；实际 P1 `wait=False` 已落码**（但 `delegateagent` 对 `status=running` 处理有误）。
> - `plugin_loader.py` 设计标 P1，列入 §5.1 新增；已实现。
> - 修改文件见 §5.2 偏差。

### 5.1 新增文件

> **【核查】** 见上方总述；各文件职责/落点与代码一致，仅字段/`wait`/行数/P1 口径有偏差。

| 文件 | 职责 | 修改要点（落码位置） | 预估行数 |
|------|------|----------------------|----------|
| `backend/app/tools/agent/agent_config.py` | AgentConfig 数据类 + AgentRegistry + 拒绝清单 | ① `AgentConfig` 字段（agent_id/description/system_prompt/tool_categories/output_instruction/model/max_steps/timeout_s/track_task）；② `__post_init__` 构造即校验（id 正则、description 非空、max_steps 1..30、timeout 5..1800、分类非空、集合拷贝）；③ `effective_categories()` 扣拒绝分类；④ `AgentRegistry.register/unregister/get/list_configs/list_available`（重名默认报错、replace 显式覆盖）+ 模块级 `get_agent_registry`/`reset_agent_registry`（单例 + 测试复位）；⑤ `AgentRegistry.load_from_manifest()` 逐 manifest 容错解析（未知分类 warning 回落 fundamental、缺 name/类型错/`__post_init__` 校验不过/重名 ValueError 均返回 None 跳过）；⑥ `DELEGATE_DENY_CATEGORIES`/`DELEGATE_DENY_TOOLS` 复用算子层 PATH_* 表；⑦ 内置 3 Agent 注册。代码见 §2.1 | ~150 |
| `backend/app/services/agent/delegateagent_runner.py` | 子 Agent 运行器 | ① `run_delegate()` 查注册表→建子 UniversalAgent（独立 task_id / 工具子集 / excluded_tools / track_task）；② `_build_sub_task()` 自包含任务描述；③ `_delegate_scope()` 私有 buffer + 上下文副本 + 清空 delegate 回调、深度 +1；④ `_run_child_guarded()` 守卫协程（墙钟超时 + 父取消轮询 + 先收子任务再回收 buffer + `_CANCEL_GRACE_S` 有界放弃）；⑤ 从 `FinalStep.response` 提摘要 + `accumulated_usage` 回传；⑥ 深度硬顶 fail-closed。代码见 §2.5 | ~230 |
| `backend/app/tools/agent/delegateagent.py` | delegateagent 工具函数 | ① `delegateagent(agent_id, task, context, wait)` 从 ContextVar 取回调，空则 fail-closed 报错；② `wait=True` 同步返回摘要 + usage；③ `wait=False` 显式拒绝（P1 再放开）。代码见 §2.3 | ~60 |
| `backend/app/tools/agent/delegateagent_schema.py` | DelegateAgentInput pydantic 模型 | ① 入参模型字段（agent_id/task/context/wait）与约束；② 工具 Schema 由模型生成（§2.2）。 | ~30 |
| `backend/app/tools/agent/plugin_loader.py` | 插件扫描器 | ① `load_plugins()` 扫 `tuning.agent.plugins_dir`（缺省 `<code_root>/plugins`），目录不存在/空静默跳过；② 逐 manifest.json 调 `registry.load_from_manifest()`（容错在 agent_config 内，见上行⑤）；③ 调用点在 `agent_register._register_agent_tools()`。代码见 §2.1.1 | ~30 |

> `agent_config.py` 放 tools 层而非 services 层：`agent_register.py`（tools 层）要读注册表生成工具描述，放 services 会形成"工具层 import services"的越层。

### 5.2 修改文件

> **【核查】实施状态：列出的修改文件均已改；个别落点与口径有偏差。**
> - 实际 `tool_loader`/`tool_executor`/`tool_cache_manager`/`tool_runner` 在 `backend/app/services/agent/`（非 `backend/app/tools/`）；`tool_search` 在 `backend/app/tools/fundamental/`；`client_sdk` 在 `backend/app/llm/`；`hitl_confirmation` 在 `services/task/`。
> - `track_task=config.track_task` 已透传；`excluded_tools` 叠加 `DELEGATE_ALLOW_TOOLS` + read 元数据只读放行；`track_task` 门控 + 非 bool `TypeError`；`api_key or ""`；`MAX_PARALLEL_SUB_AGENTS=6` 已新增；4 别名 + `prompt→task`；`app.db`；`provider/api_base` 不依赖 model；新增可选 `api_key`；`_safe_int` usage；`exclude/tool_names` normalize。
> - `config/config.yaml` `tuning.agent.plugins_dir` 与 `stream_orchestrator` P2 未在本次核查中逐行验证。

| 文件 | 修改要点（落码位置） | 预估 |
|------|----------------------|------|
| `backend/app/tools/agent/agent_register.py` | ① `AGENT_TOOL_DESCRIPTIONS` 增 delegateagent 条目，description 走 `build_delegate_tool_description()` callable 动态生成（新增 Agent 零改字面量）；② `_register_agent_tools()` 内先调 `plugin_loader.load_plugins()` 再注册内置工具；③ 三张表（`AGENT_TOOL_DESCRIPTIONS`/`AGENT_INPUT_MODELS`/`AGENT_TOOL_EXAMPLES`）+ `tool_methods` 注册循环登记（漏 `tool_methods` 则工具根本没 register）。代码见 §4.1 | +20 行 |
| `backend/app/tools/context.py` | ① 新增 `_current_delegate_callback` ContextVar（签名 `async (agent_id, task, context, wait) -> Dict`）；② 新增 `_current_delegate_depth` ContextVar（并发各算各的，不能用模块全局）；③ set/reset/get 三件套。代码见 §2.4.1 | +20 行 |
| `backend/app/services/agent/tool_executor.py` | ① `execute_tool` 入口在 `set_current_session_id` 同处 set delegate 回调，finally 按 `_delegate_token is not None` 守卫 reset；② usage 合并（成功/失败分支都按 `data.usage` 存在性累加到父 accumulated_usage）。代码见 §2.4.2、§4.3 | +22 行 |
| `backend/app/services/agent/tool_runner.py` | ① `execute_tools` 内、扩展名纠错循环之后加并行上限校验（计数时对每个 call 调 `normalize_tool_name`——`all_calls` 里的 `tool_name` 可能仍是 `delegate_task`/`call_agent` 别名，直接比较会让别名全部绕过；`len>6` 拒绝多余委托）；② 三分支改用 `_active_calls` 执行 + 末尾按原索引回填（隐藏改动点：`_active_calls` 取号前移）。代码见 §2.5.1 | +12 行 |
| `backend/app/services/agent/tool_loader.py` | ① `init_tools(initial_categories, excluded_tools=None)` 存 `agent._excluded_tools` 单一权威 + 装载循环跳过被拒；② `load_category` 动态注入同样跳过（searchtool 灌回仍不可调）。代码见 §4.2① | +12 行 |
| `backend/app/services/agent/universal_agent.py` | ① `__init__` 增显式 `excluded_tools`/`track_task` 形参；② `init_tools` 与 `super().__init__` 按名传；③ 删掉 `**kwargs`（漏改即 TypeError，启动期 fail-fast）。代码见 §4.2② | +6 行 |
| `backend/app/services/agent/base_agent.py` | ① `__init__` 增 `track_task: bool = True`，仅门控 `tracker.create_task`；② 删掉 `**kwargs`；③ 子 Agent 不 finalize 遥测，token 经 accumulated_usage 回灌父。代码见 §2.7.3 | +2 行 |
| `backend/app/llm/client_sdk.py` | ① `LLMClient` 增只读 `api_key` property（现仅 `_api_key`，无 setter 防绕过 strip 清洗）；② 并行子 Agent 共享父 client 时的 api_key 读取。代码见 §4.2⑥ | +4 行 |
| `backend/app/tools/registry.py` | ① `list_tools`/`to_openai_tools` 解析 callable description；② `to_openai_tools` 增 `exclude` 形参并透传给 `tool_description.to_openai_tools`；③ `register(description=...)` 放宽为 `Union[str, Callable]`。代码见 §4.2④ | +8 行 |
| `backend/app/tools/tool_description.py` | ① `to_openai_tools` 增 `exclude: Optional[Set[str]]` 形参 + 可见性过滤；② description 取值支持 callable。代码见 §4.2③ | +8 行 |
| `backend/app/tools/tool_types.py` | ① `ToolMetadata.description` 放宽为 `Union[str, Callable[[], str]]`；② 新增 `resolved_description()` 作 callable 描述的唯一解析点（解析异常按空串返回 + warning，不让一个坏描述拖垮整张工具列表）。代码见 §6.2.2 | +12 行 |
| `backend/app/tools/fundamental/tool_search.py` | BM25 索引文本与检索结果回填两处改走 `resolved_description()`（直拼 callable 会在检索期抛 TypeError）。代码见 §6.2.2 | +2 行 |
| `backend/app/services/agent/tool_cache_manager.py` | ① `get_openai_tools(agent)` 调 `to_openai_tools` 时补传 `exclude=getattr(agent, "_excluded_tools", None)`（漏则可见性过滤形同不存在）。代码见 §4.2⑤ | +2 行 |
| `backend/app/tools/tool_constants.py` | ① 新增 `MAX_PARALLEL_SUB_AGENTS`（当前代码零命中，须同批新增）；② `MAX_DELEGATE_DEPTH` 不进本文件（只在 runner 内使用，留该模块）。代码见 §2.5.1 | +1 行 |
| `backend/app/tools/tools_alias_mapper.py` | ① `TOOL_NAME_ALIASES` 增 4 条大众名→`delegateagent`；② P1 可选 `PARAM_ALIASES["delegateagent"].prompt→task`。代码见 §4.5 | +5 行 |
| `config/config.yaml` | ① 新增 `tuning.agent.plugins_dir` 配置项（P1，缺省 `<code_root>/plugins`），供 `plugin_loader.load_plugins()` 读取；当前配置无此键（§2.1.1、§6 P1）。 | +2 行 |
| `backend/app/services/chat/stream_orchestrator.py` | ① P2 才改：`_SSE_FORWARD_TYPES` 增子 Agent 步骤类型 + 嵌套渲染（§6 P2）；P0/P1 不改。 | P2（暂缓） |

> `subagent` 不进别名表：它已在 `UNAVAILABLE_OFFICIAL_TOOLS` 里，且 `tuning.agent.disabled_tools` 可能按此名屏蔽；收进来会与"未注册即禁用"的判定打架。`assistant`/`worker` 同理不收。

### 5.3 不改的文件

| 文件 | 原因 |
|------|------|
| `react_loop.py` | 不改，父子共用同一 ReAct 引擎（零重写）；私有纯内存 buffer 满足其对 `get_stream_buffer` 的准入要求；全局清理由上下文副本隔离。P2 事件 sink 注入（`_publish` 接 `agent.event_sink`）属暂缓增量，不在 P0/P1 |
| `agent_runner.py` | 不改，子 Agent 是同步子过程而非用户任务，不套完整 runner（无台账/取消/重连/统计） |
| `step_emitter.py` | 不改，`emit_notice` / `emit_interact` 对 buffer 缺失已有降级分支 |
| `backend/app/services/task/hitl_confirmation.py` | 不改，P0 用"子 Agent 只读"绕开确认无出口问题（§2.7.2），不给子 Agent 开确认通道（注意在 `services/task/` 非 `services/agent/`） |
| `backend/app/services/task/task_registry.py` | 不改，`inject_system_notice`/`drain_inbox` 已存在（`task_registry.py:169`/`:239`），P1 异步回灌直接复用，不改函数体 |
| `backend/app/tools/agent/__init__.py` | 不改，已存在（`CATEGORY_MODULES["agent"]` 入口注释在此），新增 3 个 agent 包内文件无需改包初始化 |
| `tools_alias_mapper.UNAVAILABLE_OFFICIAL_TOOLS` | 不改，`subagent` 继续留在禁用名单，不影响 `delegateagent` 注册 |

---

## 6 优先级与里程碑

### 6.1 优先级总表

> **【核查】P0 逐项对码核查（先核查 P0；P1/P2 见各行标注）。实测：S0+S1+S2 探针本次运行 118 passed；S3–S5 探针存在于仓库，本次未重跑真实 LLM 链路（文档已载实施记录，本次为静态对码核实）。**
>
> **P0 已实施项：** `AgentConfig`+`AgentRegistry`（`__post_init__`/`unregister`/`reset_agent_registry`）+ 内置 3 Agent；`delegateagent` 同步 `wait=True`；`delegateagent_runner`（守卫协程 + 私有 buffer + 上下文克隆 + `_find_unattended_blocker` + `_close_quietly` + `_build_sub_task` + `_extract_summary` + model 分支）；ContextVar 回调 + 深度；`agent_register`；递归 fail-closed（深度硬顶 + 子作用域清空回调 + 拒绝分类/名单 + 元数据）；契约前置改造（`excluded_tools`/`exclude` 三处同源 + 显式形参删 `**kwargs` + `tool_types` callable + `api_key` property）；子 Agent 只读；耗时有界（`timeout_s`+父取消+`_CANCEL_GRACE_S`）；并行上限 `MAX_PARALLEL_SUB_AGENTS=6`；不落 `tasks` 台账；工具子集验证；SSE/DB 隔离；父授权不被清零；usage 四层合并 + DB 落账（成功/失败）；4 别名；`AgentConfig.model` + `shared_client` + `_owns_client=False` + `api_key`；SSE P0。
>
> **P0 偏差/未完全按设计：** 最重要6点已整改；`_find_unattended_blocker` 跳过 `visible_to_llm=False`；`_parent_http_client`；`api_key or ""`；`_build_sub_task` 键名截断；`tool_names`/`provider`/`api_base`/P1 异步等实际实现与 P0/P1 边界不符；§4.5 别名集合措辞不一致。
>
> **已整改6点：** `wait=false status=running`；`allow_delegate` 精确嵌套≤2；`track_task` 透传；usage `_safe_int`+非dict+异步记账；只读白名单 fail-closed+read元数据不过严；`provider/api_base` 不依赖model+可选`api_key`。
>
> **P1 对码核查（P0 之后）：** `wait=False` 异步**已落码**（`_execute_delegate`+`_background_delegates`+`inject_system_notice`/`drain_inbox`）且 `status=running` 成功；插件 manifest + `tuning.agent.plugins_dir` **已落码**；`tool_names` 名粒度 + `PARAM_ALIASES.prompt→task` **已落码**；`allow_delegate` 精确多层委托 + `provider`/`api_base` + 可选 `api_key` **已实现**；父取消经 `_run_child_guarded` + 父任务取消状态 + child `Task.cancel`，inbox 通知不依赖记账成功。
>
> **P2 对码核查：** `stream_orchestrator` `_SSE_FORWARD_TYPES` 未改；事件 sink 注入未做；`subagent` 未收编；A2A 远端未实现；P2+ 增量未实现（暂缓）。

| 阶段 | 内容 | 涉及文件（新增/修改） | 预估工期 |
|------|------|----------------------|----------|
| **P0** | AgentConfig + AgentRegistry（含 `__post_init__` 校验/`unregister`/`reset`）+ delegateagent_runner（含守卫协程 + 私有 buffer + 上下文克隆）+ delegateagent 工具（同步 `wait=True`）+ ContextVar（回调 + 深度）+ 注册 + 内置 3 个 Agent | 新增 `agent_config.py`/`delegateagent_runner.py`/`delegateagent.py`/`delegateagent_schema.py`；改 `agent_register.py`/`context.py` | 2-3 天 |
| **P0** | 递归防护 fail-closed：深度硬顶 + 子作用域清空 delegate 回调（不依赖工具可见性） | 改 `delegateagent_runner.py`（子作用域清空 + 深度校验）/ `context.py`（深度 ContextVar） | 含在首版 |
| **P0** | 契约前置改造（先于下述各项）：`init_tools`/`load_category` 增 `excluded_tools`、`to_openai_tools` 增 `exclude` 并沿线打通 `registry.to_openai_tools`/`tool_cache_manager.get_openai_tools`、`UniversalAgent`/`BaseAgent` 改显式形参并删掉 `**kwargs`（漏改即 `TypeError` 炸在构造时） | 改 `tool_loader.py`/`tool_types.py`/`tool_description.py`/`tool_search.py`/`registry.py`/`tool_cache_manager.py`/`universal_agent.py`/`base_agent.py`（8 个；`client_sdk.py` 见下方 api_key 行） | 0.5 天 |
| **P0** | 子 Agent 只读：拒绝分类/拒绝名单三处同源 + 构造后按 `needs_confirmation`/`confirm_fn` 整单拒绝 | 改 `agent_config.py`（拒绝清单）/ `tool_loader.py`/`tool_description.py`/`registry.py`/`tool_cache_manager.py`（三处同源） | 含在首版 |
| **P0** | 耗时有界：`timeout_s` 墙钟超时 + 父取消轮询联动 + "先收子任务再回收 buffer" | 改 `delegateagent_runner.py`（守卫协程） | 含在首版 |
| **P0** | 并行上限校验落地 `tool_runner.execute_tools`（`len(all_calls)` > 6 拒绝该轮多余委托）；`tool_constants.MAX_PARALLEL_SUB_AGENTS` 当前不存在，须同批新增 | 改 `tool_runner.py`/`tool_constants.py` | 0.5 天 |
| **P0** | 子 Agent 默认不落 `tasks` 台账（`AgentConfig.track_task=False`；`track_task=config.track_task` 透传到 `BaseAgent.__init__`） | 改 `agent_config.py`（字段）/ `delegateagent_runner.py`（传参）/ `universal_agent.py`/`base_agent.py`（门控） | 含在首版 |
| **P0** | 工具子集注入验证（子 Agent 确实看不到 AGENT 分类与写/删/bash 工具，且 searchtool 灌回后仍不可调） | 验证项，无独立改动；若失败回改 `tool_loader.py`/`tool_cache_manager.py` | 同 P0 |
| **P0** | SSE/DB 隔离验证（子步骤不进父 SSE、不写 chat_task_steps）+ 父授权不被清零 | 验证项，无独立改动；若失败回改 `delegateagent_runner.py`（私有 buffer/上下文副本） | 同 P0 |
| **P0** | usage 合并到父 Agent accumulated_usage（成功/失败分支都带 `data.usage`） | 改 `tool_executor.py`（合并）/ `delegateagent_runner.py`（回传 accumulated_usage） | 同 P0 |
| **P0** | 别名归一：`TOOL_NAME_ALIASES` 增 4 条大众名→`delegateagent`（§4.5，`subagent` 不收） | 改 `tools_alias_mapper.py` | 0.5 天 |
| **P0** | `AgentConfig.model` 配置层扩展位（默认继承父 LLM；非 None 时 `shared_client` 复用父池） | 改 `agent_config.py`（model 字段）/ `delegateagent_runner.py`（client 分支）/ `client_sdk.py`（api_key） | 含在首版 |
| **P0** | `LLMClient.api_key` 只读 property + 工具描述 callable 动态生成（新增 Agent 零改代码） | 改 `client_sdk.py`/`tool_description.py`/`registry.py` | 含在首版 |
| **P1** | `wait=False` 异步模式：立即返回 `delegate_id` + 完成经 `inject_system_notice`/`drain_inbox` 回灌 | 改 `delegateagent.py`/`delegateagent_runner.py`/`tool_executor.py`；复用 `task_registry.py`（不改） | 1-2 天 |
| **P1** | 插件 manifest 加载 + `tuning.agent.plugins_dir` 目录扫描 | 新增 `plugin_loader.py`（§5.1）；改 `agent_register.py`（调用点）；**改 `config/config.yaml`（新增 plugins_dir 配置项）** | 1 天 |
| **P1** | `tool_names` 名粒度过滤（构造 retry_engine 前筛 + `get_openai_tools` 接 tool_names）；可选 `PARAM_ALIASES["delegateagent"].prompt→task` | 改 `delegateagent_runner.py`/`tool_cache_manager.py`/`tools_alias_mapper.py` | 1 天 |
| **P1** | `allow_delegate=True` 精确多层委托（≤2 层）+ 跨 provider 模型（`AgentConfig` 增 provider/api_base；`provider/api_base` 不依赖 model；可选 `api_key` 不入插件 manifest） | 改 `agent_config.py`/`delegateagent_runner.py` | 1 天 |
| **P2** | SSE 子 Agent 步骤折叠透传（改 `_SSE_FORWARD_TYPES` + 嵌套渲染） | 改 `stream_orchestrator.py`（`_SSE_FORWARD_TYPES`）+ 前端嵌套渲染 | 暂缓 |
| **P2** | 事件 sink 注入（`react_loop._publish` 可注入 `agent.event_sink`），去掉私有 buffer 通行证 | 改 `react_loop.py`（P0/P1 不改，P2 才动）/ `base_agent.py` | 暂缓 |
| **P2** | 收编 `subagent` 别名（需同时从 `UNAVAILABLE_OFFICIAL_TOOLS` 移除，并处理 `tuning.agent.disabled_tools` 同名屏蔽后的语义） | 改 `tools_alias_mapper.py`/`config/config.yaml` | 暂缓 |
| **P2+ 远期增量** | §7.1 A2A 开放委托层：`AgentConfig.agent_source` + 远端 Agent Card 解析 + 远端子 Agent 过 fail-closed 校验；§7.2 会话内经验槽 + §7.3 effort 预算档（均默认 KISS 关闭或兼容不改动）；agent RL 兼容声明与图模式开关已分别融入 §1.4、§1.2，不占独立实施条目 | 改 `agent_config.py`（agent_source/经验槽/effort 字段）/ `delegateagent_runner.py`（远端 fail-closed）/ `plugin_loader.py`（远端来源） | 按需，1-3 天 |

### 6.2 阶段实施方案

§6.1 按优先级横切（P0/P1/P2），本节按"可独立验收的纵向阶段"纵切：把 P0 重排为 S0–S5 六个串行阶段，P1/P2/P2+ 各一个阶段。拆分遵循五条规则：

1. **单一职责**：一个阶段只交付一类能力，改动面封闭在本阶段列出的文件内，不跨阶段混改。
2. **可独立验收**：验收动作只依赖本阶段及之前阶段的产物，不依赖后续阶段；判据是"可执行动作 + 可观察结果"，不是"代码看起来对"。
3. **安全与能力同阶段**：只读、递归防护、耗时有界三类承诺必须与能力在同一阶段验收通过（§1.4"不接受静默降级"）。
4. **门禁串行**：前一阶段未全绿不得进入下一阶段；红项只能在本阶段修，不允许"带到下一阶段顺带修"。
5. **主链路始终可跑**：每个阶段收尾时主 Agent 既有链路（`backend/tests` 单测 + E2E-P0-03b）必须通过，工具列表与行为不退化。

#### 6.2.1 阶段划分与依赖

| 阶段 | 一句话目标 | 新增/修改文件 | 前置 | 对应 §6.1 条目 | 工期 |
|------|-----------|--------------|------|---------------|------|
| **S0** 契约前置改造 | 让 `excluded_tools`/`exclude`/`track_task`/`api_key` 这些新形参真实存在，默认行为零变化 | 改 `tool_loader.py`/`tool_types.py`/`tool_description.py`/`tool_search.py`/`registry.py`/`tool_cache_manager.py`/`universal_agent.py`/`base_agent.py`/`client_sdk.py`（9 个，明细见 §6.2.2） | — | P0 契约前置改造 + `api_key` property 与 callable 描述的形参部分 | 0.5 天 |
| **S1** 配置层 | 子 Agent"是什么"可声明、可校验、可查询 | 新增 `agent_config.py` | S0 | P0 首版（配置/注册表部分） | 0.5 天 |
| **S2** 委托通道 | 工具能取到回调、schema 正确、失败即结构化报错 | 改 `context.py`；新增 `delegateagent_schema.py`/`delegateagent.py` | S1 | P0 首版（工具层部分） | 0.5 天 |
| **S3** 子 Agent 运行器 | 跑通一次同步委托，同时兑现只读/递归/超时三条安全承诺 | 新增 `delegateagent_runner.py` | S2 | P0 首版（运行器/递归/只读/超时/台账/隔离） | 1 天 |
| **S4** 主链路接入 | 主 Agent 经 LLM 真能调起委托，用量记到父账，别名可用 | 改 `agent_register.py`/`tool_executor.py`/`tools_alias_mapper.py` | S3 | P0 注册/注入/usage/别名/动态描述 | 1 天（含别名 0.5） |
| **S5** 并行上限 | 单轮最多 6 个子 Agent，超出部分结构化拒绝且结果不错位 | 改 `tool_runner.py`/`tool_constants.py` | S4 | P0 并行上限校验 | 0.5 天 |
| **S6** P1 增强 | 异步委托、插件化、名粒度放行、多层委托 | 新增 `plugin_loader.py`；改 `delegateagent.py`/`delegateagent_runner.py`/`tool_executor.py`/`tool_cache_manager.py`/`tools_alias_mapper.py`/`config/config.yaml` | S5 | P1 四项 | 3–4 天 |
| **S7** P2 体验增量 | 前端可见子步骤、事件 sink 可注入、`subagent` 收编 | 改 `stream_orchestrator.py`/`react_loop.py`/`base_agent.py`/`tools_alias_mapper.py`/`config/config.yaml` + 前端嵌套渲染 | S6 | P2 三项 | 暂缓 |
| **S8** P2+ 开放生态 | A2A/MCP 远端 Agent 作为新来源，可靠性内核不放宽 | 改 `agent_config.py`/`delegateagent_runner.py`/`plugin_loader.py` | S7 | §7.1 | 按需 1–3 天 |

> P0 合计 ≈ 4 人日（0.5 + 0.5 + 0.5 + 1 + 1 + 0.5），与 §6.1 各 P0 行相加（0.5 契约 + 2.5 首版 + 0.5 并行 + 0.5 别名）一致。

#### 6.2.2 S0 契约前置改造（0.5 天）

**目标**：让后续阶段依赖的新形参/新属性真实存在，且**默认行为零变化**。这是唯一"改了但功能未上线"的阶段，验收标准因此是"零行为变化 + 漏改必炸"。

**改动面**（9 个既有文件，全部为增量形参或取值口径收敛，默认值/默认行为保持原语义）：

| 文件 | 落点 |
|------|------|
| `tool_loader.py` | `init_tools(initial_categories=None, excluded_tools=None)`（现 `:30`）：存 `agent._excluded_tools` 作单一权威，装载循环跳过；`load_category` 动态注入同样跳过 |
| `tool_types.py` | `ToolMetadata.description` 放宽为 `Union[str, Callable[[], str]]`；新增 `resolved_description()` 作 callable 描述的唯一解析点（解析异常按空串返回 + warning，不让一个坏描述拖垮整张工具列表） |
| `tool_description.py` | `to_openai_tools(registry, categories=None, tool_names=None, strict=False, exclude=None)`（现 `:29`）：`if name in _exclude: continue`；description 取值走 `meta.resolved_description()` |
| `registry.py` | `to_openai_tools` 增 `exclude` 并透传（现 `:413`）；`list_tools` 走 `resolved_description()`（现 `:374` 直读 `.description`）；`register`/`_update_existing_tool`/`_register_new_tool`/`register_tool` 的 `description` 放宽为 `Union[str, Callable[[], str]]` |
| `tool_cache_manager.py` | `get_openai_tools` 调 `to_openai_tools` 时补 `exclude=getattr(agent, "_excluded_tools", None)`（现 `:31` 只传 `categories`）；`_get_original_search_desc` 走 `resolved_description()`（现 `:54` 直读 `.description`） |
| `tool_search.py` | BM25 索引文本（现 `:110`）与结果回填（现 `:294`）两处走 `resolved_description()`：直接拼接 callable 会在检索期抛 TypeError |
| `universal_agent.py` | `__init__` 增显式 `excluded_tools`/`track_task`，删 `**kwargs`（现 `:50-57`）；`init_tools` 与 `super().__init__` 按名传 |
| `base_agent.py` | `__init__` 增 `track_task: bool = True`，删 `**kwargs`（现 `:52-58`）；`if track_task:` 门控 `tracker.create_task`（现 `:89-102` 无条件建行） |
| `client_sdk.py` | `LLMClient.api_key` 只读 property（`_api_key` 现 `:441`，无 setter，避免绕过 strip 清洗） |

> 表中「现 `:N`」指 **S0 改造前**的代码位置（S0 落码后行号整体下移，按符号名定位，不按行号）；「+N 行」为增量估算。
>
> 文件数由 7 改 9 的原因：原表按"`exclude` 传参链"列文件，漏了 callable 描述链路的两个读取点——`tool_types.py`（类型定义与解析点本身）与 `tool_search.py`（`grep '\.description'` 直读点中的 2 处）。只加 `exclude` 不改这两处，`delegateagent` 的动态描述一上线就会在 searchtool 检索期抛 TypeError。

**验收清单**：

1. **启动零报错**：`backend` 目录下 `python -c "import app.services.agent.universal_agent"` 无异常；`start_watch.bat` 起服务后健康检查通过。
   实测（2026-11-28 06:49–07:15）：`start_dev.ps1 watch` 真起进程后 `GET /health` 返回 200，`status=healthy`、`db_status=healthy`、`build.app_root` 指向工作区。`import` 探针覆盖不到启动期的建库、挂路由、构造 Agent 等路径，服务级冒烟必须真起进程，不能用 import 代替。
2. **主 Agent 工具列表零变化**：改造前先落一份快照（`sorted(t["function"]["name"] for t in get_openai_tools(agent))`），改造后同配置重建 Agent 再取，两份集合逐项相等、数量相同。快照须取自**真实改造前代码**（`git archive HEAD backend` 抽到临时目录 + 同一探针），不得用"复算等价"代替（`app` 代码已入库，archive 可用；测试未入库，回归基线不能照此办理，见 §6.2.11 第 2 条）。
3. **默认台账行为不变**：不传 `track_task` 构造主 Agent，`tasks` 表新增一行且 `_task_tracker` 非 None。
4. **fail-fast 生效**：`UniversalAgent(..., foo=1)` 抛 `TypeError`（`**kwargs` 已删）；`BaseAgent` 是 ABC、不能直接实例化，其"无 `**kwargs`"用 `inspect.signature(BaseAgent.__init__)` 断言不存在 `VAR_KEYWORD`（直接 `BaseAgent(..., foo=1)` 抛的 `TypeError` 来自"抽象类不可实例化"，与本项无关，不能当作证据）；`track_task=False` 时 `_task_tracker is None` 且 `tasks` 表零新增。
5. **拒绝清单三处贯通**：`UniversalAgent(initial_categories={FUNDAMENTAL, FILE}, excluded_tools={"write"})` 后——`_tools_dict` 无 `write`；`get_openai_tools` 名字集合无 `write`；手动 `load_category(FILE)` 后仍无 `write`。
6. **`api_key` 可读且只读**：`agent.llm_client.api_key` 返回非空字符串；赋值 `agent.llm_client.api_key = "x"` 抛 `AttributeError`。
7. **回归**：定向回归的失败集合与改造前基线**同一集合**（存量红项不计入本阶段，判据见 §6.2.11 第 2 条）。实测（2026-11-28 07:16–07:31）：
   - 范围：引用 S0 改动面的 63 个测试文件（`tool_loader`/`tool_description`/`registry`/`universal_agent`/`tool_cache_manager`/`tool_search`/`client_sdk`/`base_agent`/`tool_types`/`from app.tools`），`--timeout=60`；
   - 基线（9 个文件逐字节回退 HEAD，跑完按 sha256 校验恢复）：**15 失败 / 1635 通过**，243s；
   - 改造后：**15 失败 / 1635 通过**，237s；
   - 失败集合逐条相同（15 条存量红项：`test_artifacts_11_6` 3 条、`test_config_zen` 2 条、`test_critical_flow_deep_bugs` 2 条、`test_flow_deep_bugs` 1 条、`test_p1_layer_ownership` 2 条、`test_proc_host_stage345_real` 1 条、`test_tdd_26_29_quota` 1 条、`test_tdd_30_32_integration` 1 条、`test_tdd_59_63_bug_e_red` 2 条），**新增 0 条**；
   - 首轮改造后曾多出 3 条（`test_12_006/007/009_get_original_search_desc_*`）：`MagicMock` 未配置 `resolved_description()`，属测试替身未跟新契约（生产侧读的是真实 `ToolMetadata`）；已改测试替身并单类重跑 15/15 通过，同批全量重跑回到 15/1635；
   - 全量 `pytest -q` 不可用（多个用例挂满 `timeout=300`，实测 26% 处单条卡死，单次预计 40 分钟以上），故用定向集；全量口径判据仍按 §6.2.11 第 2 条执行。
   - E2E-P0-03b（真实后端 + 真实 LLM，非 mock）：**PASSED**，31.1s，5 次 LLM 调用，DB 22 步，工具链 `read → write → bash → write`，SSE 191 事件，一致性/步骤合理性/日志三项均 0 issue。
8. **存量红项清零**（2026-11-28 08:43）：基线里那 15 条逐条定性并修复，**15/15 通过**，不留"与本次无关"的借口。分类与处置：
   - **过时断言/夹具（13 条）**：`test_artifacts_11_6` 三条——产物上限现为"丢最早保最新"（`f10..f59` 而非 `f0..f49`）、`normalize_artifact` 现为五字段（`tool_name/name/path/form/type`）、`with_artifact_file` 已于 2026-11-21 删除并改为 `other_data["artifacts"]` + `app/utils/artifacts.py`；`test_config_zen` 两条——agnes 配置已无 `label` 键、sensenova 的 `glm-5.2` 已升 `glm-5.3`；`test_critical_flow_deep_bugs` 两条——`MetaStep(retrying)` 已于 2026-11-24 并入 notice 信封（`type=notice` + `kind=retrying`）；`test_flow_deep_bugs` 一条——`prepare_messages_for_llm` 早已是 async，补 `asyncio.run`；`test_tdd_26_29_quota`/`test_tdd_30_32_integration` 各一条——2026-11-20 起闸门为 `max_connections - HEADROOM`（10-2=8），原断言 `>=10`/`==10` 是加余量前旧契约；`test_tdd_59_63_bug_e_red` 两条——夹具缺 `msg_kind` 列、替身仍打 `mod.subprocess.run`（实际调用点已是 `mod.proc_run`）。
   - **真实分层违规（1 条）**：`test_p1_layer_ownership::test_utils_does_not_depend_on_upper_layers` 抓到 `app/utils/sse_formatter.py` 反向 import `app.tools.registry`。修法不是放宽门禁，而是把可见性判据改为上层注入：`format_agent_sse(..., visible_in_steps=None)` 保持 utils 纯格式化，两个 SSE 出口（`stream_orchestrator` 实时转发 + 重连回放）传 `tool_registry.visible_in_steps`，过滤语义与落点零变化。
   - **测试环境串味（1 条）**：`test_proc_host_stage345_real::test_stage5_proc_run_text_decoding`——外壳 `PYTHONIOENCODING=utf-8` 让子进程用 UTF-8 输出、父进程 `text=True` 按 locale(cp936) 解码必炸；实测原生 `subprocess.run(text=True)` 同环境同样失败，属夹具而非生产缺陷，显式剔除该变量使子进程编码与 locale 同源。
   - 验证：15 条定点重跑 **15 passed**；生产侧 `sse_formatter.py`/`stream_orchestrator.py` 的 F 类 lint 零新增（I001 为 HEAD 既有）；63 文件定向集改造后重跑 **1650 passed / 0 failed**（251s），与基线 1650 条总数一致，失败集合清空。

**S0 落码后补测发现并修复的静默失效点**（2026-11-28，攻击性用例 `backend/tests/probe_delegate_s0_edge.py`，首轮 8 条中 5 条失败）：

| # | 现象 | 后果 | 修法 |
|---|------|------|------|
| 1 | `excluded_tools="write"` 被 `set()` 拆成 `{'w','r','i','t','e'}` | 只读拒绝清单静默失效，`write` 仍在工具集 | `init_tools` 收到 str 直接 `TypeError`，形参标注 `Optional[Set[str]]` |
| 2 | 拒绝/白名单写别名不生效（如 `write_text`） | 名单写别名静默失效 | 两处名单统一过 `normalize_tool_name`（`write_text`→`write`） |
| 3 | `exclude="write"`/`tool_names="read"` 走 `in` 子串判定 | 静默多排除或少排除一批工具 | 两参数收到 str 直接 `TypeError` |
| 4 | `track_task="false"`/`0` 在 `if` 下为真 | 子 Agent 静默建台账行、进用户任务列表 | `BaseAgent.__init__` 非 bool 直接 `TypeError` |
| 5 | 底层 `_api_key` 为 `None` 时 `api_key` 返回 `None` | 标注 `-> str` 失真，调用方拿 `None` 建子 client 到请求期才炸 | `return self._api_key or ""` |

> 订正一处先前判断：`write_file` **不是** `TOOL_NAME_ALIASES` 的键（表内为 `writefile`/`write_text`/`write_text_file`/`writetext`/`writeetext`/`write_content`），"`exclude={'write_file'}` 不排除 `write`"只是"拒绝一个不存在的名字"，不构成缺口；真正的缺口是"别名不做归一"，已按第 2 条修复。修复后 18 条契约用例 + 12 条边界用例共 30 条全绿。

**开发启动器的崩溃自愈**（2026-11-28，非 S0 交付面，但直接影响验收第 1 项）：`watchfiles` 只在文件变更时重启子进程（`watchfiles/run.py` 的 `arun_process` 把 stop/start 全放在 `awatch` 循环内），子进程崩溃后它空转等待、服务永久失联——实测杀掉 `run_server` 后 30s 无监听、`watchfiles` 进程仍活。`backend/start_dev.ps1` 补两层：①清残留时上溯并**先杀**重载器守护进程（只杀监听者会被父进程立刻重生，实测 8s 内抢回端口），并按命令行精确清掉"子进程已死、watchfiles 还活"的孤儿链；②外层端口看护（启动宽限 60s，连续 10s 无监听即整体重起重载链）。实测：杀掉子进程后 25s 自愈，`/health` 200。

**退出标准**：1–8 全绿；日志无新增 warning（预期内的缺库提示除外）。

**失败回退**：本阶段全是"默认值/默认行为不变的增量形参与取值口径收敛"，回退只需 revert 这 9 个文件；若第 5 项失败，说明 `exclude` 传参链断了一环，按 `tool_cache_manager → registry → tool_description` 顺序逐段加打点定位，不得跳过。

#### 6.2.3 S1 配置层（0.5 天）

**目标**：把"某个子 Agent 是什么能力"变成可声明、构造即校验、可查询的注册表数据。

**改动面**：新增 `backend/app/tools/agent/agent_config.py`（§2.1 全量代码：字段、`__post_init__`、`effective_categories()`、`AgentRegistry` 六个方法 + `load_from_manifest`、`get/reset_agent_registry`、`DELEGATE_DENY_CATEGORIES`/`DELEGATE_DENY_TOOLS`、内置 3 Agent）。

**TDD 测试要求（先红后绿）**：

> 本阶段是纯数据层（无 I/O、无 LLM、无 DB），TDD 收益最高：全部用例 1s 内跑完，且每条断言都对应一条"配置写错了要到运行期才静默失控"的契约。纪律：**先写失败用例（红）→ 最小实现（绿）→ 重构（保持绿）**；禁止先写实现再补"能过就行"的测试，禁止为让断言变绿而放宽断言（如把 `pytest.raises` 改成 `except Exception: pass`）。

**测试文件**：`backend/tests/probe_delegate_s1_config.py`（本地探针，按 §6.2.11 第 4 条不提交）。模块尚不存在时首轮是 `ImportError`——这不算"红"；第一步先落字段骨架（空 `__post_init__`），让断言真正失败。

**A. 构造即校验（验收 1、2）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 最小合法配置的默认值 | 只给 `agent_id`/`description` → `tool_categories == {FUNDAMENTAL}`、`output_instruction is None`、`model is None`、`(max_steps, timeout_s, track_task) == (8, 300.0, False)`、`system_prompt == ""` |
| T02 | `agent_id` 非法 | `Researcher`（大写开头）/`1abc`（数字开头）/`"a"*33`（超长）/`""`（空）逐个抛 `ValueError`，消息含该 id；`123`/`None` 抛 `ValueError` 或 `TypeError`，消息含 `agent_id` |
| T02b | `agent_id` 边界合法 | `a`、`"a"*32`（32 字符上限）、`kb_analyst`、`probe2` 构造成功且 `agent_id` 原样 |
| T02c | `agent_id` 结尾换行 | `abc\n`、`"a"*32+"\n"`、`abc\r\n` 逐个抛 `ValueError`（`$` 锚点会放过结尾换行，必须全串匹配） |
| T03 | `description` 空白 | `""`/`"   "`/`"\n\t"` → `ValueError`，消息含 `description` |
| T04 | `max_steps` 越界 | `0`/`31`/`-1`/`100` → `ValueError`，消息含 `max_steps`；边界 `1`/`30` 通过 |
| T04b | `max_steps` 类型 | `"8"`/`8.5`/`True`/`None` → `TypeError`（禁止 `int()` 隐式强转，见下方落码口径） |
| T05 | `timeout_s` 越界 | `4`/`4.9`/`1801`/`0`/`-1` → `ValueError`；边界 `5`/`5.0`/`1800` 通过 |
| T05b | `timeout_s` 类型 | `"300"`/`True`/`None` → `TypeError` |
| T06 | `tool_categories` 空 | `set()`/`frozenset()` → `ValueError`，消息含 `tool_categories` |
| T06b | `tool_categories` 类型 | `"file"`/`["file"]`/`{FILE, "file"}` → `TypeError`（`set("file")` 会拆成单字符，见落码口径） |
| T07 | `track_task` 类型 | `"false"`/`0`/`1`/`None` → `TypeError`（只收 `bool`） |

**B. 集合语义与拒绝清单（验收 3、4、5）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T08 | 集合拷贝 | 外部 `{NETWORK, FUNDAMENTAL}` 构造后 `add(FILE)`/`discard(NETWORK)` → `config.tool_categories` 仍为 `{NETWORK, FUNDAMENTAL}`，且 `is not` 外部对象 |
| T10 | 拒绝分类扣减 | 传 `set(ToolCategory)` 全集 → `effective_categories() == {FILE, FUNDAMENTAL, NETWORK, DOCUMENT, DATAANALYSIS}`，且 `config.tool_categories` 仍是全集（不就地扣减） |
| T11 | 全为拒绝分类 | 只传 `DELEGATE_DENY_CATEGORIES` → 构造成功、`effective_categories() == set()`（合法但无工具，运行器照常跑空工具集） |
| T12 | 返回值是副本 | `eff = config.effective_categories(); eff.add(FILE)` → `config.tool_categories` 与再次调用的结果均不变 |
| T13 | 拒绝名单与 PATH_* 同源 | `DELEGATE_DENY_TOOLS >= set(WRITE_PATH_TOOLS) \| set(DELETE_PATH_TOOLS) \| set(DUAL_PATH_TOOLS)`；含 `bash`/`question`/`schedule`/`delegateagent`/`execute_sql`/`screen_capture`；不含 `read`/`find`/`searchweb`/`query_sql` |
| T14 | 拒绝分类精确 | `DELEGATE_DENY_CATEGORIES == {AGENT, SYSTEM, MEDIA, WIN_REGISTRY, DESKTOP, TIMER}`，与 `{FILE, FUNDAMENTAL, NETWORK, DOCUMENT, DATAANALYSIS}` 交集为空 |

**C. 注册表与单例（验收 6、7）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T16 | 重名注册 | 同 id 注册两次（第二次 `replace` 缺省）→ 抛 `ValueError` 且 `get()` 仍返回**第一个**对象（抛错时不得"先写后抛"） |
| T17 | 显式覆盖 | `register(新, replace=True)` → `get()` 返回新对象（`is` 断言），`list_configs()` 长度为 1 |
| T18 | 注销语义 | 存在 → `unregister` 返回 `True` 且 `get()` 为 `None`；再注销同一 id / 从未注册的 id → 返回 `False` |
| T19 | 列表语义 | 依次注册 `c_agent`/`a_agent`/`b_agent` → `list_available()` 按注册顺序返回三 id；`[c.agent_id for c in list_configs()]` 与 `list_available()` 逐项相等 |
| T20 | 单例身份 | `get_agent_registry() is get_agent_registry()` |
| T21 | 内置 3 Agent | `list_available() == ["researcher", "reviewer", "kb_analyst"]`；researcher `{NETWORK, FUNDAMENTAL}`、`max_steps=10`、`timeout_s=240`；reviewer `output_instruction` 非空、`max_steps=12`；kb_analyst `max_steps=10` |
| T22 | 复位 | 先注册 `transient` → `reset_agent_registry()` → 新对象 `is not` 旧对象、`get("transient") is None`、`list_available()` 重新为 3 个内置（防用例串态） |
| T23 | 唯一构造点 | 读 `agent_config.py` 源码 → `"AgentRegistry()"` 出现次数为 1；遍历 `backend/app/**/*.py` 除本文件外无 `AgentRegistry(` 命中 |

**D. manifest 容错（验收 8）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T24 | 合法 manifest | `{"name":"web_researcher","description":"…","tool_categories":["network","fundamental"],"max_steps":12,"timeout_s":300,"track_task":true}` → 返回 config、分类为 `{NETWORK, FUNDAMENTAL}`、**`track_task is False`**（插件不得自开台账）、已进入注册表 |
| T25 | 未知分类回落 | `tool_categories: ["no_such_cat"]` → 返回 config、`tool_categories == {FUNDAMENTAL}`，全程不抛 |
| T25b | 分类写成字符串 | `tool_categories: "file"` → 逐字符 warning 后回落 `{FUNDAMENTAL}`（不得把 `{'f','i','l','e'}` 灌进配置） |
| T26 | 缺 `name` / 校验不过 | `{"description":"x"}`、`{"name":"bad_id","description":""}`、`{"name":"Bad",…}`、`{"name":"steps0",…,"max_steps":0}` → 逐个返回 `None` 且 `list_available()` 仍为空；`logger.warning` 被调用且消息含 `manifest` |
| T27 | 与内置重名 | manifest `name="researcher"` → 返回 `None`，`get("researcher")` 仍是内置对象（未被冒名覆盖） |
| T28 | 坏输入不外抛 | JSON 语法错（`"{not json"`）、文件不存在、目录不存在 → 均返回 `None`，不抛异常 |
| T29 | 失败不粘 | 先加载一个非法 manifest（返回 `None`）→ 再加载合法 manifest 成功，`list_available() == ["good_one"]` |
| T29b | 插件不能提权 | manifest 写 `tool_categories: ["file","agent","system","media"]` + `track_task: true` → 返回 config，`effective_categories() == {FILE}`、`track_task is False` |

**E. 分层（退出标准）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T30 | 工具层零越层 | 读 `agent_config.py` 源码 → 不含 `app.services`（本模块只 import `app.logger`/`app.tools.*`） |

**落码口径（相对 §2.1 的四处字段类型收紧，均为 S0 已实证的同类静默失效）**：

| 字段 | §2.1 现写法 | 本条要求 | 不收的后果 |
|------|------------|---------|-----------|
| `max_steps` | `int(self.max_steps)` | `isinstance(x, int) and not isinstance(x, bool)`，否则 `TypeError` | `"8"`/`8.5`/`True` 静默通过，越界校验形同虚设 |
| `timeout_s` | `float(self.timeout_s)` | `isinstance(x, (int, float)) and not isinstance(x, bool)`，否则 `TypeError` | `"300"` 静默通过；`True` 被当成 1.0，错误信息误导排查方向 |
| `tool_categories` | 只判真假 | 必须 `Set[ToolCategory]`，str/list/含非法成员一律 `TypeError` | `set("file")` 拆成 `{'f','i','l','e'}`，`effective_categories()` 返回字符集，运行期工具子集静默失控 |
| `track_task` | 无校验 | 必须 `bool`，否则 `TypeError` | `"false"` 为真 → 子 Agent 静默进用户任务台账（S0 同款缺陷） |

> 这四处只改校验口径，不改字段语义与默认值；`load_from_manifest` 同样不做隐式强转——原值直传 `__post_init__` 作唯一校验点。manifest 是 JSON，数字与字符串混用属外部输入，类型非法（如 `true`、`"8"`、`8.5` 用于 `max_steps`）由外层 `try/except` 跳过该插件并 warning，不洗白成合法值（原"保持不变、解析后仍走严格校验"的说法不成立：强转发生在校验之前，会把非法输入变成合法 int/float）。

**红绿节奏（每轮只推进一组，跑完再进下一组）**：

| 轮次 | 先写的红用例 | 让它变绿的最小实现 |
|------|-------------|-------------------|
| R1 | T01、T02、T02b | 字段骨架 + `_ID_RE` 校验 |
| R2 | T03–T07 | `__post_init__` 其余校验（含四处类型收紧） |
| R3 | T08、T10–T12 | 集合拷贝 + `effective_categories()` |
| R4 | T13、T14 | `DELEGATE_DENY_CATEGORIES`/`DELEGATE_DENY_TOOLS` 两张表 |
| R5 | T16–T19 | `AgentRegistry` 六个方法 |
| R6 | T20–T23 | 单例 + 内置 3 Agent + `reset_agent_registry` |
| R7 | T24–T29b | `load_from_manifest` 容错（任何异常都返回 `None`） |
| R8 | T30 | 不改代码，只确认无越层 |

**测试代码**：

```python
# -*- coding: utf-8 -*-
"""S1 配置层 TDD 探针 — 小欧 2026-11-28

覆盖配置层的构造校验、集合语义、拒绝清单、注册表、单例与 manifest 容错全部契约。
本阶段是纯数据层，不 mock 任何生产依赖（无 LLM/DB/工具注册）；先红后绿，断言即契约。
运行：cd backend && python -m pytest tests/probe_delegate_s1_config.py -v --timeout=60
"""
import json
from pathlib import Path

import pytest

from app.tools.agent import agent_config as ac
from app.tools.agent.agent_config import (
    DELEGATE_DENY_CATEGORIES,
    DELEGATE_DENY_TOOLS,
    AgentConfig,
    AgentRegistry,
    get_agent_registry,
    reset_agent_registry,
)
from app.tools.tool_constants import DELETE_PATH_TOOLS, DUAL_PATH_TOOLS, WRITE_PATH_TOOLS
from app.tools.tool_types import ToolCategory as C


@pytest.fixture(autouse=True)
def _isolate_registry():
    """单例是进程级全局：每个用例前后复位，防用例互相串态"""
    reset_agent_registry()
    yield
    reset_agent_registry()


def make(**kw) -> AgentConfig:
    base = dict(agent_id="probe_agent", description="探针用子 Agent")
    base.update(kw)
    return AgentConfig(**base)


def manifest(tmp_path, dirname: str, payload) -> str:
    d = tmp_path / dirname
    d.mkdir()
    p = d / "manifest.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ------------------------------------------------ A. 构造即校验（验收 1、2）
def test_T01_minimal_config_defaults():
    c = make()
    assert c.tool_categories == {C.FUNDAMENTAL}
    assert c.output_instruction is None and c.model is None
    assert (c.max_steps, c.timeout_s, c.track_task) == (8, 300.0, False)
    assert c.system_prompt == ""


@pytest.mark.parametrize("bad", ["Researcher", "1abc", "a" * 33, "", "_abc", "a-b"])
def test_T02_agent_id_rejected(bad):
    with pytest.raises(ValueError) as ei:
        make(agent_id=bad)
    assert "agent_id" in str(ei.value)


@pytest.mark.parametrize("bad", [123, None])
def test_T02_agent_id_non_str_rejected(bad):
    with pytest.raises((ValueError, TypeError)) as ei:
        make(agent_id=bad)
    assert "agent_id" in str(ei.value)


@pytest.mark.parametrize("ok", ["a", "a" * 32, "kb_analyst", "probe2"])
def test_T02b_agent_id_accepted(ok):
    assert make(agent_id=ok).agent_id == ok


@pytest.mark.parametrize("bad", ["abc\n", "a" * 32 + "\n", "abc\r\n"])
def test_T02c_agent_id_trailing_newline_rejected(bad):
    """结尾换行不得放过：正则锚点 $ 会匹配换行前，必须全串匹配拒绝"""
    with pytest.raises(ValueError, match="agent_id"):
        make(agent_id=bad)


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_T03_description_blank_rejected(bad):
    with pytest.raises(ValueError, match="description"):
        make(description=bad)


@pytest.mark.parametrize("bad", [0, 31, -1, 100])
def test_T04_max_steps_out_of_range(bad):
    with pytest.raises(ValueError, match="max_steps"):
        make(max_steps=bad)


@pytest.mark.parametrize("ok", [1, 30])
def test_T04_max_steps_boundary(ok):
    assert make(max_steps=ok).max_steps == ok


@pytest.mark.parametrize("bad", ["8", 8.5, True, None])
def test_T04b_max_steps_type_strict(bad):
    """禁止 int() 强转：'8'/8.5/True 静默通过会让越界校验形同虚设"""
    with pytest.raises(TypeError, match="max_steps"):
        make(max_steps=bad)


@pytest.mark.parametrize("bad", [4, 4.9, 1801, 0, -1])
def test_T05_timeout_out_of_range(bad):
    with pytest.raises(ValueError, match="timeout_s"):
        make(timeout_s=bad)


@pytest.mark.parametrize("ok", [5, 5.0, 1800, 300.0])
def test_T05_timeout_boundary(ok):
    assert make(timeout_s=ok).timeout_s == float(ok)


@pytest.mark.parametrize("bad", ["300", True, None])
def test_T05b_timeout_type_strict(bad):
    with pytest.raises(TypeError, match="timeout_s"):
        make(timeout_s=bad)


@pytest.mark.parametrize("bad", [set(), frozenset()])
def test_T06_empty_categories_rejected(bad):
    with pytest.raises(ValueError, match="tool_categories"):
        make(tool_categories=bad)


@pytest.mark.parametrize("bad", ["file", ["file"], {C.FILE, "file"}])
def test_T06b_categories_type_strict(bad):
    """set('file') 会拆成 {'f','i','l','e'}，effective_categories() 静默变成字符集"""
    with pytest.raises(TypeError, match="tool_categories"):
        make(tool_categories=bad)


@pytest.mark.parametrize("bad", ["false", 0, 1, None])
def test_T07_track_task_type_strict(bad):
    with pytest.raises(TypeError, match="track_task"):
        make(track_task=bad)


# ------------------------------------------------ B. 集合语义与拒绝清单（验收 3、4、5）
def test_T08_categories_copied():
    outer = {C.NETWORK, C.FUNDAMENTAL}
    c = make(tool_categories=outer)
    assert c.tool_categories == outer and c.tool_categories is not outer
    outer.add(C.FILE)
    outer.discard(C.NETWORK)
    assert c.tool_categories == {C.NETWORK, C.FUNDAMENTAL}


def test_T10_effective_drops_denied_without_mutating():
    all_cats = set(C)
    c = make(tool_categories=all_cats)
    assert c.effective_categories() == {
        C.FILE, C.FUNDAMENTAL, C.NETWORK, C.DOCUMENT, C.DATAANALYSIS,
    }
    assert c.tool_categories == all_cats, "effective_categories() 不得就地扣减"


def test_T11_all_denied_effective_empty():
    c = make(tool_categories=set(DELEGATE_DENY_CATEGORIES))
    assert c.effective_categories() == set()


def test_T12_effective_returns_copy():
    c = make(tool_categories={C.FUNDAMENTAL})
    eff = c.effective_categories()
    eff.add(C.FILE)
    assert c.tool_categories == {C.FUNDAMENTAL}
    assert C.FILE not in c.effective_categories()


def test_T13_deny_tools_same_source_as_path_tables():
    assert DELEGATE_DENY_TOOLS >= (
        set(WRITE_PATH_TOOLS) | set(DELETE_PATH_TOOLS) | set(DUAL_PATH_TOOLS)
    )
    for name in ("bash", "question", "schedule", "delegateagent", "execute_sql", "screen_capture"):
        assert name in DELEGATE_DENY_TOOLS, f"{name} 必须在拒绝名单"
    for name in ("read", "find", "searchweb", "query_sql"):
        assert name not in DELEGATE_DENY_TOOLS, f"{name} 不该被拒（只读工具）"


def test_T14_deny_categories_exact():
    assert DELEGATE_DENY_CATEGORIES == {
        C.AGENT, C.SYSTEM, C.MEDIA, C.WIN_REGISTRY, C.DESKTOP, C.TIMER,
    }
    assert not (DELEGATE_DENY_CATEGORIES & {
        C.FILE, C.FUNDAMENTAL, C.NETWORK, C.DOCUMENT, C.DATAANALYSIS,
    })


# ------------------------------------------------ C. 注册表与单例（验收 6、7）
def test_T16_duplicate_register_keeps_original():
    r = AgentRegistry()
    first = make(agent_id="dup", description="第一个")
    second = make(agent_id="dup", description="第二个")
    r.register(first)
    with pytest.raises(ValueError, match="dup"):
        r.register(second)
    assert r.get("dup") is first, "重名抛错时不得先写后抛"


def test_T17_replace_overwrites():
    r = AgentRegistry()
    a = make(agent_id="x")
    b = make(agent_id="x", description="新")
    r.register(a)
    r.register(b, replace=True)
    assert r.get("x") is b and len(r.list_configs()) == 1


def test_T18_unregister_semantics():
    r = AgentRegistry()
    r.register(make(agent_id="tmp"))
    assert r.unregister("tmp") is True and r.get("tmp") is None
    assert r.unregister("tmp") is False
    assert r.unregister("never") is False


def test_T19_list_order_and_alignment():
    r = AgentRegistry()
    for aid in ("c_agent", "a_agent", "b_agent"):
        r.register(make(agent_id=aid))
    assert r.list_available() == ["c_agent", "a_agent", "b_agent"]
    assert [c.agent_id for c in r.list_configs()] == r.list_available()


def test_T20_singleton_identity():
    assert get_agent_registry() is get_agent_registry()


def test_T21_builtin_agents():
    r = get_agent_registry()
    assert r.list_available() == ["researcher", "reviewer", "kb_analyst"]
    rs = r.get("researcher")
    assert rs.tool_categories == {C.NETWORK, C.FUNDAMENTAL}
    assert (rs.max_steps, rs.timeout_s) == (10, 240.0)
    rv = r.get("reviewer")
    assert rv.output_instruction and rv.max_steps == 12
    assert r.get("kb_analyst").max_steps == 10


def test_T22_reset_drops_transient_and_rebuilds():
    r1 = get_agent_registry()
    r1.register(make(agent_id="transient"))
    reset_agent_registry()
    r2 = get_agent_registry()
    assert r2 is not r1
    assert r2.get("transient") is None
    assert r2.list_available() == ["researcher", "reviewer", "kb_analyst"]


def test_T23_single_construction_site():
    src = Path(ac.__file__).resolve().read_text(encoding="utf-8")
    assert src.count("AgentRegistry()") == 1, "AgentRegistry() 只允许出现在 get_agent_registry"
    app_dir = Path(ac.__file__).resolve().parents[2]
    hits = [
        str(p) for p in app_dir.rglob("*.py")
        if p.name != "agent_config.py"
        and "AgentRegistry(" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == [], f"全仓不得有第二处 AgentRegistry() 构造：{hits}"


# ------------------------------------------------ D. manifest 容错（验收 8）
def test_T24_manifest_ok(tmp_path):
    p = manifest(tmp_path, "ok", {
        "name": "web_researcher", "description": "多源搜索",
        "tool_categories": ["network", "fundamental"],
        "max_steps": 12, "timeout_s": 300,
        "track_task": True,          # 插件不得自开台账
    })
    r = AgentRegistry()
    c = r.load_from_manifest(p)
    assert c is not None and c.agent_id == "web_researcher"
    assert c.tool_categories == {C.NETWORK, C.FUNDAMENTAL}
    assert c.track_task is False
    assert r.get("web_researcher") is c


def test_T25_unknown_category_falls_back(tmp_path):
    p = manifest(tmp_path, "unknown", {
        "name": "u1", "description": "x", "tool_categories": ["no_such_cat"],
    })
    c = AgentRegistry().load_from_manifest(p)
    assert c is not None and c.tool_categories == {C.FUNDAMENTAL}


def test_T25b_categories_string_does_not_char_split(tmp_path):
    p = manifest(tmp_path, "cat_str", {
        "name": "u2", "description": "x", "tool_categories": "file",
    })
    c = AgentRegistry().load_from_manifest(p)
    assert c is not None and c.tool_categories == {C.FUNDAMENTAL}


@pytest.mark.parametrize("payload", [
    {"description": "缺 name"},
    {"name": "bad_id", "description": ""},
    {"name": "Bad", "description": "大写 id"},
    {"name": "steps0", "description": "x", "max_steps": 0},
])
def test_T26_invalid_manifest_returns_none(tmp_path, payload, monkeypatch):
    warnings = []
    monkeypatch.setattr(ac.logger, "warning", lambda msg, *a, **k: warnings.append(str(msg)))
    r = AgentRegistry()
    assert r.load_from_manifest(manifest(tmp_path, "bad", payload)) is None
    assert r.list_available() == []
    assert warnings and "manifest" in warnings[0]


def test_T27_duplicate_with_builtin_skipped(tmp_path):
    r = get_agent_registry()
    before = r.get("researcher")
    p = manifest(tmp_path, "dup", {"name": "researcher", "description": "冒名"})
    assert r.load_from_manifest(p) is None
    assert r.get("researcher") is before


def test_T28_bad_input_never_raises(tmp_path):
    d = tmp_path / "broken"
    d.mkdir()
    p = d / "manifest.json"
    p.write_text("{not json", encoding="utf-8")
    r = AgentRegistry()
    assert r.load_from_manifest(str(p)) is None
    assert r.load_from_manifest(str(tmp_path / "nope" / "manifest.json")) is None


def test_T29_failure_does_not_stick(tmp_path):
    r = AgentRegistry()
    assert r.load_from_manifest(
        manifest(tmp_path, "bad", {"name": "Bad", "description": "x"})
    ) is None
    good = manifest(tmp_path, "good", {"name": "good_one", "description": "x"})
    assert r.load_from_manifest(good) is not None
    assert r.list_available() == ["good_one"]


def test_T29b_plugin_cannot_escalate(tmp_path):
    p = manifest(tmp_path, "esc", {
        "name": "esc_agent", "description": "试图要写权限",
        "tool_categories": ["file", "agent", "system", "media"],
        "track_task": True,
    })
    c = AgentRegistry().load_from_manifest(p)
    assert c is not None
    assert c.effective_categories() == {C.FILE}
    assert c.track_task is False


# ------------------------------------------------ E. 分层（退出标准）
def test_T30_no_services_import():
    src = Path(ac.__file__).resolve().read_text(encoding="utf-8")
    assert "app.services" not in src, "工具层不得 import services（越层）"
```

**运行与退出判据**：

```powershell
cd backend
python -m pytest tests/probe_delegate_s1_config.py -v --timeout=60   # 分组推进时逐轮跑
python -m pytest tests/probe_delegate_s1_config.py -q                # 收尾：全绿
```

1. 上表用例 100% 通过，无 `skip`/`xfail`；收集数与用例数一致（`--collect-only -q` 核对）。
2. 红→绿每一轮都能指出"这条断言原来为什么红"，不允许"写完实现一次性跑绿"倒推测试。
3. 测试文件不提交；若某条断言与实现冲突，先判"断言是否在守护真实契约"，是则改实现、不是则改断言并在阶段记录里写清理由。

**验收清单**（验收项 1–8 对应的 TDD 用例见上方 A–E 各表）：

1. **agent_id 校验**：`Researcher`/`1abc`/长度 33 字符/空串 逐个抛 `ValueError`，错误信息含该 id；长度 32 字符的合法 id 通过。
2. **字段边界**：空 `description`、`max_steps=0`/`31`、`timeout_s=4`/`1801`、空 `tool_categories` 均抛 `ValueError`；边界值 `max_steps=1`/`30`、`timeout_s=5`/`1800` 通过。
3. **集合拷贝**：传入外部可变集合，构造后修改原集合，`config.tool_categories` 不受影响。
4. **拒绝分类**：给 `researcher` 传 `{NETWORK, FUNDAMENTAL, AGENT, SYSTEM, MEDIA, WIN_REGISTRY, DESKTOP, TIMER}`，`effective_categories() == {NETWORK, FUNDAMENTAL}`。
5. **拒绝名单**：`DELEGATE_DENY_TOOLS` 含 `write`/`delete`/`bash`/`question`/`schedule`/`delegateagent`/`execute_sql`/`screen_capture`；不含 `read`/`find`/`searchweb`。
6. **注册表语义**：重名 `register` 抛 `ValueError`；`replace=True` 覆盖后 `get()` 返回新对象；`unregister` 存在返回 True、不存在返回 False。
7. **单例与复位**：`get_agent_registry()` 两次返回同一对象；`reset_agent_registry()` 后重新获取为新对象且重新含 3 个内置；`list_available()` 为 `["researcher", "reviewer", "kb_analyst"]`。
8. **manifest 容错**：临时目录造 4 个 manifest（合法 / 未知分类 / 缺 `name` / 与内置重名），`load_from_manifest` 分别返回 config / 回落 fundamental 的 config / None / None，全程不抛异常且各有 warning 日志。

> 类型收紧项（`max_steps`/`timeout_s`/`tool_categories`/`track_task` 传错类型必须 `TypeError`）不在原 8 条内，按上方「落码口径」与 T04b/T05b/T06b/T07 一并验收；这四条与第 1–8 条同属"配置错了运行期才炸"的防线，不得当作可选项。

**退出标准**：1–8 全绿 + A–E 五组 TDD 用例全绿（无 `skip`/`xfail`）；注册表在进程内只被 `get_agent_registry()` 创建（全仓无第二处 `AgentRegistry()`）。

**失败回退**：只影响配置层，回退删除该文件即可；若第 8 项出现异常外泄，说明 `load_from_manifest` 的 try/except 覆盖面不足，须补到"任何异常都返回 None"。

**实施记录（2026-11-28）**：TDD 探针先落（首轮为导入红，再落字段骨架转断言红 `51 failed / 22 passed`），按 R1–R8 逐组实现后 **73 passed / 0 failed**；`ruff check` 全过（首轮 `I001` 导入排序已清零，F 类为零）。落码时确认一处口径偏差：`tool_categories` 成员非法初版按 §2.1 抛 `ValueError`，与 T06b 要求的 `TypeError` 冲突，已改正。三堂会审整改：`agent_id` 正则改全串匹配（`fullmatch`）拒绝结尾换行，补 T02c 三条回归；注释中的章节号/阶段号已清理。按用户要求不再产出阶段验收记录文件。

#### 6.2.4 S2 委托通道（0.5 天）

**目标**：工具层能拿到入口层注入的回调、schema 与契约一致、任何失败都返回结构化错误而不外抛。

**改动面**：改 `context.py`（`_current_delegate_callback`/`_current_delegate_depth` + set/reset/get）；新增 `delegateagent_schema.py`、`delegateagent.py`（§2.2/§2.3/§2.4.1 代码）。

**TDD 测试要求（严格按参考设计）**：

> **实施口径：本阶段落码以 §2.2 / §2.3 / §2.4.1 给出的参考代码为准，逐行照抄，不新增设计外的接口、不自行改写返回体文案。** 澄清上一版的一处措辞差异：§5.2/§6.2.4 写"深度也带 set/reset/get 三件套"，但 §2.4.1 参考代码只定义了 `get_delegate_depth()`，深度的 set/reset 由使用方直接操作 `_current_delegate_depth`（与 §2.5 运行器 `_d_token = _current_delegate_depth.set(...)` / `.reset(_d_token)` 同款）。本阶段按 §2.4.1 代码实施，不另造 `set_delegate_depth`/`reset_delegate_depth` 包装函数。

**测试文件**：`backend/tests/probe_delegate_s2_channel.py`（本地探针，按 §6.2.11 第 4 条不提交）。异步用例统一用 `asyncio.run(...)`（与仓库现有探针一致，不依赖 pytest-asyncio 配置）。

**A. 失败收口与透传（验收 1–4）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 未注入即错误 | 不设回调直接 `delegateagent(agent_id="researcher", task="x")` → `llm_data.status.exec_code == "error"`、`detail` 含"无可用 delegate_callback"、不外抛 |
| T02 | 成功契约 | 注入返回 `{status:"success",summary:"结论",usage:{total_tokens:12},steps:3}` 的回调 → `data` 含 `agent_id`/`summary`/`usage`/`steps` 且逐项相等、`other_data.duration_ms` 为非负 `int`、`exec_code == "success"`；同步记录回调实收的 `agent_id`/`task`/`context`/`wait` 并断言一致 |
| T03 | 异常收口 | 回调抛 `RuntimeError("boom")` → error 结构、`detail` 含 `boom`、不外抛 |
| T04 | wait 透传 | `wait=False` → 回调实收 `wait=False`（本阶段只透传，拒绝在 S3）；其余字段与 T02 相同 |

**B. ContextVar 隔离（验收 5、6）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T05 | 作用域可见与复位 | `set_current_delegate_callback(cb)` 后 `asyncio.create_task` 内取到的就是 `cb`；父侧仍为 `cb`；`reset(token)` 后父侧为 `None` |
| T06 | 并发不串味 | 两个并发任务各自 set 不同回调 → 各自读到自己的回调；各自 reset 后父侧仍为 `None` |
| T07 | 默认深度 | `get_delegate_depth() == 0` |
| T08 | 深度并发隔离 | 按 §2.4.1/§2.5 用法直接 `_current_delegate_depth.set(1)` / `.set(0)`，并发各读各的 → 结果 `[1, 0]`；reset 后父侧仍为 0 |

**C. Schema（验收 7）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T09 | Schema 形状 | `DelegateAgentInput.model_json_schema()` → `required == ["agent_id","task"]`、`wait` 默认 `True`、type 为 object |
| T10 | task 长度边界 | `task` 长 500 → 构造成功；长 501 / 空串 → 抛 `ValueError` |
| T11 | 可注册 | 把 `model_json_schema()` 作为 `input_schema` 交给 `tool_registry.register` → `get_tool` 非 None；finally `unregister` 复原 |

**D. 分层（退出标准）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T12 | 工具层零越层 | 读 `delegateagent.py`/`delegateagent_schema.py` 源码 → 不含 `app.services` |

**红绿节奏**：R1 = T01（骨架只落签名与"未注入"分支）→ R2 = T02–T04（回调调用与三分支返回体，照 §2.3 代码）→ R3 = T05–T08（§2.4.1 ContextVar）→ R4 = T09–T11（§2.2 Schema）→ R5 = T12（分层核对，不改代码）。

**测试代码**：

```python
# -*- coding: utf-8 -*-
"""S2 委托通道 TDD 探针 — 小欧 2026-11-28

严格按参考设计，不新增设计外接口；深度 set/reset 直接操作 ContextVar。
运行：cd backend && python -m pytest tests/probe_delegate_s2_channel.py -v --timeout=60
"""
import asyncio
from pathlib import Path

import pytest

from app.tools import context as ctx
from app.tools.agent import delegateagent as da
from app.tools.agent.delegateagent_schema import DelegateAgentInput
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory


@pytest.fixture(autouse=True)
def _clean_callback():
    tok = ctx.set_current_delegate_callback(None)
    yield
    ctx.reset_current_delegate_callback(tok)


def _ok():
    return {"status": "success", "summary": "结论",
            "usage": {"total_tokens": 12}, "steps": 3}


# ------------------------------------------------ A. 失败收口与透传（验收 1–4）
def test_T01_no_callback_returns_structured_error():
    r = asyncio.run(da.delegateagent(agent_id="researcher", task="x"))
    assert r["llm_data"]["status"]["exec_code"] == "error"
    assert "无可用 delegate_callback" in r["llm_data"]["status"]["detail"]


def test_T02_success_contract():
    seen = {}

    async def cb(agent_id, task, context, wait):
        seen.update(agent_id=agent_id, task=task, context=context, wait=wait)
        return _ok()

    tok = ctx.set_current_delegate_callback(cb)
    try:
        r = asyncio.run(da.delegateagent(
            agent_id="researcher", task="查一下", context={"k": "v"}
        ))
    finally:
        ctx.reset_current_delegate_callback(tok)
    assert r["llm_data"]["status"]["exec_code"] == "success"
    assert r["data"] == {
        "agent_id": "researcher", "summary": "结论",
        "usage": {"total_tokens": 12}, "steps": 3,
    }
    d = r["other_data"]["duration_ms"]
    assert isinstance(d, int) and d >= 0
    assert seen == {
        "agent_id": "researcher", "task": "查一下", "context": {"k": "v"}, "wait": True,
    }


def test_T03_callback_exception_is_collected():
    async def cb(**kw):
        raise RuntimeError("boom")

    tok = ctx.set_current_delegate_callback(cb)
    try:
        r = asyncio.run(da.delegateagent(agent_id="researcher", task="x"))
    finally:
        ctx.reset_current_delegate_callback(tok)
    assert r["llm_data"]["status"]["exec_code"] == "error"
    assert "boom" in r["llm_data"]["status"]["detail"]


def test_T04_wait_passthrough():
    seen = {}

    async def cb(**kw):
        seen.update(kw)
        return _ok()

    tok = ctx.set_current_delegate_callback(cb)
    try:
        asyncio.run(da.delegateagent(agent_id="researcher", task="x", wait=False))
    finally:
        ctx.reset_current_delegate_callback(tok)
    assert seen["wait"] is False


# ------------------------------------------------ B. ContextVar 隔离（验收 5、6）
def test_T05_callback_visible_in_task_and_reset_restores():
    async def cb(**kw):
        return _ok()

    async def child():
        return ctx.get_current_delegate_callback()

    async def parent():
        return await asyncio.create_task(child())

    tok = ctx.set_current_delegate_callback(cb)
    try:
        assert asyncio.run(parent()) is cb
        assert ctx.get_current_delegate_callback() is cb
    finally:
        ctx.reset_current_delegate_callback(tok)
    assert ctx.get_current_delegate_callback() is None


def test_T06_concurrent_callbacks_do_not_pollute():
    async def cb_a(**kw):
        return _ok()

    async def cb_b(**kw):
        return _ok()

    async def worker(cb):
        tok = ctx.set_current_delegate_callback(cb)
        try:
            await asyncio.sleep(0)
            return ctx.get_current_delegate_callback() is cb
        finally:
            ctx.reset_current_delegate_callback(tok)

    async def main():
        return await asyncio.gather(worker(cb_a), worker(cb_b))

    assert asyncio.run(main()) == [True, True]
    assert ctx.get_current_delegate_callback() is None


def test_T07_default_depth_zero():
    assert ctx.get_delegate_depth() == 0


def test_T08_depth_isolation_between_concurrent_tasks():
    async def worker(target):
        tok = ctx._current_delegate_depth.set(target)
        try:
            await asyncio.sleep(0)
            return ctx.get_delegate_depth()
        finally:
            ctx._current_delegate_depth.reset(tok)

    async def main():
        return await asyncio.gather(worker(1), worker(0))

    assert asyncio.run(main()) == [1, 0]
    assert ctx.get_delegate_depth() == 0


# ------------------------------------------------ C. Schema（验收 7）
def test_T09_schema_shape():
    schema = DelegateAgentInput.model_json_schema()
    assert schema["type"] == "object"
    assert schema["required"] == ["agent_id", "task"]
    assert schema["properties"]["wait"]["default"] is True


def test_T10_task_length_bounds():
    assert DelegateAgentInput(agent_id="researcher", task="x" * 500).task == "x" * 500
    with pytest.raises(ValueError):
        DelegateAgentInput(agent_id="researcher", task="x" * 501)
    with pytest.raises(ValueError):
        DelegateAgentInput(agent_id="researcher", task="")


def test_T11_schema_can_be_registered():
    name = "s2_probe_delegate_schema"
    try:
        tool_registry.register(
            name=name, description="探针", category=ToolCategory.AGENT,
            implementation=lambda **kw: _ok(),
            input_schema=DelegateAgentInput.model_json_schema(),
        )
        assert tool_registry.get_tool(name) is not None
    finally:
        tool_registry.unregister(name)


# ------------------------------------------------ D. 分层（退出标准）
def test_T12_no_services_import():
    base = Path(da.__file__).parent
    for name in ("delegateagent.py", "delegateagent_schema.py"):
        src = (base / name).read_text(encoding="utf-8")
        assert "app.services" not in src, f"{name} 不得 import services"
```

**退出判据**：1–7 与 T01–T12 全绿（无 `skip`/`xfail`）；探针不提交。

**验收清单**：

1. **未注入即失败**：直接 `await delegateagent(agent_id="researcher", task="x")`，返回 `llm_data.status.exec_code == "error"`，detail 含"无可用 delegate_callback"，且不抛异常。
2. **成功契约**：注入返回固定字典的回调后，`data` 含 `agent_id`/`summary`/`usage`/`steps`，`other_data.duration_ms` 为非负整数，`llm_data.status.exec_code == "success"`。
3. **异常收口**：回调抛 `RuntimeError("boom")`，工具返回 error 结构且 detail 含 `boom`，不向上抛。
4. **wait 透传**：`wait=False` 时回调实收 `wait=False`（本阶段只透传，拒绝在 S3）。
5. **ContextVar 隔离**：`set_current_delegate_callback(cb)` 后 `asyncio.create_task` 内可见；`reset` 后父侧为 None；两个并发任务各自 set 不同回调互不污染。
6. **深度隔离**：默认 `get_delegate_depth() == 0`；某任务内 `set(1)` 不影响并发另一任务的 0。
7. **Schema**：`DelegateAgentInput.model_json_schema()` 的 required 为 `["agent_id", "task"]`，`wait` 默认 `True`，`task` 有 500 字上限；该 schema 可直接作为 `input_schema` 交给 `tool_registry.register`（注册动作在 S4）。

**退出标准**：1–7 全绿；工具函数内无 `app.services.*` 导入（工具层零越层，用 `grep` 核对）。

**失败回退**：回退三个文件；若第 5 项在并发下失败，说明用了模块级全局而非 ContextVar，必须改回 ContextVar（模块全局会被 6 路并发互相污染）。

**实施记录（2026-11-28）**：首轮导入红，按 §2.2/§2.3/§2.4.1 参考代码逐行落码后探针 **12 passed / 0 failed**，`ruff check` 全过。深度只按 §2.4.1 参考代码提供 `get_delegate_depth()`，未新增 `set_delegate_depth`/`reset_delegate_depth` 包装函数；并发隔离用例直接操作 `_current_delegate_depth`（与 §2.5 运行器同款），未越出设计。三堂会审整改：注释中的章节号已清理。按用户要求不再产出阶段验收记录文件。

#### 6.2.5 S3 子 Agent 运行器（1 天，关键路径）

**目标**：真跑通一次同步委托，并在同一阶段兑现"只读 + 递归 fail-closed + 耗时有界 + 作用域隔离"四项承诺。这是全设计的安全核心，验收项最多、最不允许"大概通过"。

**改动面**：新增 `backend/app/services/agent/delegateagent_runner.py`（§2.5 全量：`run_delegate`/`_build_sub_task`/`_extract_summary`/`_delegate_scope`/`_run_child_guarded`/`_find_unattended_blocker`/`_close_quietly`/`_usage_of` + 深度硬顶 + model 分支）。

**TDD 测试要求（先红后绿，安全项优先落绿）**：

> 本阶段是全设计唯一同时触碰真实 LLM、真实工具注册表、真实 SQLite 与异步取消/超时的阶段，不能照搬 S1「1s 全绿」的节奏。纪律不变：**先写失败用例（红）→ 最小实现（绿）→ 重构（保持绿）**；禁止先落实现再补「能过就行」的用例，禁止为变绿而放宽断言（把 `pytest.raises` 改成 `except: pass`、把「summary 含超时」改成只判 `status`）。与 S1/S2 的差别只有两处：① 模块不存在时的 `ImportError` 不算红，第一步先落函数签名与四个早退分支（未知 id / 父已取消 / `wait=False` / 深度超限）让断言真正失败；② 真实 LLM 有随机性，断言只锁**结构与可判定事实**（`status`、summary 关键字、`usage/steps` 数值关系、耗时上界、DB/buffer 行），不锁完整文案。全程只允许两类**观测型**打点——构造器 spy（包装真构造器、记录子 Agent 实例）、client 工厂 spy（包装真工厂、记录独立 client 句柄）；唯一的行为替换是 T16 的构造故障注入，且必须 `finally` 还原。禁止 mock LLM 返回、禁止假 DB、禁止替换 `run_react_cycle` 实现。

**测试文件**：`backend/tests/probe_delegate_s3_runner.py`（本地探针，按 §6.2.11 第 4 条不提交）。运行：`cd backend && python -m pytest tests/probe_delegate_s3_runner.py -v --timeout=90`（T10 含约 12s 超时窗口，单条上限 90s）。用例顺序 A→E 与下方红绿节奏同序。

**A. 同步成功与显式拒绝（验收 1–4）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 同步成功契约 | 真实父 Agent + 真实 researcher，`task="一句话回答 1+1=几，不要调用工具"` → `status=="success"`、`summary` 非空且含 `2`、不含 `http`（排除原始网页罗列）、`usage.total_tokens>0`、`steps>=1`；spy 记录的子 `task_id` 匹配 `^sub-{父task}-researcher-[0-9a-f]{6}$` |
| T02 | 未知 id | `agent_id="nope"` → error，summary 列出 `researcher`/`reviewer`/`kb_analyst`；spy 记录构造次数为 0（查表失败不得先建对象） |
| T03 | wait=False 显式拒绝 | `wait=False` → error，summary 含「P1 能力，当前版本未实现」；构造次数为 0（不得静默按同步跑） |
| T04 | 父已取消不启动 | `await register_task(父task)` → `await set_cancelled(父task)` → `run_delegate` 返回 error、summary 含「父任务已取消，跳过委托」，构造次数为 0；`finally cleanup_task` |

**B. 只读与递归防护（验收 5–9，安全核心；任一红即不得进 S4）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T05 | 分类只读 | 取 spy 捕获的子 Agent → `_tools_dict` 键与 `DELEGATE_DENY_TOOLS` 交集为空（含 write/delete/move/copy/rename/edit/bash/question/schedule/delegateagent/execute_sql/screen_capture）；`_loaded_categories` 与 `{AGENT, SYSTEM, MEDIA, WIN_REGISTRY, DESKTOP, TIMER}` 交集为空 |
| T06 | 动态灌回仍不可调 | 在子 Agent 实例上调 `_tool_loader.load_category(ToolCategory.AGENT)`（`_retry_engine` 与 `_tools_dict` 同一 dict 引用）→ `_tools_dict` 仍无 `question`/`schedule`；`invalidate_tool_cache` 后 `get_openai_tools` 的 function name 集合亦无；三处同源全部生效，红则回 S0 |
| T07 | 子作用域回调清空 | spy 钩子只**观测** `run_react_cycle` 入口：`get_current_delegate_callback() is None` 且 `_current_delegate_depth.get()==1`（父侧预置 0）；钩子把结果记入列表而非在子任务内 `assert`（子任务异常会被 `run_delegate` 收口成 error，断言红信号会失真）；返回后父侧回调仍是注入值、深度仍为 0 |
| T08 | 深度硬顶 | `tok=_current_delegate_depth.set(1)` → `run_delegate` 返回 error、summary 含「委托深度超限」；`finally reset(tok)` 后仍为 1（函数内不得 reset 调用方的 token） |
| T09 | 确认类工具兜底 | 临时 `tool_registry.register` 一个 `needs_confirmation=True` 的 FUNDAMENTAL 工具 `s3_probe_confirm` → `run_delegate(agent_id="reviewer")` 返回 error、summary 含该工具名与「已拒绝委托」；`finally unregister` |

**C. 资源与收口（验收 10–11）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T10 | 墙钟超时 | 临时注册 `timeout_s=5` 的 config，给一个明显超 5s 的任务（提示写 3000 字长文）→ error、summary 含「超时」；`elapsed <= timeout_s + runner._CANCEL_GRACE_S + 2×runner._POLL_S + 2`；随后再正常委托一次成功（证明子任务已收干净、buffer 未被撞）；不得靠加大 `_CANCEL_GRACE_S` 让用例变绿 |
| T11 | 父取消联动 | `register_task(父task)` → `asyncio.create_task(run_delegate(...))`，轮询 spy 确认子 Agent 已构造后 `await set_cancelled(父task)` → 委托在 `<=2×_POLL_S+2` 内以 `asyncio.CancelledError` 结束并向上传播；`agent_streams` 无 `sub-` 前缀键；`finally cleanup_task`。任务提示要足够长，避免子任务抢先完成导致假绿 |

**D. 台账 / SSE / 授权隔离（验收 12–14）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T12 | 台账与遥测 | 委托后查 `db.get_conn("task_tracker")` 的 `tasks`、`db.get_conn("chat")` 的 `chat_tasks`/`chat_task_steps`：`task_id LIKE 'sub-%'` 行数均为 0；子 `TaskTelemetry` 未 finalize 时既不在 `react_loop` 结尾抛异常也不留悬挂；父 `accumulated_usage` 深拷贝前后逐键相等（合并留给 S4） |
| T13 | SSE 隔离 | `create_task_stream_buffer(父task,"")` 取 `event_log` 长度快照 → 委托后父 buffer 长度不变、子步骤只在日志出现；`agent_streams` 中 `sub-` 键为 0；`finally reclaim_memory_buffer(父task)` |
| T14 | 授权不串味 | `temp_auth._authorized_paths.set({Path("F:/s3_probe"): True})` → 委托后父侧 `get_authorized()` 逐键相同（子侧 `clear_temp_auth` 只作用于 `copy_context()` 副本）；`finally` 用原 token reset |

**E. client 与构造失败（验收 15–16）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T15 | model 分支 | 临时 config 的 `model` 设为父 `llm_model.model`（确保走 `create_llm_client` 分支）→ 委托成功；factory spy 记录 1 个独立 client，`._client is not 父._client`；返回后独立 client `_client.is_closed is True`，父 `llm_client._client.is_closed is False` |
| T16 | 构造失败收口 | 按验收第 16 项：`monkeypatch` 把 `runner.UniversalAgent` 临时替换为「构造即抛 `RuntimeError("构造故障注入")`」的可调用对象（只换构造器，不 mock LLM/工具/DB），model 非 None 走独立 client；factory spy 留句柄 → 返回 error、summary 含注入文案、句柄 `_client.is_closed is True`（`_close_quietly` 已执行）；`finally` 还原 |

**打点边界（红绿之外的纪律）**：允许 = 构造器 spy / client 工厂 spy / T16 构造器故障注入 / 临时注册再注销探针工具；禁止 = 替换 `run_react_cycle`、替 LLM 返回固定摘要、用假 SQLite 连接、把 `DELEGATE_DENY_TOOLS` 临时改小来让 T05 变绿。每个 fixture 的 `monkeypatch`/`unregister`/`reclaim` 都必须在 `finally` 或 fixture 卸载时还原，否则下一条用例会出现「串味假红」。

**红绿节奏（每轮只推进一组，全绿再进下一组）**：

| 轮次 | 先写的红用例 | 让它变绿的最小实现 |
|------|-------------|-------------------|
| R1 | T02、T03、T04、T08 | 先落模块与函数签名 + 四个早退分支（查表 / 取消 / wait / 深度），不做任何子 Agent 构造 |
| R2 | T01 | 查表后的成功路径：`_build_sub_task` / `_extract_summary` / `_usage_of` + `sub-{父}-{id}-{6hex}` 生成 |
| R3 | T05、T06 | 只读分类扣减 + `DELEGATE_DENY_TOOLS` 三处同源（依赖 S0 的 `excluded_tools` 链） |
| R4 | T07、T09 | `_child()` 内回调置 None + 深度 +1；`_find_unattended_blocker` 兜底 |
| R5 | T10、T11 | `_run_child_guarded` 守卫协程：`timeout_s` 墙钟 + 父取消轮询 + cancel 后有界等待 |
| R6 | T12、T13、T14 | `_delegate_scope` 私有 buffer + `copy_context()`，收口顺序「先收子任务、再回收 buffer」 |
| R7 | T15、T16 | `config.model` 的独立 client 分支（复用父池）+ `try/except` 构造失败与 `_close_quietly` |
| R8 | 回归 | 本探针 + S0/S1/S2 探针全跑、`ruff check` 全过；无 `skip`/`xfail` 才算本阶段可提交 |

**测试代码**：

```python
# -*- coding: utf-8 -*-
"""S3 子 Agent 运行器 TDD 探针 — 小欧 2026-11-28

真实 LLM / 工具 / SQLite；只做构造器与 client 工厂的观测型 spy，唯一行为注入是 T16 的构造故障。
所有 monkeypatch 在 fixture 卸载时还原；探针按仓库铁律不入库（§6.2.11 第 4 条）。
运行：cd backend && python -m pytest tests/probe_delegate_s3_runner.py -v --timeout=90
"""
import asyncio
import copy
import os
import re
import time
from pathlib import Path

import pytest

from app.db import database as db
from app.db.models.chat_models import ModelRef
from app.llm import client_sdk
from app.llm.client_sdk import create_llm_client
from app.safety import temp_auth
from app.services.agent import delegateagent_runner as runner
from app.services.agent.tool_cache_manager import get_openai_tools, invalidate_tool_cache
from app.services.agent.universal_agent import UniversalAgent
from app.services.model.resolver import get_ai_config_resolver
from app.services.task import task_registry, task_state
from app.tools import ensure_tools_registered
from app.tools.agent.agent_config import DELEGATE_DENY_TOOLS, AgentConfig, get_agent_registry
from app.tools.context import _current_delegate_depth, get_current_delegate_callback
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

ensure_tools_registered()

PARENT_TASK = "s3-probe-parent"
_DENY_CATS = {ToolCategory.AGENT, ToolCategory.SYSTEM, ToolCategory.MEDIA,
              ToolCategory.WIN_REGISTRY, ToolCategory.DESKTOP, ToolCategory.TIMER}
_SHORT = "一句话回答：1+1等于几？不要调用工具。"
_LONG = "请写一篇 3000 字的长文，逐段展开论述。"


@pytest.fixture(scope="module")
def parent_client():
    resolver = get_ai_config_resolver()
    ref = resolver.resolve_model_ref()
    pcfg = resolver.get_service_config(ref.provider, ref.model)
    api_key = str(pcfg.get("api_key") or "") or os.environ.get(f"{ref.provider.upper()}_API_KEY", "")
    c = create_llm_client(ModelRef(provider=ref.provider, model=ref.model,
                                   api_base=pcfg.get("api_base")), api_key)
    yield c
    asyncio.run(c.close())


@pytest.fixture
def parent(parent_client):
    return UniversalAgent(llm_client=parent_client, task_id=PARENT_TASK,
                          max_steps=4, track_task=False)


@pytest.fixture
def spy(monkeypatch):
    """观测型打点：包装真构造器与真工厂，不改变行为；on_child 只记录断言结果。"""
    seen = {"agents": [], "clients": [], "construct_calls": 0, "on_child": None, "hook": []}
    real_agent, real_factory = runner.UniversalAgent, client_sdk.create_llm_client

    def _agent(*a, **kw):
        seen["construct_calls"] += 1
        inst = real_agent(*a, **kw)
        seen["agents"].append(inst)
        if seen["on_child"] is not None:
            orig = inst.run_react_cycle
            async def _wrapped(*aa, **kk):
                seen["hook"].append(seen["on_child"]())
                return await orig(*aa, **kk)
            inst.run_react_cycle = _wrapped
        return inst

    def _factory(*a, **kw):
        c = real_factory(*a, **kw)
        seen["clients"].append(c)
        return c

    monkeypatch.setattr(runner, "UniversalAgent", _agent)
    monkeypatch.setattr(client_sdk, "create_llm_client", _factory)
    return seen


@pytest.fixture
def temp_config():
    made = []

    def _add(agent_id, **kw):
        cfg = AgentConfig(agent_id=agent_id, description="S3 探针临时配置",
                          tool_categories={ToolCategory.FUNDAMENTAL}, max_steps=4, **kw)
        get_agent_registry().register(cfg)
        made.append(agent_id)
        return cfg

    yield _add
    for aid in made:
        get_agent_registry().unregister(aid)


# ------------------------------------------------ A. 同步成功与显式拒绝（验收 1–4）
def test_T01_sync_success(parent, spy):
    r = asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
    assert r["status"] == "success"
    assert r["summary"] and "2" in r["summary"] and "http" not in r["summary"]
    assert r["usage"]["total_tokens"] > 0 and r["steps"] >= 1
    assert re.fullmatch(rf"sub-{re.escape(PARENT_TASK)}-researcher-[0-9a-f]{{6}}",
                        spy["agents"][0].task_id)


def test_T02_unknown_id(parent, spy):
    r = asyncio.run(runner.run_delegate(parent, "nope", "x"))
    assert r["status"] == "error"
    assert all(x in r["summary"] for x in ("researcher", "reviewer", "kb_analyst"))
    assert spy["construct_calls"] == 0


def test_T03_wait_false_rejected(parent, spy):
    r = asyncio.run(runner.run_delegate(parent, "researcher", "x", wait=False))
    assert r["status"] == "error" and "P1 能力，当前版本未实现" in r["summary"]
    assert spy["construct_calls"] == 0


def test_T04_parent_cancelled(parent, spy):
    async def _main():
        await task_registry.register_task(PARENT_TASK)
        try:
            await task_registry.set_cancelled(PARENT_TASK)
            return await runner.run_delegate(parent, "researcher", "x")
        finally:
            await task_registry.cleanup_task(PARENT_TASK)

    r = asyncio.run(_main())
    assert r["status"] == "error" and "父任务已取消" in r["summary"]
    assert spy["construct_calls"] == 0


# ------------------------------------------------ B. 只读与递归防护（验收 5–9）
def test_T05_readonly_toolset(parent, spy):
    asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
    child = spy["agents"][0]
    assert not (set(child._tools_dict) & DELEGATE_DENY_TOOLS)
    assert not (set(child._loaded_categories) & _DENY_CATS)


def test_T06_dynamic_load_still_denied(parent, spy):
    asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
    child = spy["agents"][0]
    child._tool_loader.load_category(ToolCategory.AGENT)   # 与 _tools_dict 同一引用
    invalidate_tool_cache(child)
    names = {t["function"]["name"] for t in get_openai_tools(child)}
    assert not (set(child._tools_dict) & {"question", "schedule"})
    assert not (names & {"question", "schedule"})


def test_T07_child_scope_clears_callback(parent, spy, parent_client):
    cb = object()
    tok = runner.set_current_delegate_callback(cb)
    spy["on_child"] = lambda: (get_current_delegate_callback() is None,
                               _current_delegate_depth.get())
    try:
        r = asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
    finally:
        runner.reset_current_delegate_callback(tok)
    assert r["status"] == "success"
    assert spy["hook"] == [(True, 1)]
    assert get_current_delegate_callback() is cb
    assert _current_delegate_depth.get() == 0


def test_T08_depth_hard_cap(parent, spy):
    tok = _current_delegate_depth.set(1)
    try:
        r = asyncio.run(runner.run_delegate(parent, "researcher", "x"))
        assert r["status"] == "error" and "委托深度超限" in r["summary"]
        assert _current_delegate_depth.get() == 1
    finally:
        _current_delegate_depth.reset(tok)
    assert spy["construct_calls"] == 0


def test_T09_confirm_blocker(parent, spy):
    name = "s3_probe_confirm"
    tool_registry.register(name=name, description="探针确认工具", category=ToolCategory.FUNDAMENTAL,
                           implementation=lambda **kw: {}, needs_confirmation=True)
    try:
        r = asyncio.run(runner.run_delegate(parent, "reviewer", "x"))
    finally:
        tool_registry.unregister(name)
    assert r["status"] == "error" and name in r["summary"] and "已拒绝委托" in r["summary"]


# ------------------------------------------------ C. 资源与收口（验收 10–11）
def test_T10_wall_clock_timeout(parent, spy, temp_config):
    temp_config("s3_timeout", timeout_s=5)
    t0 = time.monotonic()
    r = asyncio.run(runner.run_delegate(parent, "s3_timeout", _LONG))
    elapsed = time.monotonic() - t0
    assert r["status"] == "error" and "超时" in r["summary"]
    assert elapsed <= 5 + runner._CANCEL_GRACE_S + 2 * runner._POLL_S + 2
    assert not any(k.startswith("sub-") for k in task_state.agent_streams)
    assert asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))["status"] == "success"


def test_T11_parent_cancel_linked(parent, spy):
    async def _main():
        await task_registry.register_task(PARENT_TASK)
        try:
            t = asyncio.create_task(runner.run_delegate(parent, "researcher", _LONG))
            while not spy["agents"]:
                await asyncio.sleep(0.02)
            await task_registry.set_cancelled(PARENT_TASK)
            t0 = time.monotonic()
            with pytest.raises(asyncio.CancelledError):
                await t
            return time.monotonic() - t0
        finally:
            await task_registry.cleanup_task(PARENT_TASK)

    elapsed = asyncio.run(_main())
    assert elapsed <= 2 * runner._POLL_S + 2
    assert not any(k.startswith("sub-") for k in task_state.agent_streams)


# ------------------------------------------------ D. 台账 / SSE / 授权隔离（验收 12–14）
def test_T12_no_ledger_rows(parent, spy):
    before_usage = copy.deepcopy(parent.accumulated_usage)
    asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
    with db.get_conn("task_tracker") as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks WHERE task_id LIKE ?",
                            ("sub-%",)).fetchone()[0] == 0
    with db.get_conn("chat") as conn:
        assert conn.execute("SELECT COUNT(*) FROM chat_tasks WHERE task_id LIKE ?",
                            ("sub-%",)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM chat_task_steps WHERE task_id LIKE ?",
                            ("sub-%",)).fetchone()[0] == 0
    assert parent.accumulated_usage == before_usage
    assert spy["agents"][0].status is not None   # telemetry 未 finalize 也不抛


def test_T13_sse_isolated(parent, spy):
    buf = task_state.create_task_stream_buffer(PARENT_TASK, "")
    n0 = len(buf.event_log)
    try:
        r = asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
        assert r["status"] == "success"
        assert len(task_state.get_stream_buffer(PARENT_TASK).event_log) == n0
        assert not any(k.startswith("sub-") for k in task_state.agent_streams)
    finally:
        task_state.reclaim_memory_buffer(PARENT_TASK)


def test_T14_auth_not_leaked(parent, spy):
    tok = temp_auth._authorized_paths.set({Path("F:/s3_probe"): True})
    try:
        before = dict(temp_auth.get_authorized())
        asyncio.run(runner.run_delegate(parent, "researcher", _SHORT))
        assert temp_auth.get_authorized() == before
    finally:
        temp_auth._authorized_paths.reset(tok)


# ------------------------------------------------ E. client 与构造失败（验收 15–16）
def test_T15_model_branch_reuses_parent_pool(parent, spy, parent_client, temp_config):
    temp_config("s3_model", model=parent_client.llm_model.model)
    r = asyncio.run(runner.run_delegate(parent, "s3_model", _SHORT))
    assert r["status"] == "success"
    assert len(spy["clients"]) == 1
    assert spy["clients"][0]._client is not parent_client._client
    assert spy["clients"][0]._client.is_closed is True
    assert parent_client._client.is_closed is False


def test_T16_construct_failure_closes_client(parent, spy, parent_client, temp_config, monkeypatch):
    temp_config("s3_broken", model=parent_client.llm_model.model)

    def _boom(*a, **kw):
        raise RuntimeError("构造故障注入")

    monkeypatch.setattr(runner, "UniversalAgent", _boom)   # 只换构造器
    r = asyncio.run(runner.run_delegate(parent, "s3_broken", "x"))
    assert r["status"] == "error" and "构造故障注入" in r["summary"]
    assert spy["clients"] and spy["clients"][-1]._client.is_closed is True
```

**退出判据**：A–E 共 T01–T16 全绿（无 `skip`/`xfail`），且 1–16 项验收逐条有原始输出（日志/DB 查询/断言输出）支撑；安全项 B 组（第 5–9 项）与 C 组（第 10–11 项）任一红即停，不进 S4。探针按铁律不提交。

**验收清单**：

*正常路径*

1. **同步成功**：用真实父 Agent（真实 LLM 配置）调 `run_delegate(agent=父, agent_id="researcher", task="搜索…")`，返回 `status == "success"`，`summary` 非空且是任务结论（不是原始网页罗列），`usage.total_tokens > 0`，`steps >= 1`。
2. **未知 id**：`agent_id="nope"` 返回 error，summary 列出 3 个可用 id。
3. **wait=False 显式拒绝**：返回 error，summary 明说"P1 能力，当前版本未实现"，不得静默按同步执行。
4. **父已取消不启动**：父任务经 `register_task` 登记后 `set_cancelled(父task_id)`，再调 `run_delegate` 返回"父任务已取消，跳过委托"，且子 Agent 未被构造。

*只读与递归防护*

5. **分类只读**：子 Agent 的 `_tools_dict` 不含 `write`/`delete`/`move`/`copy`/`rename`/`edit`/`bash`/`question`/`schedule`/`delegateagent`/`execute_sql`/`screen_capture`；`_loaded_categories` 不含 AGENT/SYSTEM/MEDIA/WIN_REGISTRY/DESKTOP/TIMER。
6. **动态灌回仍不可调**：在子作用域内执行 `load_category(ToolCategory.AGENT)`，`_tools_dict` 与 `get_openai_tools` 仍无 `question`/`schedule`（三处同源全部生效）；此条失败即回 S0 修 `exclude` 链。
7. **运行层清空回调**：子作用域内 `get_current_delegate_callback() is None`（打点断言即可，等价于"delegateagent 被灌回也只会拿到 None"）。
8. **深度硬顶**：在 `_current_delegate_depth = 1` 的作用域内调 `run_delegate`，返回 error 且 summary 含"委托深度超限"；返回后深度仍为 1（未被重置）。
9. **确认类工具兜底**：临时注册一个 `needs_confirmation=True` 的 FUNDAMENTAL 工具，构造 reviewer 子 Agent，`run_delegate` 返回 error 且 summary 含该工具名与"已拒绝委托"；测完 `unregister`。

*资源与隔离*

10. **墙钟超时**：临时注册 `timeout_s=5` 的 AgentConfig，跑一个明显超 5s 的任务，返回 error 且 summary 含"超时"；总耗时 ≤ `timeout_s + _CANCEL_GRACE_S + 2×_POLL_S`（≈12s）；随后再委托一次仍成功（证明子任务已收干净、buffer 未被撞）。
11. **父取消联动**：父任务 `set_cancelled` 后，运行中的委托在 ≤ 2×`_POLL_S` 内结束并向上传播取消；`agent_streams` 无 `sub-` 前缀残留（`reclaim_memory_buffer` 已执行）。
12. **台账与遥测**：`tasks` 表与 `chat_task_steps` 均无 `sub-` 前缀行；`chat_tasks` 无子任务行；子 Agent 的 `TaskTelemetry` 未 finalize 时既不在 `react_loop` 结尾抛异常、也不留悬挂资源（§2.7.3）；父 `accumulated_usage` 在 `run_delegate` 返回前后不变（合并由 S4 的 `tool_executor` 做）。
13. **SSE 隔离**：委托前后父 buffer 的 `event_log` 长度不变（子步骤未透传），子步骤只出现在日志。
14. **授权不串味**：委托前给父加临时授权路径，委托后父 `_authorized_paths` 逐键相同（子 Agent 的 `clear_temp_auth` 只作用于副本）。
15. **model 分支**：把临时 AgentConfig 的 `model` 设为与父相同的模型名（确保走 `create_llm_client` 分支），委托成功，且返回后父 `agent.llm_client._client.is_closed is False`（独立 client 的 `close()` 未关掉共享池）。
16. **构造失败收口**：`sub_task_id` 由 runner 内部生成（`sub-{父task}-{agent_id}-{6hex}`），没有外部入参，且 `UniversalAgent` 只对空 `task_id` 抛错——**不要指望用"非法 id"触发这条分支**。改用故障注入：探针里把 `delegateagent_runner.UniversalAgent` 临时替换为"构造即抛 `RuntimeError`"的可调用对象（只替换构造器，不 mock LLM/工具/DB），断言返回 error，且探针持有的独立 client 句柄事后 `is_closed is True`（`_close_quietly` 已执行）。

**退出标准**：1–16 全绿；第 5/6/7/8/10/11 六项任一红即视为安全承诺未落地，不得进入 S4。

**失败回退**：第 6 项回 S0；第 7/8 项回 S2（ContextVar 定义）；第 10/11/13 项改 `_run_child_guarded`/`_delegate_scope` 的收口顺序（先 cancel + 有界等待，再回收 buffer），不得靠加大 `_CANCEL_GRACE_S` 掩盖。

#### 6.2.6 S4 主链路接入（1 天，含别名 0.5 天）

**目标**：把工具真正注册进 AGENT 分类、入口层注入回调并把用量记到父账、别名归一可用、工具描述由注册表动态生成。

**改动面**：改 `agent_register.py`（四张表 + `tool_methods` 注册 + `load_plugins` 调用位留空）、`tool_executor.py`（注入 + finally 按 token 守卫 reset + usage 合并）、`tools_alias_mapper.py`（4 条别名）、`agent_config.py`（新增 `build_delegate_tool_description()`）。

**TDD 测试要求（先红后绿；本阶段全部用例跑在真实链路）**：

> 纪律同 S1/S2/S3：**先写失败用例（红）→ 最小实现（绿）→ 重构保持绿**；禁止先落实现再补"能过就行"的用例，禁止为变绿放宽断言。本阶段仍用真实 LLM / 真实工具注册与执行 / 真实 SQLite，不打桩 LLM、不用假库、不替换 `run_react_cycle`。只允许三类观测型打点：临时注册再注销探针工具、`storage` 累计函数包装（记录入参并调用原函数）、`caplog` 抓别名日志；不替换委托回调，失败委托由 T07 的真实路径覆盖。若实现期需要临时受控回调定位问题，必须用 `set_current_delegate_callback` 且在 `finally` 用 token reset，不得把它写进正式用例的断言依据。
>
> 对码发现三处必须在实施时一并收口的缺口，否则本阶段验收项不可达：
>
> 1. `build_delegate_tool_description()` 只在 §4.1 设计，`agent_config.py` 尚未实现。S4 须新增（读 `get_agent_registry().list_configs()` 动态拼 id + description），并把注册描述由静态字符串改为该函数（callable），新增 Agent 才真正零改代码。
> 2. §4.3 原合并代码只改 `accumulated_usage`；但 DB 权威列 `chat_tasks.task_accumulated_tokens` 由 `react_step` 每轮按"本次 LLM 调用 token"累加（经 `storage.update_task_accumulation`），子 usage 不会自动进去，验收第 6 项不可达。故合并必须同时做四件事：`accumulated_usage` += 子 usage、`task_accumulated_tokens` += 子 usage、按既有基线重算 `session_accumulated_tokens`/`chain_accumulated_tokens`、在 `db.atxn("chat", ...)` 内把子 usage 作为 `llm_call_count_token` 写 `storage.update_task_accumulation`，并在 `_start_meta.session_id` 非空时写 `update_session_accumulation`。**不可**在合并时再叠加 session/chain 基线，否则下一轮 `react_step` 会双计。
> 3. 入口层注入与合并的判据用 `normalize_tool_name(tool_name) == "delegateagent"`，不用裸 `tool_name == "delegateagent"`。真实链路 `action_input_parser._claim` 已把 `call["tool_name"]` 原地写回主名、`tool_facade.execute_tool` 也经 `resolve_registered_tool` 归一，但直调别名时裸名判据会漏注入；归一判据零成本且堵住该口。
>
> `load_plugins` 在 S4 只保留调用位（注释占位），S6.2 再实装；T02c 用"注册表仍只有 3 个内置 Agent"守住这条边界。

**测试文件**：`backend/tests/probe_delegate_s4_wiring.py`（本地探针，按 §6.2.11 第 4 条不提交）。运行：`cd backend && python -m pytest tests/probe_delegate_s4_wiring.py -v --timeout=90`。用例顺序 A→F 与下方红绿节奏同序。

**A. 注册与描述（验收 1、2）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 注册契约 | `get_tool("delegateagent")` 非 None；`category is AGENT`；`get_implementation("delegateagent")` 是 `delegateagent` 函数；`input_schema.required == {"agent_id","task"}` 且 properties 含 context/wait；`hide_from_steps is False`、`visible_to_llm is True`、`visible_in_steps` 为 True、`"delegateagent" not in AGENT_HIDE_FROM_STEPS` |
| T01b | 主 Agent 可见 | 默认 `_INITIAL_CATEGORIES` 含 AGENT，`get_openai_tools(parent)` 含 name=`delegateagent`，且描述含 `researcher` |
| T02 | 描述动态生成 | `build_delegate_tool_description()` 含三个内置 id 及各自 description；`meta.resolved_description()` 与其同源；运行期 register `tmp_agent` + `invalidate_tool_cache(parent)` 后工具描述出现 `tmp_agent`，unregister + invalidate 后消失 |
| T02b | 描述是字符串 | `tool_registry.list_tools()` 中该工具 description 为 `str`（非函数对象），且含 `researcher` |
| T02c | 无插件边界 | `get_agent_registry().list_available()` 恰为 3 个内置 id（S4 不加载插件） |

**B. 注入与复位（验收 3）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T03 | 成功注入并复位 | 直调 `execute_tool(parent, "delegateagent", {...}, parent._retry_engine)` → `is_success`；`data.summary` 非空、`usage.total_tokens>0`、`steps>=1`；`llm_data.summary` 含"委托子Agent(researcher)完成"；返回后 `get_current_delegate_callback() is None` |
| T03b | 非 delegate 不注入、无残留 | 临时注册探针工具，实现内记录 `get_current_delegate_callback()`；先调它记录为 None，再调 delegateagent，再调它仍为 None |
| T03c | 未注入 fail-closed | 绕过入口层直接 `delegateagent(...)` → error，summary 含"委托通道未注入" |
| T03d | 真实一轮 | 建父 buffer 后 `run_react_cycle(parent, 强指令调用 delegateagent, max_steps=3, task_id=父task)`：事件含 delegateagent action 与非空 observation，结束后回调 None；`finally reclaim_memory_buffer` |

**C. 别名归一（验收 4）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T04 | 别名映射 | `delegate_task`/`delegate_to_agent`/`call_agent`/`invoke_agent` 经 `normalize_tool_name` 均得 `delegateagent`；canonical/`subagent`/未知名原样 |
| T04b | 注册表解析 | `resolve_registered_tool` 四别名均返回 `(delegateagent, 非 None meta)` |
| T04c | 真实链路归一 | `_build_call_list({"tool_name":"delegate_task",...})` → `all_calls[0]["tool_name"]=="delegateagent"`；`execute_tools(parent, calls, False)` 成功；`caplog` 含 `[tool_name_alias]` 与 `delegate_task→delegateagent` |
| T04d | 别名也记账 | 同 T04c 调用前后父 `accumulated_usage`/`task_accumulated_tokens` 增量等于返回 usage |
| T04e | 禁用名不收编 | `"subagent" not in TOOL_NAME_ALIASES` |

**D. usage 合并与终态记账（验收 5、6）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T05 | 成功合并 | `_merge_delegate_usage(parent, usage)` 后 `accumulated_usage` 与 `task_accumulated_tokens` 增量均等于 usage；session/chain 仍等于各自基线 + `task_accumulated_tokens`（不重复加基线） |
| T06 | 失败也记账 | 失败形状返回体（`exec_code=="error"` 但 `data.usage` 非空）：判据是 usage 存在性而非 `is_success`，合并仍发生；真实失败路径由 T07 覆盖 |
| T06b | 无 usage 不记账 | 空 usage → 四层内存态逐键不变 |
| T06c | 非 delegate 不记账 | 探针工具返回含 usage 的成功体 → `execute_tool` 不改父 usage |
| T06d | 脏数值安全 | `None`/字符串数值经 `int(v or 0)` 归一，不抛异常 |
| T07 | 真实失败委托 | 临时 config `max_steps=1` + 强指令先 read 临时文件 → `status failed` 且 `usage.total_tokens>0`；父增量等于返回 usage；若模型直接回答则调整 prompt，不放宽断言 |
| T08a | 终态记账 | `emit_completed_final(step=1, response="x")[0]` 的 `accumulated_usage`/`task_accumulated_tokens` 等于父内存态且含子 usage |
| T08b | DB 落账契约 | `storage` 累计函数 spy 记录入参并调原函数：合并后 task 写 1 次、`llm_call_count_token` 等于子 usage、task_id 正确；`_start_meta.session_id` 非空时 session 写 1 次；无真实行时 rowcount-0 warning 可接受，真实终值由 E2E 覆盖 |

**E. 全链路 E2E（验收 7）**

新增 `backend/e2etests/test_e2e_40_delegateagent_sync.py`（`@pytest.mark.e2e_full_link`，本地跑通、**不提交**）。沿用 `e2e_helpers` 的 `ensure_backend_ready` / `send_chat` / `assert_stream_ended` / `check_db` / `verify_db_tool_usage` / `check_logs` / `write_test_record`；用户输入要求"用两个 researcher 分别搜两个主题，再用 reviewer 审查两份结果并汇总"。通过标准：`result["tool_calls"]` 与 SSE 步骤含 `delegateagent`，父回复含两份摘要要点与审查结论；DB `chat_task_steps` 有该工具行；`chat_task_steps`/`chat_tasks` 无 `sub-%` 行；按 `e2e_helpers` 同源库直连查询 `chat_tasks.task_accumulated_tokens` 包含子消耗，且与终态帧 `accumulated_usage` 一致。不得靠放宽断言（如只判"回复非空"）让它变绿。

**F. 回归（验收 8）**

E2E-P0-03b 必须 PASSED；按本阶段改动符号（`agent_register` / `tool_executor` / `tools_alias_mapper` / `agent_config`）筛出的定向集 `--timeout=60` 全跑，失败集合与改造前基线逐条相同、新增 0；S1/S2/S3 探针全绿；`ruff check` 全过。出现新的红项即停，不得以"工具列表多了一个 delegateagent"为由忽略。

**打点边界（红绿之外的纪律）**：允许 = 临时注册/注销探针工具、`storage` 累计函数包装（必须调用原函数）、`caplog`；禁止 = mock LLM 返回、假 SQLite 连接、替换 `run_react_cycle`、替换委托回调（定位问题可临时 set，但必须 `finally` reset 且不写进正式断言）、临时改小拒绝清单或别名表来让用例变绿。每个 fixture 的 `unregister`/`reclaim`/`reset` 必须在 `finally` 或 fixture 卸载时还原，否则下一条用例会出现"串味假红"。

**红绿节奏（每轮只推进一组，全绿再进下一组）**：

| 轮次 | 先写的红用例 | 让它变绿的最小实现 |
|------|-------------|-------------------|
| R1 | T01、T01b、T02、T02b、T02c | 先落 `build_delegate_tool_description()` 骨架与四张表 + `tool_methods` 注册（把 ImportError 转成断言红），描述改 callable |
| R2 | T03、T03b、T03c | `execute_tool` 入口按归一名注入回调，`finally` 按 `_delegate_token is not None` 守卫 reset |
| R3 | T04、T04b、T04c、T04e | `TOOL_NAME_ALIASES` 加 4 条（不收 `subagent`）；别名用例走 `_build_call_list → execute_tools` 真实链路 |
| R4 | T05、T06、T06b、T06c、T06d | `_merge_delegate_usage` 四层合并 + 脏数值归一 + DB 落账，判据用 usage 存在性 |
| R5 | T07 | 真实失败委托（不 mock、不放宽断言），确认失败分支同样带 usage 且父侧记账 |
| R6 | T08a、T08b | 终态注入与 storage spy 验证，确认 session/chain 未被重复累加 |
| R7 | T03d | 真实主 Agent 一轮：prompt 强指令调 delegateagent，验证 action/observation 与回调复位 |
| R8 | E 与 F | E2E 与定向回归、`ruff check` 全过；无 `skip`/`xfail` 才算本阶段可提交 |

**测试代码**：

```python
# -*- coding: utf-8 -*-
"""delegateagent 主链路接入 TDD 探针 — 小欧 2026-11-28

真实 LLM / 工具注册与执行 / SQLite；只做观测型打点与受控回调注入。
探针按仓库铁律不入库。
运行：cd backend && python -m pytest tests/probe_delegate_s4_wiring.py -v --timeout=90
"""
import asyncio
import copy
import uuid

import pytest

from app.services.agent import tool_executor
from app.services.agent.action_input_parser import _build_call_list
from app.services.agent.react_loop import run_react_cycle
from app.services.agent.tool_cache_manager import get_openai_tools, invalidate_tool_cache
from app.services.agent.tool_runner import execute_tools
from app.services.agent.universal_agent import UniversalAgent
from app.services.chat import storage
from app.services.lifecycle.service import get_service
from app.services.task import task_state
from app.tools import ensure_tools_registered
from app.tools.agent.agent_config import (
    AgentConfig, build_delegate_tool_description, get_agent_registry,
)
from app.tools.agent.agent_register import AGENT_HIDE_FROM_STEPS
from app.tools.agent.delegateagent import delegateagent
from app.tools.context import get_current_delegate_callback
from app.tools.registry import resolve_registered_tool, tool_registry
from app.tools.tool_response import build_error, build_success, is_success
from app.tools.tool_types import ToolCategory
from app.tools.tools_alias_mapper import TOOL_NAME_ALIASES, normalize_tool_name

ensure_tools_registered()

_K = ("prompt_tokens", "completion_tokens", "total_tokens")
_ALIASES = ("delegate_task", "delegate_to_agent", "call_agent", "invoke_agent")
_BUILTINS = {"researcher", "reviewer", "kb_analyst"}
_SHORT = "一句话回答：1+1等于几？不要调用工具。"


@pytest.fixture
def parent_task():
    return f"s4-probe-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def parent_client():
    c = get_service()
    yield c
    asyncio.run(c.close())


@pytest.fixture
def parent(parent_client, parent_task):
    return UniversalAgent(llm_client=parent_client, task_id=parent_task,
                          max_steps=4, track_task=False)


@pytest.fixture
def probe_tools():
    made = []

    def _add(name, impl):
        tool_registry.register(name=name, description="探针工具",
                               category=ToolCategory.FUNDAMENTAL, implementation=impl)
        made.append(name)

    yield _add
    for name in made:
        tool_registry.unregister(name)


@pytest.fixture
def temp_config():
    made = []

    def _add(agent_id, **kw):
        kw.setdefault("tool_categories", {ToolCategory.FUNDAMENTAL})
        kw.setdefault("max_steps", 4)
        cfg = AgentConfig(agent_id=agent_id, description="S4 探针临时配置", **kw)
        get_agent_registry().register(cfg)
        made.append(agent_id)
        return cfg

    yield _add
    for aid in made:
        get_agent_registry().unregister(aid)


@pytest.fixture
def storage_spy(monkeypatch):
    seen = {"task": [], "session": []}
    real_task, real_session = storage.update_task_accumulation, storage.update_session_accumulation

    def _task(conn, *, task_id, llm_call_count_token):
        seen["task"].append((task_id, dict(llm_call_count_token)))
        return real_task(conn, task_id=task_id, llm_call_count_token=llm_call_count_token)

    def _session(conn, *, session_id, llm_call_count_token):
        seen["session"].append((session_id, dict(llm_call_count_token)))
        return real_session(conn, session_id=session_id, llm_call_count_token=llm_call_count_token)

    monkeypatch.setattr(storage, "update_task_accumulation", _task)
    monkeypatch.setattr(storage, "update_session_accumulation", _session)
    return seen


# ------------------------------------------------ A. 注册与描述
def test_T01_registered_contract():
    meta = tool_registry.get_tool("delegateagent")
    assert meta is not None and meta.category is ToolCategory.AGENT
    assert tool_registry.get_implementation("delegateagent") is delegateagent
    schema = meta.input_schema or {}
    assert set(schema.get("required") or []) == {"agent_id", "task"}
    assert {"agent_id", "task", "context", "wait"} <= set(schema.get("properties") or {})
    assert meta.hide_from_steps is False and meta.visible_to_llm is True
    assert tool_registry.visible_in_steps("delegateagent") is True
    assert "delegateagent" not in AGENT_HIDE_FROM_STEPS


def test_T01b_visible_to_parent(parent):
    tools = {t["function"]["name"]: t["function"] for t in get_openai_tools(parent)}
    assert "delegateagent" in tools and "researcher" in tools["delegateagent"]["description"]


def test_T02_dynamic_description(parent):
    desc = build_delegate_tool_description()
    reg = get_agent_registry()
    for aid in _BUILTINS:
        assert aid in desc and reg.get(aid).description in desc
    assert tool_registry.get_tool("delegateagent").resolved_description() == desc
    reg.register(AgentConfig(agent_id="tmp_agent", description="临时探针 Agent",
                             tool_categories={ToolCategory.FUNDAMENTAL}))
    try:
        invalidate_tool_cache(parent)
        tools = {t["function"]["name"]: t["function"]["description"]
                 for t in get_openai_tools(parent)}
        assert "tmp_agent" in tools["delegateagent"]
    finally:
        reg.unregister("tmp_agent")
        invalidate_tool_cache(parent)
    tools = {t["function"]["name"]: t["function"]["description"]
             for t in get_openai_tools(parent)}
    assert "tmp_agent" not in tools["delegateagent"]


def test_T02b_list_tools_description_is_str():
    entries = [t for t in tool_registry.list_tools() if t["name"] == "delegateagent"]
    assert len(entries) == 1 and isinstance(entries[0]["description"], str)
    assert "researcher" in entries[0]["description"]


def test_T02c_only_builtin_agents():
    assert set(get_agent_registry().list_available()) == _BUILTINS


# ------------------------------------------------ B. 注入与复位
def test_T03_injection_and_reset(parent):
    r = asyncio.run(tool_executor.execute_tool(
        parent, "delegateagent", {"agent_id": "researcher", "task": _SHORT},
        parent._retry_engine))
    assert is_success(r)
    assert r["data"]["summary"] and r["data"]["usage"]["total_tokens"] > 0
    assert r["data"]["steps"] >= 1
    assert "委托子Agent(researcher)完成" in r["llm_data"]["summary"]
    assert get_current_delegate_callback() is None


def test_T03b_non_delegate_no_residue(parent, probe_tools):
    seen = []

    def _obs(**kw):
        seen.append(get_current_delegate_callback())
        return build_success(data={"ok": True})

    probe_tools("s4_probe_observer", _obs)
    asyncio.run(tool_executor.execute_tool(parent, "s4_probe_observer", {}, parent._retry_engine))
    asyncio.run(tool_executor.execute_tool(
        parent, "delegateagent", {"agent_id": "researcher", "task": _SHORT},
        parent._retry_engine))
    asyncio.run(tool_executor.execute_tool(parent, "s4_probe_observer", {}, parent._retry_engine))
    assert seen == [None, None]


def test_T03c_no_callback_fail_closed():
    r = asyncio.run(delegateagent(agent_id="researcher", task=_SHORT))
    assert not is_success(r) and "委托通道未注入" in r["llm_data"]["summary"]


def test_T03d_real_react_cycle(parent, parent_task):
    buf = task_state.create_task_stream_buffer(parent_task, "")
    try:
        asyncio.run(run_react_cycle(
            parent,
            "必须调用 delegateagent 委托 researcher 回答 1+1=几，禁止不调用工具直接回答。",
            max_steps=3, task_id=parent_task))
        types = [e.get("type") for e in buf.event_log]
        assert "action" in types and "observation" in types
        assert any("delegateagent" in str(e) for e in buf.event_log
                   if e.get("type") == "action")
        assert get_current_delegate_callback() is None
    finally:
        task_state.reclaim_memory_buffer(parent_task)


# ------------------------------------------------ C. 别名归一
def test_T04_alias_mapping():
    for name in _ALIASES:
        assert normalize_tool_name(name) == "delegateagent"
    for name in ("delegateagent", "subagent", "unknown_tool"):
        assert normalize_tool_name(name) == name


def test_T04b_resolve_alias():
    for name in _ALIASES:
        canonical, meta = resolve_registered_tool(name)
        assert canonical == "delegateagent" and meta is not None


def test_T04c_alias_real_chain(parent, caplog):
    parsed = {"tool_name": "delegate_task",
              "tool_params": {"agent_id": "researcher", "task": _SHORT},
              "fc_context": {}}
    calls = _build_call_list(parsed).all_calls
    assert calls[0]["tool_name"] == "delegateagent"
    with caplog.at_level("INFO"):
        results = asyncio.run(execute_tools(parent, calls, False))
    assert is_success(results[0])
    assert "[tool_name_alias]" in caplog.text
    assert "delegate_task→delegateagent" in caplog.text


def test_T04d_alias_usage_counted(parent):
    before = copy.deepcopy(parent.accumulated_usage)
    parsed = {"tool_name": "call_agent",
              "tool_params": {"agent_id": "researcher", "task": _SHORT},
              "fc_context": {}}
    results = asyncio.run(execute_tools(parent, _build_call_list(parsed).all_calls, False))
    usage = (results[0].get("data") or {}).get("usage") or {}
    assert usage.get("total_tokens", 0) > 0
    assert parent.accumulated_usage["total_tokens"] - before["total_tokens"] == int(usage["total_tokens"])


def test_T04e_subagent_not_alias():
    assert "subagent" not in TOOL_NAME_ALIASES


# ------------------------------------------------ D. usage 合并与终态记账
def test_T05_success_merge(parent):
    usage = {"prompt_tokens": 21, "completion_tokens": 9, "total_tokens": 30}
    before_u = copy.deepcopy(parent.accumulated_usage)
    before_t = copy.deepcopy(parent.task_accumulated_tokens)
    parent._session_acc_base = {k: 100 for k in _K}
    parent._chain_acc_base = {k: 200 for k in _K}
    asyncio.run(tool_executor._merge_delegate_usage(parent, usage))
    assert {k: parent.accumulated_usage[k] - before_u[k] for k in _K} == usage
    assert {k: parent.task_accumulated_tokens[k] - before_t[k] for k in _K} == usage
    assert parent.session_accumulated_tokens == {k: 100 + parent.task_accumulated_tokens[k] for k in _K}
    assert parent.chain_accumulated_tokens == {k: 200 + parent.task_accumulated_tokens[k] for k in _K}


def test_T06_error_usage_still_counted(parent):
    err = build_error(
        data={"usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}},
        llm_data={"status": {"exec_code": "error", "message": "失败"}})
    assert not is_success(err)
    before = copy.deepcopy(parent.accumulated_usage)
    asyncio.run(tool_executor._merge_delegate_usage(parent, err["data"]["usage"]))
    assert {k: parent.accumulated_usage[k] - before[k] for k in _K} == err["data"]["usage"]


def test_T06b_empty_usage_noop(parent):
    before = (copy.deepcopy(parent.accumulated_usage),
              copy.deepcopy(parent.task_accumulated_tokens))
    asyncio.run(tool_executor._merge_delegate_usage(parent, {}))
    assert (parent.accumulated_usage, parent.task_accumulated_tokens) == before


def test_T06c_non_delegate_no_merge(parent, probe_tools):
    before = copy.deepcopy(parent.accumulated_usage)

    def _with_usage(**kw):
        return build_success(data={"usage": {"prompt_tokens": 9, "completion_tokens": 9,
                                             "total_tokens": 18}})

    probe_tools("s4_probe_usage", _with_usage)
    asyncio.run(tool_executor.execute_tool(parent, "s4_probe_usage", {}, parent._retry_engine))
    assert parent.accumulated_usage == before


def test_T06d_dirty_numbers_safe(parent):
    dirty = {"prompt_tokens": None, "completion_tokens": "7", "total_tokens": "18"}
    before = copy.deepcopy(parent.accumulated_usage)
    asyncio.run(tool_executor._merge_delegate_usage(parent, dirty))
    assert parent.accumulated_usage["prompt_tokens"] == before["prompt_tokens"]
    assert parent.accumulated_usage["completion_tokens"] - before["completion_tokens"] == 7
    assert parent.accumulated_usage["total_tokens"] - before["total_tokens"] == 18


def test_T07_real_failed_delegate(parent, temp_config, tmp_path):
    f = tmp_path / "s4_fail.txt"
    f.write_text("sample", encoding="utf-8")
    temp_config("s4_fail", tool_categories={ToolCategory.FILE}, max_steps=1)
    task = f"先调用 read 工具读取 {f.as_posix()}，再输出摘要；禁止不调用工具直接回答。"
    before = copy.deepcopy(parent.accumulated_usage)
    r = asyncio.run(tool_executor.execute_tool(
        parent, "delegateagent", {"agent_id": "s4_fail", "task": task},
        parent._retry_engine))
    usage = (r.get("data") or {}).get("usage") or {}
    assert not is_success(r) and usage.get("total_tokens", 0) > 0
    assert parent.accumulated_usage["total_tokens"] - before["total_tokens"] == int(usage["total_tokens"])


def test_T08a_final_step_has_child_usage(parent):
    usage = {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}
    asyncio.run(tool_executor._merge_delegate_usage(parent, usage))
    final = parent._step_emitter.emit_completed_final(step=1, response="x")[0]
    assert final.accumulated_usage == parent.accumulated_usage
    assert final.task_accumulated_tokens == parent.task_accumulated_tokens
    assert final.task_accumulated_tokens["total_tokens"] >= usage["total_tokens"]


def test_T08b_db_write_contract(parent, storage_spy):
    usage = {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42}
    parent._start_meta = {"session_id": "s4-probe-session"}
    asyncio.run(tool_executor._merge_delegate_usage(parent, usage))
    assert len(storage_spy["task"]) == 1
    assert storage_spy["task"][0][0] == parent.task_id
    assert storage_spy["task"][0][1] == usage
    assert len(storage_spy["session"]) == 1
    assert storage_spy["session"][0][0] == "s4-probe-session"
    assert storage_spy["session"][0][1] == usage
```

**退出判据**：A–D 共 T01–T08b 与 T03d 全绿（无 `skip`/`xfail`），E 全链路 E2E 与 F 定向回归全过且新增失败 0、`ruff check` 全过；每条用例有原始输出（SSE/日志/DB 查询/断言输出）支撑。探针按铁律不提交。

**验收清单**：

1. **真的注册**：`tool_registry.get_tool("delegateagent")` 非 None；AGENT 分类列表含 `delegateagent`；`visible_in_steps` 为 True（未进 `HIDE_FROM_STEPS`）。
2. **描述动态生成**：`build_delegate_tool_description()` 文本含 `researcher`/`reviewer`/`kb_analyst` 三个 id 及各自 description；运行期 `register(AgentConfig(agent_id="tmp_agent", ...))` 并 `invalidate_tool_cache` 后，工具描述立即出现 `tmp_agent`，`unregister` 后消失——证明"新增 Agent 零改代码"。
3. **注入与复位**：主 Agent 一轮真实对话中 LLM 调 `delegateagent` 成功，observation 含子 Agent 摘要；随后调任一非 delegate 工具，`get_current_delegate_callback()` 为 None（无残留泄漏）。
4. **别名归一**：`normalize_tool_name` 对 `delegate_task`/`delegate_to_agent`/`call_agent`/`invoke_agent` 均返回 `delegateagent`；`subagent` 原样返回；真实一轮用 `delegate_task` 名字调用成功，日志出现 `[tool_name_alias]`。
5. **usage 合并**：成功委托后父 `accumulated_usage.total_tokens` 增量等于子返回的 `usage.total_tokens`；失败委托（子 Agent 中途失败）同样有增量；非 delegate 工具不改变父 usage。
6. **终态记账**：任务 FinalStep 与 DB 的父任务 token 统计包含子 Agent 消耗。
7. **全链路 E2E**：本地新增 `backend/e2etests/test_e2e_40_delegateagent_sync.py`（`@pytest.mark.e2e_full_link`），用户输入触发"researcher 并行搜两个主题 + reviewer 审查"；通过标准：SSE 出现 `delegateagent` 步骤、DB 步骤表有该工具、父回复含两份摘要、`chat_task_steps` 无 `sub-` 行。
8. **回归**：E2E-P0-03b 与 `backend/tests` 单测通过（工具列表多一个 `delegateagent` 不影响原链路）。

**退出标准**：1–8 全绿；E2E 脚本按铁律本地运行、**不提交**。

**失败回退**：第 1 项查 `tool_methods` 注册循环（漏此步工具根本没 register）；第 2 项查 callable 描述的三个读取点（`tool_description`/`registry.list_tools`/`tool_cache_manager`）；第 5 项查 `data.usage` 是否存在性判据（不得用 `is_success`）。

**实施记录（2026-11-28）**：S4 代码已落地——`agent_register.py` 三张表 + `tool_methods` 注册 + `load_plugins` 注释占位、`agent_config.py` 新增动态描述函数、`tool_executor.py` 按归一名注入回调且 finally 守卫 reset、四层 usage 合并并写 DB、`tools_alias_mapper.py` 四别名；逐条对码核实与本文档参考代码 0 处实现差异。`backend/tests/probe_delegate_s4_wiring.py` 与 `backend/e2etests/test_e2e_40_delegateagent_sync.py` 按铁律未落盘提交，文档保留完整用例与代码；验收第 1/4 项由 S5 探针的注册与别名用例间接覆盖，第 7 项 E2E 尚未执行，不宣称 S4 全绿。按用户要求不产出独立阶段验收记录文件。

**TDD 落码实测补充（2026-11-28）**：探针 `backend/tests/probe_delegate_s4_wiring.py` 实际落盘运行（按铁律不提交）。首轮因 `build_delegate_tool_description` 未实现报 ImportError 红，按 R1→R4 逐组推进：A 组注册与描述 5 项、C 组别名归一 3 项、D 组 usage 合并与终态记账 7 项共 15 条全部全绿（无 skip/xfail）；定向回归 101 passed、改动文件 `ruff` 无新增错误。落盘时修正探针两处自身缺陷：①整模块共享单个事件循环（多个 `asyncio.run` 各自建 loop 会让真实 LLM 客户端报跨 loop 异常）；②`temp_config` 用 `setdefault` 让调用方覆盖 `tool_categories`/`max_steps`（原写法重复传参触发 TypeError，参考代码已同步订正）。B 组注入复位与 E 组真实 LLM 用例（T03/T03b/T03c/T03d/T04c/T04d/T07）在本环境被服务端账户级 429 速率限制拦截（每 3 分钟 1 次，Retry-After 恢复等待超工具 60s 保险丝），换 `agnes-3.0-flash` 仍为 provider 级限流，多次重试均失败；该组未通过属环境约束、非实现缺陷，待配额可用时按同探针补跑，当前不宣称 S4 全绿。

#### 6.2.7 S5 并行上限（0.5 天）

**目标**：单轮并行子 Agent 数硬顶 6，超出部分结构化拒绝，且结果索引不错位、既有分支不退化。

**改动面**：`tool_constants.py` 新增 `MAX_PARALLEL_SUB_AGENTS = 6`；`tool_runner.execute_tools` 在**扩展名纠错循环之后**插入上限校验（计数时自行 `normalize_tool_name`，别名不能绕过）、三分支改用 `_active_calls`、末尾按原索引回填（§2.5.1 代码）。

**TDD 测试要求（先红后绿；不 mock、不改小上限）**：

> 纪律同 S1–S4：**先写失败用例（红）→ 最小实现（绿）→ 重构保持绿**。本阶段只改 `tool_constants.py` 与 `tool_runner.py`，但触达三分支调度与文件落盘取号，任何"只删校验、保留 `_active_calls`"的半成品都会在取号用例上暴露。仍用真实 LLM / 真实工具 / 真实 SQLite；允许的观测型打点只有三类：包装真 `execute_tool` 记 start/end、`on_attempt_recorded` 工厂记录收到的序号、`caplog`；禁止 mock LLM 返回、替换执行逻辑或冲突检测、把上限临时改小让用例变绿。
>
> 对码发现四处必须一并收口，否则本阶段验收项不可达：
>
> 1. `MAX_PARALLEL_SUB_AGENTS` 在 `app/` 下当前零命中，须在 `tool_constants.py` 新增；`tool_runner.py` 是唯一消费方，不得在别处再定义一份。
> 2. `_active_calls` 改造不是换个列表那么简单：B' 分支的 `_partition_calls`/组内 `all_calls[i]`/回填 `results[_i]`、C 分支的 `enumerate(all_calls, 1)`、A 分支固定取号 `1`，都要同步改。最关键是取号必须用 `_active_indices[pos] + 1`——`handle_action` 传给 `execute_tools` 的是 `make_fp_callback(agent, step, _exec_calls)`，工厂按 `exec_calls[_tno - 1]` 取 `params_raw_str`；取号回退会把**原始参数串写错文件**（落盘污染，非仅仅序号难看）。
> 3. 被拒调用的结果体用 `build_error(llm_data={summary, action, status})`，`data` 为空即可；observation 拼装直接读 `llm_data.summary`，不需要伪造工具数据。
> 4. 别名计数不能只归一不写回：`tool_retry_engine._prepare_execution` 用 `self._tools.get(action)` **裸名查表**，别名不写回会在执行层报"工具未找到"。计数循环命中委托时须把 `c["tool_name"]` 原地写回主名（只写回委托别名，不碰其它工具的别名路径），否则别名虽然被正确计数，前 6 个也跑不起来。
>
> 并行前提不变：`delegateagent` 不在 `FILE_OPERATION_TOOLS`/`WINDOW_TARGET_TOOLS`/`_SQL_TOOLS`，`_partition_calls` 对无冲突键的委托各自成组，`gather` 才真并行；不得为了"方便"把它加进这三张表。

**测试文件**：`backend/tests/probe_delegate_s5_parallel_cap.py`（本地探针，按 §6.2.11 第 4 条不提交）。运行：`cd backend && python -m pytest tests/probe_delegate_s5_parallel_cap.py -v --timeout=90`（用例含多轮 6 路真实委托；遇到 429 限流时把任务提示改短、分批跑，不得改为 mock）。

**A. 上限拦截（验收 1、2）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 常量单点 | `tool_constants.MAX_PARALLEL_SUB_AGENTS == 6`；`tool_runner.MAX_PARALLEL_SUB_AGENTS` 与之同一对象；`tool_runner` 源码中无 `MAX_PARALLEL_SUB_AGENTS =` 定义行 |
| T02 | 超限拒绝 | 一轮 7 个 `delegateagent` → `len(results)==7`；前 6 个锁"真实执行返回的结构体（含 `llm_data`、无上限拒绝文案）"，第 7 个 `is_success` 为 False、summary 含「上限 6」；执行 spy 只记录 6 次（第 7 个未执行）。provider 限流下前 6 个可能返回限流错误体，故不锁 LLM 成功；上限断言本身不放宽 |
| T03 | 别名同拦 | 7 个调用混用 `delegate_task`/`delegate_to_agent`/`call_agent`/`invoke_agent`：计数自带归一仍按 6 拦；前 6 个写回主名后真实执行、第 7 个被拒（同 T02，只判真实执行与被拒结果，不锁 LLM 成功） |
| T04 | 不误伤 | 8 个非委托探针工具全执行、全成功；另测 3 委托 + 5 探针混跑同样 8 条全执行（委托数 3 < 6） |

**B. 索引与取号（验收 3、4、5）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T05 | 结果索引对齐 | 8 调用 = 7 委托 + 1 探针（探针在第 8 位）：`len(results)==8`，被拒的委托位是 error、其它位保留各自真实结果，不得整体前移错位 |
| T06 | 取号不回退 | 同上用例注入 `on_attempt_recorded` 工厂记录收到的序号 → 恰为 `[1,2,3,4,5,6,8]`（被拒的第 7 位不取号，第 8 位不能回退成 7） |
| T07 | 单工具路径不变 | 1 个 `delegateagent` 仍走 A 分支：`len(results)==1`、结果仍是真实委托返回、执行 spy 只 1 次，与 S4 一致 |

**C. 并行不退化（验收 6）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T08 | 真并行 | 同轮 3 个不同主题 researcher 委托：执行 spy 的 start/end 时间戳显示至少 2 个 start 早于第一个 end（重叠执行）；静态断言 `_has_conflict(calls) is False`（结构性前提），并报告总耗时佐证；重叠断言比验收第 6 项的耗时阈值更严格（串行时必红），耗时只作证据、不放宽为"只判耗时" |
| T09 | 冲突仍串行 | 同路径 `write` + `read`（读-读无竞态不算冲突，必须用一写一读）：`_has_conflict` 为 True；spy 显示第 2 个 start 不早于第 1 个 end——证明切到 `_active_calls` 后 B' 分组串行语义未退化 |

**D. 回归与静态契约**

S1–S4 探针全绿；E2E-P0-03b PASSED；按改动符号（`tool_runner`/`tool_constants`）筛出的定向集 `--timeout=60` 失败集合与基线逐条相同、新增 0；`ruff check` 全过；`MAX_PARALLEL_SUB_AGENTS` 全仓只在 `tool_constants.py` 定义、`tool_runner.py` 消费。

**打点边界（红绿之外的纪律）**：允许 = 包装真 `execute_tool` 记时间戳（行为原样透传）、`on_attempt_recorded` 工厂只记序号、`caplog`；禁止 = mock LLM / 替执行函数 / 替 `_has_conflict` / 改小常量上限 / 把被拒调用直接丢弃而不回填 error（那会让 `len(results)` 变短，属于用破坏契约换"看起来正常"）。快照与还原统一放 fixture 卸载，`finally` 里 reset。

**红绿节奏（每轮只推进一组，全绿再进下一组）**：

| 轮次 | 先写的红用例 | 让它变绿的最小实现 |
|------|-------------|-------------------|
| R1 | T01、T02 | 新增常量 + 扩展名纠错循环之后插入计数与 `_over` 拒绝（先把 ImportError 转成断言红） |
| R2 | T03 | 计数时 `normalize_tool_name` + 委托别名写回主名；只拦不写回会让前 6 个"工具未找到" |
| R3 | T04 | 非委托调用不进 `_over`：`_active_calls` 原样透传，三分支行为不变 |
| R4 | T05、T06、T07 | 全量 `_active_indices` 映射：末尾按原索引回填、三分支取号统一用 `_active_indices[pos]+1`、A 分支同样走映射 |
| R5 | T08、T09 | 不动冲突检测与 `gather` 分组；只把分组/组内取数改读 `_active_calls`，验证并行与串行两面都不退化 |
| R6 | D 组 | 四探针 + 定向回归 + `ruff check` 全过；无 `skip`/`xfail` 才算本阶段可提交 |

**测试代码**：

```python
# -*- coding: utf-8 -*-
"""并行上限 TDD 探针 — 小欧 2026-11-28

真实 LLM / 工具 / SQLite；只做观测型打点（包装真执行函数、记录取号序号）。
探针按仓库铁律不入库。
运行：cd backend && python -m pytest tests/probe_delegate_s5_parallel_cap.py -v --timeout=90
"""
import asyncio
import inspect
import time
import uuid
from pathlib import Path

import pytest

from app.services.agent import tool_runner
from app.services.agent.tool_runner import execute_tools
from app.services.agent.universal_agent import UniversalAgent
from app.services.lifecycle.service import get_service
from app.tools import ensure_tools_registered, tool_constants
from app.tools.conflict_detector import _has_conflict
from app.tools.registry import tool_registry
from app.tools.tool_response import build_success, is_success
from app.tools.tool_types import ToolCategory

ensure_tools_registered()


def _delegate(task):
    return {"tool_name": "delegateagent",
            "tool_params": {"agent_id": "researcher", "task": task},
            "fc_context": {}}


@pytest.fixture
def parent_task():
    return f"s5-probe-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def parent_client():
    c = get_service()
    yield c
    asyncio.run(c.close())


@pytest.fixture
def parent(parent_client, parent_task):
    return UniversalAgent(llm_client=parent_client, task_id=parent_task,
                          max_steps=4, track_task=False)


@pytest.fixture
def events(monkeypatch):
    seen = []
    real = tool_runner.execute_tool

    async def _spy(agent, tool_name, *a, **kw):
        seen.append(("start", tool_name, time.monotonic()))
        try:
            return await real(agent, tool_name, *a, **kw)
        finally:
            seen.append(("end", tool_name, time.monotonic()))

    monkeypatch.setattr(tool_runner, "execute_tool", _spy)
    return seen


@pytest.fixture
def echo_tools(parent):
    made = []
    seen = []

    for i in range(8):
        name = f"s5_probe_echo_{i}"

        def _make(idx):
            def _impl(**kw):
                seen.append(idx)
                return build_success(data={"idx": idx})
            return _impl

        tool_registry.register(name=name, description="探针回显",
                               category=ToolCategory.FUNDAMENTAL, implementation=_make(i))
        made.append(name)
    parent._tool_loader.load_category(ToolCategory.FUNDAMENTAL)
    yield seen
    for name in made:
        tool_registry.unregister(name)


def test_T01_constant_single_source():
    assert tool_constants.MAX_PARALLEL_SUB_AGENTS == 6
    assert tool_runner.MAX_PARALLEL_SUB_AGENTS is tool_constants.MAX_PARALLEL_SUB_AGENTS
    src = Path(inspect.getsourcefile(tool_runner)).read_text(encoding="utf-8")
    assert "MAX_PARALLEL_SUB_AGENTS =" not in src


def test_T02_cap_rejects(parent, events):
    calls = [_delegate(f"1+1=? 第{i}题") for i in range(7)]
    results = asyncio.run(execute_tools(parent, calls, True))
    assert len(results) == 7
    assert len([e for e in events if e[0] == "start"]) == 6
    # 前 6 个锁真实执行返回的结构体，不锁 LLM 成功：provider 限流下委托可能返回限流错误体，
    # 但上限断言（spy 只 6 次、第 7 个被拒、results 长度 7）不受影响。
    assert all(isinstance(r, dict) and isinstance(r.get("llm_data"), dict)
               and "上限 6" not in (r.get("llm_data") or {}).get("summary", "")
               for r in results[:6])
    assert not is_success(results[6])
    assert "上限 6" in results[6]["llm_data"]["summary"]


def test_T03_alias_cap(parent, events):
    names = ("delegate_task", "delegate_to_agent", "call_agent",
             "invoke_agent", "delegate_task", "call_agent", "invoke_agent")
    calls = [{"tool_name": n, "tool_params": {"agent_id": "researcher", "task": "1+1=?"},
              "fc_context": {}} for n in names]
    results = asyncio.run(execute_tools(parent, calls, True))
    assert len(results) == 7
    assert len([e for e in events if e[0] == "start"]) == 6
    assert all(isinstance(r, dict) and isinstance(r.get("llm_data"), dict)
               and "上限 6" not in (r.get("llm_data") or {}).get("summary", "")
               for r in results[:6])
    assert not is_success(results[6]) and "上限 6" in results[6]["llm_data"]["summary"]


def test_T04_no_false_positive(parent, echo_tools):
    calls = [{"tool_name": f"s5_probe_echo_{i}", "tool_params": {}, "fc_context": {}}
             for i in range(8)]
    results = asyncio.run(execute_tools(parent, calls, True))
    assert len(results) == 8 and all(is_success(r) for r in results)
    assert echo_tools == list(range(8))
    mixed = [_delegate("1+1=?") for _ in range(3)] + calls[:5]
    results2 = asyncio.run(execute_tools(parent, mixed, True))
    assert len(results2) == 8 and all(isinstance(r, dict) for r in results2)


def test_T05_result_index_aligned(parent, echo_tools):
    calls = [_delegate(f"1+1=? 第{i}题") for i in range(7)]
    calls.append({"tool_name": "s5_probe_echo_7", "tool_params": {}, "fc_context": {}})
    results = asyncio.run(execute_tools(parent, calls, True))
    assert len(results) == 8
    assert not is_success(results[6]) and is_success(results[7])
    assert results[7]["data"]["idx"] == 7


def test_T06_attempt_number_not_shifted(parent, echo_tools):
    calls = [_delegate(f"1+1=? 第{i}题") for i in range(7)]
    calls.append({"tool_name": "s5_probe_echo_7", "tool_params": {}, "fc_context": {}})
    numbers = []

    def _factory(n):
        numbers.append(n)
        return lambda *a, **kw: None

    asyncio.run(execute_tools(parent, calls, True, on_attempt_recorded=_factory))
    assert numbers == [1, 2, 3, 4, 5, 6, 8]


def test_T07_single_tool_path(parent, events):
    results = asyncio.run(execute_tools(parent, [_delegate("1+1=?")], False))
    assert len(results) == 1
    assert (results[0].get("data") or {}).get("agent_id") == "researcher"
    assert len([e for e in events if e[0] == "start"]) == 1


def test_T08_true_parallel(parent, events):
    calls = [_delegate(f"主题{i}：1+1=?") for i in range(3)]
    assert _has_conflict(calls) is False
    t0 = time.monotonic()
    results = asyncio.run(execute_tools(parent, calls, True))
    elapsed = time.monotonic() - t0
    starts = [e[2] for e in events if e[0] == "start"]
    first_end = min(e[2] for e in events if e[0] == "end")
    assert sum(1 for t in starts if t < first_end) >= 2, "至少两个委托在第一个结束前启动"
    assert len(results) == 3 and all(isinstance(r, dict) for r in results)
    print(f"  [T08] 3 路委托总耗时 {elapsed:.2f}s，重叠启动 {len(starts)} 次")


def test_T09_conflict_still_serial(parent, events, tmp_path):
    f = tmp_path / "s5_conflict.txt"
    f.write_text("x", encoding="utf-8")
    calls = [
        {"tool_name": "write", "tool_params": {"path": str(f), "content": "x"}, "fc_context": {}},
        {"tool_name": "read", "tool_params": {"path": str(f)}, "fc_context": {}},
    ]
    assert _has_conflict(calls) is True
    asyncio.run(execute_tools(parent, calls, True))
    starts = [e[2] for e in events if e[0] == "start"]
    ends = [e[2] for e in events if e[0] == "end"]
    assert starts[1] >= ends[0], "同路径两读必须串行，切 _active_calls 不得退化"
```

**退出判据**：A–C 共 T01–T09 全绿（无 `skip`/`xfail`），D 组回归与静态契约全过；每条用例有原始输出（执行 spy 时间戳 / 取号序号 / 结果体 / `ruff` 输出）支撑。探针按铁律不提交。

**验收清单**：

1. **超限拒绝**：一轮 7 个 `delegateagent` 调用，前 6 个执行、第 7 个返回 error（summary 含"上限 6"），`results` 长度仍为 7 且索引对齐。
2. **别名同拦**：7 个调用混用 `delegate_task`/`call_agent`，计数自带 `normalize_tool_name` 后仍按 6 拦（此时 `all_calls` 里的 `tool_name` 仍是别名，直接比较会全部放过——本条就是卡这个漏洞）。
3. **不误伤**：一轮 8 个非委托工具（或 3 个委托 + 5 个读工具）全部执行，无上限误拦。
4. **取号不回退**：被拒委托之后的调用，`on_attempt_recorded` 序号仍等于其原始调用序号（§2.5.1 隐藏改动点）。
5. **单工具路径不变**：1 个 `delegateagent` 调用仍走 A 分支，结果与 S4 一致。
6. **真并行**：同轮 3 个不同主题的 researcher 委托，总耗时 < 最慢单个耗时 × 2（证明 `gather` 生效，不是串行累加）。

**退出标准**：1–6 全绿；`MAX_PARALLEL_SUB_AGENTS` 全仓仅 `tool_constants.py` 定义、`tool_runner.py` 引用两处。

**失败回退**：第 1/4 项说明回填或取号映射没做对，回退 `tool_runner` 改动重做（不得只删校验保留 `_active_calls`）；第 6 项若退化，核对是否误把 `delegateagent` 加入了 `FILE_OPERATION_TOOLS`/`WINDOW_TARGET_TOOLS`/`_SQL_TOOLS`（§2.5.1 结构性前提）。

**实施记录（2026-11-28）**：按参考代码落地——`tool_constants.py` 新增单点常量，`tool_runner.execute_tools` 计数前归一并写回委托主名、超限结构化拒绝、三分支改读活跃集且取号统一走 `_active_indices[pos]+1`、末尾按原索引回填。探针 `backend/tests/probe_delegate_s5_parallel_cap.py` 分批跑通后完整一次 **9 passed / 0 failed**（253.95s）。过程中修正两处用例设计错误：同路径两 `read` 不构成冲突（改一写一读）、探针工具注册晚于 Agent 构造（注册后 `load_category` 灌入执行字典）。T02/T03 在 provider 限流（每 3 分钟 3 次）下前 6 路委托返回限流/超时错误体，断言改为只锁"真实执行返回的结构体 + 第 7 个被拒 + results 长度 7"，spy 仍只 6 次，上限断言未放宽。`ruff check`：F 类零命中；8 条 W29x 为未改动 docstring 的存量空白字符告警。定向回归尚未执行，不宣称 D 组全过。按用户要求不产出独立阶段验收记录文件。

#### 6.2.8 S6 P1 增强（3–4 天，四个可独立验收的子阶段）

| 子阶段 | 目标 | 验收要点 |
|--------|------|----------|
| **S6.1** 异步委托 | `wait=False` 立即返回 `delegate_id`，完成后经 inbox 回灌 | ①调用 1s 内返回 `status=running` + `delegate_id`；②子 Agent 完成后父下一轮 `drain_inbox` 取到通知，对话历史出现该消息且带 `delegate_id`；③3 个并发异步委托结果不串（按 `delegate_id` 区分）；④父任务取消后未完成后台委托终止，无 `sub-` 残留；⑤不再出现"P1 未实现"拒绝 |
| **S6.2** 插件化 | manifest 扫描注册，新增 Agent 不放代码 | ①`config/config.yaml` 增 `tuning.agent.plugins_dir`；②放 2 个 manifest（1 合法 1 非法），启动后 `list_available` 含合法项、非法项仅 warning；③工具描述含插件 agent；④manifest 写 `track_task`/`allow_delegate` 被忽略（`config.track_task is False`）；⑤目录不存在静默跳过、不阻塞启动 |
| **S6.3** 名粒度放行 | `tool_names` 精确放行 + 参数别名 | ①manifest 写 `tool_names:["read","find"]` 后子 `_tools_dict` 与可见列表都只剩这两项（过滤发生在 `ToolRetryEngine` 构造之前）；②`PARAM_ALIASES["delegateagent"]={"prompt":"task"}` 下传 `prompt` 能成功；③未声明 `tool_names` 时行为与 S5 一致 |
| **S6.4** 多层与跨 provider | `allow_delegate=True` 允许 2 层；`AgentConfig` 增 `provider`/`api_base` | ①允许配置下深度 1 可再委托、深度 2 被拒；②不带 `allow_delegate` 仍只 1 层；③跨 provider 子 client 用正确 `base_url`，不误用父池；④父池不被关闭 |

**TDD 实施方法（按子阶段逐个先红后绿，纪律同 S5）**：

> 四个子阶段各自独立验收、串行为主（§6.2.12：S6.3 依赖 S6.2 的 manifest，S6.4 依赖 S6.3 的名粒度放行）。**先写失败用例 → 最小实现 → 重构保持绿**；禁止先落实现再补用例，禁止为变绿放宽断言。仍用真实 LLM / 真实工具 / 真实 SQLite；配置一律经 `app.config.get_config_path()` / `get_code_root()` 读写，禁止硬编码配置路径，测试目录用 `tmp_path`，不碰生产 `config.yaml`。允许的观测型打点：构造器/client 工厂 spy（包装真实现）、`caplog`、临时目录与临时 manifest；禁止 mock LLM、假 DB、替换 `run_react_cycle`、把拒绝清单/别名表/深度上限临时改小来变绿。
>
> 对码核实的实施缺口（写码前先确认，避免"文档写了但代码里没有"）：
>
> 1. **S6.1**：`task_registry.inject_system_notice(task_id, content, session_id)` 与 `drain_inbox(task_id)` 已存在、`react_step._absorb_inbox` 每轮调用（`react_step.py:244-267`），**回灌通道不用新建**；缺的是 `wait=False` 放开（`delegateagent_runner.py:221-223` 当前显式拒绝）、`delegate_id` 生成与后台句柄表、以及完成时注入带 `delegate_id` 的通知。注意 `drain_inbox` 返回 `(content, uid)` 元组，注入内容必须自带 `delegate_id` 文本，不能靠结构化字段。
> 2. **S6.2**：`plugin_loader.py` 当前**不存在**，`agent_register` 只有注释占位；`AgentRegistry.load_from_manifest` 已存在且硬编码 `track_task=False`、未消费 `allow_delegate`（`agent_config.py:141-151`），越权字段天然被忽略。配置项按 `get_config().get("tuning.agent.plugins_dir", "")` 读，缺省 `get_code_root()/plugins`。
> 3. **S6.3**：`AgentConfig` 当前无 `tool_names` 字段；`to_openai_tools` 的 `tool_names` 形参语义是**额外包含**（`tool_description.py:45/66-68`：分类命中的工具无条件保留，`tool_names` 只放行分类外的工具），**不是精确白名单**，因此不能靠「透传」达成「只剩两项」——须新增真正的白名单过滤（`categories=None` + `tool_names` 精确集，或独立过滤路径）；`tool_cache_manager.get_openai_tools` 当前只透传 `exclude`、未透传 `tool_names`（`tool_cache_manager.py:31-34`）；执行面必须在 `ToolRetryEngine(self._tools_dict)` **构造之前**筛字典（`universal_agent.py:78-80`），构造后改 `_tools_dict` 不改引擎。子 Agent 唯一构造点在 `delegateagent_runner.py:259-266`，`tool_names` 须由 `AgentConfig` 在该处传入；`UniversalAgent.__init__`（`universal_agent.py:52-60`）当前无 `tool_names` 形参，新增该形参并接入 `ToolLoader.init_tools` 属 R5 最小实现。`PARAM_ALIASES` 当前无 `delegateagent` 条目，`prompt→task` 需新增。
> 4. **S6.4**：`AgentConfig` 无 `allow_delegate`/`provider`/`api_base` 字段；`MAX_DELEGATE_DEPTH=1` 是 runner 模块常量，须改为按配置取值；跨 provider 时 `create_llm_client` 的 `base_url` 取子配置且**不传 `shared_client`**（不能复用父 httpx 池），否则 base_url 错配。
>
> 四个探针均放本地 `backend/tests/`，按铁律不提交；真实 429 限流下只锁"结构与可判定事实"（状态、id、条数、DB/buffer 行、池对象身份），不锁 LLM 文案。

**S6.1 异步委托（`backend/tests/probe_delegate_s6_1_async.py`）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 立即返回契约 | `wait=False` 调 `run_delegate` → 1s 内返回 `status=="running"`、非空 `delegate_id`，不再含「P1 未实现」；`wait=True` 仍同步返回 `success/failed`（回归） |
| T02 | inbox 回灌 | 子 Agent 完成后 `inject_system_notice(父task, 带 delegate_id 的文本)`；父下一轮 `_absorb_inbox`（或父 step）后 `drain_inbox` 为空且对话历史末条含该文本与 `delegate_id`（只看 inbox→历史，SSE notice 不算通过；探针须真跑吸收路径，只手工 `inject`/`drain` 不算通过；注入前已有 assistant/tool 对时配对不破，以历史条数只 +1 判定） |
| T03 | 并发不串 | 3 个 `wait=False` 并发，三个 `delegate_id` 互不相同；3 条 inbox 通知内容各自带对应 id、不串味（探针锁 id 唯一；通知内容不串由完成回调注入实现与 T02 同源覆盖） |
| T04 | 父取消联动 | 父任务 `set_cancelled` 后未完成后台委托被终止；`agent_streams` 无 `sub-` 残留；`finally cleanup_task`（探针须先让 `wait=False` 真正创建 `sub-` 委托再取消，仅在 `wait=False` 被拒绝时断言无 `sub-` 属恒绿、不算通过） |
| T05 | 同步回归 | `wait=True` 仍同步返回 `success/failed`，不再含「P1 未实现」拒绝；异步 T01–T04 不改同步路径行为（tool_call 配对不破由 T02 的历史条数断言覆盖） |

**S6.2 插件化（`backend/tests/probe_delegate_s6_2_plugin.py`）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 配置项与扫描器 | `plugin_loader.load_plugins` 可导入；`get_config().get("tuning.agent.plugins_dir", "")` 缺省回落 `get_code_root()/plugins` |
| T02 | 合法/非法 manifest | `tmp_path` 放 2 个 manifest（1 合法 1 非法）→ `load_plugins()` 只返回合法 id；`list_available` 含合法项、非法项仅 warning；`caplog` 有跳过原因 |
| T03 | 描述含插件 | `build_delegate_tool_description()` 与 `get_openai_tools(parent)` 均含插件 agent id |
| T04 | 越权字段忽略 | manifest 写 `track_task:true`/`allow_delegate:true` → 加载后 `config.track_task is False`，本子阶段 `allow_delegate` 不生效 |
| T05 | 目录不存在 | 指向不存在目录 → `load_plugins()` 返回 `[]`、不抛、不阻塞 |
| T06 | 调用点生效 | spy 包装 `load_plugins`，`ensure_tools_registered()` 后确认在 `delegateagent` 注册前被调用一次 |

**S6.3 名粒度放行（`backend/tests/probe_delegate_s6_3_tool_names.py`）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 执行面构造前过滤 | manifest 写 `tool_names:["read","find"]` → 子 `_tools_dict` 与 `_retry_engine._tools` **同一 dict 引用**且只剩两项；构造后无残留写类工具 |
| T02 | 可见性同源 | `get_openai_tools(child)` 的 function name 集合恰为 `{read,find}`（可见性也读 `tool_names`，不只看分类） |
| T03 | 参数别名 | `PARAM_ALIASES["delegateagent"]["prompt"]=="task"`；别名归一执行路径由 S4 探针覆盖，本探针只锁映射表条目（真调一次受 429 限流时按同一口径） |
| T04 | 未声明不退化 | 不带 `tool_names` 的 manifest 与 S5 行为一致：子工具集按分类 + 拒绝清单，不误收窄 |

**S6.4 多层与跨 provider（`backend/tests/probe_delegate_s6_4_depth.py`）**

| # | 场景 | 测试设计（输入 → 预期 → 断言） |
|---|------|-------------------------------|
| T01 | 允许两层 | `allow_delegate=True` 的 config：深度 0 委托成功、深度 1 子 Agent 再委托成功、深度 2 被拒且 summary 含「深度超限」（探针只锁深度门禁早退边界；「两层都成功」由真实委托调用覆盖，429 限流下不锁 LLM 文案） |
| T02 | 默认仍一层 | 不带 `allow_delegate` → 深度 1 即被拒（S3 基线不退化） |
| T03 | 跨 provider client | config 写 `provider`/`api_base` → 子 client 的 `llm_model.provider/api_base` 等于子配置、`shared_client` 为 None（不复用父池） |
| T04 | 父池不被关 | 跨 provider 委托返回后父 `ensure_client_pool().is_closed is False`，子独立池已 close |

**打点边界**：允许 = 构造器/client 工厂 spy、`caplog`、`tmp_path` 临时目录与合法/非法 manifest、受控 `set_current_delegate_callback`（仅观察回灌时 `finally` reset）；禁止 = mock LLM 返回、假 SQLite、替换 `run_react_cycle`/`_absorb_inbox`、临时改小拒绝清单/深度上限、把非法 manifest 改成合法来让 T02 变绿。S6.3 的 `named_agent` 直接构造只验证执行面（`_tools_dict` / `_retry_engine` / 可见性）过滤；真实委托路径由 runner 在 `delegateagent_runner.py:259-266` 透传 `config.tool_names` 覆盖（R5），两者缺一不可。

**红绿节奏（每子阶段内全绿再进下一个）**：

| 轮次 | 先写的红用例 | 让它变绿的最小实现 |
|------|-------------|-------------------|
| R1 | S6.1 T01 | `run_delegate` 放开 `wait=False`：生成 `delegate_id` + 后台句柄表，立即返回 running |
| R2 | S6.1 T02–T05 | 完成回调经既有 `inject_system_notice` 注入带 id 的文本；探针 T02 必须真跑 `_absorb_inbox` 且断言 `message_builder.conversation_history` 含 `delegate_id`（只手工 `inject`/`drain` 不算红转绿）；T04 须先确认 `sub-` 委托已创建再取消并断言清退 |
| R3 | S6.2 T01、T05 | 新增 `plugin_loader.py`（按 §2.1.1 参考实现）+ 配置项读取，目录不存在静默跳过 |
| R4 | S6.2 T02–T04、T06 | 调用点接入 `_register_agent_tools`，manifest 容错与越权字段忽略由 `load_from_manifest` 兜底 |
| R5 | S6.3 表 T01、T02、T04 | `AgentConfig.tool_names` 字段 + `UniversalAgent.__init__` 新增 `tool_names` 形参并接入 `ToolLoader.init_tools`（在 `ToolRetryEngine(self._tools_dict)` 构造前筛字典，`universal_agent.py:80`）+ runner 构造子 Agent 处透传 `config.tool_names`（`delegateagent_runner.py:259-266`）+ `get_openai_tools` 以 `tool_names` 作**精确白名单**（不能用现有「额外包含」语义，否则分类内工具不会被收窄） |
| R6 | S6.3 表 T03 | `PARAM_ALIASES["delegateagent"]` 加 `prompt→task`（别名归一执行路径由 S4 探针覆盖，本探针只锁映射表条目） |
| R7 | S6.4 T01、T02 | `allow_delegate` 字段 + 深度上限改配置驱动（默认仍 1） |
| R8 | S6.4 T03、T04 | `provider`/`api_base` 字段 + 跨 provider 新建独立 client（不共享父池） |
| R9 | 四探针 + 定向回归 + `ruff check` | 全绿、无 `skip`/`xfail`、失败集合与基线逐条相同才算 S6 可提交；探针条数以实际代码为准（S6.1 5 条、S6.2 6 条、S6.3 3 条、S6.4 4 条） |

**测试代码（四个探针，本地不提交）**：

```python
# backend/tests/probe_delegate_s6_1_async.py — 小欧 2026-11-28
# 运行：cd backend && python -m pytest tests/probe_delegate_s6_1_async.py -v --timeout=90
import asyncio
import uuid

import pytest

from app.services.agent import delegateagent_runner as runner
from app.services.agent import react_step
from app.services.task import task_registry, task_state
from app.services.agent.universal_agent import UniversalAgent
from app.services.lifecycle.service import get_service
from app.tools import ensure_tools_registered

ensure_tools_registered()
TASK = "s6-async-probe"


@pytest.fixture(scope="module")
def client():
    c = get_service()
    yield c
    asyncio.run(c.close())


@pytest.fixture
def parent(client):
    return UniversalAgent(llm_client=client, task_id=TASK, max_steps=4, track_task=False)


def test_T01_immediate_return(parent):
    async def _main():
        await task_registry.register_task(TASK)
        try:
            return await runner.run_delegate(parent, "researcher", "1+1=?", wait=False)
        finally:
            await task_registry.cleanup_task(TASK)
    r = asyncio.run(_main())
    assert r["status"] == "running" and r.get("delegate_id")
    assert "P1" not in r.get("summary", "")


def test_T02_inbox_to_history(parent):
    did = "d-" + uuid.uuid4().hex[:8]
    async def _main():
        await task_registry.register_task(TASK)
        try:
            parent.message_builder.add_assistant_tool_call([{"id": "c1", "type": "function"}])
            parent.message_builder.add_tool_result("c1", "done")
            before = len(parent.message_builder.conversation_history)
            await task_registry.inject_system_notice(TASK, f"异步委托完成 {did}")
            n = await react_step._absorb_inbox(parent)      # 真跑吸收路径，不是手工 drain
            assert n >= 1
            assert not await task_registry.drain_inbox(TASK)              # inbox 已取走
            hist = parent.message_builder.conversation_history
            assert len(hist) == before + 1                                # 已有 assistant/tool 对未被改写
            assert any(did in str(m.get("content", "")) for m in hist)    # 父 LLM 真读到
        finally:
            await task_registry.cleanup_task(TASK)
    asyncio.run(_main())


def test_T03_concurrent_ids(parent):
    async def _main():
        await task_registry.register_task(TASK)
        try:
            return await asyncio.gather(*[
                runner.run_delegate(parent, "researcher", f"1+1=? #{i}", wait=False)
                for i in range(3)])
        finally:
            await task_registry.cleanup_task(TASK)
    rs = asyncio.run(_main())
    ids = [r["delegate_id"] for r in rs]
    assert len(set(ids)) == 3


def test_T04_cancel_stops_background(parent):
    async def _main():
        await task_registry.register_task(TASK)
        try:
            r = await runner.run_delegate(parent, "researcher", "写一篇长文", wait=False)
            assert r["status"] == "running" and r.get("delegate_id")      # 必须先真创建后台委托
            await asyncio.sleep(0.1)
            assert any(k.startswith("sub-") for k in task_state.agent_streams)  # 后台委托已建
            await task_registry.set_cancelled(TASK)
            await asyncio.sleep(2)
            return r
        finally:
            await task_registry.cleanup_task(TASK)
    asyncio.run(_main())
    assert not any(k.startswith("sub-") for k in task_state.agent_streams)  # 取消联动已清退


def test_T05_sync_not_regressed(parent):
    r = asyncio.run(runner.run_delegate(parent, "researcher", "1+1=?", wait=True))
    assert r["status"] in ("success", "failed") and "P1" not in r.get("summary", "")
```

```python
# backend/tests/probe_delegate_s6_2_plugin.py — 小欧 2026-11-28
# 运行：cd backend && python -m pytest tests/probe_delegate_s6_2_plugin.py -v --timeout=90
import json
from pathlib import Path

import pytest

from app.config import get_config, get_code_root
from app.services.lifecycle.service import get_service
from app.services.agent.universal_agent import UniversalAgent
from app.tools import ensure_tools_registered
from app.tools.agent import agent_register
from app.tools.agent.agent_config import build_delegate_tool_description, get_agent_registry
from app.tools.agent.plugin_loader import load_plugins
from app.tools.registry import tool_registry

ensure_tools_registered()


@pytest.fixture
def plugin_dir(tmp_path, monkeypatch):
    d = tmp_path / "plugins"
    (d / "ok_agent").mkdir(parents=True)
    (d / "ok_agent" / "manifest.json").write_text(json.dumps({
        "name": "s6_ok", "description": "探针合法插件",
        "tool_categories": ["fundamental"], "max_steps": 4,
        "track_task": True, "allow_delegate": True,
    }), encoding="utf-8")
    (d / "bad_agent").mkdir()
    (d / "bad_agent" / "manifest.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr("app.config.get_config", lambda: {"tuning.agent.plugins_dir": str(d)})
    yield d
    get_agent_registry().unregister("s6_ok")


def test_T01_config_and_loader():
    assert callable(load_plugins)
    root = Path(get_config().get("tuning.agent.plugins_dir", "") or str(Path(get_code_root()) / "plugins"))
    assert isinstance(root, Path)


def test_T02_manifest_tolerant(plugin_dir, caplog):
    loaded = load_plugins()
    assert "s6_ok" in loaded and "s6_ok" in get_agent_registry().list_available()
    assert "bad json" in caplog.text or "manifest" in caplog.text.lower()


def test_T03_description_has_plugin(plugin_dir):
    load_plugins()
    assert "s6_ok" in build_delegate_tool_description()
    client = get_service()
    agent = UniversalAgent(llm_client=client, task_id="s6-plugin-probe", track_task=False)
    tools = {t["function"]["name"]: t["function"]["description"]
             for t in tool_registry.to_openai_tools(categories=agent._loaded_categories)}
    assert "s6_ok" in tools["delegateagent"]["description"]


def test_T04_no_privilege_escalation(plugin_dir):
    load_plugins()
    cfg = get_agent_registry().get("s6_ok")
    assert cfg.track_task is False


def test_T05_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.get_config", lambda: {"tuning.agent.plugins_dir": str(tmp_path / "nope")})
    assert load_plugins() == []


def test_T06_call_site(monkeypatch):
    calls = []
    real = agent_register.load_plugins
    monkeypatch.setattr(agent_register, "load_plugins", lambda: calls.append(1) or real())
    agent_register._register_agent_tools()
    assert calls and tool_registry.get_tool("delegateagent") is not None
```

```python
# backend/tests/probe_delegate_s6_3_tool_names.py — 小欧 2026-11-28
# 运行：cd backend && python -m pytest tests/probe_delegate_s6_3_tool_names.py -v --timeout=90
import pytest

from app.services.agent.tool_cache_manager import get_openai_tools
from app.services.agent.universal_agent import UniversalAgent
from app.services.lifecycle.service import get_service
from app.tools import ensure_tools_registered
from app.tools.agent.agent_config import AgentConfig, get_agent_registry
from app.tools.tools_alias_mapper import PARAM_ALIASES
from app.tools.tool_types import ToolCategory

ensure_tools_registered()


@pytest.fixture
def named_agent():
    cfg = AgentConfig(agent_id="s6_named", description="探针名粒度",
                      tool_categories={ToolCategory.FILE, ToolCategory.FUNDAMENTAL},
                      tool_names={"read", "find"})
    get_agent_registry().register(cfg)
    c = get_service()
    agent = UniversalAgent(llm_client=c, task_id="s6-named-probe",
                           initial_categories={ToolCategory.FILE, ToolCategory.FUNDAMENTAL},
                           tool_names=cfg.tool_names, track_task=False)
    yield agent
    get_agent_registry().unregister("s6_named")


def test_T01_exec_and_visible(named_agent):
    assert set(named_agent._tools_dict) == {"read", "find"}
    assert set(named_agent._retry_engine._tools) == {"read", "find"}
    assert named_agent._retry_engine._tools is named_agent._tools_dict
    assert {t["function"]["name"] for t in get_openai_tools(named_agent)} == {"read", "find"}


def test_T02_param_alias():
    assert PARAM_ALIASES["delegateagent"]["prompt"] == "task"


def test_T03_no_tool_names_default():
    c = get_service()
    agent = UniversalAgent(llm_client=c, task_id="s6-default-probe", track_task=False)
    assert "write" in agent._tools_dict       # 未声明 tool_names 不误收窄
```

```python
# backend/tests/probe_delegate_s6_4_depth.py — 小欧 2026-11-28
# 运行：cd backend && python -m pytest tests/probe_delegate_s6_4_depth.py -v --timeout=90
import asyncio

import pytest

from app.services.agent import delegateagent_runner as runner
from app.services.agent.universal_agent import UniversalAgent
from app.services.lifecycle.service import get_service
from app.tools import ensure_tools_registered
from app.tools.agent.agent_config import AgentConfig, get_agent_registry
from app.tools.tool_types import ToolCategory

ensure_tools_registered()


@pytest.fixture
def parent():
    c = get_service()
    return UniversalAgent(llm_client=c, task_id="s6-depth-probe", max_steps=4, track_task=False)


@pytest.fixture
def configs():
    made = []
    yield
    for aid in made:
        get_agent_registry().unregister(aid)


def test_T01_two_levels(parent, configs):
    get_agent_registry().register(AgentConfig(agent_id="s6_l1", description="一层",
        tool_categories={ToolCategory.FUNDAMENTAL}, allow_delegate=True))
    get_agent_registry().register(AgentConfig(agent_id="s6_l2", description="二层",
        tool_categories={ToolCategory.FUNDAMENTAL}, allow_delegate=True))
    configs.extend(["s6_l1", "s6_l2"])
    tok = runner._current_delegate_depth.set(1)
    try:
        r = asyncio.run(runner.run_delegate(parent, "s6_l1", "1+1=?"))
        assert "深度超限" not in r.get("summary", "")   # 深度 1 不再早退
        tok2 = runner._current_delegate_depth.set(2)
        try:
            r2 = asyncio.run(runner.run_delegate(parent, "s6_l2", "x"))
            assert r2["status"] == "error" and "深度超限" in r2["summary"]
        finally:
            runner._current_delegate_depth.reset(tok2)
    finally:
        runner._current_delegate_depth.reset(tok)


def test_T02_default_one_level(parent):
    tok = runner._current_delegate_depth.set(1)
    try:
        r = asyncio.run(runner.run_delegate(parent, "researcher", "x"))
        assert r["status"] == "error" and "深度超限" in r["summary"]
    finally:
        runner._current_delegate_depth.reset(tok)


def test_T03_cross_provider(parent, configs, monkeypatch):
    from app.llm import client_sdk
    seen = {}
    real = client_sdk.create_llm_client

    def _spy(*a, **kw):
        seen.update(kw)
        return real(*a, **kw)

    monkeypatch.setattr(client_sdk, "create_llm_client", _spy)
    get_agent_registry().register(AgentConfig(agent_id="s6_cross", description="跨provider",
        tool_categories={ToolCategory.FUNDAMENTAL}, model="m",
        provider="p2", api_base="https://p2.example"))
    configs.append("s6_cross")
    r = asyncio.run(runner.run_delegate(parent, "s6_cross", "1+1=?"))
    assert isinstance(r, dict)
    assert seen.get("llm_model") is not None
    assert "shared_client" in seen and seen["shared_client"] is None  # 显式传 None，不是省略参数
    assert parent.llm_client.ensure_client_pool().is_closed is False


def test_T04_child_pool_closed(parent, configs, monkeypatch):
    from app.llm import client_sdk
    made = []
    real = client_sdk.create_llm_client

    def _spy(*a, **kw):
        c = real(*a, **kw)
        made.append(c)
        return c

    monkeypatch.setattr(client_sdk, "create_llm_client", _spy)
    get_agent_registry().register(AgentConfig(agent_id="s6_cross2", description="跨provider",
        tool_categories={ToolCategory.FUNDAMENTAL}, model="m",
        provider="p2", api_base="https://p2.example"))
    configs.append("s6_cross2")
    asyncio.run(runner.run_delegate(parent, "s6_cross2", "1+1=?"))
    assert made and made[0].ensure_client_pool().is_closed            # 子独立池已关闭
    assert parent.llm_client.ensure_client_pool().is_closed is False  # 父池不受影响
```

**退出判据**：四个探针实际条数全绿（S6.1 T01–T05、S6.2 T01–T06、S6.3 T01–T03、S6.4 T01–T04），无 `skip`/`xfail`；S6.1 必须证明父 LLM 经 inbox 真读到结果——探针 T02 真跑 `_absorb_inbox` 且 `message_builder.conversation_history` 末条含 `delegate_id`，只手工 `inject`/`drain` 不算通过；四个探针与 S1–S5 探针全绿、定向回归失败集合与基线逐条相同、`ruff check` 全过；探针按铁律不提交。

**原验收要点表格（见上）与退出标准保持不变**：

**退出标准**：四个子阶段各自全绿后才算 S6 完成；S6.1 必须验证"父 LLM 真能读到结果"（只看 SSE 出现 notice 不算通过）。

**失败回退**：S6.1 若出现 tool_call 配对错乱，说明直接改了 `conversation_history`，必须改回 `inject_system_notice → drain_inbox`；S6.2/S6.3 若插件 manifest 能越权（自开写权限/多层委托），视为 fail-closed 破口，立即回退并补拒绝清单。

#### 6.2.9 S7 P2 体验增量（暂缓）

- **目标**：前端折叠展示子 Agent 步骤（`stream_orchestrator._SSE_FORWARD_TYPES` + 嵌套渲染）、`react_loop._publish` 支持 `agent.event_sink` 注入、`subagent` 收编。
- **验收要点**：①子步骤在前端可折叠展开，关闭开关时行为回退到 P0；②`event_sink` 注入后不再需要"纯内存 buffer 通行证"，且默认路径零开销；③`subagent` 收编同批完成三件事——从 `UNAVAILABLE_OFFICIAL_TOOLS` 移除、`tuning.agent.disabled_tools` 同步移除、设置页说明同步修改；三者缺一不得上线。
- **退出标准**：三项各自开关可控、默认关闭时与 P0/P1 行为完全一致。

#### 6.2.10 S8 P2+ 开放生态（按需）

- **目标**：`AgentConfig.agent_source`（`local`/`a2a_endpoint`/`mcp_server`）+ 来源解析器，把远端 Agent Card / MCP 工具清单转成本地 `AgentConfig` 进同一注册流程。
- **验收要点**：①`local` 行为零变化（S1–S5 验收项全部仍绿）；②远端 Agent Card 能转出合法 `AgentConfig` 并通过 `__post_init__` 校验；③远端来源默认按不可信处理——远程工具默认视为需确认，`_find_unattended_blocker` 命中即整单拒绝；④深度硬顶、拒绝分类/名单、只读约束对远端**照旧生效**（不因"是远端"放宽）。
- **退出标准**：远端全部走 fail-closed 且失败信息可读；未接入远端时 `load_plugins` 与工具描述与 S6 完全一致。

#### 6.2.11 验收门禁与记录规则

1. **一阶段一记录**：每阶段收尾产出 `notes/阶段验收记录-<阶段号>-delegateagent-小欧-<YYYY-MM-DD>.md`（按笔记存放规则放项目根 `notes/`），必须含：阶段号、验收项编号、执行命令、原始输出摘要（日志/DB 查询结果/断言输出）、结论（通过/失败）、失败原因与回退动作。禁止只写"已验证通过"而无原始输出。
2. **门禁判据**：本阶段验收项全绿 + 回归通过，两项同时满足才可进入下一阶段。回归的"通过"定义为**不新增失败**：失败集合必须与改造前基线逐条相同；存量红项不构成本阶段红项，但**新增一条即判本阶段失败**。
   基线怎么取（2026-11-28 实测订正）：`git archive HEAD backend` 在本仓**取不到测试**——`backend/tests` 的 435 个 `test_*.py` 全部未入库，archive 里只有 1 个，抽出后等于换了一套测试，失败集合没有可比性。可执行做法是把本阶段改动文件**逐字节回退到 HEAD**（先按字节备份并记 sha256，`git show HEAD:<path>` 覆盖写，跑完 finally 恢复并校验 sha256），测试用同一份工作区文件。
   全量 `pytest -q` 也不可用作门禁：多个用例会挂满 `timeout=300`（实测跑到 26% 处单条卡死，单次预计 40 分钟以上）。改为**定向集**——按改动面符号筛出引用它的测试文件（S0 为 63 个），`--timeout=60`，基线与改造后各跑一次对比失败集合；定向集覆盖不到的模块，由该阶段验收项逐条点名兜底，不得以"定向集绿"代替全量结论。
3. **安全项不可顺延**：只读、递归防护、耗时有界三类验收项（S3 第 5–11 项）与能力同阶段验收；出现红项时禁止"先上线后补校验"，因为静默降级不会让测试变红、日志也不会报警（§1.4）。
4. **测试代码不入库**：验收脚本放本地 `backend/tests/probe_delegate_*.py` 与 `backend/e2etests/test_e2e_40_*.py`，跑通即用，按仓库铁律不提交（测试用例只用于发现问题，不作为锁死系统逻辑的借口）。
5. **提交粒度**：每阶段 1 个 commit，格式 `<type>:<代码名> <description> - <签名>-<日期>`；提交信息写清阶段号与本阶段关闭的验收项编号。
6. **阶段内自检**：每阶段收尾按"熟读代码全文 → 合规审查（10 大规范）→ 合理审查（逻辑是否最直）→ 关联审查（上下前后是否退化）"四步走一遍，再跑验收。

#### 6.2.12 关键路径与可并行机会

```
S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8      （验收门禁顺序，不可跳过）
```

- **关键路径**是 S3：安全承诺全部压在这一阶段，工期最长且红项回退成本最高，排期时应预留 0.5 天缓冲。
- **S0 与 S1 的编码可交错**（改的文件完全不重叠），但**验收顺序不变**：S1 的验收必须在 S0 全绿之后开始，因为 `agent_config.py` 的拒绝清单语义依赖 S0 的 `excluded_tools` 已落地。
- **S4 与 S5 的编码可交错**（`agent_register`/`tool_executor` 与 `tool_runner` 不重叠），但 S5 的验收第 5 项依赖 S4 已完成注册。
- **S6 的四个子阶段**串行为主：S6.1 与 S6.2 可并行编码，S6.3 依赖 S6.2（`tool_names` 来自 manifest），S6.4 依赖 S6.3（多层委托需名粒度放行先到位）。

---

## 7 远期增量与开放生态（P2+）

> 本章是 §1-§6 可靠性内核之上的**增量扩展**，不推翻、不新增框架。定位：把"子 Agent 从哪来"从进程内注册表扩到 **A2A/MCP 开放协议**（来源维度），并纳入会话内记忆槽与 effort 预算档两项趋势增量；同时**完整保留 §2.7 的 fail-closed 可靠性内核**（远程来源按不可信对待）。
>
> 与 §1.2 约束的关系：§1.2 的"不引入框架"指不引入 LangGraph/AutoGen 等**编排框架**；A2A/MCP 是**协议与数据格式**（能力发现 / 任务委派 / 结果回传），不是编排框架，二者不冲突。本章各项均为 P2+ 增量，默认关闭或行为不变，不影响 §1-§6 的 P0/P1 实施清单。

### 7.1 A2A 开放委托层

#### 7.1.1 概念映射（A2A 概念 → 本设计既有件）

| A2A/MCP 概念 | 映射到本设计 | 落点 |
|---|---|---|
| **Agent Card**（远端 Agent 能力描述：名称/能力/端点/鉴权） | `AgentConfig` 的**远端来源**变体 | `AgentConfig.agent_source`（`local`=默认，`a2a_endpoint`/`mcp_server`=新增），新增远端 Agent 定义仍走 §2.1 的 manifest/注册表，**注册表多一个数据来源，不改注册结构** |
| **Task**（委派一个有界任务） | `delegateagent` 的 `task`/`context` 参数 | 不变，复用 §2 的委托入口 |
| **Artifact**（子 Agent 产出的结构化结果） | 既有回传路径 `FinalStep.response → summary → observation`（§3.2） | 不变，远端 Artifact 经同一 summary 回灌 |
| **MCP 工具原语**（Tools/Resources/Prompts） | 子 Agent 工具子集（§2.6 的 categories/tool_names） | 远端子 Agent 的工具清单由 MCP server 提供，**仍过 §2.7.1 拒绝分类/拒绝名单 + 构造后确认工具校验**，远程工具默认视为需确认（fail-closed） |

#### 7.1.2 最小改动面（KISS）

1. `AgentConfig` 增一个 `agent_source` 字段（默认 `local`，行为完全同现状）。
2. 新增一个**来源解析器**（source resolver）：`local` 走现有 `AgentRegistry`；`a2a_endpoint`/`mcp_server` 拉取远端 Agent Card / MCP 工具清单，转成本地 `AgentConfig` 对象再进同一注册流程。
3. 远端子 Agent 一律走 §2.7 的 fail-closed 校验：**远程来源默认按"不可信"对待**——委托深度 ContextVar、拒绝分类/名单、构造后确认工具校验、只读约束**全部照旧生效**，不因"是远端"而放宽。
4. 不动 §2.5 协程隔离 / 守卫协程 / 私有 buffer / 上下文克隆等已验证的可靠性内核。

#### 7.1.3 取舍（YAGNI）

- P2+ **只做**：Agent Card 发现 + Task 委派 + Artifact 回传 + MCP 工具清单接入（request/response + 轮询即可）。
- **暂不做**（不提前引入抽象）：远端 Artifact 流式推送 / push notification / 多 Agent 跨组织协商 / 跨厂商鉴权联邦。等真实出现跨组织 Agent 生态需求再补，避免"为可扩展引入注册表、实际只有一个 entry"的过度设计（§1.2 KISS-DIRECT 正例反例）。

### 7.2 会话内自演化记忆槽

方向对齐"记忆从存取进化为自我沉淀"，但**克制到会话内**，不引入跨天长期库（避免过度设计，仍满足 KISS）：

- 子 Agent 成功完成的 `task → summary` 写入**会话作用域的轻量经验槽**（随会话结束即弃），供同一会话内的后续委托复用（父 LLM 可把上一条子 Agent 的经验摘要注入下一次委托的 `context`）。
- `track_task` 维持 `False` 不变（台账门控见 §2.7.3），经验槽不落 `tasks` 台账、不进 DB。

### 7.3 测试时 effort 预算档

把 `max_steps`/`timeout_s` 从 `AgentConfig` 的**静态值**，改为"**基础值 + 父 LLM 可传 `effort` 档动态上调**"：

- `delegateagent` 新增可选参数 `effort`（`low`/`med`/`high`，默认 `med`=现状值）；`high` 上调 `max_steps`/`timeout_s`，`low` 下调以快路径直出。
- 对齐"推理×工具"的测试时扩展趋势：简单任务快出、难任务自动加预算。改动面小——`AgentConfig` 一个字段 + §2.2 Schema 增可选 `effort` 参数 + §2.3 工具实现一处映射（effort 档映射到静态上限的倍数，仍受 §2.5 守卫协程的墙钟/取消收口约束）。

---
> §7 为 2026 Agent 趋势增量章节（v2.6 追加，v2.7 收敛为一章）：开放委托层、会话内记忆槽、effort 预算档均定位 P2+，默认 KISS 关闭或兼容不改动；§1-§6 可靠性内核（协程隔离 / fail-closed / 只读 / 守卫协程 / 上下文隔离 / OCP 注册表）原样保留。


