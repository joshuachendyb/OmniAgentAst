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


---

## 1 概述

### 1.1 目标

为 OmniAgent 引入**多 Agent 委托能力**：主 Agent 通过一个 tool（`delegateagent`）创建独立子 Agent，子 Agent 拥有独立上下文、独立工具子集、有界 ReAct 循环，完成后回传摘要和 token 用量。

### 1.2 设计约束

| 约束 | 说明 |
|------|------|
| **不引入框架** | 不引入 LangGraph、AutoGen 等外部编排框架 |
| **不引入 DAG** | 不做多 Agent 图编排，保持"一个 tool 调一个有界子循环" |
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
| 上下文副本（`copy_context` + `create_task(context=)`） | `clear_temp_auth`、`set/reset_current_task_id`、七组工具回调都是 ContextVar 操作，副本天然隔离父子，优于手工保存恢复 |
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
| 子 Agent `track_task=False` | 它不是用户任务：不该占 `tasks` 台账、不该被启动期超时扫描当僵尸任务、也不该让 `_finalize_cycle` 去写用户可见状态。**该门控须在 `BaseAgent.__init__` 实装**——当前无条件建台账且 `track_task` 会被 `**kwargs` 静默吞掉 |
| 改造项一律"显式形参 + 启动期 fail-fast"，不接受 `**kwargs` 兜底 | `UniversalAgent`/`BaseAgent` 现有 `**kwargs` 只接收不校验，`excluded_tools`/`track_task` 漏改时无任何报错：sub 拿到全量工具（只读承诺失效）、sub 建台账行（幽灵任务）。安全类承诺若走静默降级，测试不红、日志不报，只能靠线上发现 |
| P0 只做分类粒度工具集，名粒度推迟 P1 | 现成 `to_openai_tools(tool_names=)` 只控可见性不控执行，需与 `ToolRetryEngine` 构造前筛选联动 |
| 主名称定为 `delegateagent`，其它生态名走别名归一 | 名称唯一、零重复注册；复用 `TOOL_NAME_ALIASES`/`normalize_tool_name` 现成能力，注册表 `get_tool`/`resolve_registered_tool` 已内置归一调用，零改调用点 |
| `wait` 默认 True（P0 同步）/ False（P1 异步） | P0 先跑通同步直线路径；异步复用既有 inbox 通道回灌，不在父轮次结束后硬改 `conversation_history` |
| 子 Agent 前台阻塞 + 可并行，不做后台 fire-and-forget | "前台/后台"与"串行/并行"是两个独立维度：子 Agent 是父 `await` 的协程任务（前台），但同轮多个委托经 `asyncio.gather` 同时跑（并行）。后台化要求父循环有"挂起态"，而 `react_loop` 是无挂起态的同步 while 循环、`AgentStatus` 五态里也没有挂起态；且前台并行已拿到 `max(t_i)` 耗时，后台化收益为零 |
| 子 Agent 的价值是上下文隔离，不是"后台干活" | 父 `conversation_history` 只多一行摘要，子 Agent 的 reasoning 与工具原始输出全部留在子域（§3.2）。这是 `tuning.trim.keep_recent_rounds` 之外的第二道上下文防线：装不下的事在子域内消化，不挤占父的裁剪预算 |


---

## 2 核心设计

### 2.1 AgentConfig 数据类

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
#   AGENT       — 用户交互（question/schedule），子 Agent 没有前端出口（§2.7.2）
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

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


@dataclass
class AgentConfig:
    """子 Agent 配置 — 定义一个可委托的 Agent 实例的全部参数"""
    agent_id: str                          # 唯一标识，如 "researcher" / "reviewer" / "kb_analyst"
    description: str                       # 一句话说明（给 LLM 看，帮助主 Agent 选择委托目标）
    system_prompt: str = ""                # 子 Agent 的 system prompt（注入方式见 §2.5）
    tool_categories: Set[ToolCategory] = field(default_factory=lambda: {ToolCategory.FUNDAMENTAL})
    output_instruction: Optional[str] = None  # 输出约束（自由文本；None=默认摘要要求，见 §2.5）
    model: Optional[str] = None            # 指定模型（None=继承父 Agent 的 LLM，见 §2.5）
    max_steps: int = 8                     # 子 Agent 最大 ReAct 步数（有界）
    timeout_s: float = 300.0               # 墙钟超时（秒），由 §2.5 守卫协程强制执行
    track_task: bool = False               # 是否在 tasks 台账建行（子过程默认不建，见 §2.7.3）

    def __post_init__(self) -> None:
        """构造即校验 — 非法配置在注册/委托之前失败，不留到运行期"""
        if not isinstance(self.agent_id, str) or not _ID_RE.match(self.agent_id):
            raise ValueError(f"agent_id 非法: {self.agent_id!r}（要求小写字母开头，[a-z0-9_]）")
        if not (self.description or "").strip():
            raise ValueError(f"agent_id={self.agent_id}: description 不能为空（LLM 靠它路由）")
        if not 1 <= int(self.max_steps) <= 30:
            raise ValueError(f"agent_id={self.agent_id}: max_steps={self.max_steps} 越界（1..30）")
        if not 5 <= float(self.timeout_s) <= 1800:
            raise ValueError(f"agent_id={self.agent_id}: timeout_s={self.timeout_s} 越界（5..1800）")
        if not self.tool_categories:
            raise ValueError(f"agent_id={self.agent_id}: tool_categories 不能为空")
        self.tool_categories = set(self.tool_categories)   # 拷贝成独立集合，防调用方共享可变对象

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

### 2.2 delegateagent 工具 Schema

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
        # 失败也带上 usage：子 Agent 可能已烧掉几步 token，父侧仍要记账（§4.3）
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

**文件位置**：`backend/app/services/agent/tool_executor.py`（扩展 `execute_tool` 的 ContextVar 注入段）

在 `execute_tool` 函数中，与现有的 hooks/text_task/notice/question/generate/precheck/session_id 注入同层，新增：

```python
# 2026-11-27 小欧 - 注入 delegate 回调(同 notice/question 模式)
from app.tools.context import (
    set_current_delegate_callback,
    reset_current_delegate_callback,
)

# 构建闭包：捕获当前 agent（registry 由 run_delegate 内部惰性查单例）
from app.services.agent.delegateagent_runner import run_delegate

async def _delegate_cb(**kwargs):
    return await run_delegate(agent=agent, **kwargs)

token = set_current_delegate_callback(_delegate_cb)
try:
    # ... 工具执行逻辑 ...
finally:
    reset_current_delegate_callback(token)
```

### 2.5 子 Agent 运行器（核心）

> 注入只发生在主 Agent 的每次工具调用期间；子 Agent 作用域内会被显式清空（见下方 `_run_child_guarded`），因此即使 `delegateagent` 被 searchtool 动态灌回子 Agent，`get_current_delegate_callback()` 也返回 None，工具立即失败。这是递归防护的最后一道防线，且**不依赖工具可见性**。

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

    覆盖面（别高估）：AGENT 分类工具 + 声明了 needs_confirmation / confirm_fn 的工具
    （现为 bash、execute_sql）。FILE 写类工具不声明 needs_confirmation——
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

位置还有第二个硬约束：**必须在工具名归一之后**。`execute_tools` 开头逐 call 做 `c["tool_name"] = _corrected`（别名/纠错归一，`tool_runner.py:54-59`）；插在归一之前，`delegate_task`/`call_agent` 这类别名会绕过计数（名字还没变成 `delegateagent`）。正确位置是归一循环结束、`if len(all_calls) == 1` 分支之前。

```python
MAX_PARALLEL_SUB_AGENTS = 6  # tool_constants.py

# tool_runner.execute_tools 内、工具名归一之后 / 单调用分支之前：
#   ① 先算超限索引（保序，不静默丢弃）
_delegate_idx = [i for i, c in enumerate(all_calls) if c.get("tool_name") == "delegateagent"]
_over = set(_delegate_idx[MAX_PARALLEL_SUB_AGENTS:])
_rejected = {
    i: build_error(llm_data={
        "summary": f"delegateagent，失败：单轮并行子Agent上限 {MAX_PARALLEL_SUB_AGENTS}",
        "status": {"exec_code": "error", "message": "失败",
                   "detail": f"本轮共 {len(_delegate_idx)} 个委托，超出 {MAX_PARALLEL_SUB_AGENTS} 个的部分未执行",
                   "hint": "请分批委托：本轮先处理这些，下一轮再发其余"},
    })
    for i in _over
}
#   ② 三分支只对"活跃调用"执行：_active = [(i, c) for i, c in enumerate(all_calls) if i not in _over]
#   ③ 末尾按原索引把 _rejected 回填进 results（results 长度与 all_calls 一致，预览/observation 不错位）
```

### 2.6 开放封闭原则（OCP）扩展点总表

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
| 工具回调通道 | 入口层注入 | `ContextVar` set/reset（hooks/text_task/notice/question/generate/session_id/precheck/delegate/depth） | P0 | 工具层零越层，新增回调不动工具代码 |
| 事件总线 | 私有纯内存 buffer | `_delegate_scope` 可换 sink（P2 `agent.event_sink` 注入） | P0/P2 | 不改 react_loop/runner |
| ReAct 引擎 | `react_loop.run_react_cycle` | 共用同一引擎，差异全在配置 | P0 | 子 Agent 零重写 |
| 并行上限 | 6 | `tool_constants.MAX_PARALLEL_SUB_AGENTS` | P0 | 常量单点，校验落 tool_runner |
| 子 Agent 拒绝清单 | 拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用）+ 写/删/双路径/bash 名单 | `agent_config.DELEGATE_DENY_*` + 工具元数据校验 | P0 | 新增写类工具只要进 PATH_* 表即自动拦截 |
| 同步/异步 | `wait=True` 同步 | `wait` 参数切 P1 异步 + inbox 回灌 | P0/P1 | 不新增工具，参数复用 |
| 完成回灌通道 | inbox（`inject_system_notice`） | 经既有 inbox 注入，可换实现 | P1 | 不改 conversation_history 装配 |
| 插件/Skill | 内置注册 | `plugins/*/manifest.json` + `load_from_manifest` | P1 | 新增插件不放代码 |
| 注册表生命周期 | 进程内单例 | `register/unregister/reset_agent_registry` | P0 | 热插拔/测试复位不改单例内部 |

**未列为扩展点（有意封闭，理由充分）**：工具集/模型/权限**不入工具参数**——这三类是"这个 agent 是谁"的配置属性，交给 LLM 入参会破坏递归防护与能力承诺（见 §2.2、§3.3）；ReAct 循环本身封闭——父子共用同一引擎，不允许子 Agent 定制循环逻辑，避免分叉出难以维护的多套实现。

**扩展代价（可核对的数字）**：
- 新增一个子 Agent：**0 个文件改动**（`register(...)` 一行，或放一个 `manifest.json`）。
- 新增一类工具给子 Agent 用：**0 个文件改动**（工具注册后按分类自动可用；写类工具自动进拒绝清单）。
- 换模型：**0 个文件改动**（`AgentConfig.model`，限同 provider/api_base）。
- 改并行上限/超时/步数：**0 个文件改动**（常量或配置字段）。
- 换事件总线/换引擎：需要动 1 处（`_delegate_scope`）或明确不开放（引擎）。

**架构三性**：
- **灵活**：上表 17 个扩展口均为"配置字段 / 注册表条目 / ContextVar 回调 / 策略参数 / 工具元数据"，新增能力不改调用链主干。
- **可靠**：每个扩展位都有明确默认值（继承父、内存 buffer、同步 wait），缺配置即走零开销默认路径；异常/取消/超时路径统一在 `_run_child_guarded` + `finally` 收口（子任务先收干净、buffer 后回收、client 归还、token reset）；递归防护三层且最后一层不依赖工具可见性。
- **高效**：默认路径不新建进程/线程/client/池（§3.1），扩展时才付额外成本，符合"按需付费"。

### 2.7 安全与递归防护

#### 2.7.1 递归防护

| 防护层 | 机制 | 是否依赖 LLM/工具可见性 |
|--------|------|------------------------|
| **配置层** | `effective_categories()` 扣掉拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用）；拒绝名单再扣 `delegateagent` | 是最外层，但**单独不成立**（见下） |
| **运行层（决定性）** | 子作用域内 `set_current_delegate_callback(None)`：工具就算被注入也拿不到回调，`delegateagent` 立即返回"委托通道未注入" | 否（不看可见性） |
| **深度层** | `_current_delegate_depth` 硬顶，`MAX_DELEGATE_DEPTH=1`（P0）；入口 `run_delegate` 先查 | 否 |
| **硬顶** | 子 Agent `max_steps` 有界（默认 8）+ `timeout_s` 墙钟兜底 | 否 |

**为什么"配置层 + 实例层"不够（实测路径）**：`tool_executor.auto_inject_from_search` 在工具返回后按 `matches[].category` 调 `agent._tool_loader.load_category(cat)`，把整类工具灌进 `_tools_dict`；而 `ToolRetryEngine` 持有的是**同一个 dict 对象**（`tool_retry_engine.py:275-276`），所以灌进来的 `delegateagent` 立刻可执行。仅靠"初始分类里没有 AGENT"，一条 searchtool 结果就能把防线拆掉。

> 粒度说明：P0 用"整类 + 名单"粗粒度就够（子 Agent 本就不该交互/写入）；P1 引入 `AgentConfig.allow_delegate` 与可配深度时，改为按工具名精确放行（见 §4.2），`MAX_DELEGATE_DEPTH` 从常量换成配置字段。P0 不预留该字段——没人读的开关是假开关。

#### 2.7.2 安全继承与作用域隔离

子 Agent 跑在 `contextvars.copy_context()` 的副本里（见 §2.5），副本继承父作用域的全部 ContextVar：

- `DefaultToolSecurityHooks`：安全确认/拒绝照常生效
- 沙箱预检：读文件类工具（`reviewer` 允许 FILE 分类里的读侧）同样走路径校验；bash/写侧在 P0 已被拒绝清单挡住，P1 放开时也只会经过同一套安全门，不会因为"子 Agent"而放宽
- 临时授权（ `_authorized_paths` 是 ContextVar）：子 Agent 继承父的授权映射；其 `clear_temp_auth()` 只清副本，**父 Agent 的授权不受影响**
- 七组工具回调（hooks/notice/question/generate/session_id/task_id/delegate）在副本内 set/reset，父子互不干扰；其中 `delegate` 在副本启动前被显式置 `None`（§2.7.1 运行层）

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

| 保护 | 机制 |
|------|------|
| token 预算 | 子 Agent `max_steps` 有界（默认 8）+ 不继承父对话历史（初始上下文只有 task 描述与 system_prompt） |
| 并行数 | 单轮 ≤ 6 个子 Agent（`MAX_PARALLEL_SUB_AGENTS`，在 `tool_runner.execute_tools` 按 `len(all_calls)` 校验，见 §2.5） |
| 总耗时 | `AgentConfig.timeout_s`（默认 300s）墙钟硬顶，由 `_run_child_guarded` 计时；超时即 `task.cancel()` + 宽限期内等收敛后按失败回传，P0 即生效。取消后子任务超过 `_CANCEL_GRACE_S` 仍未退出则放弃等待并留 error 日志——宁可留残留日志，也不把父任务拖成无界等待 |
| 连接池 | 默认共享父 Agent 的 `httpx` 客户端（`create_llm_client(..., shared_client=...)` 使 `_owns_client=False`，子实例 `close()` 为 no-op）；`AgentConfig.model` 非 None 才新建独立 client，finally 关闭 |
| 取消联动 | 子 Agent 不注册进 `running_tasks`，框架内 `is_cancel_requested(子task_id)` 恒为 False，故联动只能由父侧轮询：`_run_child_guarded` 按 `_POLL_S` 周期查 `is_cancel_requested(父task_id)`，命中即 `task.cancel()` 并等待收敛 |
| 事件总线 | 私有纯内存 buffer；回收顺序必须是"先 cancel + 有界等待子任务收干净，再 `reclaim_memory_buffer`"，反序会让子任务 publish 撞上已回收 buffer 抛 RuntimeError |
| 任务台账 | 子 Agent 须 `track_task=False`，但 **`BaseAgent.__init__` 当前无条件执行 `tracker.create_task(...)` 且无 `track_task` 形参**（`base_agent.py:95`；该参数会被 `**kwargs` 静默吞掉、不报错）。P0 前必须实装门控，否则子 Agent 以 `sub-xxx` 建台账行，既占 `tasks` 列表被用户看见，又会被启动期僵尸任务扫描命中 |

---

## 3 通信交互与数据流总览

### 3.1 主 Agent 的五条通信通道

主 Agent 同时与五个对象通信，各有独立载体，互不串扰：

| 通道 | 对象 | 载体 | 谁消费 |
|------|------|------|--------|
| ① LLM 回路 | LLM | `message_builder.conversation_history`（内存消息列表） | 仅 LLM |
| ② 工具层 | 各工具实现 | `ContextVar` 回调注入（hooks/text_task/notice/question/generate/session_id/precheck/delegate） | 工具实现 |
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
  │  9. _delegate_scope: 建 sub_task_id 纯内存 buffer + copy_context() + delegate 回调置空
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
2. `ToolMetadata.description` 现为 `str`；需让 `tool_description.to_openai_tools`（`tool_description.py:54` 取值处）与 `registry.list_tools`（`registry.py:374`）在取值时解析 callable（各 +1 行，向后零影响），否则 callable 会被原样塞进 schema；同时把 `ToolRegistry.register(description=...)` 的形参标注放宽为 `Union[str, Callable[[], str]]`。注意 `tool_cache_manager.py:54` 也直接读 `.description`，目前只服务 searchtool，`delegateagent` 不走该路径；若将来把 callable 描述推广到别的工具，这处必须一并解析。

### 4.2 工具子集注入

子 Agent 的工具注入走 `ToolLoader.init_tools`，但 **`excluded_tools` 形参当前并不存在**——`tool_loader.py:28` 实际签名为 `init_tools(self, initial_categories=None)`，须按 §5.2 改造后下段代码才成立：

> 改造前提：下文「三处同源」列的每个落点都要改造才生效（`init_tools`/`load_category` 增 `excluded_tools`、`to_openai_tools` 增 `exclude` 形参并经 `registry`/`tool_cache_manager` 打通、两个构造器改显式形参并删掉 `**kwargs`）。**当前 `UniversalAgent.__init__` 与 `BaseAgent.__init__` 都是 `**kwargs` 接收后不消费、不报错**（`universal_agent.py:56`、`base_agent.py:57`），所以漏改任何一项都表现为"参数被吞掉、程序照跑"，不会在启动期暴露；删掉 `**kwargs` 后，漏改由 Python 原生 `TypeError` 在构造时炸出来。

```python
# delegateagent_runner.py 中
sub_agent = UniversalAgent(
    llm_client=_llm_client,
    task_id=sub_task_id,
    max_steps=config.max_steps,
    initial_categories=sub_categories,    # AgentConfig.effective_categories()
    excluded_tools=DELEGATE_DENY_TOOLS,   # 只读拒绝清单（§2.1）
    track_task=config.track_task,
)
```

**拒绝清单必须三处同源**（漏一处就有一条暗道）：

1. `init_tools` 装载时跳过被拒工具（`_tools_dict` 不含它）；
2. `load_category` 动态注入时同样跳过（否则 searchtool 一命中又灌回来）；
3. `get_openai_tools`/`to_openai_tools` 生成可见列表时同样跳过（否则 LLM 看得见但调不通，白耗轮次）。

实现口径：`ToolLoader.init_tools(..., excluded_tools)` 把清单存成 `agent._excluded_tools`（单一权威），`load_category` 读它过滤动态注入。**可见性侧不能直接抄 `to_openai_tools(exclude=...)`——该形参不存在**：现签名为 `to_openai_tools(registry, categories=None, tool_names=None, strict=False)`（`tool_description.py:27`），`tool_description.py:54` 处 `"description": meta.description` 也是原样取 `str`。故须先给 `to_openai_tools` 增 `exclude` 形参（或改由 `tool_names` 白名单反推），再让 `_excluded_tools` 生效。写入点只有 `UniversalAgent.__init__`（`excluded_tools=None` 保持既有行为）。

> 传参链要一次打通，缺一环拒绝清单在 LLM 眼里就等于不存在：`tool_cache_manager.get_openai_tools(agent)`（现为 `to_openai_tools(categories=agent._loaded_categories)`，`tool_cache_manager.py:29`）→ `registry.to_openai_tools(..., exclude=agent._excluded_tools)` → `tool_description.to_openai_tools(...)`。三者任一漏传，子 Agent 会"看得见但调不通"，白耗一轮。

**P0 是"分类粒度 + 名字级拒绝清单"**：`initial_categories` 一次传到位（`ToolLoader.init_tools` 同时写 `_tools_dict` 与 `_loaded_categories`），拒绝清单在装载/动态注入/可见性三处同源过滤（见上）。

**P1 再加"名字级允许清单 `tool_names`"**——它比黑名单更严，且**不能**在 `init_tools` 之后改 `_tools_dict` 实现，两头都不靠：

- LLM 可见性由 `_loaded_categories` 决定（`tool_cache_manager.get_openai_tools` 以 `categories=agent._loaded_categories` 调 `to_openai_tools`），改 `_tools_dict` 不影响 LLM 看到什么；
- 可执行性由 `_retry_engine._tools` 决定（`UniversalAgent.__init__` 用 `ToolRetryEngine(self._tools_dict)`，引擎持有 `self._tools = tools` 同一 dict 引用），构造后**重新赋值** `_tools_dict` 不会更新引擎，被"过滤掉"的工具照样能执行。

P1 正确做法：过滤发生在 `ToolRetryEngine` 构造之前（把筛完的字典传进去），并让可见性同源（`get_openai_tools` 接 `tool_names`，`to_openai_tools` 已原生支持该形参）。

### 4.3 usage 合并

子 Agent 完成后，`run_delegate` 返回的 `usage` 字典（`accumulated_usage` 快照）由父 Agent 在 observation 中看到；父 Agent 的 `accumulated_usage` **不自动合并**（LLM 不知道子 Agent 花了多少 token）。

**设计决策**：usage 合并放在父 Agent 侧——`tool_executor.execute_tool` 完成后累加。两条硬要求：

1. **不分成功失败，有 usage 就记账**：子 Agent 跑了 6 步才失败，那 6 步的 token 是真实花费。故 §2.3 的失败分支也把 `usage` 放进 `data`。
2. **判据用 `data.usage` 存在性，不用 `is_success`**：`is_success` 读的是 `llm_data.status.exec_code`（工具"是否成功"），与"是否产生 token"是两件事。

```python
# tool_executor.py 中，工具执行完成后：
if tool_name == "delegateagent":
    sub_usage = (result.get("data") or {}).get("usage") or {}
    if sub_usage:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            agent.accumulated_usage[key] += int(sub_usage.get(key, 0) or 0)
```

这样父 Agent 的 `FinalStep` 终态输出里已包含子 Agent 的 token 消耗（失败委托也计入）。

### 4.4 SSE 隔离（P0 已实现）

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

### 5.1 新增文件

| 文件 | 职责 | 预估行数 |
|------|------|----------|
| `backend/app/tools/agent/agent_config.py` | AgentConfig 数据类 + AgentRegistry + `DELEGATE_DENY_CATEGORIES`/`DELEGATE_DENY_TOOLS` + 内置 3 Agent 注册 | ~150 |
| `backend/app/services/agent/delegateagent_runner.py` | 子 Agent 创建/守卫协程（超时+取消）/私有事件总线/上下文克隆/摘要提取 | ~230 |
| `backend/app/tools/agent/delegateagent.py` | delegateagent 工具函数 | ~60 |
| `backend/app/tools/agent/delegateagent_schema.py` | DelegateAgentInput pydantic 模型 | ~30 |
| `backend/app/tools/agent/plugin_loader.py` | `plugins/` 目录扫描 + manifest 容错 + 逐个注册 | ~50 |

> `agent_config.py` 放 tools 层而非 services 层：`agent_register.py`（tools 层）要读注册表生成工具描述，放 services 会形成"工具层 import services"的越层。

### 5.2 修改文件

| 文件 | 改动 | 预估 |
|------|------|------|
| `backend/app/tools/agent/agent_register.py` | 注册 delegateagent（描述走 callable 动态生成）+ 注册前调 `plugin_loader` 扫插件 | +20 行 |
| `backend/app/tools/context.py` | 新增 delegate_callback ContextVar + 委托深度 ContextVar（token/reset 模式） | +20 行 |
| `backend/app/services/agent/tool_executor.py` | 注入 delegate 回调（token 模式）+ usage 合并（成功/失败都算，按 `data.usage` 存在性判定） | +22 行 |
| `backend/app/services/agent/tool_runner.py` | 并行分支加 delegate 数量上限校验（唯一持有 `all_calls` 的层） | +10 行 |
| `backend/app/services/agent/tool_loader.py` | `init_tools`/`load_category` 增 `excluded_tools` 参数（挡动态注入回灌） | +12 行 |
| `backend/app/services/agent/universal_agent.py` | `__init__` 增显式 `excluded_tools`/`track_task` 形参，`init_tools` 与 `super().__init__` 按名传；同时删掉 `**kwargs` | +6 行 |
| `backend/app/services/agent/base_agent.py` | `__init__` 增 `track_task: bool = True`（仅供 `tracker.create_task` 门控）+ 删掉 `**kwargs`：未知参数由 Python 原生 `TypeError` 拦截，比手写校验少一层代码 | +2 行 |
| `backend/app/llm/client_sdk.py` | `LLMClient` 增只读 `api_key` property（现仅有 `_api_key`） | +4 行 |
| `backend/app/tools/registry.py` | `list_tools`/`to_openai_tools` 解析 callable description | +6 行 |
| `backend/app/tools/tool_description.py` | `to_openai_tools` 支持 callable description + 新增 `exclude: Optional[Set[str]]` 形参（当前无此形参） | +8 行 |
| `backend/app/services/agent/tool_cache_manager.py` | `get_openai_tools(agent)` 调 `to_openai_tools` 时补传 `exclude=getattr(agent, "_excluded_tools", None)`（漏此处则可见性过滤形同不存在） | +2 行 |
| `backend/app/tools/tool_constants.py` | 新增 `MAX_PARALLEL_SUB_AGENTS`（`tool_runner` 跨层读取须单点）；`MAX_DELEGATE_DEPTH` 不进本文件——它只在 `delegateagent_runner` 内使用，留在该模块（§2.5） | +1 行 |
| `backend/app/tools/tools_alias_mapper.py` | `TOOL_NAME_ALIASES` 新增 4 条大众名→`delegateagent`（P1 可选 `PARAM_ALIASES["delegateagent"].prompt→task`） | +5 行 |

> `subagent` 不进别名表：它已在 `UNAVAILABLE_OFFICIAL_TOOLS` 里，且 `tuning.agent.disabled_tools` 可能按此名屏蔽；收进来会与"未注册即禁用"的判定打架。`assistant`/`worker` 同理不收。

### 5.3 不改的文件

| 文件 | 原因 |
|------|------|
| `react_loop.py` | 不改，父子共用同一 ReAct 引擎（零重写）；私有纯内存 buffer 满足其对 `get_stream_buffer` 的准入要求；全局清理由上下文副本隔离 |
| `agent_runner.py` | 不改，子 Agent 是同步子过程而非用户任务，不套完整 runner（无台账/取消/重连/统计） |
| `step_emitter.py` | 不改，`emit_notice` / `emit_interact` 对 buffer 缺失已有降级分支 |
| `backend/app/services/task/hitl_confirmation.py` | 不改，P0 用"子 Agent 只读"绕开确认无出口问题（§2.7.2），不给子 Agent 开确认通道（注意在 `services/task/` 非 `services/agent/`） |
| `tools_alias_mapper.UNAVAILABLE_OFFICIAL_TOOLS` | 不改，`subagent` 继续留在禁用名单，不影响 `delegateagent` 注册 |

---

## 6 优先级与里程碑

| 阶段 | 内容 | 预估工期 |
|------|------|----------|
| **P0** | AgentConfig + AgentRegistry（含 `__post_init__` 校验/`unregister`/`reset`）+ delegateagent_runner（含守卫协程 + 私有 buffer + 上下文克隆）+ delegateagent 工具（同步 `wait=True`）+ ContextVar（回调 + 深度）+ 注册 + 内置 3 个 Agent | 2-3 天 |
| **P0** | 递归防护 fail-closed：深度硬顶 + 子作用域清空 delegate 回调（不依赖工具可见性） | 含在首版 |
| **P0** | 契约前置改造（先于下述各项）：`init_tools`/`load_category` 增 `excluded_tools`、`to_openai_tools` 增 `exclude` 并沿线打通 `registry.to_openai_tools`/`tool_cache_manager.get_openai_tools`、`UniversalAgent`/`BaseAgent` 改显式形参并删掉 `**kwargs`（漏改即 `TypeError` 炸在构造时） | 0.5 天 |
| **P0** | 子 Agent 只读：拒绝分类/拒绝名单三处同源 + 构造后按 `needs_confirmation`/`confirm_fn` 整单拒绝 | 含在首版 |
| **P0** | 耗时有界：`timeout_s` 墙钟超时 + 父取消轮询联动 + "先收子任务再回收 buffer" | 含在首版 |
| **P0** | 并行上限校验落地 `tool_runner.execute_tools`（`len(all_calls)` > 6 拒绝该轮多余委托）；`tool_constants.MAX_PARALLEL_SUB_AGENTS` 当前不存在，须同批新增 | 0.5 天 |
| **P0** | 子 Agent 不落 `tasks` 台账（`track_task=False` 透传到 `BaseAgent.__init__`） | 含在首版 |
| **P0** | 工具子集注入验证（子 Agent 确实看不到 AGENT 分类与写/删/bash 工具，且 searchtool 灌回后仍不可调） | 同 P0 |
| **P0** | SSE/DB 隔离验证（子步骤不进父 SSE、不写 chat_task_steps）+ 父授权不被清零 | 同 P0 |
| **P0** | usage 合并到父 Agent accumulated_usage（成功/失败分支都带 `data.usage`） | 同 P0 |
| **P0** | 别名归一：`TOOL_NAME_ALIASES` 增 4 条大众名→`delegateagent`（§4.5，`subagent` 不收） | 0.5 天 |
| **P0** | `AgentConfig.model` 配置层扩展位（默认继承父 LLM；非 None 时 `shared_client` 复用父池） | 含在首版 |
| **P0** | `LLMClient.api_key` 只读 property + 工具描述 callable 动态生成（新增 Agent 零改代码） | 含在首版 |
| **P1** | `wait=False` 异步模式：立即返回 `delegate_id` + 完成经 `inject_system_notice`/`drain_inbox` 回灌 | 1-2 天 |
| **P1** | 插件 manifest 加载 + `tuning.agent.plugins_dir` 目录扫描 | 1 天 |
| **P1** | `tool_names` 名粒度过滤（构造 retry_engine 前筛 + `get_openai_tools` 接 tool_names）；可选 `PARAM_ALIASES["delegateagent"].prompt→task` | 1 天 |
| **P1** | `allow_delegate=True` 精确多层委托（≤2 层）+ 跨 provider 模型（`AgentConfig` 增 provider/api_base） | 1 天 |
| **P2** | SSE 子 Agent 步骤折叠透传（改 `_SSE_FORWARD_TYPES` + 嵌套渲染） | 暂缓 |
| **P2** | 事件 sink 注入（`react_loop._publish` 可注入 `agent.event_sink`），去掉私有 buffer 通行证 | 暂缓 |
| **P2** | 收编 `subagent` 别名（需同时从 `UNAVAILABLE_OFFICIAL_TOOLS` 移除，并处理 `tuning.agent.disabled_tools` 同名屏蔽后的语义） | 暂缓 |
| **P2+ 开放委托层** | §7 A2A 来源维度：`AgentConfig.agent_source` + 远端 Agent Card 解析 + 远端子 Agent 过 fail-closed 校验；§8 四项增量（agent RL 兼容声明 / 会话内记忆槽 / 测试时 effort 预算档 / 按需图编排开关，均默认 KISS 关闭或兼容不改动） | 按需，1-3 天 |

---

## 7 A2A 开放委托层（P2+ 增量）

> 本章是 §1-§6 可靠性内核之上的**来源维度扩展**，不推翻、不新增框架。定位：把"子 Agent 从哪来"从进程内注册表，扩到 **A2A/MCP 开放协议**，吃到"一次接入、处处可用"的 Agent 生态红利；同时**完整保留 §2.7 的 fail-closed 可靠性内核**（远程来源按不可信对待）。
>
> 与 §1.2 约束的关系：§1.2 的"不引入框架"指不引入 LangGraph/AutoGen 等**编排框架**；A2A/MCP 是**协议与数据格式**（能力发现 / 任务委派 / 结果回传），不是编排框架，二者不冲突。

### 7.1 概念映射（A2A 概念 → 本设计既有件）

| A2A/MCP 概念 | 映射到本设计 | 落点 |
|---|---|---|
| **Agent Card**（远端 Agent 能力描述：名称/能力/端点/鉴权） | `AgentConfig` 的**远端来源**变体 | `AgentConfig.agent_source`（`local`=默认，`a2a_endpoint`/`mcp_server`=新增），新增远端 Agent 定义仍走 §2.1 的 manifest/注册表，**注册表多一个数据来源，不改注册结构** |
| **Task**（委派一个有界任务） | `delegateagent` 的 `task`/`context` 参数 | 不变，复用 §2 的委托入口 |
| **Artifact**（子 Agent 产出的结构化结果） | 既有回传路径 `FinalStep.response → summary → observation`（§3.2） | 不变，远端 Artifact 经同一 summary 回灌 |
| **MCP 工具原语**（Tools/Resources/Prompts） | 子 Agent 工具子集（§2.6 的 categories/tool_names） | 远端子 Agent 的工具清单由 MCP server 提供，**仍过 §2.7.1 拒绝分类/拒绝名单 + 构造后确认工具校验**，远程工具默认视为需确认（fail-closed） |

### 7.2 最小改动面（KISS）

1. `AgentConfig` 增一个 `agent_source` 字段（默认 `local`，行为完全同现状）。
2. 新增一个**来源解析器**（source resolver）：`local` 走现有 `AgentRegistry`；`a2a_endpoint`/`mcp_server` 拉取远端 Agent Card / MCP 工具清单，转成本地 `AgentConfig` 对象再进同一注册流程。
3. 远端子 Agent 一律走 §2.7 的 fail-closed 校验：**远程来源默认按"不可信"对待**——委托深度 ContextVar、拒绝分类/名单、构造后确认工具校验、只读约束**全部照旧生效**，不因"是远端"而放宽。
4. 不动 §2.5 协程隔离 / 守卫协程 / 私有 buffer / 上下文克隆等已验证的可靠性内核。

### 7.3 取舍（YAGNI）

- P2+ **只做**：Agent Card 发现 + Task 委派 + Artifact 回传 + MCP 工具清单接入（request/response + 轮询即可）。
- **暂不做**（不提前引入抽象）：远端 Artifact 流式推送 / push notification / 多 Agent 跨组织协商 / 跨厂商鉴权联邦。等真实出现跨组织 Agent 生态需求再补，避免"为可扩展引入注册表、实际只有一个 entry"的过度设计（§1.2 KISS-DIRECT 正例反例）。

## 8 其他 2026 趋势增量

> 本章四块均为**增量/兼容**，遵循 KISS：能声明兼容的不改代码，要动的只加一个字段或一个默认关闭的开关。

### 8.1 agent RL 兼容声明

模型层"被训练成会规划/会调工具/会长程执行"（Qwen3-Coder、GPT-5 等 agent RL 方向）与本设计**解耦**：本设计的外层脚手架（`delegateagent` tool + 注册表 + prompt + fail-closed）是纯 scaffolding，**天然兼容**任一底座模型；底座换成更强的 agent RL 模型时，子 Agent 外层脚手架可顺势变薄。**本设计无需改动**，仅在 §1.4 决策记录补一句"模型线独立演进，scaffolding 不变"。

### 8.2 会话内自演化记忆槽

方向对齐"记忆从存取进化为自我沉淀"，但**克制到会话内**，不引入跨天长期库（避免过度设计，仍满足 KISS）：

- 子 Agent 成功完成的 `task → summary` 写入**会话作用域的轻量经验槽**（随会话结束即弃），供同一会话内的后续委托复用（父 LLM 可把上一条子 Agent 的经验摘要注入下一次委托的 `context`）。
- `track_task` 维持 `False` 不变（§2.5/§5.3），经验槽不落 `tasks` 台账、不进 DB。

### 8.3 测试时 effort 预算档

把 `max_steps`/`timeout_s` 从 `AgentConfig` 的**静态值**，改为"**基础值 + 父 LLM 可传 `effort` 档动态上调**"：

- `delegateagent` 新增可选参数 `effort`（`low`/`med`/`high`，默认 `med`=现状值）；`high` 上调 `max_steps`/`timeout_s`，`low` 下调以快路径直出。
- 对齐"推理×工具"的测试时扩展趋势：简单任务快出、难任务自动加预算。改动面小——一个字段 + §4.1 一处校验（effort 档映射到静态上限的倍数，仍受 §2.5 守卫协程的墙钟/取消收口约束）。

### 8.4 按需图编排开关（默认关闭）

- 默认坚持 §1.2"不引入 DAG"原则（if/elif 分派 + 单 tool 有界循环）。
- **仅当**真实出现"条件分支 + 循环回边 + 并行汇聚"的多步骤任务时，才在 §7 来源层之上加一个**可选的"图模式"开关**（默认关），支持显式节点/边表达；开关关闭时代码路径与现状完全一致，**不引入框架**（图只是配置数据，执行仍走 `run_react_cycle`）。

---
> §7/§8 为 2026 Agent 趋势增量章节（v2.6，OmniAgent 2026-11-27 追加）：开放委托层定位 P2+、其余四项默认 KISS 关闭或兼容不改动；§1-§6 可靠性内核（协程隔离 / fail-closed / 只读 / 守卫协程 / 上下文隔离 / OCP 注册表）原样保留。


