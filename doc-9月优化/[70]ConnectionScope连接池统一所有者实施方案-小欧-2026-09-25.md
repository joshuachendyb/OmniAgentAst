# [70] ConnectionScope 连接池统一所有者实施方案

**文档名**: [70]ConnectionScope连接池统一所有者实施方案-小欧-2026-09-25.md  
**编写人/签名**: 小欧（资深后端开发、全架构设计与分析）  
**创建时间**: 2026-09-25 11:40:25  
**更新时间**: 2026-09-25 17:53:48  
**版本**: v1.11  
**状态**: 设计定稿 + **第三章 14 个文件逐真实 diff 已落笔（基于干净 HEAD `527cfc727` 逐行精读后编写）**；尚未修改任何程序源码  
**适用基线**: `F:\OmniAgentAs-repair` HEAD `527cfc727`（6 个 lease 半成品文件已撤销回 HEAD 的干净基线；此前 8a58edb57 起点见 [69] 文档）  
**关联问题**: 配置热重载期间活动任务仍使用已关闭的共享 `httpx.AsyncClient`（任务零感知 + 不泄漏）  
**决策依据**: [69] 文档 5.4 改判 A——北京老陈 2026-09-25 11:24 拍板，ConnectionScope 定为终局  

---

## 版本历史

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|----------|
| v1.0 | 2026-09-25 11:40:25 | 小欧 | 建档：一章问题与目标（复用 [69] 取证与欠账分析）、二章 ConnectionScope 设计（唯一所有者/状态机/计数模型/六环节收口/reset 新语义）、三章占位（diff 待编写，需基于干净 HEAD 通读后做）、四章验证框架、五章实施与回滚；本版只写文档，未改业务源码 |
| v1.1 | 2026-09-25 12:15:36 | 小欧 | ①三章落地：13 个目标文件逐真实 unified diff（3.1 client_sdk lease 落户 → 3.13 agent_runner，依赖序），全部基于 HEAD `527cfc727` 逐行精读编写，`check_doc_diff` 类校验器复核；②二章设计修正（三堂会审 YAGNI 复查）：删 `mark_config_changed`/四态状态机（`close_on_zero` 使零穿越只可能发生在退休后，状态机为冗余抽象）、删 `scope.release_lease`/`scope.resolve_session`（快照 close 直接归还 lease、查询职责留 resolver——SRP）、`__init__` 改持 `ai_service`（一代=一实例一池）、新增 `ensure_pool`/`release_owner`；③registry"ai_service"字段全仓零消费核证后删除；④runner 关闭判据改无条件（resolver 恒返回任务私有快照，`_is_snapshot` 死判据消亡）；⑤五章步骤改依赖序（client_sdk→base_service→scope→工厂/停机→resolver→registry→接线→测试），每步 `py_compile` 自检、全步后 `compileall` |
| v1.2 | 2026-09-25 12:59:14 | 小欧 | 校验与迁移清单收尾：①`check_doc_diff_70` 变体复核全部 13 个 diff 块 → TOTAL_BAD=0、blocks=13、skipped=1（3.4 新文件预期），修正 3.5 编辑历史锚行漏杠（`2026-09-23 - 小欧`）；②五章 step 8 补**存量测试迁移清单**（逐调用点扫描核证）：`register_task` **58 调用点/16 文件**（带 `session_id=` 31 处删位后 TypeError 响亮、**裸传第 2 位 27 处漏改静默错位**必须逐处去位）、删 `test_tdd_14_20_inbox.py:111` 字段断言、resolver 直调 8 处改传 scope、`snapshot` 桩补 `client_lease`（test_repro_v01936 L186/L225）、`_is_snapshot` 断言迁移 6 处；③3.11 调用点 60→58 按精确扫描更正；④step 2 reset_sdk"改走 lease"更正为"零调用核证直接删除"（与 3.2 一致） |
| v1.3 | 2026-09-25 13:37:58 | 小欧 | 新增**第六章 TDD 实施步骤（详细执行篇）**：①6.1 执行总则（RED→GREEN 循环定义、每步验证三件套、3 个新测试文件与阶段总览）；②6.2 阶段0 存量迁移清单 M1~M8（58 调用点/resolver 直调 8 处/`_is_snapshot` 断言 6 处/snapshot 桩/工厂桩/字段断言/G2 桩，逐项标 RED 性质与 GREEN 归属，分批执行）；③6.3~6.5 阶段1~3 共 **29 个新增 case（TDD-74~102，续接现有 TDD-01~73）**逐 case 规格（文件/函数名/断言要点/对应 diff/命令），scope 核心 5 case（TDD-83~87）附完整代码；④6.6 [69] 4.3 十五场景→case 映射表；⑤6.7 全量验收（compileall/静态 grep/定向序列/全量基线 7355 对照/真实 E2E/并发矩阵）；⑥6.8 提交切片与回滚。五章加执行细则指引，五章 8 步依赖序保留 |
| v1.4 | 2026-09-25 13:58:47 | 小欧 | **全文十遍一致性审核后修订（11 项问题，每项三遍复核：①[69] 原始要求 ②本文现状 ③HEAD 代码/全文搜索）**——已解决 8 条根因/3 条欠账（diff 与 HEAD 逐行对得上），落实修复 4 项：①**3.12 补 hunk-7~9 交接兜底**（`_session_client`/`_snapshot_handed_to_runner` 预初始化 + create_task 后置标记 + `finally` 单点归还未交接快照）——根治 [69] 1.2.5 泄漏窗口（原 3.12 缺失，六章 TDD-102 曾是无实现的空断言）；②**3.1 `acquire()` 增 `client.is_closed` 检查**——偿还 [69] 1.2.3⑥/2.2 池约束④"底层被外部关闭后仍可借出"；③**3.6 `shutdown` 改全停机总预算**（原按代逐个计，最坏代数×30s 无界）+ 补 `import time`；④**2.3 并发边界如实界定**（池锁只护 `_ref_count/_closing`；`lease._released` 无锁，幂等由单 loop async 串行保证，零跨线程调用面）——修正"池级锁线程安全"说过头。**如实交代取舍**（2.7 单节，只列不做的理由）：①事件循环策略（全仓 33 处线程调用无一在 reset 路径，不跨 loop）、②软配额按 loop 隔离（Semaphore 仅竞争时绑 loop，生产单 loop 不触发）、③裸 client 传递（LLMClient 必须持有 client 才能发请求，约束前提不成立）、④关闭失败重试（归零后无人再碰，需先造触发者；**失败日志已补池标识**）、⑤`config_helpers:387` 写盘前错位 reset **由"不做"改判为"做"**（新增 3.14，删 1 行风险为零且语义更正确）、⑥取消语义非不做（零改动已保留）。五章 step5 同步纳入 3.14、4.1 静态核查增 3 条、4.2 增 2 类 case、六章 6.1/6.4 同步 |
| v1.5 | 2026-09-25 14:19:47 | 小欧 | **补充内容十遍复核（找缺口）**：①**3.12 hunk-9 加 try/except**——归还时 `close()` 抛错（独占池 `aclose` 失败）会中断 `_current_task_id.reset()`（ContextVar 泄漏）并覆盖原始异常根因，与 3.13 runner 同款保护对齐；②**3.14 附带收益入档**：`test_model_ref_normalization.py:96` monkeypatch `lifecycle_mod.reset` 因 `config_helpers` 是导入时绑定而失效→该"不调 reset"断言实为假绿，且 HEAD 下调用 `_update_model_ref` 会触发真实 `lifecycle.reset()` 造成跨测试污染，3.14 删除后转真绿；③**六章 6.2 增 M9 + 6.7 定向序列补 2 文件**（`test_model_ref_normalization.py`、`test_settings_editsave_red.py` 为 3.14 回归面，此前遗漏）；④TDD-102 增"close 抛错不挡 reset/不覆盖根因"断言分支；⑤6.7 验收项同步 4.4 校准表述（"可查"非"可重试"、裸 client 仅反射清零） |
| v1.6 | 2026-09-25 14:31:41 | 小欧 | **v1.5 之后第二轮十遍复核（本轮新增 diff 的逻辑分支穷举 + 全文 stale 表述清理）**：①第1遍二章：L78"变更由它标记"过时（`mark_config_changed` v1.1 已删，改为"换代由它退休"）、L164"类级 `_soft_pool_semaphore`"与 2.7"模块级"矛盾（HEAD L131 实为模块级）；②第2-3遍 3.1/3.2：hunk-9 直接访问 `self._client_lease` 对两处 `__new__` 构造安全（全仓仅此 2 处且均不调 `close()`，另 grep e2etests 确认无第三处，无需防御性 getattr）；③第4-5遍 3.10/3.5：3.10 八分支穷举全过（acquire 抛/空会话/同代/跨代/构造失败/except 兜底/`_default_snapshot` 内抛/`lease.client` 不抛）；**缺口 #5**：hunk-6 失败语义已由"清 `_instance=None`"变为"旧代保留继续服务"（更可用，BUG-06 本质不变），G2 断言成立仅因前置 fixture 已清位——3.5 说明区+M7 行+TDD-88 规格三处补记；④第6遍 hunk 引用全有效，step1 GREEN 行补 v1.4 新增内容（`is_closed`+warning 标识）；⑤第7遍一章：L34"HEAD 含两处正规 reset"（实为一正一错位，且 3.14 将删其一）、L40 夸大 HEAD 反射形态（HEAD 仅实例级 `getattr`，类级/`__dict__` 系工作树形态）、L50"关闭失败可重试"（与 2.3/2.7④矛盾）、L53"标记换代"（与 2.6"不是标记是归还"矛盾）、L66"HEAD 已含同内容"（与 387 仍在矛盾）——五处全部修正；⑥第8遍：4.1/6.7 检查清单查工作树形态改为"任何 `_shared_client` 反射（含实例级与类级）"；⑦第9遍 36 个新增条件分支审计：仅 B23b（shutdown 多代预算耗尽 `break`）无显式条款——TDD-93 补入；⑧第10遍 3.4 新鲜眼：循环导入风险为零（`app.llm.*` 全仓无 `app.services` 导入）、drain 0.05 收尾/`_pending_release_tasks`/loop 分支均 sound |
| v1.7 | 2026-09-25 15:11:31 | 小欧 | **第三轮十遍复核（源码反证 + 迁移清单补全，5 类 9 处）**：①**失败语义三处改判**（3.5 说明区/M7 行/TDD-88，纠正 v1.5/v1.6 自身补记）——源码证实 `get_service`(L152)/`get_service_for_model`(L220) 均**先** `cleanup_old_instance`（清 `_instance` + 退休旧 scope）**再**建新代，attach 失败时 `_instance`/`_scope` 皆 None、旧代已退休，不存在"旧代保留继续服务"，新旧代失败结果等价（断服至重试）；真实改进改为两条：锁外 `check_cache_valid`/`get_scope` 永不见半初始化 + 旧代池经 `_retire_scope` 归还由活动 lease 撑住（HEAD 同位置 `close_instance_sync` 真关旧池连坐活动任务）；②**2.3 生命周期图纠正**：退休判据是 `_owner_released=True`、`_owner_lease` 引用保留供 `ref_count` 观测——原"owner_lease=None"与 3.4 代码（L490-492）及 TDD-86 `ref_count==1` 直接矛盾；③**6.2 增 M10/M11（M1~M11）**：M10=基线红孤儿 4 case（6 文件撤销时 tests 未回退，HEAD 即红——v1.7 定向实测 12 文件 349 case = 4 failed/345 passed 全部为它们）逐个迁移规格：`acquire_shared_lease`→`ConnectionScope` 三件套 + 补 patch `_scope`（否则 reset→retire 落空）、`_close_tasks`→`_pending_release_tasks` 强引用改写、race case 并入 TDD-98、`owner.close()`→`scope.release_owner()`+drain 收尾；M11=`test_s2_s4_review_bugs:266` 源码断言 `get_service()`→`get_scope()` 并增强反向断言（3.12 落地后旧断言必红，此前漏入表）；④**M4 拆批**：repro L118 死属性删除移 step7（须与 3.13 无条件 close、M3 升级同批，step6 删会使 L292/L209/246 中途红）、桩补存 `self._client_lease` 供 M3 判据；M2 补 race case 语义换；⑤step5/6/7 RED 与验证序列补 M10/M11 配对项、6.7 定向序列补 test_s2_s4_review_bugs、全量对照改"实施前实测 B0 + 差异逐项解释"（7355 系旧口径已过期）；⑥stale 清理：L8/L1077"13 个 diff"→14（3.14 后）、L1071/L1104 `M1~M8`→`M1~M11`、L35 换代职责引用补明 `config_service.py:113` 调用链 |
| v1.8 | 2026-09-25 15:34:08 | 小欧 | **第四轮复核：第五章 TDD 流程作为实施依据的可行性审查（5 类问题，全部修正）**——生产码 7 步依赖序逐条反证无误（3.4 走 `from app.llm import ...` 包级、3.2 走 `client_sdk` 模块级、3.5 依赖 3.2+3.4、3.12 依赖 3.8+3.10），但**执行流程层 4 处会导致实施爆错**：①**3.3 归属矛盾（致命）**：TDD-76 `from app.llm import SharedClientLease` 在 step1 即硬依赖 3.3 包级导出（3.4 亦然），而五章把 3.3 排为 step3、六章 step1 GREEN 写"3.1+3.3"却在 step3 又写"落 3.3 diff 后复跑"——同一 diff 两处落地自相矛盾，照五章字面 step1 末尾 TDD-76 必 `ImportError` 卡死、违反"本步全绿才进下一步"；**修正**：3.3 明确随 step1 的 3.1 同批落地，五章 step1 加"（+ 3.3 同批）"、step3 改"依赖序占位、不得二次落 diff"，六章 step3 同步改"无独立 diff，仅复跑 TDD-76"；②**step8 迁移堆到最后（致命）**：与 6.2 明文"迁移不一次性做完、与该步 RED 同批落下，否则中间态大面积报错"直接矛盾——按字面执行会在半改生产码上一次性引爆 27 处 `register_task` 裸传第 2 位**静默**错位 + 8 处 resolver 直调 `AttributeError` + M10 四孤儿 case 叠加；**修正**：step8 改为"收口+全量验收"，前置"分批归属铁律"（step5=M7+M9+M10①~③、step6=M2+M3(4处)+M4(桩2处+L177)+M10④、step7=M1+M3(2处)+M4(L118)+M5+M6+M11），各步另补"配套 RED"指引；③**数字错误**："移植 4.2 六个新文件"把 4.2 标题中 [69] 的**源**文件数误作目标数——**修正**为六个 [69] 源文件**合并为 3 个新测试文件**（TDD-74~87 / 88~93 / 94~102）；④**清单缺项**：step8 旧版漏列 **M5**（orchestrator 桩 `get_service`→`get_scope`）、**M7**（G2 桩 `_ensure_client`→`ensure_client_pool`）、**M8**（真实池 case 补 close 收尾），M4 漏 2 处死属性（L177/L118）与桩需存 `self._client_lease`——全部补入并标注随属步；⑤四章 4.2 标题"六个测试文件"加来源标注（自 [69] 移植，合并为 3 个）避免再被误读为 6 个目标文件 |
| v1.9 | 2026-09-25 15:38:28 | 小欧 | **第六章 TDD 实施步骤执行性审查（6 处缺陷全修）**——先反证**依赖序本身无误**（逐步核对无前向依赖：step1 的 TDD-74~78 只需 3.1+3.3、step2 只需 3.2、step4 只需 3.4、step5 只需 3.5~3.9+3.14、step6 只需 3.10、step7 只需 3.11~3.13；且 3.6 `shutdown` 用**函数内延迟 import** 取 `get_retired_scopes`、3.7 `__init__` 先导 `lifecycle` 后导 `service`，**无循环导入风险**），再查出 6 处**执行闭环缺失**（照字面做会漏做/返工，非顺序错误）：①**"阶段0"标签语义倒挂**——6.2 置于 6.3 之前且名"阶段0"，易被读成"先做存量迁移"，实为随阶段1~3 分批；**修正**：标题改"非独立阶段：随 step5/6/7 分批执行"，6.1 阶段总览阶段0 行同步注明；②**M9 未进 step5 闭环**——归属 step5（3.14）但验证只写"配置保存相关存量测试"未点名，改点名 `test_model_ref_normalization.py` + `test_settings_editsave_red.py`（v1.5 引入后一直悬空）；③**M8 归属"随所属步"过虚**——落到 step4（TDD-83~87 真实池收尾）+ step5（M10②③ drain 收尾），并在 6.1 三件套**新增第 4 条"真实池收尾自检"**（每步统一判据，防残留连接与 warning 噪声掩盖真实失败）；④**step6 验证漏 `test_repro_v01936.py`**（M4 step6 批含其 L186/L225 桩签名，3.10 传 `client_lease` 漏补即 `TypeError`——漏跑则本步存量面留红），已补入并注明；⑤**6.1 三件套第 2 条"单 case 定向"与实际用法不符**（各步实为多 case `-k` 模式，如 step1 的 `-k "relinquish or three_states or shared_lease"` 一次覆盖 5 case），改为"判据是本步 case 全绿"；⑥**6.6 两条增强断言跨节悬空**——场景2→TDD-84、场景10→TDD-76 原只写在 6.6 映射表，6.3 的 case 规格与完整代码块均无，照 6.3 落盘必漏做；已回填两 case 规格 + 在 6.3 末新增"6.6 增强段代码"（两段可直接落 `test_tdd_74_87_scope_lease.py` 末尾：①aclose 抛错→release 不抛+warning 留痕 ②两快照 gather 并发 close→最后一个归还才归零），6.6 改注"本表此后仅作索引，出处已回填 6.3"防再分叉 |
| v1.10 | 2026-09-25 15:55:17 | 小欧 | **实施 step1~4 期间实测暴露的文档自身缺陷修正（1 类 3 处）**——代码实施严格按 3.1/3.2/3.3/3.4 逐行落地（`verify_impl_vs_doc_70.py` 对账：112/29/2/92 条 `+` 行**零缺失零多余**），但 step4 实测发现**文档给出的测试代码与其自身实现矛盾**：`release_owner()`（3.4 hunk）把 `lease.release()` 放进 `create_task`，**ref 计数在协程真正跑完前不变**，而 ①TDD-86 代码 ②6.6 增强段②代码 均在 `release_owner()` 后**立即**断言 `ref_count`（`== 1` / `== 2`）——照抄必红（实测 2 failed：`assert 3 == 2`）；文档自带的注"断言前一律经 `await scope.drain(...)` 收尾"才是正确纪律，但该注与同章代码块自相矛盾。**修正**：6.3 代码块新增 `_settle_owner_release()` helper（经 3.4 强引用表 `_pending_release_tasks` 确定性 `gather` 等待，不用 sleep 押注），TDD-86 与增强段②各补一次结算后再断言 ref，块后注补"v1.10 实施补正"明示该纪律。**另如实记录中间态风险（不改设计，step7 消解）**：3.2 删 `snap._is_snapshot` 标记后，`agent_runner.py:531` 的 `getattr(_snap_client,"_is_snapshot",False)` 判据在 step2~step6 窗口内恒 False → runner 该窗口不关快照（独占池延迟释放）；按设计于 step7 的 3.13"改无条件 close"消解。实施期间禁止提交、末次统一验收，该窗口不落地运行。**实施实录**：step1 6 case 绿 / step2 4 case 绿 / step4 整文件 16 case 绿；step2~step4 存量面 8 红全部与 6.2 M 表逐条吻合（M3 step6 批 4 处 + M10①~④ 4 处），无意外回归 |
| v1.11 | 2026-09-25 17:53:48 | 小欧 | **实施后代码审查（10 大规范 + 编辑历史两轮）查出并修正 5 处**——①**B1（Type hints required）**：`service.py` 的 `get_scope()`/`get_retired_scopes()` 缺返回类型标注（同批 `_attach_scope() -> None` 有，注解不一致）；**修正**：3.5 hunk-4 两条签名补 `-> ConnectionScope` / `-> List[ConnectionScope]`（`List` 已在 hunk-2 导入）②**B2（YAGNI）**：`_SharedClientPool.closing` property 全仓核**零消费点**（含测试，`_closing` 实例标志本身仍被 `acquire`/`release` 判据与 2.3 并发边界描述引用，删的只是无读者的公开 property）；**修正**：3.1 hunk-2 删该 property + v1.4 说明补记删除依据 ③**B3（DRY）**：`set_instance` 与 `reset_instance` 重复"清位+retire"3 行——因 `_instance_lock` 不可重入（`set_instance` 已在锁内，直接调 `reset_instance` 死锁）属**必要重复**，实施侧补注释说明理由（不动逻辑）④**A1（复用优先流程）**：实施前**未查 `backend/FUNCTIONS.md`**（AGENTS 1.3 强制先查后建）——事后核 418 行清单确认**无可复用 lease/scope/pool 函数**，未重复造轮子，但流程违规如实记录 ⑤**A2（复用优先"及时更新"）**：7 个新公用项（`SharedClientLease`/`LLMClient.relinquish_ownership`/`LLMClient.client`/`BaseAIService.ensure_client_pool`/`ConnectionScope`/`service.get_scope`/`service.get_retired_scopes`/`lifecycle.shutdown`）未登记 FUNCTIONS.md——已按既有表格格式补登记。**另修**：`main.py`/`lifecycle/__init__.py`/`services/__init__.py` 三个文件的 [70] 编辑历史条目**漏写**（其余 11 个文件均合规），已补日期+署名+逻辑说明。**未违规已核**：SRP/KISS-DIRECT/SLAP/禁止backward(3 处改签名全无兼容 shim)/OCP/LSP/ISP 逐条过 |
| v1.12 | 2026-09-25 20:03:13 | 小欧 | 实施收尾：用真实场景审计（真改配置+真热重载+真并发，被测码零打桩）查出并修复 **2 个真缺陷**——换代窗口打死新请求、退役代归零后永不剪枝；补齐 `ref_count` 可观测性并二次审查删冗余；新增 13 个真实场景 case。详见 **4.5** |

---

## 一、问题与目标

### 1.1 关联问题（摘自 [69] 1.1~1.3，取证素材复用）

- 用户可见症状：配置热重载（设置页保存/手工改 config.yaml）期间，正在流式输出的后台任务下一拍 LLM 请求报 `Cannot send a request, as the client has been closed`，任务断流失败。
- 根因：`reload_ai_config → reset()` 无条件关闭全局 `BaseAIService` 单例及其共享 httpx 连接池，而活动任务仍持有该池；"新配置生效"与"活动任务存活"两个目标通过"关旧池"硬切换，必然误伤。
- 补充：`config_helpers._update_model_ref` 在**写盘前**错位 `reset()`（HEAD L387；写盘前已换代、校验失败也不该换）——3.14 删除，换代职责归 `config_service.py:113` 调用的 `reload_ai_config()`（其 config_helpers.py L147 内 `reset()`，见 2.7⑤、2.8⑤改判实证）；
- 磁盘↔内存参数表一层已由 `get_config()` mtime 对账保证（[69] 5.2，2026-09-02），本方案不涉及。

### 1.2 历史欠账与演进（摘要自 [69] 5.1/5.2，全文见彼处）

三条欠账：
1. **私有字段外泄**：resolver 用 `getattr(ai_service, "_shared_client")` 反射摸池（HEAD 现状；工作树另有 `getattr(type(...))`/`__dict__` 更重形态，已随 6 文件撤销），`_owns_client`/`_is_snapshot` 私有标记跨层传播（`base_service.close` 摸 `_owns_client`）；
2. **资源所有权无单一归属**：创建/决议/注册/使用/关闭/停机 6 段各管一节，无一处能回答"池现在归谁、何时能关"；
3. **全局开关表达细粒度语义**：`lifecycle.reset()` 一按全按，必然误伤（[69] 病灶制度根源）。

演进：2026-06 单例 → 08-22 reset_sdk → 08-29 快照 → 09-02 mtime 对账 → 09-20 C1 共享池 → 09-25 lease 半成品（已撤销，素材保留）→ 09-25 定案重组为终局。

### 1.3 目标与非目标

**目标**：
1. 任务零感知：配置热重载不打断任何活动任务的 LLM 请求（引用计数保旧池存活至自然结束）；
2. 不泄漏：旧池在最后一个 lease 释放后必然 `aclose()`，关闭失败有日志可查（2.7④；重试不做，见 2.3）；
3. **单一所有者**：`ConnectionScope` 成为共享连接池的唯一所有者，六环节全部经它收口（消除欠账①②）；
4. **registry 去资源化**：`task_registry` 不再持有/管理资源句柄，只存任务身份；
5. reset 新语义：由"关实例关池"改为"归还换代"（归还 owner 引用，绝不关旧池；2.6。v1.1 已纠"标记"为"归还"——归还后零穿越才可能发生）。

**非目标**：
- 不动 mtime 对账与 `reload_ai_config` 触发链（已正确）；
- 不改前端、不引入新第三方依赖；
- 不追求 6 环节物理合并到单文件——收的是**所有权与调用门面**，本质分布（工厂在 service、停机在 main）保留。

### 1.4 素材与基线（摘资产执行记录，[69] 5.4 路径步骤①②已完成）

| 素材 | 位置/入库 | 用途 |
|------|----------|------|
| lease 核心两段类（`_SharedClientPool`+`SharedClientLease`，~90 行，原样） | `doc-9月优化/[70]素材-lease核心-小欧-2026-09-25.py`（已随 c9122963f 入库） | 本方案 2.2 引用计数语义吸收（不重写） |
| 6 文件全量改动 patch（30,650B） | `backup-6files未提交改动-2026-09-25.patch`（已随 527cfc727 入库） | 历史追溯/翻盘兜底 |
| config_helpers 独立修复 patch（656B） | `backup-config_helpers修复-2026-09-25.patch`（已随 527cfc727 入库） | 删 `_update_model_ref` 错位 `reset()` 的永久存档（HEAD 未含——撤回 6 文件时随基线带回，3.14 重新落实；见 2.7⑤/2.8⑤） |
| 6 文件 stash | `stash@{0}`（本地保留至本方案定案） | 第四重兜底 |
| [69] 文档可复用块 | [69] 1.x 问题取证、2.x 状态机、3.10 测试设计、4.x 验收标准 | 直接搬入本方案三/四章 |

**基线状态验证**（2026-09-25 摘资产后实测）：`client_sdk.py` 无 `SharedClientLease`（0 处）、`_owns_client = shared_client is None` 回 HEAD；`base_service.py` 含 `def reset_sdk`；`config_helpers.py` 含 2 处 `reset()`；`git status` 干净。

---

## 二、ConnectionScope 设计

### 2.1 定位

`ConnectionScope` = 共享 httpx 连接池的**唯一所有者**：池由它创建、计数由它维护、换代由它退休（`release_owner` 归还）、归零由它关闭、停机由它 drain。任何其他模块（resolver/registry/runner/orchestrator）**只经公开门面借用，不摸池内部**。

### 2.2 模块与核心 API（v1.1 定稿签名；实现代码在第三章 diff 落定）

- 新增模块：`backend/app/services/lifecycle/connection_scope.py`
- 吸收素材：`_SharedClientPool`/`SharedClientLease` 引用计数语义（素材文件，见 1.4；归零关闭 `close_on_zero`、释放幂等、池级线程锁；**v1.1 核查确认：素材无状态机概念，`release()` 归零即返回 True 触发 `pool.close()`——四态状态机系 v1.0 臆造冗余，已删）

```python
class ConnectionScope:
    """共享连接池唯一所有者（一代配置 = 一个 scope）。"""

    def __init__(self, ai_service: BaseAIService) -> None:
        """持本代单例（池未建）；owner lease 于 ensure_pool 建立。"""

    def ensure_pool(self) -> None:
        """建池 + 所有权移交（幂等）：单例 LLMClient.relinquish_ownership 后
        保留使用引用不关池；SharedClientLease(client) 计数起点=1（2.4 模型）。"""

    def acquire_lease(self) -> SharedClientLease:
        """任务/快照借用本代池（ref+1）；已退休/未初始化抛 RuntimeError
        （防新任务混入旧代），池已归零由素材 acquire 自身拦截。"""

    def release_owner(self) -> None:
        """换代/停机归还 owner 引用（幂等，ref-1）；归零自动 aclose。
        事件循环内 create_task（强引用防 GC 取消），无运行循环参照
        close_instance_sync 用 asyncio.run。**reset() 新语义即此调用**。"""

    async def drain(self, timeout: float = 30.0) -> None:
        """停机收口：等本代池 lease 全部归零关闭（0.1s 轮询、带超时）；
        超时记 warning 放行（不阻塞进程退出）。归零关闭由 release 触发，本函数只等。"""

    @property
    def ref_count(self) -> int: ...     # 可观测/测试断言（owner 未归还时含 1）
    @property
    def is_released(self) -> bool: ...  # 退休态（owner 已归还）
```

**v1.1 删项（YAGNI 三堂会审结论）**：
- ~~`mark_config_changed()`~~ 删——owner 引用随换代立即归还后，`ref_count==0` 只可能发生在退休后，`close_on_zero` 天然实现"换代才可能关、活动任务撑住不关"，无状态可标；
- ~~`release_lease(lease)`~~ 删——快照 `close()` 即 `lease.release()`（3.2/3.13），scope 不做归还中介（KISS-DIRECT，直线不绕行）；
- ~~`resolve_session(...)`~~ 删——会话覆盖查询（DB/provider 配置）是业务查询职责，留 resolver（SRP）；resolver 改签名 `(scope, session_id)`，**资源只从 `scope.acquire_lease()` 出**，反射消亡；
- ~~`state` 四态属性~~ 删——状态可由 `is_released` + 池 `ref_count` 直接观测，不引入状态机枚举。

- `reset()`（lifecycle）新语义：工厂 `_retire_scope()`（= `scope.release_owner()` 归还 owner）+ `_instance=None`（下次 `get_service` 创建**新代 scope**），**绝不再"关旧池"**。
- `close_instance`/`close_instance_sync` 保留：关闭旧**实例**（其池所有权已 relinquish，故关闭动作天然不碰共享池）。

### 2.3 生命周期模型（v1.1 修订：无状态机，纯引用计数）

v1.0 曾画四态状态机（ACTIVE→CONFIG_CHANGED→DRAINED→CLOSED），v1.1 三堂会审证伪删除——**零穿越只可能发生在退休后**，一切状态都可由两个事实直接观测：

```
在役:  _owner_released=False（owner_lease 持有，ref_count ≥ 1，恒 ≥1 ⇒ 池永不关）
退休:  release_owner() 后 _owner_released=True（is_released=True；v1.7 纠正: owner_lease
        引用**保留**供 ref_count 观测，其 release 幂等只减一次——非"置 None"，置 None 则
        TDD-86 的 ref_count==1 断言不成立）
        ├─ 活动任务 lease >0 → ref_count>0 → 池存活 → 最后一个 release 归零 → aclose
        └─ 无活动任务        → ref_count=0 → 归零 → aclose（创建释放协程内完成）
停机:  drain() 只是"等上述过程结束"（0.1s 轮询 + 超时放行），不改变任何状态
非法迁移: 退休后再 acquire → ConnectionScope 抛 RuntimeError（防混代）
          池已归零后再 acquire → 素材 SharedClientLease.acquire 抛 RuntimeError（双重防线）
aclose 失败: 素材 pool.close 内 try/except + logger.warning 留痕（[69] 2.3 retry_close 语义
          经素材 close_on_zero 单次关闭 + 日志可查承接；不引入二次重试复杂度——YAGNI）
```

- 素材既有语义原样继承：`_closing` 标志、释放幂等（`lease._released`）、池级 `threading.Lock` 保护 `_ref_count/_closing`。
- **v1.4 审核修正（并发边界如实界定）**：池内 `_ref_count`/`_closing` 的判断与迁移在同一把锁内（[69] 2.2 池约束①已兑现）；`lease._released` 是**无锁实例标志**，其"释放只减一次"的幂等在**单事件循环内由 async 串行性保证**，本方案全部调用面（resolver/snapshot close/runner finally/orchestrator finally）均在事件循环内 → **实际无跨线程暴露**；若未来出现"同一 lease 被多线程并发 release"的调用面，须将 `_released` 纳入池锁或改原子标志（本次不引入，YAGNI：零调用面不预设计）。

### 2.4 所有权与计数模型

| 角色 | 引用计数 | 说明 |
|------|---------|------|
| scope 自身（owner） | +1（`ensure_pool` 起点） | 随 `release_owner()`（换代/停机）归还，归还后不再保池 |
| 每个活动任务的快照 | `scope.acquire_lease()` +1 / 任务 `close()` → `lease.release()` -1 | release 幂等（重复归还不计）；**v1.1：经 base_service.close 直线归还，不经 scope 中介** |
| 同 provider 多快照共享同一池 | 各自 acquire 独立 lease 实例 | 绝不共享同一 lease 实例（[69] 设计红线，素材 `_from_pool` 天然满足） |
| 跨 provider 快照 | 不挂 scope（acquire 的 lease finally 归还） | 独占新池，归属该快照自身，随快照 close 关闭 |
| 归零 | `ref_count==0` → `aclose`（`close_on_zero`） | owner 已随换代归还 ⇒ **零穿越只可能在退休后** = "任务零感知 + 不泄漏"（v1.1 删"且 CONFIG_CHANGED/DRAINED"条件） |

### 2.5 六环节收口映射（[69] 5.3 表的具体化）

| 环节 | 现状（HEAD）落点 | 重组后 | 收口变化 |
|------|-----------------|--------|---------|
| 创建 | `service.get_service` 锁内建单例 + C1 惰性建池后**裸暴露 `_shared_client` 属性** | 锁内 `_attach_scope`：`ConnectionScope(instance)` + `ensure_pool()`（建池 + `relinquish_ownership` 移交） | 建池、所有权移交、scope 诞生同一处；裸属性暴露消亡（**池地址的传递路径仍为裸 `shared_client` 构造参数**——见 2.7 取舍③） |
| 决议 | resolver 用 `getattr(ai_service, "_shared_client")` 反射摸池 | `resolve_session_client(scope, session_id)`：进门 `scope.acquire_lease()`，快照接走、未转移 finally 归还 | 反射消亡；**lease 只从 scope 发**；查询职责（DB/provider 配置）留 resolver（v1.1 修正：不迁 scope，SRP） |
| 注册 | `task_registry.register_task` 存 `"ai_service"` 字段（且**全仓零消费点**，v1.1 核证） | 删参数删字段，只存任务身份/状态/inbox | registry 不 import 任何资源类型；死字段直接删除（YAGNI） |
| 使用 | orchestrator 反射/`_shared_client` 属性 + runner 摸 `_is_snapshot` 私有标记 | 快照构造注入 `scope.acquire_lease()`；runner 无条件 `close()`（快照恒私有） | `_is_snapshot` 消亡；`_owns_client` 收敛回 LLMClient 类内（relinquish/公开 `client` property），跨层摸私有清零；**新增：orchestrator `finally` 单点归还未交接快照**（3.12 hunk-7~9，根治交接窗口泄漏） |
| 取消 | task_runtime 经 `running_tasks["agent"].llm_client` 取消在飞 HTTP | **不变**（v1.1 核证：取消链本就不经 registry 的 ai_service 字段，零改动） | 取消只作用于任务与 HTTP response；池引用随任务结束 close 归还 |
| 停机 | `main.shutdown_event` 调裸 `reset()` | `await lifecycle.shutdown()` = `reset()`（换代归还）+ 各退休代 `scope.drain(剩余预算)` | 关闭等待收编进 scope.drain 单点；`timeout` 为**全停机总预算**（v1.4 修订，原按代逐个计） |
| 跨 loop（**本次不做**） | [69] 2.3 曾要求 owner loop 绑定 + `run_coroutine_threadsafe` 回归；实际调用面全在单事件循环内 | 保持现状（`release_owner` 有 loop 走 `create_task`、无 loop 走 `asyncio.run` 兜底） | 见 2.7 取舍①：真实链路不触发，风险为"未来新增同步调用面" |
| 软配额跨 loop（**本次不做**） | `client_sdk` 模块级 `_soft_pool_semaphore`（HEAD L131-140）为单例 | 保持现状 | 见 2.7 取舍②：单 loop 部署下无实际收益 |

### 2.6 reset 换代模型（配置代 generation）

1. 配置变更触发 `reload_ai_config → reset()`；
2. `reset()` = `reset_instance()` 锁内 `_retire_scope()`（即 `scope.release_owner()` **归还 owner 引用**，幂等；v1.1 修正：不是"标记"而是"归还"——归还后零穿越才可能发生）+ 工厂 `_instance=None`；
3. **新请求** → `get_service()` → 锁内 `_attach_scope` 创建**新一代 scope**（新池、新配置参数）→ 新任务用新池；
4. **旧任务**继续持有旧 scope 的 lease → 请求照常 → 全部结束 release 归零 → 旧池在最后一个 release 协程内自动 `aclose()`；
5. 结果：新配置即时生效（新请求即新代），旧任务零感知，旧池不泄漏。

### 2.7 不做的项与理由（v1.4，2026-09-25 14:15:06）

| # | 项 | 理由 |
|---|---|---|
| ① | 事件循环策略（owner loop 绑定、跨 loop 回归） | 配置保存/重置全在 FastAPI 事件循环内，全仓 33 处线程调用无一在此路径，不会跨 loop；真出现时改两个函数即可，现在预埋 loop 字段会阻止内存回收 |
| ② | 软配额按 loop 隔离 | `Semaphore` 仅排队竞争时绑 loop，生产单进程单 loop、多 worker 多进程均不触发；做它收益为零 |
| ③ | LLMClient 不再接收裸 client | LLMClient 必须持有 client 才能发请求（HEAD L283/399），约束前提不成立；防误关已由池唯一所有者+relinquish+close 三态+引用计数达成 |
| ④ | 关闭失败可重试 | 池归零后无人再碰，重试需先造触发者（新功能）；停机时进程将退、重试无意义。**失败日志已补池标识**（3.1），可定位 |
| ⑤ | ~~写盘前错位 reset~~ | **已改判为做**（3.14 删除）：留着会致"保存模型换两次代"，删 1 行风险为零且语义更正确 |
| ⑥ | 取消语义 | 非"不做"——`cancel`/`reset_cancel`/`_current_response`/取消短路全部零改动，已保留 |

---

## 三、逐文件实施 diff（v1.1 已落笔）

**基线**：干净 HEAD `527cfc727`（后端内容与其后 docs-only 提交一致，已 `git diff 527cfc727..HEAD -- backend/` 空核证）。  
**校验**：每个 ```diff 块的 `-`/上下文行经 `check_doc_diff` 类校验器对基线**整行精确**比对（`+`/`@@`/空行不校验）；3.4 为全新文件，预期 `SKIPPED=1`。  
**编排**：3.1→3.13 = 依赖序（底层 lease → 所有权门面 → 工厂/停机 → 决议 → 注册 → 接线），与五章实施步骤一一对应；每文件编辑历史区只在**尾部追加**，不删不插中间。

### 3.1 `backend/app/llm/client_sdk.py` — lease 核心落户 + 所有权移交门面

- 吸收 [70]素材-lease核心 两段类（原样：归零关闭 `close_on_zero`、释放幂等、池级线程锁）；
- 新增 `relinquish_ownership()`（幂等移交）与 `client` property（公开 `_client`，消灭跨层摸私有，欠账①）；
- `close()` 三态：`_owns_client=False`（共享池/已移交）→ no-op；独占池 → `aclose`（`is_closed` 双保险）；
- **v1.4 审核新增**：`acquire()` 增 `client.is_closed` 检查——偿还 [69] 1.2.3⑥ / 2.2 池约束④"底层被外部关闭后池仍可 acquire"（借出即炸的真病灶），`close()` 已有同款双保险、acquire 侧此前缺失；
- **v1.4 说明**：`close_on_zero=False` 为素材保留分支（借用池不随引用归零关闭的旧语义），本方案全部调用点用默认 `True`（引用归零即关）——保留是为不毁素材已验证逻辑，不新增用法（YAGNI：不预设第二种所有权形态）；**v1.11 补**：`_SharedClientPool.closing` property 经全仓核**零消费点**（含测试），按 YAGNI **删除**——`_closing` 实例标志本身保留（`acquire`/`release` 内部判据 + 2.3 并发边界描述仍引用它），删的只是无读者的公开 property。

```diff
@@ hunk-1 imports: +inspect/+threading（素材 close 判可等待对象 / 池级线程锁）
 import asyncio  # 2026-09-20 小欧 P5: 软配额信号量 — 小欧-2026-09-20
 import httpx
+import inspect  # [70] SharedClientPool.close 判定可等待对象 — 小欧-2026-09-25
 import json
+import threading  # [70] SharedClientPool 池级线程锁(多线程 acquire/release) — 小欧-2026-09-25
 from typing import Any, AsyncGenerator, Dict, List, Optional

@@ hunk-2 lease 两段类落于 _RETRYABLE_STATUS 之后（素材原样 + 署名头）
 # 可重试 HTTP 状态: 429限流 / 5xx服务端瞬时错误, 由 base_service L1 重试处理 — 小欧 2026-07-17
 _RETRYABLE_STATUS = (429, 500, 502, 503, 504)
 
+# ============================================================
+# [70] 共享连接池 lease 核心(引用计数) — 落户自 doc-9月优化/[70]素材-lease核心 原样吸收
+# 归零关闭(close_on_zero)/释放幂等(lease._released)/池级线程锁 — 小欧 2026-09-25
+# ============================================================
+
+class _SharedClientPool:
+    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
+        self.client = client
+        self.close_on_zero = close_on_zero
+        self._ref_count = 1
+        self._closing = False
+        self._lock = threading.Lock()
+
+    def acquire(self) -> "SharedClientLease":
+        with self._lock:
+            if self._closing:
+                raise RuntimeError("共享 httpx 客户端已关闭，不能继续获取 lease")
+            if getattr(self.client, "is_closed", False):
+                # [70] v1.4 审核新增: 底层被池外 aclose 后禁借, 防借出即炸(偿还 [69] 1.2.3⑥/2.2 池约束④) — 小欧-2026-09-25
+                raise RuntimeError("共享 httpx 客户端已被外部关闭，不能继续获取 lease")
+            self._ref_count += 1
+        return SharedClientLease._from_pool(self)
+
+    def release(self) -> bool:
+        with self._lock:
+            if self._closing or self._ref_count <= 0:
+                return False
+            self._ref_count -= 1
+            if self._ref_count != 0 or not self.close_on_zero:
+                return False
+            self._closing = True
+            return True
+
+    @property
+    def ref_count(self) -> int:
+        with self._lock:
+            return self._ref_count
+
+    async def close(self) -> None:
+        if getattr(self.client, "is_closed", False) is True:
+            return
+        try:
+            result = self.client.aclose()
+            if inspect.isawaitable(result):
+                await result
+        except Exception as exc:
+            logger.warning(f"[LLM] 共享 httpx 客户端关闭失败(pool={id(self):#x}): {exc}")  # [70] v1.4 审核新增: warning 带池标识, 多代并存时可定位(2.7④) — 小欧-2026-09-25
+
+
+class SharedClientLease:
+    """共享连接池的一次引用；释放幂等，最后一个引用负责关闭。"""
+
+    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
+        self._pool = _SharedClientPool(client, close_on_zero=close_on_zero)
+        self._released = False
+
+    @classmethod
+    def _from_pool(cls, pool: _SharedClientPool) -> "SharedClientLease":
+        lease = cls.__new__(cls)
+        lease._pool = pool
+        lease._released = False
+        return lease
+
+    @property
+    def client(self) -> Any:
+        return self._pool.client
+
+    @property
+    def ref_count(self) -> int:
+        return self._pool.ref_count
+
+    @property
+    def is_released(self) -> bool:
+        return self._released
+
+    def acquire(self) -> "SharedClientLease":
+        if self._released:
+            raise RuntimeError("已释放的 lease 不能继续获取引用")
+        return self._pool.acquire()
+
+    async def release(self) -> None:
+        if self._released:
+            return
+        self._released = True
+        if self._pool.release():
+            await self._pool.close()
+
 
 def _build_request_body(

@@ hunk-3 LLMClient: relinquish_ownership + client property + close 三态
             except Exception as e:
                 logger.warning(f"[LLMClient.cancel] 关闭流式响应失败: {e}")
 
+    def relinquish_ownership(self) -> None:
+        """移交底层 httpx 客户端所有权(本实例不再关闭) — [70] ConnectionScope.ensure_pool 调用 — 小欧 2026-09-25
+        幂等: 重复移交无害; 移交后 close() 对共享池变 no-op, 实例仍保留使用引用(不丢连接)。"""
+        self._owns_client = False
+
+    @property
+    def client(self) -> httpx.AsyncClient:
+        """公开底层 httpx 客户端 — [70] 替代跨层摸 _client 私有字段(欠账①) — 小欧 2026-09-25"""
+        return self._client
+
     async def close(self):
-        """关闭客户端,释放连接池 - 小沈 2026-06-09"""
-        await self._client.aclose()
+        """关闭客户端,释放连接池 - 小沈 2026-06-09
+        [70] 三态收口(小欧 2026-09-25): _owns_client=False(共享池/已移交) → no-op(池归 ConnectionScope
+        引用计数管理); 独占池 → aclose(带 is_closed 双保险)。_owns_client 判据全部收敛回本类(欠账①)。"""
+        if not self._owns_client:
+            return
+        if getattr(self._client, "is_closed", False):
+            return
+        await self._client.aclose()
```

### 3.2 `backend/app/llm/base_service.py` — ensure_client_pool / lease 注入 / close 三分支 / 删 reset_sdk

- `ensure_client_pool()`：`_ensure_client()` → `relinquish_ownership()`（幂等）→ 返回 `sdk.client`（`_attach_scope` 唯一调用点）；
- `__init__`/`snapshot` 增 `client_lease` 参数（与 `shared_client` 成对）；删 `snap._is_snapshot = True`（死判据，判据移入 close）；
- `close()` 三分支：归还 `_client_lease`（摘引用防重复 + release 自身幂等双保险）→ `sdk.close()`（类内三态）；
- **删 `reset_sdk`**：全仓（app+tests）零调用核证（仅定义与注释提及），裸置 `_llm_sdk=None` 还泄漏独占池——YAGNI 直接删除。

```diff
@@ hunk-1 编辑历史尾部追加（禁插中间）
 # 2026-09-23 小欧 - wiring假保存修复: request_stream 流总硬超时 3 处改读 tuning.llm_net.stream_total_timeout 兜底常量（此前设置页可改实际不生效）
+# 2026-09-25 小欧 - [70] ConnectionScope连接池统一所有者: ①新增 ensure_client_pool()(建池+relinquish移交+返回client); ②__init__/snapshot 增 client_lease 参数(与 shared_client 成对), close() 改三分支(共享归还lease/独占aclose/单例no-op), 删 _owns_client 跨层判据; ③删 snap._is_snapshot 死判据(runner 无条件 close); ④删除零调用的 reset_sdk(裸置None泄漏独占池, YAGNI)
 """
@@ hunk-2 import 增 SharedClientLease
 from app.llm.core import create_cancelled_chunk
-from app.llm.client_sdk import create_llm_client
+from app.llm.client_sdk import create_llm_client, SharedClientLease  # [70] client_lease 注解 — 小欧-2026-09-25
 from app.llm.reasoning import extract_reasoning_from_chunk, extract_reasoning_from_message
@@ hunk-3 __init__ 增 client_lease 形参与存储
         shared_client: Optional["httpx.AsyncClient"] = None,  # C1: 共享连接池, 快照复用不 new(仅在 snapshot 构造时传)
+        client_lease: Optional[SharedClientLease] = None,  # [70] 与 shared_client 成对的池 lease, close() 归还 — 小欧-2026-09-25
     ):
@@ hunk-4 存储成对
         self._shared_client = shared_client  # 2026-09-20 小欧 C1: 构造期定论, 杜绝"先建独占池再注入"竞态 — 小欧-2026-09-20
+        self._client_lease = client_lease   # [70] 共享池 lease(close 时归还, 归零由 ConnectionScope 关) — 小欧-2026-09-25
         try:
@@ hunk-5 ensure_client_pool 取代 reset_sdk
                 shared_client=self._shared_client,  # 2026-09-20 小欧 C1: 快照构造期已定共享地址 — 小欧-2026-09-20
             )
 
+    def ensure_client_pool(self) -> "httpx.AsyncClient":
+        """[70] 建池 + 所有权移交(幂等), 返回底层共享 httpx 客户端 — 小欧 2026-09-25
+        ConnectionScope.ensure_pool 唯一调用点: 首次 create_llm_client(独占池) → relinquish_ownership
+        (保留使用引用不关池) → 池生命周期交 ConnectionScope 引用计数; 重复调用直接复用已建池。"""
+        self._ensure_client()
+        self._llm_sdk.relinquish_ownership()   # 幂等: 已移交再调无害
+        self._shared_client = self._llm_sdk.client
+        return self._shared_client
+
-    def reset_sdk(self):
-        """重置底层 SDK 缓存 — L2 会话级换模(整体替换 llm_model, 可能变更 api_base)后必须调用:
-        _ensure_client 只在首次创建 SDK 时读取 llm_model, 不重置则新 api_base/model 不生效,
-        造成"记录身份与实际 HTTP 连接不一致" — 三堂会审 P1 修复 小欧 2026-08-22"""
-        self._llm_sdk = None
-
     def snapshot(self, model_ref: Optional[ModelRef] = None,
@@ hunk-6 snapshot 签名 + docstring _is_snapshot 语义更新
                  context_limit: Optional[int] = None,
-                 shared_client: Optional["httpx.AsyncClient"] = None) -> "BaseAIService":
+                 shared_client: Optional["httpx.AsyncClient"] = None,
+                 client_lease: Optional[SharedClientLease] = None) -> "BaseAIService":  # [70] 与 shared_client 成对注入 — 小欧-2026-09-25
@@ hunk-7 docstring 死判据表述更新
-        模型快照, 共享单例恒定全局默认不再被污染, 彻底根除该竞态。返回实例带 _is_snapshot 标记,
-        供 run_agent_in_background 结束后释放其 httpx 连接池。
+        模型快照, 共享单例恒定全局默认不再被污染, 彻底根除该竞态。[70] 小欧 2026-09-25: _is_snapshot
+        标记消亡(runner 无条件 close, 判据在 close 三分支内); 共享快照经 client_lease 归还池引用。
@@ hunk-8 构造调用接 lease、删 _is_snapshot 赋值
             shared_client=shared_client,  # C1: 共享与否由调用方(resolver)按 provider 判据定, 构造期定论
-        )
-        snap._is_snapshot = True
+            client_lease=client_lease,  # [70] 与 shared_client 成对: 同 provider 快照接管池 lease — 小欧-2026-09-25
+        )
         logger.info(f"[BaseAIService.snapshot] 构造独立客户端快照: model={snap.llm_model.model}, provider={snap.llm_model.provider}")
@@ hunk-9 close() 三分支
     async def close(self):
         # 2026-09-20 小欧 C1: 共享池 snapshot 不关连接池(全局单例生命周期统一关), 仅独占池才真关 — 小欧-2026-09-20
-        if getattr(self, "_llm_sdk", None) is not None and getattr(self._llm_sdk, "_owns_client", False) is False:
-            return
-        if self._llm_sdk:
-            await self._llm_sdk.close()
+        # [70] 三分支(小欧 2026-09-25): ①共享池快照 → 归还 _client_lease(ref-1, 归零由 ConnectionScope 关);
+        #   ②独占池快照 → LLMClient.close 真关; ③全局单例(relinquish 后 owns=False) → no-op。
+        #   _owns_client 判据收敛回 LLMClient.close 类内, 本层跨层摸私有清零(欠账①) — [70] 2.5「使用」
+        if self._client_lease is not None:
+            _lease = self._client_lease
+            self._client_lease = None   # 先摘引用防重复归还(lease.release 自身幂等, 双保险)
+            await _lease.release()
+            logger.info(f"[BaseAIService.close] 共享池 lease 已归还(model={self.llm_model.model})")
+        if self._llm_sdk:
+            await self._llm_sdk.close()
```

### 3.3 `backend/app/llm/__init__.py` — 导出 SharedClientLease

```diff
 from app.llm.base_service import BaseAIService
+from app.llm.client_sdk import SharedClientLease  # [70] 共享池 lease 对外导出(scope/resolver 注入用) — 小欧 2026-09-25
 
 from app.llm.xml_adapter import (
@@ __all__
 __all__ = [
     "BaseAIService",
+    "SharedClientLease",
     "convert_xml_tool_call_to_json",
```

### 3.4 `backend/app/services/lifecycle/connection_scope.py` — 新增：共享池唯一所有者

> 全新文件，全部为 `+` 行 → 校验器预期 `SKIPPED=1`（无基线可比）。

```diff
+# -*- coding: utf-8 -*-
+"""
+connection_scope — 共享连接池唯一所有者(一代配置 = 一个 scope)
+
+[70] ConnectionScope连接池统一所有者实施方案 — 小欧 2026-09-25
+职责(SRP): 池由它建(ensure_pool), 计数由它发(acquire_lease), 换代由它退休(release_owner),
+停机由它等(drain); 不做业务查询(决议留 resolver), 不做归还中介(快照 close 直线 release)。
+生命周期模型见 [70] 2.3: 无状态机, 纯引用计数——owner 归还后零穿越只可能在退休后,
+close_on_zero 天然实现"活动任务撑池不关、任务全结束后最后一个 release 归零 aclose"。
+"""
+
+import asyncio
+import time
+from typing import Optional
+
+from app.logger import logger
+from app.llm import BaseAIService, SharedClientLease
+
+# 换代归还的 owner 释放协程强引用表: asyncio 仅持 Task 弱引用, GC 回收会取消协程致 ref 悬挂,
+# 强引用持有, done 时 discard 防泄漏(与 orchestrator._background_tasks 同精神) — 小欧 2026-09-25
+_pending_release_tasks: set = set()
+
+
+class ConnectionScope:
+    """共享 httpx 连接池唯一所有者 — 一代配置(单例+池)的生命周期锚 — [70] 小欧 2026-09-25"""
+
+    def __init__(self, ai_service: BaseAIService) -> None:
+        """持本代单例(池未建); owner lease 于 ensure_pool 建立(计数起点=1) — 小欧 2026-09-25"""
+        self.ai_service = ai_service
+        self._owner_lease: Optional[SharedClientLease] = None
+        self._owner_released = False
+
+    def ensure_pool(self) -> None:
+        """建池 + 所有权移交(幂等): 首次经 ai_service.ensure_client_pool() 建 LLMClient 池并
+        relinquish_ownership(保留使用引用不关池), SharedClientLease(client) 计数起点=1 — [70] 2.4 小欧 2026-09-25"""
+        if self._owner_lease is not None:
+            return
+        client = self.ai_service.ensure_client_pool()
+        self._owner_lease = SharedClientLease(client)
+
+    def acquire_lease(self) -> SharedClientLease:
+        """任务/快照借用本代池(ref+1)。已退休/未初始化抛 RuntimeError(防新任务混入旧代);
+        池已归零(_closing)由素材 SharedClientLease.acquire 自身拦截(双重防线) — [70] 2.3 小欧 2026-09-25"""
+        if self._owner_lease is None:
+            raise RuntimeError("ConnectionScope 未初始化(池未建), 禁止借用")
+        if self._owner_released:
+            raise RuntimeError("ConnectionScope 已退休(换代/停机), 禁止新任务混入旧代")
+        return self._owner_lease.acquire()
+
+    def release_owner(self) -> None:
+        """换代/停机归还 owner 引用(幂等, ref-1; 归零由素材 close_on_zero 自动 aclose)。
+        调度参照 close_instance_sync 双分支: 运行中事件循环 create_task(强引用防 GC 取消),
+        无运行循环 asyncio.run 同步完成 — [70] 2.2; reset() 新语义即此调用 — 小欧 2026-09-25"""
+        if self._owner_released or self._owner_lease is None:
+            return
+        self._owner_released = True
+        coro = self._owner_lease.release()
+        try:
+            loop = asyncio.get_running_loop()
+        except RuntimeError:
+            loop = None
+        if loop is not None:
+            task = loop.create_task(coro)
+            _pending_release_tasks.add(task)
+            task.add_done_callback(_pending_release_tasks.discard)
+        else:
+            asyncio.run(coro)
+
+    async def drain(self, timeout: float = 30.0) -> None:
+        """停机收口: 等本代池 lease 全部归零关闭(0.1s 轮询, 超时记 warning 放行不阻塞退出)。
+        归零关闭由 release 触发, 本函数只等 — [70] 2.3 小欧 2026-09-25"""
+        deadline = time.monotonic() + timeout
+        while self.ref_count > 0:
+            if time.monotonic() >= deadline:
+                logger.warning(
+                    f"[ConnectionScope] drain 超时{timeout}s 放行: 剩余 ref={self.ref_count}(活动任务未结束)")
+                return
+            await asyncio.sleep(0.1)
+        # 归零与 aclose 之间存在微窗口(最后一个 release 协程在途), 短歇让关闭收尾 — 小欧 2026-09-25
+        await asyncio.sleep(0.05)
+
+    @property
+    def ref_count(self) -> int:
+        """池引用计数(owner 未归还时含 1) — 可观测/测试断言 — [70] 2.4 小欧 2026-09-25"""
+        if self._owner_lease is None:
+            return 0
+        return self._owner_lease.ref_count
+
+    @property
+    def is_released(self) -> bool:
+        """退休态(owner 已归还) — 替代四态状态机的直接观测 — [70] 2.3 小欧 2026-09-25"""
+        return self._owner_released
```

### 3.5 `backend/app/services/lifecycle/service.py` — 工厂收口：_attach_scope / _retire_scope / get_scope

- 全局：`_scope`（当前代）、`_retired_scopes`（退休代表，归零即清防无界增长）；
- **不变式（写者保证）**：`_instance` 非 None ⟹ `_scope` 非 None——所有落位路径"先 attach 后落位"，所有清位路径"先清 `_instance` 再 retire"（锁外 `get_scope`/`get_service` 早退因此永远见不到半初始化）；
- `_retire_scope()`：`release_owner()` + 入退休表 + `_scope=None`——**绝不关旧池**；`get_scope()`：`_scope is None → get_service()` 惰性建代（读全局无需 `global`）。
- **失败语义（v1.7 三轮复核改判，取代 v1.5/v1.6 补记）**：`get_service`/`get_service_for_model` 都是**先 `cleanup_old_instance`（清 `_instance` + 退休旧 scope）再建新代**——attach 失败时 `_instance`/`_scope` 必已为 None、旧代已退休，**不存在 v1.5 所称"旧代保留继续服务"**；新旧代失败结果等价（`_instance=None`、`_current_model_ref=None`、raise，断服至下次调用重试；[70] except 省去显式 `_instance=None` 正因 cleanup 已清位）。[70] 的真实改进有二：①`_scope` 与 `_instance` 均不落位（`_attach_scope` 成功才挂、挂后才落位）——锁外 `check_cache_valid`/`get_scope` 永不见半初始化；②旧代池经 `_retire_scope` 归还 owner 由活动 lease 撑住——HEAD 同位置 `close_instance_sync(old)` **真关旧池连坐活动任务**（[69] 病灶同源），失败路径不再雪上加霜。BUG-06"半初始化不缓存"本质不变；G2 断言 `_instance is None` 两代语义下均成立（[70] 下因 cleanup 先清位）。

```diff
@@ hunk-1 编辑历史尾部追加
 # 2026-09-23 - 小欧 - [64] LLM补充采样参数: ①create_service_instance 三参 None 透传(top_p/frequency_penalty/presence_penalty, 仿 max_tokens 写法); ②temperature 去 float(...,0.7) 恒非 None 改可 None(死键复活); ③parse_model_params pop 缺省改读 llm.context_limit_default 全局兜底
+# 2026-09-25 小欧 - [70] ConnectionScope连接池统一所有者: ①新增 _scope/_retired_scopes 全局与 _attach_scope/_retire_scope/get_scope/get_retired_scopes(不变式: _instance 非None⟹_scope 非None); ②get_service/get_service_for_model 建池改经 _attach_scope(删 _ensure_client+裸暴露 _shared_client 反射点); ③reset_instance/cleanup_old_instance/set_instance 换代改走 _retire_scope(release_owner 归还, 绝不关旧池)
 """
@@ hunk-2 imports
-from typing import Optional, Dict, Any, Tuple
+from typing import Optional, Dict, Any, Tuple, List  # [70] List: _retired_scopes — 小欧-2026-09-25
 import threading
@@ hunk-3 ConnectionScope 导入
 from app.services.lifecycle.lifecycle import close_instance_sync
+from app.services.lifecycle.connection_scope import ConnectionScope  # [70] 唯一所有者 — 小欧-2026-09-25
 from app.config import get_config  # 新增 — 小欧 2026-09-23
@@ hunk-4 全局 + 收口函数
 _instance_lock = threading.Lock()
+_scope: Optional[ConnectionScope] = None   # [70] 当前代唯一所有者; 不变式: _instance 非None ⟹ _scope 非None — 小欧-2026-09-25
+_retired_scopes: List[ConnectionScope] = []   # [70] 已退休代(供 shutdown drain); 归零即清防无界增长 — 小欧-2026-09-25
+
+
+def _attach_scope(instance: BaseAIService) -> None:
+    """[70] 新代 scope 诞生收口: 建池+所有权移交成功后才挂载, 失败 _scope 不落位(防半初始化) — 小欧 2026-09-25"""
+    global _scope
+    scope = ConnectionScope(instance)
+    scope.ensure_pool()
+    _scope = scope
+
+
+def _retire_scope() -> None:
+    """[70] 换代退休收口: 归还当前代 owner 引用(活动任务 lease 撑池, 归零自动关) + 移入退休表供 shutdown drain。
+    绝不主动关池([69] 病灶: 关旧池必然误伤活动任务) — 小欧 2026-09-25"""
+    global _scope, _retired_scopes
+    if _scope is None:
+        return
+    _scope.release_owner()
+    _retired_scopes.append(_scope)
+    # 已归零的退休代即时清出(仍>0 的在役退休代保留), 防长驻进程列表无界增长 — 小欧 2026-09-25
+    _retired_scopes = [s for s in _retired_scopes if s.ref_count > 0]
+    _scope = None
+
+
+def get_scope() -> ConnectionScope:   # [70] v1.11 补返回类型标注(AGENTS.md 要求 type hints) — 小欧 2026-09-25
+    """[70] 取当前代 ConnectionScope(共享池唯一所有者); 无则经 get_service 惰性创建新代 — 小欧 2026-09-25"""
+    if _scope is None:
+        get_service()
+    if _scope is None:
+        raise RuntimeError("ConnectionScope 未初始化(get_service 未创建 scope)")
+    return _scope
+
+
+def get_retired_scopes() -> List[ConnectionScope]:   # [70] v1.11 补返回类型标注(AGENTS.md 要求 type hints) — 小欧 2026-09-25
+    """[70] 已退休代快照(list 拷贝, 供 lifecycle.shutdown 逐个 drain) — 小欧 2026-09-25"""
+    return list(_retired_scopes)
+
 
 def get_resolver_and_config():
@@ hunk-5 cleanup_old_instance: 先清位再退休
     global _instance, _current_model_ref
     old_instance = _instance
-    _instance = None
+    _instance = None   # [70] 先清实例再退休: 锁外漏读窗口只可能拿到旧 scope(安全), 永不见半初始化 — 小欧-2026-09-25
+    _retire_scope()    # [70] 换代: 归还旧代 owner(活动任务撑池), 绝不关旧池 — 小欧-2026-09-25
     _current_model_ref = new_model_ref
     close_instance_sync(old_instance)
@@ hunk-6 get_service 建池改经 _attach_scope（先 attach 后落位）
             provider_config = get_provider_config(ai_config, config_model.provider)
 
-            _instance = create_service_instance(provider_config, config_model.provider, config_model.model)
-
-            # 2026-09-20 小欧 C1: 惰性触发单例首次建池(复用原 _ensure_client 路径),
-            #   并暴露共享【底层 httpx.AsyncClient】引用供 resolver 快照构造期注入(存 httpx 连接池,
-            #   非 LLMClient 对象 —— 快照经 create_llm_client(shared_client=...) 建自己的 LLMClient 复用连接池) — 小欧-2026-09-20
-            try:
-                _instance._ensure_client()
-                _shared_llm_sdk = getattr(_instance, "_llm_sdk", None)
-                if _shared_llm_sdk is not None:
-                    _instance._shared_client = _shared_llm_sdk._client
-            except Exception:
-                # BUG-06修复(小欧 2026-09-20): _ensure_client/共享池赋值失败时回滚, 防半初始化实例被缓存
-                _instance = None
-                _current_model_ref = None
-                raise
+            # [70] 新代 scope 诞生(小欧 2026-09-25): 建池 + LLMClient 所有权移交(relinquish) + 挂载三事一处,
+            #   取代 2026-09-20 C1 的 _ensure_client + 裸暴露 _shared_client 属性——反射摸私有消亡,
+            #   池/计数/关闭唯一归属 ConnectionScope([70] 2.5「创建」环节); 先 attach 后落位保不变式
+            _new_instance = create_service_instance(provider_config, config_model.provider, config_model.model)
+            try:
+                _attach_scope(_new_instance)
+            except Exception:
+                # BUG-06修复(小欧 2026-09-20): 建池/挂载失败时回滚, 防半初始化实例被缓存 — [70] 维持该语义
+                _current_model_ref = None
+                raise
+            _instance = _new_instance
     except:
@@ hunk-7 reset_instance 换代新语义
     with _instance_lock:
         old = _instance
         _instance = None
         _current_model_ref = None
+        _retire_scope()   # [70] 换代新语义: 归还 owner 引用(任务撑池, 归零自动关), 绝不关旧池 — 小欧-2026-09-25
     return old
@@ hunk-8 set_instance: 清位 → 退休 → 挂新 → 落位
     global _instance, _current_model_ref
     with _instance_lock:
+        _instance = None   # [70] 先清位再换代(锁外漏读窗口安全) — 小欧-2026-09-25
+        _current_model_ref = None
+        _retire_scope()
+        if instance is not None:
+            _attach_scope(instance)   # [70] 先 attach 后落位, 维持不变式 — 小欧-2026-09-25
         _instance = instance
         _current_model_ref = model_ref
@@ hunk-9 get_service_for_model 直赋点补挂载
         instance = create_service_instance(provider_config, model_ref.provider, model_ref.model)
         # BUG-16: 直接赋值(已在锁内), 不调set_instance(内部也加锁会死锁)
         global _instance, _current_model_ref
+        _attach_scope(instance)   # [70] 新代 scope 挂载(先 attach 后落位, 与 get_service 同构) — 小欧-2026-09-25
         _instance = instance
         _current_model_ref = model_ref
```

### 3.6 `backend/app/services/lifecycle/lifecycle.py` — 新增 shutdown() 停机收口

```diff
@@ hunk-1 模块 docstring 追加（禁插中间）
 小欧 2026-08-14 llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
+小欧 2026-09-25 [70] 新增 shutdown(): 停机收口 = reset() 换代归还 + 逐个退休代 scope.drain(超时放行)
 """
@@ hunk-1b imports 增 time(总预算 deadline 所需)
 import asyncio
+import time  # [70] shutdown 总预算 deadline 计算 — 小欧-2026-09-25
 from typing import Optional
@@ hunk-2 文件尾追加 shutdown
 def reset():
     """重置工厂状态 — 小沈 2026-06-08
     P1-07/P2-07修复: 使用公开reset_instance替代直接操作私有变量
     """
     from app.services.lifecycle.service import reset_instance
     old = reset_instance()
     close_instance_sync(old)
     logger.info("[AIServiceFactory] 工厂状态已重置")
+
+
+async def shutdown(timeout: float = 30.0) -> None:
+    """[70] 停机收口(小欧 2026-09-25): ①reset() 换代归还当前代 owner(阻断新任务混入)+关闭旧实例;
+    ②逐个等待退休代池 lease 归零关闭(0.1s 轮询)。v1.4 审核修订: timeout 为**全停机总预算**
+    (原按代逐个计, 最坏 代数×timeout 无界上界), 各代按剩余预算 drain, 耗尽即放行不阻塞进程退出。
+    main.shutdown_event 调用, 取代原裸 reset()(原调用只清工厂不等池关闭)。"""
+    from app.services.lifecycle.service import get_retired_scopes
+    reset()
+    deadline = time.monotonic() + timeout
+    for scope in get_retired_scopes():
+        remaining = deadline - time.monotonic()
+        if remaining <= 0:
+            logger.warning(f"[AIServiceFactory] 停机收口预算耗尽({timeout}s), 剩余退休代未等完(放行)")
+            break
+        await scope.drain(timeout=remaining)
+    logger.info("[AIServiceFactory] 停机收口完成(共享池 lease 已归零或超时放行)")
```

### 3.7 `backend/app/services/lifecycle/__init__.py` — 导出 shutdown + get_scope

```diff
-- close_instance/close_instance_sync: 服务生命周期
+- close_instance/close_instance_sync/shutdown: 服务生命周期(含停机 drain)
@@ docstring 行
-- get_service/get_service_for_model/reset: 服务创建
+- get_service/get_service_for_model/get_scope/reset: 服务创建与唯一所有者门面
 """
 from app.services.lifecycle.validation import ConfigValidationResult
 from app.services.lifecycle.lifecycle import close_instance, close_instance_sync, reset
+from app.services.lifecycle.lifecycle import shutdown  # [70] 停机收口 — 小欧-2026-09-25
 from app.config import get_config_path
 from app.services.lifecycle.validation import make_validation_error, validate_credentials, validate_config
-from app.services.lifecycle.service import get_service, get_service_for_model
+from app.services.lifecycle.service import get_service, get_service_for_model, get_scope  # [70] — 小欧-2026-09-25
 
 __all__ = [
     "ConfigValidationResult",
     "close_instance", "close_instance_sync", "get_config_path",
     "make_validation_error", "validate_credentials", "validate_config",
-    "get_service", "get_service_for_model", "reset",
+    "get_service", "get_service_for_model", "get_scope", "reset", "shutdown",  # [70] +get_scope/shutdown — 小欧-2026-09-25
 ]
```

### 3.8 `backend/app/services/__init__.py` — 导出 get_scope（orchestrator 入口）

```diff
     get_service,
     get_service_for_model,
+    get_scope,
     reset,
 )
 
 __all__ = [
     "ConfigValidationResult",
     "close_instance", "close_instance_sync", "get_config_path",
     "make_validation_error", "validate_credentials", "validate_config",
-    "get_service", "get_service_for_model", "reset",
+    "get_service", "get_service_for_model", "get_scope", "reset",  # [70] +get_scope — 小欧-2026-09-25
 ]
```

> `shutdown` 不在本文件导出：唯一消费点 `main.py` 直接 `from app.services.lifecycle import shutdown`（YAGNI，不加无消费导出）。

### 3.9 `backend/app/main.py` — shutdown_event 改停机收口

```diff
     global _cleanup_task_ref
     if _cleanup_task_ref is not None and not _cleanup_task_ref.done():
         _cleanup_task_ref.cancel()
-    from app.services.lifecycle import reset
-    reset()
+    # [70] 停机收口(小欧 2026-09-25): 换代归还 + 等退休代共享池 lease 归零关闭(超时放行)
+    from app.services.lifecycle import shutdown
+    await shutdown()
```

### 3.10 `backend/app/services/model/resolver.py` — resolve_session_client 改签名 (scope, session_id)

- 进门 `scope.acquire_lease()`（在 try **外**，失败诚实上抛不建任务）；`transferred` 标记 + `finally` 未转移归还（跨 provider / 构造失败防 ref 悬挂）；
- 同 provider/无覆盖/空会话/两失败兜底 → 快照接管 lease（`transferred=True`）；跨 provider 独占新池 → 不接，finally 归还；
- `_default_snapshot(ai_service, lease)`：`lease.client` 替代 `getattr(..."_shared_client")` 反射（欠账①清零）；
- 空会话不再 `return None`——走无覆盖分支派生默认快照（恒非 None，编排层 None 死分支随之消亡）。

```diff
@@ hunk-1 编辑历史尾部追加
 #   双源，与 model_service.get_current_ref / config_helpers._update_model_ref 统一为单一真相源）
+# 2026-09-25 - 小欧 - [70] ConnectionScope连接池统一所有者: ①resolve_session_client 签名 ai_service→scope(lease 只从 scope.acquire_lease() 出, 反射摸 _shared_client 消亡); ②进门 acquire + transferred 标记 + finally 未转移归还; ③空会话走无覆盖分支派生默认快照(恒非 None); ④_default_snapshot 改传 lease 接管池引用
 """
@@ hunk-2 _default_snapshot 接管 lease
-def _default_snapshot(ai_service) -> "BaseAIService":
+def _default_snapshot(ai_service, lease) -> "BaseAIService":   # [70] 增 lease 参数, 快照接管本代池 — 小欧-2026-09-25
     """C3/C4(小欧 2026-09-20): 会话决议失败路径派生全局默认快照兜底(无条件快照)。
-    resolver 失败时绝不允许返回 None 让主流程回退全局单例(破坏C1'无条件快照'), 
-    统一返回 ai_service.snapshot(复用其共享连接池, 快照模型=全局默认)。"""
-    _shared_llm = getattr(ai_service, "_shared_client", None)  # 内部自取, 防 except 分支 L146 未执行 NameError(DRY)
-    _snap = ai_service.snapshot(shared_client=_shared_llm)
+    resolver 失败时绝不允许返回 None 让主流程回退全局单例(破坏C1'无条件快照'),
+    统一返回 ai_service.snapshot(复用其共享连接池, 快照模型=全局默认)。[70] 增 lease, 快照接管本代池。"""
+    # [70] 共享池地址改经 lease.client 公开属性(反射摸 _shared_client 消亡) — 小欧 2026-09-25
+    _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)
     logger.warning(f"[chat] 会话决议失败, 派生全局默认快照兜底: model={_snap.llm_model.model}")
     return _snap
@@ hunk-3 函数签名 + 进门 acquire + 空会话经 _ov=None 走无覆盖分支
-async def resolve_session_client(ai_service, session_id):
-    """会话模型覆盖决议：返回独立客户端快照，无覆盖返回None。纯搬迁，逻辑零改动。
-    # 2026-09-05 - 小健 - 自 stream_orchestrator 编排⑥(原 285-336)整块外迁, 逐字复制逻辑零改动。
-    #   S2 sessionModel 生效(10.1.7②-4/文档2 6.1.1/6.1.8)：编排层读会话覆盖写 ai_service.llm_model(L2 结构化)
-    #   归一(小欧 2026-08-22 报告v1.25 6.5): 整个 ModelRef 单变量原子切换——缺省键回退原值合并,
-    #   消除原逐属性赋值的半覆盖中间态(KISS-DIRECT 纯增强)
-    """
-    if not session_id:
-        return None
-    try:
-        # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
-        _ov = await db.atxn("chat", lambda conn: get_session_model(conn, session_id))
-        # 2026-09-20 小欧 C1(修正): 无条件快照——无论有无覆盖都构造独立 BaseAIService(状态分离),
-        #   有覆盖按原路径查目标 provider 配置; 无覆盖仅派生全局默认, snapshot 复用全局共享连接池 — 小欧-2026-09-20
-        _shared_llm = getattr(ai_service, "_shared_client", None)
+async def resolve_session_client(scope, session_id):
+    """会话模型覆盖决议：返回任务私有快照(恒非 None), 同 provider 快照接管本代 lease — [70] 小欧 2026-09-25
+    # 2026-09-05 - 小健 - 自 stream_orchestrator 编排⑥(原 285-336)整块外迁 — 小健 2026-09-05
+    # [70] 签名 ai_service→scope: lease 只从 scope.acquire_lease() 出(反射摸 _shared_client 消亡);
+    #   进门 acquire(ref+1) + transferred 标记 + finally 未转移归还——跨 provider 独占池不接 lease。"""
+    ai_service = scope.ai_service
+    lease = scope.acquire_lease()   # 进门借用本代池(ref+1); 已退休/未初始化诚实上抛(不建任务)
+    transferred = False
+    try:
+        _ov = None
+        if session_id:
+            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
+            _ov = await db.atxn("chat", lambda conn: get_session_model(conn, session_id))
+        # 2026-09-20 小欧 C1(修正): 无条件快照——无论有无覆盖都构造独立 BaseAIService(状态分离),
+        #   有覆盖按原路径查目标 provider 配置; 无覆盖仅派生全局默认, snapshot 复用本代共享池 — [70] 小欧-2026-09-25
         # BUG-12修复(小欧 2026-09-20): 添加类型保护, 防非ModelRef类型(如dict)导致AttributeError静默失效
@@ hunk-4 跨 provider 配置失败兜底接管 lease
             if _pv_cfg is None and _ov.provider and _ov.provider != ai_service.llm_model.provider:
                 logger.warning(f"[chat] 会话模型覆盖已跳过(配置查找失败), 使用全局默认模型快照: provider={ai_service.llm_model.provider}, model={ai_service.llm_model.model}")
-                return _default_snapshot(ai_service)  # C-3(小欧 2026-09-20): 配置失败不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
+                _snap = _default_snapshot(ai_service, lease)  # C-3(小欧 2026-09-20): 配置失败不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
+                transferred = True   # [70] 默认快照接管 lease(close 归还) — 小欧-2026-09-25
+                return _snap
@@ hunk-5 快照构造改 lease 成对注入
-            session_client = ai_service.snapshot(
-                override_ref,
-                api_key=_pv_key,
-                extra_body_params=_pv_ebp,
-                context_limit=_pv_ctx,
-                shared_client=(_shared_llm
-                               if _shared_llm is not None
-                               and (not _ov.provider or _ov.provider == ai_service.llm_model.provider)
-                               else None),  # 2026-09-20 小欧 C1: 同 provider 复用全局共享池; 跨 provider(api_key 不同)保留独占池 — 小欧-2026-09-20
-            )
+            _same_pv = (not _ov.provider or _ov.provider == ai_service.llm_model.provider)
+            session_client = ai_service.snapshot(
+                override_ref,
+                api_key=_pv_key,
+                extra_body_params=_pv_ebp,
+                context_limit=_pv_ctx,
+                shared_client=(lease.client if _same_pv else None),  # [70] 同 provider 复用本代共享池; 跨 provider 独占新池 — 小欧-2026-09-25
+                client_lease=(lease if _same_pv else None),  # [70] lease 与池成对: 同 provider 接管(close 归还), 跨 provider 不接 — 小欧-2026-09-25
+            )
+            if _same_pv:
+                transferred = True   # [70] 跨 provider 不转移 → finally 归还 — 小欧-2026-09-25
             return session_client
@@ hunk-6 无覆盖分支 + except/finally 收口
-        # ---- 无条件快照新增分支(无覆盖): 派生全局默认快照 + 复用全局共享连接池 ----
-        logger.info(f"[chat] C1 无覆盖会话快照(session={session_id})")
-        return ai_service.snapshot(shared_client=_shared_llm)   # 构造期注入共享池, _ensure_client 惰性复用(原 set_shared_client 后置注入已废弃)
-    except Exception as _ov_e:
-        logger.warning(f"[chat] 读会话sessionModel失败(session={session_id}): {_ov_e}")
-    return _default_snapshot(ai_service)  # C-4(小欧 2026-09-20): 读 sessionModel 异常不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
+        # ---- 无条件快照分支(无覆盖/空会话): 派生全局默认快照 + 接管本代共享池 lease ----
+        logger.info(f"[chat] C1 无覆盖会话快照(session={session_id})")
+        _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)   # [70] 构造期注入共享池+成对 lease — 小欧-2026-09-25
+        transferred = True
+        return _snap
+    except Exception as _ov_e:
+        logger.warning(f"[chat] 读会话sessionModel失败(session={session_id}): {_ov_e}")
+        _snap = _default_snapshot(ai_service, lease)  # C-4(小欧 2026-09-20): 异常不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
+        transferred = True
+        return _snap
+    finally:
+        # [70] 未转移的 lease 归还(跨 provider/构造失败), 防 ref 永久悬挂 — 小欧-2026-09-25
+        if not transferred:
+            await lease.release()
```

### 3.11 `backend/app/services/task/task_registry.py` — register_task 删 ai_service 参数与字段

- `ai_service` 字段全仓**零消费点**核证（生产 0 读、测试仅 `test_tdd_14_20_inbox.py:111` 一处断言——step 8 迁移删除）；
- 参数删除后 58 个测试调用点/16 文件机械去第 2 位实参（step 8 清单，逐调用点核证）；`task_runtime` 取消链走 `running_tasks["agent"].llm_client`，**零改动**；
- `typing.Any` 仍被 `pop_task_field` 消费（L228），import 不动。

```diff
@@ hunk-1 编辑历史尾部追加
 # 2026-09-24 21:36:38 小欧 - 配置组改名 tuning.stream_task→tuning.live_front：任务保留时长读取键路径同步，
 #   清理逻辑/默认值 1 小时零改动 — 小欧-2026-09-24
+# 2026-09-25 小欧 - [70] ConnectionScope连接池统一所有者: register_task 删 ai_service 参数与 "ai_service" 字段(全仓零消费点核证, YAGNI); registry 只存任务身份/状态/inbox, 不 import 不持资源句柄(欠账②)
 """
@@ hunk-2 签名 + 字段删除
-async def register_task(task_id: str, ai_service: Any, session_id: Optional[str] = None) -> Optional[str]:
+async def register_task(task_id: str, session_id: Optional[str] = None) -> Optional[str]:  # [70] 删 ai_service 参数 — 小欧-2026-09-25
@@ hunk-3 注册字典
             "_inbox": asyncio.Queue(),         # B机制: 运行中注入消息队列(多条), agent 侧每轮 LLM 调用前合并吸收
             "created_at": datetime.now(),
-            "ai_service": ai_service,
             "_task": asyncio.current_task(),
             "_pause_event": asyncio.Event(),
```

### 3.12 `backend/app/services/chat/stream_orchestrator.py` — 接线：get_scope / 注册去参 / resolve 传 scope / 交接兜底

- hunk-1~6：门面切换与注册去参（`get_scope` 原子取本代、resolve 传 scope、恒非 None 死分支消亡）；
- hunk-7~9 **交接兜底（v1.4 审核新增，根治 [69] 1.2.5 泄漏窗口）**：`_session_client`/`_snapshot_handed_to_runner` 预初始化（同 `bg_task` 防 NameError 模式）→ `create_task` 交接后置标记（其后无 await，无竞态窗口）→ `finally` 单点归还未交接快照（异常/断连/取消/`create_task` 失败全路径覆盖，不逐路径 close——DRY）；**无快照泄漏则旧池必然归零关闭**；
- 边界核证：`register_task`（HEAD 368/375）与 `UniversalAgent` 构造（385）**均在 resolve 之前**，此二者失败时快照尚未创建、无 lease 可泄漏（[69] 4.3 场景 6/7 在本方案顺序下不成立，真实窗口是 resolve 成功后至 bg_task 交接前）。

```diff
@@ hunk-1 编辑历史尾部追加
 # 2026-09-24 21:36:38 小欧 - 配置组改名 tuning.stream_task→tuning.live_front：心跳读取键路径同步(北京老陈裁定组名更准确)，
 #   读逻辑/默认值 _D_HEARTBEAT/心跳周期语义零改动 — 小欧-2026-09-24
+# 2026-09-25 小欧 - [70] ConnectionScope统一流接线: ①get_service→get_scope(本代唯一所有者原子取 ai_service); ②register_task 删 ai_service 实参(两处); ③resolve_session_client 改传 scope, 恒返回快照(删 None 死分支)
 """
@@ hunk-2 import 换门面
-from app.services import get_service
+from app.services import get_scope  # [70] 唯一所有者入口(经 get_service 惰性建代) — 小欧-2026-09-25
 from app.services.model.resolver import get_ai_config_resolver, resolve_session_client  # 8.7 外迁: 会话模型覆盖决议 — 小健 2026-09-05
@@ hunk-3 编排②取本代所有者（原子，防换代窗口双代竞态）
     # ── 编排②取全局服务(LLM单例/model警告/task_id) ————————————————————————— 小健 2026-08-17
-    ai_service = get_service()
+    scope = get_scope()            # [70] 原子取本代唯一所有者(防换代窗口双代) — 小欧-2026-09-25
+    ai_service = scope.ai_service  # [70] 同代单例(UniversalAgent 兜底/注入应答用) — 小欧-2026-09-25
     session_id = session_id or str(uuid.uuid4())
@@ hunk-4 两处注册删实参
-        _reg_res = await register_task(task_id, ai_service, session_id=session_id)
+        _reg_res = await register_task(task_id, session_id=session_id)  # [70] 删 ai_service — 小欧-2026-09-25
@@ hunk-5
-            _reg_retry = await register_task(task_id, ai_service, session_id=session_id)
+            _reg_retry = await register_task(task_id, session_id=session_id)  # [70] 删 ai_service — 小欧-2026-09-25
@@ hunk-6 决议改传 scope、恒非 None（死分支消亡）
         # ── 编排⑥建 UniversalAgent + 会话sessionModel(先建才有 llm_client) ——— 小健 2026-08-17
         agent = UniversalAgent(llm_client=ai_service, task_id=task_id)
         # 8.7 会话模型覆盖决议外迁 resolver.resolve_session_client(纯搬迁, 逻辑零改动) — 小健 2026-09-05
-        #   无覆盖/无 session_id 返回 None, agent 维持全局默认; 有覆盖则换装独立客户端快照(单例不受污染)
-        _session_client = await resolve_session_client(ai_service, session_id)
-        if _session_client is not None:
-            agent.llm_client = _session_client
-            # S2 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry 显示真实生效模型
-            #   (而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神 — 小欧 2026-09-01
-            agent._task_llm_model = getattr(_session_client, "llm_model", None)
+        #   [70] 小欧 2026-09-25: 改传 scope(lease 只从 scope.acquire_lease() 出); 恒返回任务私有快照
+        #   (无 None 死分支)——同 provider 快照接管本代 lease(agent 结束 close 归还), 跨 provider 独占新池
+        _session_client = await resolve_session_client(scope, session_id)
+        agent.llm_client = _session_client
+        # S2 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry 显示真实生效模型
+        #   (而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神 — 小欧 2026-09-01
+        agent._task_llm_model = getattr(_session_client, "llm_model", None)
         # ── [TASK_START] 在会话覆盖快照生效后打印, 用 agent.llm_client(实际生效模型)非全局默认
@@ hunk-7 预初始化快照交接标记(防 finally NameError, 同 bg_task 预初始化模式)
     bg_task = None  # BUG-32修复: 预初始化, 防 except 块 NameError — 小沈 2026-08-13
+    _session_client = None  # [70] 快照预初始化: finally 交接守卫用(防 NameError) — 小欧-2026-09-25
+    _snapshot_handed_to_runner = False  # [70] 交接标记: create_task 后置 True, finally 据此定归还方 — 小欧-2026-09-25
     try:
@@ hunk-8 bg_task 交接后置标记(其后无 await, 无竞态窗口)
         _agent_tasks.add(bg_task)
         bg_task.add_done_callback(_agent_tasks.discard)
+        # [70] 交接完成: 快照关闭责任移交 runner finally, orchestrator 不再归还 — 小欧-2026-09-25
+        _snapshot_handed_to_runner = True
@@ hunk-9 finally 兜底: 未交接快照单点归还([69] 1.2.5 泄漏窗口根治)
     finally:
+        if _session_client is not None and not _snapshot_handed_to_runner:
+            # [70] 未交接 runner 的快照统一单点归还(lease 随之 release 归还本代池);
+            #   异常/断连/取消/create_task 失败等全部路径经此 finally, 不逐路径 close(DRY);
+            #   try/except 与 3.13 runner 同款: 独占池 aclose 抛错也不得吞掉根因/挡住 ContextVar reset — 小欧 2026-09-25
+            try:
+                await _session_client.close()
+            except Exception as _sce:
+                logger.warning(f"[chat] 未交接快照关闭失败(task={task_id}): {_sce}")
         _current_task_id.reset(_task_token)
```

### 3.13 `backend/app/services/agent/agent_runner.py` — finally 关客户端改无条件

- resolver 恒返回任务私有快照 → `getattr(..., "_is_snapshot", False)` 死判据消亡；关闭语义由 `base_service.close` 三分支兜底（共享 lease 归还幂等 / 独占 aclose / 单例 no-op）；
- 连接顺序核证：`resolve`(388) < `bg_task 创建`(489) < 本 finally——resolve 抛错时 runner 根本不执行，**无裸单例入口**；
- 即使直连入口传入无 `close` 的假对象，异常被本块 `except` 捕获记 warning，不打断终态落库。

```diff
@@ hunk-1 编辑历史尾部追加
 # 2026-09-20 - 小欧 - D-1修复(B机制注入消息DB幽灵): 终态 update_user_message_final 增传 session_id,
 #   由 storage 侧对该注入 user_message_id 补 chat_tasks 配对(注入消息答复归属任务), 消除 fetch 重建"user+AI"对时的
 #   NULL 幽灵(前端双栖渲染/linked 误判未回答)。compliance: KISS-DIRECT/禁止backward
+# 2026-09-25 小欧 - [70] finally 关客户端判据改无条件: resolver 恒返回任务私有快照(_is_snapshot 死判据消亡),
+#   关闭语义由 base_service.close 三分支兜底(共享 lease 归还幂等/独占 aclose/单例 no-op) — [70] 2.5「使用」
 """
@@ hunk-2 finally 关闭块
-        # 关闭本任务持有的独立客户端快照(若有), 释放其 httpx 连接池, 防覆盖会话累积泄漏 — 小沈 2026-08-29
-        _snap_client = getattr(agent, "llm_client", None) if agent is not None else None
-        if _snap_client is not None and getattr(_snap_client, "_is_snapshot", False):
-            # 2026-09-20 小欧 C1: 共享池快照 close 由 13.2.3 base_service.close 判据兜底(共享不真关),
-            #   独占池快照照常释放 — 完全兼容原逻辑 — 小欧-2026-09-20
-            try:
-                await _snap_client.close()
-                logger.info(f"[Runner] 会话客户端快照已关闭(task={task_id})")
-            except Exception as _ce:
-                logger.warning(f"[Runner] 关闭会话客户端快照失败(task={task_id}): {_ce}")
+        # 关闭本任务持有的客户端(快照恒私有, 无条件 close) — [70] 小欧 2026-09-25
+        #   三分支由 base_service.close/LLMClient.close 兜底: 共享池快照→归还 lease(ref-1, 归零自动关),
+        #   独占池快照→aclose, 单例(relinquish 后 owns=False)→no-op; _is_snapshot 死判据消亡。
+        #   连接顺序: resolve(388) < bg_task 创建(489) < 本 finally——resolve 抛错时 runner 不执行, 无裸单例入口
+        _snap_client = getattr(agent, "llm_client", None) if agent is not None else None
+        if _snap_client is not None:
+            try:
+                await _snap_client.close()
+                logger.info(f"[Runner] 任务客户端已关闭(task={task_id})")
+            except Exception as _ce:
+                logger.warning(f"[Runner] 关闭任务客户端失败(task={task_id}): {_ce}")
```

### 3.14 `backend/app/services/model/config_helpers.py` — 删写盘前错位 reset（v1.4 审核新增）

- 病灶实证（`config_service.update_config` 顺序）：L98-101 handler（`_update_model_ref` 内 **L387 `reset()`**）→ L103 校验 → **L108 写盘** → L113 `reload_ai_config()`（`_load_config` + 再 `reset()`）——**写盘前已换代一次**，属 [69] 4.1 判定并已在工作树删过的错位触发点（撤销 6 文件时随基线带回）；
- 删除后语义：`reset()` 的正确位置由 L113 承担（写盘+校验成功后一次性换代）；写盘失败时不换代 = 配置未变本就不该换代（**语义更正确**）；消除"写盘前换代 → 窗口内新请求用旧配置建代 → 随即被退休"的多余换代；
- 引用计数模型下它已不致害（只归还 owner，活动 lease 撑池），但**留着即留隐患**（2.7⑤ 审核后决定删除）；
- **附带收益（v1.4 复核发现）**：`test_model_ref_normalization.py:96` monkeypatch 的是 `lifecycle_mod.reset`，而本模块是 `from ...lifecycle import reset` **导入时绑定**→monkeypatch 失效，该"不调 reset"断言实为**假绿**；且 HEAD 下任何调 `_update_model_ref` 的测试会触发**真实 `lifecycle.reset()`（跨测试污染：单例被换代清空）**。删除后该测试名副其实变真绿、污染消除。

```diff
@@ hunk-1 编辑历史尾部追加（禁插中间，锚点=末条历史）
 # 2026-09-22 - 小欧 - 31候选修复 #10: _update_project_root 取代 _set_app_field lambda —— 原写 app.project_root
 #   死键（全读取方统一走 workspace.project_root，保存"成功"永不生效）；改写 workspace.project_root + 类型门禁
+# 2026-09-25 - 小欧 - [70] 审核新增: 删 _update_model_ref 写盘前错位 reset()——换代正确位置在写盘+校验成功后的 reload_ai_config(撤回 6 文件时随基线带回的错位触发点); 保留它会致"保存模型换两次代"(写盘前换代→窗口内新请求拿旧配置建代→随即被退休) — 小欧 2026-09-25
@@ hunk-2 删错位 reset(换代职责归 reload_ai_config)
         config_data['ai'][update.ai_model_ref.provider]['api_base'] = update.ai_model_ref.api_base
-    reset()
     logger.info(f"更新AI模型: provider={update.ai_model_ref.provider}, model={update.ai_model_ref.model}")
```

**零改动声明（v1.4 修正）**：`services/task/task_runtime.py`（取消链走 `running_tasks["agent"].llm_client`，不经 registry ai_service 字段，已核证）；`config_helpers.py` 的 `reload_ai_config():147` 保持（换代正确入口），仅删 `_update_model_ref:387` 错位 reset（3.14）。

---

## 四、验证测试（框架；用例从 [69] 3.10/4.x 移植改造）

### 4.1 静态验证

```powershell
python -m compileall -q app
```

检查：`_owns_client`/`_is_snapshot`/`_shared_client` 反射在生产代码无引用；resolver 无任何 `_shared_client` 反射（含 HEAD 实例级 `getattr(ai_service, ...)` 与工作树类级 `getattr(type(...))`/`__dict__`）；registry 不 import 资源类型、不存 `ai_service` 字段；`reset()` 无 `close` 调用（只经 `_retire_scope` 归还 owner）；全仓无 `mark_config_changed`/`scope.resolve_session`/`scope.release_lease`/`state` 状态机残留；**v1.4 增**：`config_helpers.py` 的 `reset()` 仅 `reload_ai_config()` 一处调用点（3.14 删错位后）；orchestrator `finally` 含未交接快照归还守卫（3.12 hunk-9）；`_SharedClientPool.acquire` 含 `client.is_closed` 检查、`close` warning 含池标识。

### 4.2 定向单元测试（从 [69] 3.10 **六个源测试文件**移植合并；断言按 scope API 改造）

> **v1.8 标注**：此"六个"是 [69] 的**源**文件数，非本方案目标文件数——本方案新增用例合并为 **3 个**新测试文件（见 6.1 表），六章分步追加。

- 计数正确性：`acquire_lease`/快照 `close`→release/归零/幂等 release/`ref_count` 观测；
- 池外守卫（v1.4 增）：底层 client 被池外 `aclose()` 后 `acquire` 抛 `RuntimeError`（3.1 新增 `is_closed` 检查）；
- 交接兜底（v1.4 增）：resolve 成功后至 bg_task 交接前的异常/取消（`log_and_print`/组装/`db.atxn` 被 `CancelledError` 中断/`create_task` 失败）→ orchestrator `finally` 归还快照，池最终归零（3.12 hunk-7~9，见 TDD-102）；
- 换代：`reset()` 后旧 scope `is_released=True` 且旧池存活（活动任务撑住）、新 scope 生效、旧任务全结束后旧池归零关闭；
- 决议：`resolve_session_client(scope, ...)` 全路径（覆盖/无覆盖/配置失败/DB 异常）guard 不泄漏；同 provider 多快照互不归还（`_from_pool` 独立 lease）；跨 provider finally 归还（含 race 用例）；
- 非法迁移：退休 scope `acquire_lease` 抛 RuntimeError、素材池归零后 acquire 抛 RuntimeError；
- registry：不含 `ai_service`/`llm_client`/`snapshot` 资源句柄字段、取消只作用于任务；
- 停机：`drain()` 超时放行、归零后 `is_released` 恒 True。

### 4.3 场景与 E2E（移植 [69] 4.3~4.5 场景表）

- 同/异 Provider 双任务 + reload、任务取消并发 reload、drain 停机等；
- 真实 reload E2E：流式任务运行中改配置 → 任务不中断 + 新请求新配置 + 旧池归零关闭（观测 `ref_count` 日志）。

### 4.4 验收基准（移植 [69] 4.7 并按 2.7 取舍校准，全部满足才允许提交）

任务零感知、旧池归零必关、**未交接快照必归还（3.12 hunk-7~9）**、**底层被外部关闭后 acquire 拦截（3.1）**、关闭失败有日志可查（按 2.7④"不做重试"，与 2.3 一致——非"可重试"）、无裸 client **反射**入口（按 2.7③ 裸参数传递为已知取舍）、无私有标记跨层摸、registry 无资源、真实 E2E 通过。

### 4.5 实施收尾审计（v1.12 新增）

实施完成后另做了一轮**真实场景审计**：不用打桩桩件，而是真改 `config.yaml`、真调 `reload_ai_config()`、真取服务、真开并发线程跑。查出两个真缺陷并修掉。

#### 4.5.1 缺陷一：换代窗口会打死正在起步的新请求

**现象**：用户在配置保存的那一刻，正好有一个新请求在"准备阶段"，这个请求直接失败，用户看到 `路由异常: ConnectionScope 已退休(换代/停机), 禁止新任务混入旧代`。

**原因**：`get_scope()` 拿到当前代之后，到真正去借连接池，中间隔着 **8 个 `await`**（落库、兜底查历史、查活跃任务、注册任务、取消检查……）。每个 `await` 都是一个让出点，别的请求可以插进来执行。只要这期间有人点了保存，这一代就被标记为"已退休"，后面借池时自然被守卫拦下——拦得对，但拦的是个无辜的新请求。

**这违背了两条设计**：2.6 写的"新请求即新代"，4.3 写的"任务不中断"。

**修法**：借池前就地看一眼这一代是否已退休，是就改取当前代重新开始。**为什么这样改是安全的**：复核和借池之间没有任何 `await`，事件循环是单线程、没有让出点，所以复核完到借池之间不可能再被换代插进来——等于没有新窗口。

**怎么证明修对了**：把守卫临时撤掉，测试立刻复现出上面那条 `router_error`；装回去，测试通过。不是"看着对"，是反向验证过的。

#### 4.5.2 缺陷二：退役代归零后一直不回收

**现象**：某一代的连接池早就归零关闭了，但它一直留在"退役表"里，相关的 scope、service、llm_sdk 对象都不释放。

**原因**：剪枝只挂在"换代"这个动作上。可要是这一代是在**最后一次换代之后**才归零的，就再没有下一次换代来触发剪枝，它就一直赖着。这跟那行代码自己写的目的（"已归零的退休代即时清出，防长驻进程列表无界增长"）是矛盾的。

**影响**：每个这样的代多占一点内存。不影响功能，但违背了自己的设计意图，长驻进程会持续累积。

**修法**：把剪枝规则收成一个函数（`_prune_retired()`），换代时过一遍，读取退役表时也过一遍。归零这个动作发生在连接归还那一侧，本模块当时不知道，但**读取的时候一定知道**——所以在读的地方补上就行。

#### 4.5.3 日志：先补齐，再删冗余

4.3 要求"观测 `ref_count` 日志"，但原来只有 `drain` 超时一条。换代这条主线上，建代、退代、换代触发**全是静默的**——出了事根本没法复盘是哪一代、当时有几个任务在用。这次补齐了整条链。

补完之后又回头审了一遍，**删掉 4 条多余的、降了 1 条级别**：

| 处理 | 日志 | 原因 |
|------|------|------|
| 删 | `ensure_pool` 的"新代建池" | 唯一调用点就是 `_attach_scope`，跟"建代"重复报同样的内容 |
| 删 | `release_owner` 的"归还 owner" | 跟 `_retire_scope` 的"退代"记的是**同一个数**（归还走异步任务，那时计数还没减） |
| 删 | `cleanup_old_instance` 的"建新代" | 跟"建代"重复，且"建代"信息更全 |
| 改 | "退役表剪枝"打印代清单 | 运维用不上，长度还不定，只报数量 |
| 降级 | "借出 lease" INFO→DEBUG | 每个请求一条，太吵；而且**不带 task_id，定位不到是谁借的**，留着也没用 |

另外修了一处**日志本身不准确**的问题：原来"换代触发"那行打的是"旧模型 → 新模型"，但热重载路径下旧模型那一侧**永远是 `<none>`**（旧值早被清空了），看着像"之前根本没模型"，纯属误导。真实的旧代身份改由 `reset_instance` 打——那是唯一能在旧值被清空前拿到它的地方。

还顺手改掉一个会**掩盖真相**的地方：3.10 的 `finally` 里归还连接池原来是直接 `await`，一旦这里抛错，会把真正的失败原因顶替掉。现在归还失败单独记 error，不影响原始异常。

#### 4.5.4 新增 13 个真实场景 case

`tests/test_e2e_p9_08_reload_scenarios.py`。特点是**被测代码一行都不打桩**：真配置文件、真热重载、真取服务、真并发。

覆盖：三代并存逐代归零、换代与新请求交叉、坏配置不得瘫痪在役代、活动连接未归还时池不许关、同代双快照互不归还、停机预算耗尽不卡死、归零后被剪枝、按模型取服务落新代、换代窗口端到端（就是 4.5.1 那个缺陷）。

**实测结论**：S1~S13 全绿；全量基线无回归；4.4 基准 8/8；真实 E2E 7 个 case 全绿。另外在跑 E2E 期间连续改 9 次配置，实测 **ERROR 为 0、借出被拒 0 次、退役表峰值 2、3 代全部归零关闭无泄漏**。

#### 4.5.5 新增不做项（2.7⑦）：同模型重复保存不换代

有人会提"保存了同一个模型也换代，白建一个池，能不能跳过"。**结论：不做。**

- 现在的行为**是安全的**：老任务照常跑完，新任务拿新池，功能没有任何破坏。
- 代价很小：人工点一次保存，多建一个池，多一次连接握手。
- **而做错的代价比收益大得多**：换代不只承载模型，还装着 `api_key`、`api_base`、`timeout`、`max_tokens` 等一整套参数。如果偷懒只比模型字符串，那么"只改了 api_key、模型没变"就会被判成"相同"而跳过换代，**新参数永远不生效**——这是把功能改坏，不是优化。
- 真要做，判据必须是"整代配置全字段相等"，等于要引入"代身份"这个新概念，还要防漏字段。违反 YAGNI 和禁止 backward。

所以维持现状。如果将来真出现"自动脚本疯狂保存配置"的场景，正确的做法是在**源头降低保存频率**，而不是在后端加一层身份比较。

#### 4.5.6 本轮自身失误（如实记录）

1. 临时探针脚本抛异常后崩在还原语句**之前**，把 `config.yaml` 的 `model_ref` 留在了不可用模型上，导致真实 E2E 一度 7 个 case 全红。已定位并修正。**根因**：`config/` 没纳入 git 跟踪，没有版本控制兜底。**教训**：改配置类文件的脚本，还原必须放 `finally`。
2. 统计日志事件时用了 PowerShell 内嵌中文正则，因为编码损坏报出假的"建代回滚 3 次"，实际是 **0 次**。**纪律**：日志统计一律走 Python 读 UTF-8，不在 PowerShell 里内嵌中文正则。

---

## 五、实施步骤与回滚

**步骤**（v1.1 改为依赖序，8 步；v1.4 审核后 3.14 并入 step5 同批、**v1.8 修正后 3.3 并入 step1 同批**落地，步数不变；每步末 `python -m py_compile <本步文件>` 自检，全步后 4.1 `compileall`）：
1. **3.1 client_sdk（+ 3.3 同批）**：`SharedClientLease`/`_SharedClientPool` 落户（含 v1.4 审核新增 `acquire` 侧 `is_closed` 检查 + close warning 池标识）+ `relinquish_ownership()` + `client` property；**同批落 3.3 `llm/__init__.py` 导出 `SharedClientLease`**（v1.8 修正：TDD-76 `from app.llm import SharedClientLease` 硬依赖包级导出，3.3 若后置到 step3 则 step1 末尾不可能全绿，违反 6.1"本步全绿才进下一步"）。**配套**：RED 先落 TDD-74~78 到 `test_tdd_74_87_scope_lease.py`；
2. **3.2 base_service**：`ensure_client_pool()`（建池+移交+返回 client）、`_shared_client` 收编、snapshot 构造接 lease、`close()` 三分支、删 `reset_sdk`（app+tests 零调用核证，YAGNI 直接删除）；**配套**：RED 先落 TDD-79~82（同文件追加）；
3. **3.3 `llm/__init__.py`**：导出 `SharedClientLease`（scope/resolver 注入与 type 提示用）——**TDD 实施时已随 step1 的 3.1 同批落地，本步为依赖序占位、不得二次落 diff**（v1.8 修正，与 6.3 step3 表述统一）；
4. **3.4 connection_scope.py**：新增（依赖 1~3 的 API；hunk import 为 `from app.llm import BaseAIService, SharedClientLease`——包级，硬依赖 3.3 先于本步）。**配套**：RED 先落 TDD-83~87（6.3 附完整代码，直接落盘）；
5. **3.5~3.9 工厂与停机 + 3.14 错位 reset**：service（`_attach_scope`/`_retire_scope`/`get_scope`/set_instance 改造）→ lifecycle.py（`shutdown()` 总预算）→ `lifecycle/__init__` → `services/__init__` → main（`shutdown_event`）→ config_helpers（删写盘前错位 `reset`，v1.4 三省改判）；**配套**：RED 先落 TDD-88~93 + M7 + M9 + M10①~③ 同批（6.4）；
6. **3.10 resolver**：`resolve_session_client(scope, ...)` 改签名 + acquire/transferred/finally；**配套**：RED 先落 TDD-94~98 + M2 + M3（step6 批 4 处）+ M4（桩签名 2 处 + L177）+ M10④ 同批（6.5）；
7. **3.11~3.13 接线**：task_registry 删 ai_service → orchestrator（`get_scope`/注册参数/resolve 传参）→ agent_runner（无条件 close）；**配套**：RED 先落 TDD-99~102 + M1（58 点/16 文件）+ M3（step7 批 2 处）+ M4（L118）+ M5 + M6 + M11 同批（6.5）；
8. **存量迁移与新增 case 收口 + 全量验收**（**v1.8 修正：迁移不集中在本步**——随 step5/6/7 各自 RED 同批落下，本步为核对与验收；旧版把全量迁移列作最后一步，按字面执行会在半改态上一次性引爆数十个错误）：
   - **分批归属铁律**（逐项明细以 6.2 表"GREEN 归属"列为准）：step5 = M7 + M9 + M10①~③；step6 = M2 + M3（4 处）+ M4（桩签名 2 处 + L177）+ M10④；step7 = M1 + M3（2 处）+ M4（L118）+ M5 + M6 + M11；新增 case = TDD-74~87 随 step1~4、TDD-88~93 随 step5、TDD-94~102 随 step6~7。**严禁**先落完 7 步生产码再一次性迁移（6.1/6.2 明文纪律）；
   - `register_task` 去第 2 位实参：**58 调用点 / 16 文件**（test_7_01:1、test_7_02:2、test_7_03:9、test_7_04:1、test_7_05:2、test_9_08:5、test_critical_flow_deep_bugs:6、test_tdd_01_02:1、test_tdd_14_20:7、test_tdd_21_25:3、test_tdd_30_32:2、test_tdd_34_40:12、test_tdd_41_46:3、test_tdd_47_51:1、test_tdd_52_58:1、test_tdd_64_73:2，逐调用点核证）：带 `session_id=` 的 31 处删位后 TypeError 响亮暴露；**裸传第 2 位的 27 处漏改会把 mock 静默绑进 session_id**，必须逐处去位（随 step7）；
   - 删 `test_tdd_14_20_inbox.py:111` 的 `["ai_service"]` 字段断言（字段消亡，3.11 已核证唯一读点；随 step7）；
   - `resolve_session_client` 直调 8 处改传 scope（test_resolve_session_client ×5、test_tdd_03_08 ×1、test_tdd_41_46 ×2）+ 测试桩补 `scope.ai_service` / `scope.acquire_lease()`（随 step6）；
   - `snapshot` 桩签名补 `client_lease=None` **并存 `self._client_lease`**（M3 升级判据需要，test_repro_v01936 L186/L225 随 step6）+ 自设 `_is_snapshot` 死属性删除 2 处（test_tdd_41_46 L177 随 step6、test_repro_v01936 L118 随 step7——L118 须与 3.13 无条件 close、M3 升级同批，提前删会使 L292/L209/246 中途红）；
   - `_is_snapshot` 断言迁移 6 处（test_resolve_session_client L76/87/127、test_tdd_03_08 L43、test_repro_v01936 L209/246）：判据升为"快照持 `_client_lease` / close 已归还"，fake 自设属性的死断言删除（4 处随 step6、2 处随 step7）；
   - **M5**（v1.8 补入，旧版漏列）：orchestrator 测试桩 `get_service` → `get_scope`（`monkeypatch.setattr(orch_mod, "get_scope", lambda: FakeScope(ai))`，FakeScope 带 `.ai_service` 与 `acquire_lease()`；随 step7）；
   - **M7**（v1.8 补入，旧版漏列）：G2 桩 `BadInst._ensure_client` → `BadInst.ensure_client_pool`（随 step5）；
   - **M8**（v1.8 补入，旧版漏列）：凡新逻辑建了真实 httpx 池的 case 补 `await snap.close()` / `await owner.close()` 收尾（防连接残留与 warning 噪声；随所属步）；
   - 基线红孤儿 4 case 修复（M10：①`owner_reset_keeps_live_snapshot_pool_open`/②`snapshot_close_before_request_is_idempotent`/③`async_close_task_is_strongly_referenced` 随 step5、④race case 并入 TDD-98 随 step6）与 `test_s2_s4_review_bugs:266` 源码断言迁移（M11，随 step7）；
   - **新增用例载体（v1.8 修正数字）**：4.2 的六个 [69] 源测试文件**合并为 3 个新测试文件**——`test_tdd_74_87_scope_lease.py`（TDD-74~87）/ `test_tdd_88_93_generation.py`（TDD-88~93）/ `test_tdd_94_102_wiring.py`（TDD-94~102），均随所属步分步追加、**不得预先写完**（旧版"移植 4.2 六个新文件"把 [69] 源数量误作目标数量）；
   - **本步验收动作**：4.1 静态（`python -m compileall -q app` + grep 清单）→ 6.7 定向序列（一次一文件，全绿才下一个）→ 6.7 全量对照（实测基线 B0 + 差异逐项解释，**不允许放宽断言换全绿**）→ 4.3 真实 E2E 九步 + 4.3 并发矩阵六行 → 4.4 验收基准逐条核对；4.3 场景用例**不新增独立 case**（按 6.6 映射增强并入对应 case，回归项以存量迁移后全绿为达成）。

**回滚**：本方案实施全部为新 commit；若翻盘（[69] 5.4 省可证伪），`git revert` 实施序列即可；摘资产三重备份（素材/patch/stash）在此之前始终保留。

> **执行细则**：逐步 RED→GREEN 循环、存量迁移配对（M1~M11）与新增 case 清单（TDD-74~102）见第六章 6.1~6.8。

---

## 六、TDD 实施步骤（详细执行篇）

> **章节定位**（小欧 2026-09-25 13:37:58）：把第三章 14 个 diff、第四章验证框架、第五章 8 步依赖序展开为可逐步执行的 **RED→GREEN 循环**。第五章保留依赖序概要与回滚（不重复），本章给执行细则。case 分三类：**存量迁移**（6.2 阶段0，按 GREEN 归属分批执行）、**新增 case**（TDD-74~102 共 29 个，续接现有 TDD-01~73 编号）、**场景回归**（6.6：[69] 4.3 十五场景 → case 映射）。断言只增强不放宽（[69] 3.10 三原则继承）。

### 6.1 执行总则

**RED→GREEN 循环定义**：

- **RED**：先落本步 case——新增 case（import 新 API，此时必 `ImportError`/`AttributeError`）+ 配对存量迁移项（对旧生产码跑必失败或报错）；跑一次确认失败原因正是"新 API 不存在/签名不符"（而非 case 自身写错），失败原因不符先修 case。
- **GREEN**：落本步 3.x diff → case 转绿 → `python -m py_compile <本步生产文件>` → 定向 `pytest` 全绿才进入下一步。**严格按第五章 8 步依赖序，不得跳步**。

**每步验证三件套**：

1. `python -m py_compile <本步生产文件>`（步末自检，五章同款）；
2. `pytest tests/<文件> -k <case名或模式> --timeout=120 -x --tb=short -v`（**v1.8 澄清**：`-k` 可为单 case 名，也可为多 case 匹配模式（如 step1 的 `-k "relinquish or three_states or shared_lease"` 一次覆盖 TDD-74~78）——判据是**本步 case 全绿**，不是"只跑一个"）；
3. 阶段末整文件：`pytest tests/<文件> --timeout=120 -x --tb=short -v` 全绿；
4. **真实池收尾自检（v1.8 新增，M8 闭环）**：本步凡新建真实 httpx 池的 case，末尾须有 `await snap.close()` / `await owner.close()` / `await scope.drain(...)` 之一收尾——否则进程残留连接与 warning 噪声会掩盖真实失败信号。

**新增测试文件**（3 个，**分步长大**：每步只追加本步 case，不提前写后续阶段代码）：

| 文件 | 阶段 | case 范围 | 对应 diff |
|------|------|----------|-----------|
| `backend/tests/test_tdd_74_87_scope_lease.py` | 阶段1（step1~4） | TDD-74~87（14 个） | 3.1 / 3.2 / 3.3 / 3.4 |
| `backend/tests/test_tdd_88_93_generation.py` | 阶段2（step5） | TDD-88~93（6 个） | 3.5 / 3.6 / 3.7 / 3.8 / 3.9 / 3.14 |
| `backend/tests/test_tdd_94_102_wiring.py` | 阶段3（step6~7） | TDD-94~102（9 个） | 3.10 / 3.11 / 3.12 / 3.13 |

**阶段总览**：

| 阶段 | 内容 | 五章步骤 | case |
|------|------|---------|------|
| 0 | **非独立阶段**：存量迁移清单（6.2），按"GREEN 归属"列**分批随 step5/6/7 落下**（v1.8 改判：旧称"阶段0"易被误读为"先做迁移"，实为随阶段1~3 分批执行） | 配套 step5/6/7 | M1~M11 |
| 1 | lease 核心 + ConnectionScope | step1~4 | TDD-74~87 |
| 2 | 工厂收口 / 换代 / 停机 / 错位 reset | step5 | TDD-88~93 |
| 3 | 决议与接线 | step6~7 | TDD-94~102 |
| 4 | 场景回归映射（[69] 4.3 十五场景） | 各步收尾 | 存量改造 + 增强断言 |
| 5 | 全量验收 | 全步后 | 无新增 |

### 6.2 存量迁移清单（**非独立阶段**：随 step5/6/7 分批执行）

> 迁移**不一次性做完**——每项标注 GREEN 归属，与该步 RED 同批落下，否则中间态大面积报错。红性分类：**红迁移** = 改完对旧码必失败（即该步 RED 信号）；**非红迁移** = 随同批落下，GREEN 后语义才成立。

| # | 迁移项 | 量（逐点核证） | GREEN 前表现 | 性质 | GREEN 归属 |
|---|--------|---------------|--------------|------|-----------|
| M1 | `register_task(task_id, svc[, session_id=...])` → `register_task(task_id[, session_id=...])`，删第 2 位实参 | **58 点/16 文件**：test_7_01:1、test_7_02:2、test_7_03:9、test_7_04:1、test_7_05:2、test_9_08:5、test_critical_flow_deep_bugs:6、test_tdd_01_02:1、test_tdd_14_20:7、test_tdd_21_25:3、test_tdd_30_32:2、test_tdd_34_40:12、test_tdd_41_46:3、test_tdd_47_51:1、test_tdd_52_58:1、test_tdd_64_73:2 | 31 处带 `session_id=` 关键字 → `TypeError: multiple values for 'session_id'`（响亮）；**27 处裸传第 2 位 → 静默把 mock 绑进 session_id（不报错！必须逐处去位）** | 红迁移 | step7（3.11） |
| M2 | `resolve_session_client(ai, sid)` 直调改传 `scope`（测试内构造 scope 桩或 `ConnectionScope(ai)` + `ensure_pool()`）。**v1.7 补**：race case（test_resolve_session_client L132-158）不止换参——整体随 TDD-98 重写（M10④），含 `await owner.close()` → `scope.release_owner()` 语义换（[70] owner 引用在 scope 不在实例，原句在新语义下为 no-op 且 L158 归零关断言必失） | **8 处/3 文件**：test_resolve_session_client ×5、test_tdd_03_08 ×1、test_tdd_41_46 ×2 | 旧码把 scope 当 ai_service 用 → `AttributeError: llm_model` | 红迁移 | step6（3.10） |
| M3 | `_is_snapshot` 断言 6 处升级为等价或更强判据（`snap is not ai` / 快照持 `_client_lease` / close 已归还） | test_resolve_session_client L76/87/127、test_tdd_03_08 L43（**step6 批**）；test_repro_v01936 L209/246（**step7 批**，随 M5 桩） | 真实快照路径 → 属性消亡 `AttributeError`；fake 自设属性 → 恒真死断言（删除） | 非红迁移 | step6 / step7 |
| M4 | snapshot 桩签名补 `client_lease=None` 并存 `self._client_lease = client_lease`（3.10 新传参，漏补即 `TypeError`；存属性供 M3 升级判据断言）；`_FakeClient`/`MockSnapshot` 自设 `_is_snapshot` 死属性删除。**v1.7 拆批**：test_repro_v01936 桩签名 2 处（L186/L225）+ test_tdd_41_46 L177 → step6（后者无读点安全）；**test_repro_v01936 L118 移 step7**——须与 3.13 无条件 close、M3 升级同批，step6 删会使 L292（runner 关闭靠 `_is_snapshot` 触发）与 L209/246 中途红 | 桩签名 2 处 + 死属性 2 文件 | 桩签名缺 `client_lease` → `TypeError`；L118 提前删 → L292/L209/246 中途红（3.13/M3 未落） | 红迁移（L118 为非红，随 step7 批） | step6（3.10）/ L118 step7 |
| M5 | orchestrator 测试桩 `get_service` → `get_scope`：`monkeypatch.setattr(orch_mod, "get_scope", lambda: FakeScope(ai))`（FakeScope 带 `.ai_service` 与 `acquire_lease()`） | test_repro_v01936（_bug05_patch）等 orchestrator 桩 | 桩未接住新门面 → 真实工厂被调 / `AttributeError` | 随批落地 | step7（3.12） |
| M6 | 删 `test_tdd_14_20_inbox.py:111` 的 `["ai_service"]` 字段断言（全仓唯一读点） | 1 处 | 字段删除后 `KeyError` | 随批落地 | step7（3.11） |
| M7 | G2 桩 `BadInst._ensure_client` → `BadInst.ensure_client_pool`（工厂路径改走 `_attach_scope → ConnectionScope.ensure_pool → ensure_client_pool`；`assert svc._instance is None` 断言不变——cleanup 已在锁内清位。**v1.7 纠正 v1.5 补记**：失败时 `_instance`/`_scope` 皆 None（与 HEAD 等价），改进是旧代池归还不被连坐关闭、锁外不见半初始化，**非**"旧代保留继续服务"，见 3.5 说明区） | test_tdd_64_73 G2 一处 | 旧工厂调 `_ensure_client` → 桩接不住，回滚核证漂移 | 红迁移 | step5（3.5） |
| M8 | 收尾 close 补齐：凡新逻辑建了真实 httpx 池的 case 补 `await snap.close()` / `await owner.close()` / `await scope.drain(...)` 收尾（防进程残留未关连接与 warning 噪声） | 随各文件 | （非红项） | 非红迁移 | **v1.8 落到具体步**：step4（TDD-83~87 真实池 case 收尾）+ step5（M10②③ `drain` 收尾）+ 6.1 三件套第 4 条为每步统一自检 |
| M9 | 3.14 删错位 `reset()` 的回归面：`test_model_ref_normalization.py`（其 `:96` monkeypatch 因导入时绑定而失效，删除后断言转真绿）、`test_settings_editsave_red.py`（S10 两 case 直接调 `_update_model_ref`） | 2 文件 | 无需改测试（3.14 反而修正其假绿/污染）；RED 不适用 | 非红迁移（回归验证） | step5（3.14） |
| M10 | **基线红孤儿 4 case**（6 文件撤销时 tests 未随回退的 lease 时代遗留，HEAD 即红，非实施引入）：①test_tdd_03_08 `owner_reset_keeps_live_snapshot_pool_open`：`owner.acquire_shared_lease()`→`ConnectionScope(owner)+ensure_pool()+acquire_lease()`、`snapshot(shared_client=lease)`→`snapshot(shared_client=lease.client, client_lease=lease)`、**补 monkeypatch `service_mod._scope`**（否则 reset→`_retire_scope` 落空、L136 归零关断言必失——同 TDD-89 先例）；②同文件 `snapshot_close_before_request_is_idempotent`：同款构造换法，`finally` 补 `scope.release_owner()` + `await scope.drain(timeout=2)` 收尾（[70] 下 `owner.close()` 为 no-op，不归还 owner 引用则 L159 `is_closed=True` 必失；release_owner 走 create_task，断言前必须 drain——6.3 注同款纪律）；③同文件 `async_close_task_is_strongly_referenced`：断言对象 `lifecycle._close_tasks`（lease 时代）已消亡→改写为 `connection_scope._pending_release_tasks` 强引用断言（release_owner 后任务保活、gather 后关闭完成），`close_instance_sync` 直调段仅保留"完成关闭"功能断言（其强引用保活为 HEAD 既有行为，如实界定不在 [70] 范围）；④test_resolve_session_client race case（L132-158）并入 TDD-98 整体重写（直调点已计 M2，不重复计数） | 4 case/3 文件 | **基线即红**（v1.7 定向实测 12 文件 349 case = 4 failed/345 passed，4 failed 全部为本行 4 case） | 存量欠账迁移 | ①②③ step5（3.4/3.5）、④ step6（TDD-98） |
| M11 | `test_s2_s4_review_bugs.py:266` 源码断言迁移：`assert "get_service()" in src` → `assert "get_scope()" in src` 并增强 `assert "get_service()" not in src`（3.12 hunk-3 换门面后旧断言必红；orchestrator 中 `get_service` 仅 import+L296 调用，替换后零残留——反向断言防回潮） | 1 处 | 3.12 落地前新断言 `get_scope() in src` 对旧码必失败 = 该步 RED 信号 | 红迁移 | step7（3.12） |

### 6.3 阶段1（step 1~4）：lease 核心与 ConnectionScope

**step 1 — RED（追加 case 到 `test_tdd_74_87_scope_lease.py`；GREEN = 3.1 + 3.3 diff）**

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-74 | `test_relinquish_ownership_noop_close` | `relinquish_ownership()` 后 `await sdk.close()` 为 no-op（底层池 `is_closed=False`）、`client` property 即底层池、二次 relinquish 幂等 |
| TDD-75 | `test_llmclient_close_three_states` | 独占池 `close()` 真关（`is_closed=True`）；relinquish 后 `close()` no-op；已关闭池再 `close()` 不抛（`is_closed` 双保险） |
| TDD-76 | `test_shared_lease_lifecycle` | `from app.llm import SharedClientLease` 导入成功（3.3）；构造 ref=1 → `acquire()` ref=2 → `release()` ref=1 池活；最后 `release()` 归零 `aclose`；二次 `release()` 幂等（ref 不再减、不重关）。**v1.8 回填 6.6 场景10 增强**：patch 底层 `client.aclose` 抛错 → `release()` **不抛**（3.1 hunk-2 `close` 的 try/except 捕获）+ logger 留 warning（见 6.3 末"增强段"代码①） |
| TDD-77 | `test_shared_lease_concurrent_release_once` | `asyncio.gather(*(lease.release() for _ in range(8)))` 只减一次、池只关一次、无异常（[69] 4.3 场景1） |
| TDD-78 | `test_shared_lease_double_defense_raises` | 已释放 lease `.acquire()` 抛 `RuntimeError`；池归零 `_closing` 后 `pool.acquire()` 抛 `RuntimeError`（素材防线）；**v1.4 增：底层 client 被池外 `aclose()` 后 `pool.acquire()` 抛 `RuntimeError`**（3.1 新增 `is_closed` 检查，偿还 [69] 1.2.3⑥） |

**GREEN**：3.1（hunk-1 imports / hunk-2 `_SharedClientPool`+`SharedClientLease`，含 v1.4 审核新增 `acquire` 侧 `is_closed` 拦截 + close warning 池标识 / hunk-3 `relinquish_ownership`+`client` property+`close` 三态）、3.3（导出 `SharedClientLease`）。
**验证**：`python -m py_compile app/llm/client_sdk.py app/llm/__init__.py`；`pytest tests/test_tdd_74_87_scope_lease.py -k "relinquish or three_states or shared_lease" --timeout=120 -x --tb=short -v`

**step 2 — RED（追加 case；GREEN = 3.2 diff）**

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-79 | `test_ensure_client_pool_relinquishes` | `ensure_client_pool()` 返回底层 client、此后单例 `close()` no-op（池活）、幂等（二次调用同池不重建、ref 不变） |
| TDD-80 | `test_base_close_three_branches` | 共享 lease 快照 `close()` → lease 归还（`is_released=True`）池未关；独占快照 `close()` → 真关；单例（已 relinquish）`close()` → no-op；快照二次 `close()` 不抛（摘引用 + release 幂等双保险） |
| TDD-81 | `test_snapshot_pairs_client_lease` | `snapshot(client_lease=L)` → `snap._client_lease is L` 且共享池地址成对（`snap._shared_client is L.client`）；不传 → 均 None |
| TDD-82 | `test_reset_sdk_removed` | `assert not hasattr(BaseAIService, "reset_sdk")`（零调用删除的存在性核证，等价断言不放宽） |

**GREEN**：3.2 hunk-1~9。
**验证**：`python -m py_compile app/llm/base_service.py`；`pytest tests/test_tdd_74_87_scope_lease.py -k "ensure_client_pool or three_branches or pairs or reset_sdk" --timeout=120 -x --tb=short -v`

**step 3 —** 无独立新 case、**无独立 diff**（v1.8 修正）：3.3 导出**已随 step1 GREEN 与 3.1 同批落地**——TDD-76 `from app.llm import SharedClientLease` 在 step1 即硬依赖包级导出，3.3 若后置到本步，则 step1 末尾整文件不可能全绿（违反 6.1"本步全绿才进下一步"），原文"落 3.3 diff 后复跑 TDD-76"与 step1 GREEN 重复矛盾已废；本步仅复跑 TDD-76 确认导入转绿即视为通过（依赖序上 3.3 仍列于 3.2 与 3.4 之间，见五章 step3 占位说明）。

**step 4 — RED（追加 case；GREEN = 3.4 新文件 connection_scope.py）**

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-83 | `test_scope_ensure_pool_idempotent_refcount_start` | 【代码①】ensure_pool 幂等、owner 计数起点=1、relinquish 后单例 close 不关池、无借用归还即归零关 |
| TDD-84 | `test_scope_acquire_release_close_on_zero` | 【代码②】acquire ref+1、快照成对接管 lease、快照 close 归还 ref-1、owner 归还后归零自动 `aclose`、`is_released=True`。**v1.8 回填 6.6 场景2 增强**：两快照（两 lease 同一池）`asyncio.gather` 并发 close，**最后一个归还才归零关闭**，先归零一侧不得关池（见 6.3 末"增强段"代码②） |
| TDD-85 | `test_scope_acquire_rejects_uninit_and_retired` | 【代码③】未初始化/已退休 scope `acquire_lease()` 抛 `RuntimeError`（防混代，双重防线）、无借用退休代归零即关 |
| TDD-86 | `test_scope_release_owner_idempotent` | 【代码④】`release_owner()` 幂等（二次调用 ref 不再减）、`is_released=True`、活动借用撑池不关 |
| TDD-87 | `test_scope_drain_timeout_and_settle` | 【代码⑤】活动借用未归还时 `drain(timeout=0.3)` 超时放行且**不强关**（任务零感知）；归还后 `drain(timeout=2)` 等到归零关闭 |

**GREEN**：3.4 全新文件落盘（connection_scope.py——校验器 SKIPPED 的那个块）。
**验证**：`python -m py_compile app/services/lifecycle/connection_scope.py`；`pytest tests/test_tdd_74_87_scope_lease.py --timeout=120 -x --tb=short -v`（整文件 14 case 全绿）

**关键 case 完整代码**（TDD-83~87，基于 3.4/3.1 真实 API；含文件头与共享 fixture，直接落 `test_tdd_74_87_scope_lease.py` 的 scope 段；step1/2 的 TDD-74~82 同文件在前序步先建）：

```python
# TDD-83~87: [70] ConnectionScope 建池/计数/换代/停机核心 — 小欧 2026-09-25
import asyncio
import pytest
from app.db.models.chat_models import ModelRef


@pytest.fixture
def owner_service():
    """真实构造(零网络): BaseAIService.__init__ 仅建字段, 池由 ensure_pool 惰性建"""
    from app.llm.base_service import BaseAIService
    return BaseAIService(api_key="test-key",
                         llm_model=ModelRef(provider="openai", model="gpt-4"))


async def _settle_owner_release() -> None:
    """[70] v1.10 增: 等 release_owner() 的释放协程真正跑完 — 小欧 2026-09-25
    必需: release_owner() 把 lease.release() 放进 create_task(3.4 hunk), ref 计数在协程跑完前不变,
    故任何"release_owner() 之后立即断言 ref_count"的写法必红(实施 step4 实测暴露)。经 3.4 强引用表
    _pending_release_tasks 确定性 gather 等待, 不用 sleep 押注时序。"""
    from app.services.lifecycle import connection_scope as scope_mod
    pending = list(scope_mod._pending_release_tasks)
    if pending:
        await asyncio.gather(*pending)


@pytest.mark.asyncio
async def test_scope_ensure_pool_idempotent_refcount_start(owner_service):
    """TDD-83: ensure_pool 幂等, owner 计数起点=1 — [70] 2.4 — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    scope = ConnectionScope(owner_service)
    assert scope.ref_count == 0, "池未建时 ref_count=0"
    scope.ensure_pool()
    assert scope.ref_count == 1, "owner 计数起点=1"
    first_client = owner_service._llm_sdk.client
    scope.ensure_pool()  # 幂等: 不重建不加计数
    assert scope.ref_count == 1, "重复 ensure_pool 不得重复加计数"
    assert owner_service._llm_sdk.client is first_client, "重复 ensure_pool 不得重建池"
    await owner_service.close()  # relinquish 后单例 close 必须 no-op
    assert first_client.is_closed is False, "所有权已移交, 单例 close 不得关共享池"
    scope.release_owner()
    await scope.drain(timeout=2)
    assert first_client.is_closed is True, "owner 归还且无借用时池必须归零关闭"


@pytest.mark.asyncio
async def test_scope_acquire_release_close_on_zero(owner_service):
    """TDD-84: acquire ref+1 / 快照 close 归还 ref-1 / 归零自动 aclose — [70] 2.4 — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    scope = ConnectionScope(owner_service)
    scope.ensure_pool()
    pool = owner_service._llm_sdk.client

    lease = scope.acquire_lease()
    assert scope.ref_count == 2, "owner(1) + 借用(1) = 2"
    snap = owner_service.snapshot(shared_client=lease.client, client_lease=lease)
    assert snap._client_lease is lease, "快照必须成对接管 lease"

    await snap.close()  # 快照 close 直线归还 lease([70] 2.4 不经 scope 中介)
    assert scope.ref_count == 1, "快照归还后只剩 owner 引用"
    assert pool.is_closed is False, "owner 撑池不关"

    scope.release_owner()
    await scope.drain(timeout=2)
    assert pool.is_closed is True, "最后一个引用归零必须自动 aclose"
    assert scope.is_released is True, "release_owner 后进入退休态"


@pytest.mark.asyncio
async def test_scope_acquire_rejects_uninit_and_retired(owner_service):
    """TDD-85: 未初始化/已退休 scope 禁止借用(防混代) — [70] 2.3 双重防线 — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    # ① 未初始化(池未建): 拒绝借用
    fresh = ConnectionScope(owner_service)
    with pytest.raises(RuntimeError, match="未初始化"):
        fresh.acquire_lease()

    # ② 已退休(owner 已归还): 拒绝新任务混入旧代
    scope = ConnectionScope(owner_service)
    scope.ensure_pool()
    pool = owner_service._llm_sdk.client
    scope.release_owner()
    assert scope.is_released is True
    with pytest.raises(RuntimeError, match="退休"):
        scope.acquire_lease()
    await scope.drain(timeout=2)
    assert pool.is_closed is True, "无借用的退休代归零即关"


@pytest.mark.asyncio
async def test_scope_release_owner_idempotent(owner_service):
    """TDD-86: release_owner 幂等(二次归还不减计数不重关) — [70] 2.2 — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    scope = ConnectionScope(owner_service)
    scope.ensure_pool()
    pool = owner_service._llm_sdk.client
    lease = scope.acquire_lease()  # ref=2, 归还 owner 后仍有 1 撑池

    scope.release_owner()
    scope.release_owner()  # 二次归还必须无害(幂等)
    assert scope.is_released is True
    await _settle_owner_release()   # [70] v1.10 修: 释放协程跑完, ref 2→1(原直接断言 ref_count 必红)
    assert scope.ref_count == 1, "owner 只归还一次, 借用仍撑池"
    assert pool.is_closed is False, "活动借用期间池不得关闭"

    await lease.release()
    await scope.drain(timeout=2)
    assert pool.is_closed is True


@pytest.mark.asyncio
async def test_scope_drain_timeout_and_settle(owner_service):
    """TDD-87: drain 正常等归零收尾; 活动任务未结束超时放行不强关 — [70] 2.3 — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    scope = ConnectionScope(owner_service)
    scope.ensure_pool()
    pool = owner_service._llm_sdk.client
    lease = scope.acquire_lease()
    scope.release_owner()

    # 活动借用未归还: 超时放行, 绝不强关([70] 任务零感知)
    await scope.drain(timeout=0.3)
    assert pool.is_closed is False, "有活动 lease 时 drain 超时必须放行且不得强关"

    await lease.release()
    await scope.drain(timeout=2)
    assert pool.is_closed is True, "活动 lease 归还后归零关闭"
```

**6.6 增强段代码**（v1.8 补：6.6 场景2/场景10 的增强断言原只写在 6.6 映射表，6.3 的 case 规格与完整代码块均无——照 6.3 落盘会漏做；以下两段**追加到 `test_tdd_74_87_scope_lease.py` 末尾**，复用同文件已导入的 `asyncio`/`pytest` 与 `owner_service` fixture）：

```python
# 6.6 增强段①: 池外关闭失败可查不炸流程 — [69] 4.3 场景10 — 小欧 2026-09-25
@pytest.mark.asyncio
async def test_shared_lease_close_failure_warns(monkeypatch):
    """TDD-76 增强: aclose 抛错 → release 不抛 + warning 留痕(2.7④ 不做重试, 只可查) — 小欧 2026-09-25"""
    import httpx
    from app.llm import client_sdk
    from app.llm import SharedClientLease

    warns = []
    monkeypatch.setattr(client_sdk.logger, "warning", lambda msg: warns.append(str(msg)))

    async def _boom():
        raise RuntimeError("aclose 模拟失败")

    client = httpx.AsyncClient()
    monkeypatch.setattr(client, "aclose", _boom)
    lease = SharedClientLease(client)
    await lease.release()
    assert any("关闭失败" in msg for msg in warns), "池关闭失败必须留 warning 可查"
    assert lease.is_released is True, "关闭失败不影响归还状态(引用已减, 幂等成立)"


# 6.6 增强段②: 多 snapshot 并发关闭, 最后一个归还才关池 — [69] 4.3 场景2 — 小欧 2026-09-25
@pytest.mark.asyncio
async def test_scope_two_snapshots_close_on_last(owner_service):
    """TDD-84 增强: 两快照并发 close, 最后一个归还才归零 aclose — 小欧 2026-09-25"""
    from app.services.lifecycle.connection_scope import ConnectionScope

    scope = ConnectionScope(owner_service)
    scope.ensure_pool()
    pool = owner_service._llm_sdk.client

    lease_a = scope.acquire_lease()
    lease_b = scope.acquire_lease()
    snap_a = owner_service.snapshot(shared_client=lease_a.client, client_lease=lease_a)
    snap_b = owner_service.snapshot(shared_client=lease_b.client, client_lease=lease_b)
    assert scope.ref_count == 3, "owner(1) + 两借用(2) = 3"

    scope.release_owner()
    await _settle_owner_release()   # [70] v1.10 修: 释放协程跑完, ref 3→2(原直接断言 ref_count 必红)
    assert scope.ref_count == 2, "owner 归还后剩两借用撑池"
    assert pool.is_closed is False

    await asyncio.gather(snap_a.close(), snap_b.close())
    assert scope.ref_count == 0, "两借用并发归还后归零"
    await scope.drain(timeout=2)
    assert pool.is_closed is True, "最后一个归还者负责归零 aclose"
```

> 注：TDD-83~87 在事件循环内调 `release_owner()` 走 3.4 的 `create_task` 分支（强引用 `_pending_release_tasks` 防 GC 取消），`drain()` 的 0.1s 轮询即给该 task 调度机会——断言前一律经 `await scope.drain(...)` 收尾，不裸 `sleep(0)` 押注时序。**v1.10 实施补正**：若要在 `release_owner()` 之后**立即**断言 `ref_count`（不等 drain 归零），必须先 `await _settle_owner_release()`——`create_task` 是异步调度，ref 计数在协程真正跑完前不变，直接断言必红（TDD-86 与 6.6 增强段② 原写法即此病灶，step4 实测 2 failed 暴露）。

### 6.4 阶段2（step 5）：工厂收口与换代、停机

**RED**：追加 TDD-88~93 到 `test_tdd_88_93_generation.py` + M7（G2 桩迁移）+ M10①②③（基线红孤儿 3 case 迁移，随本步 API 转绿——本步 RED 信号仍以新 case `ImportError` 为准）+ M9（**非红**，3.14 回归面，仅随批核对不产生 RED，见验证段点名两文件）同批落下；`from app.services import get_scope` 此时 `ImportError`（3.8 才导出）= RED 信号。

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-88 | `test_get_service_attaches_scope_invariant` | 参照 G2 的 monkeypatch 方式（patch `get_resolver_and_config`/`create_service_instance` 等，桩实例带 `ensure_client_pool()`）：`get_service()` 成功后**不变式成立**——`svc._instance is not None ⟹ svc._scope is not None`、`get_scope().ai_service is svc._instance`、`get_scope().ref_count >= 1`；`get_service_for_model` 同断言（3.5 hunk-9 直赋点补挂载）。**v1.7 修（取代 v1.5 增）**：建池失败路径断言——`_instance is None` ∧ `_scope is None`（cleanup 先清位+退休、新代均未落位，与 HEAD 失败结果等价；`get_service` 路径另断 `_current_model_ref is None`，`get_service_for_model` 路径 cleanup 残留 model_ref 与 HEAD 等价且 `check_cache_valid` 受 `_instance is not None` 拦截）、失败实例不被缓存（解桩后重调 `get_service()` 可重建新代）、旧代已入 `get_retired_scopes()` 且 `is_released=True`（owner 已归还、活动 lease 撑池——比 HEAD `close_instance_sync` 真关旧池更安全）。BUG-06"半初始化不缓存"等价断言成立；**不作**"旧代保留继续服务"类断言（源码反证不存在该状态） |
| TDD-89 | `test_reset_generation_keeps_live_pool` | [70] 2.6 换代模型：monkeypatch `_instance`/`_scope` 为持活动快照的真 scope → `lifecycle.reset()` → 旧 `scope.is_released=True` 且旧池 `is_closed=False`（活动 lease 撑住）、`_scope is None`（待惰性重建）；活动快照照常可用；释放活动 lease → `drain` 后旧池归零关 |
| TDD-90 | `test_reset_closes_idle_old_pool` | 无活动借用时 `reset()` → 旧池归零自动关（`drain(timeout=2)` 确认），不残留连接 |
| TDD-91 | `test_set_instance_cleanup_invariant_and_lazy_scope` | `set_instance(None)` / `cleanup_old_instance` 后 `_instance is None`、旧 scope 入退休表（`get_retired_scopes()` 含之）、`get_scope()` 惰性重建新代（`_scope is not None` 且 `is_released=False`）——"先清位再 retire"顺序核证（3.5 hunk-5/8） |
| TDD-92 | `test_retired_scopes_pruned_on_zero` | 退休代归零后被剪出 `_retired_scopes`（防无界增长）；ref>0 的在役退休代保留（3.5 hunk-4 剪枝语义） |
| TDD-93 | `test_shutdown_drains_retired_scopes` | `await shutdown(timeout=...)`（3.6）= `reset()` 换代归还 + 逐退休代 `drain`：无活动任务时调用后各池 `is_closed=True`；持活动任务时超时 warning 放行、不阻塞退出（3.9 main 改 `await shutdown()` 的收口语义）。**v1.5 增**：多退休代预算耗尽分支——前代 drain 耗尽总预算时 `remaining<=0` 即 warning + `break`（不再逐代各等 30s，总时长有界），断言 `shutdown` 返回且 warning 留痕 |

**GREEN**：step5 整步 = 3.5（工厂收口）+ 3.6（`shutdown` 总预算）+ 3.7（lifecycle 导出）+ 3.8（services 导出）+ 3.9（main 接线）+ **3.14（删写盘前错位 `reset`）** 按依赖序同批落地。
**验证**：`python -m py_compile app/services/lifecycle/service.py app/services/lifecycle/lifecycle.py app/services/lifecycle/__init__.py app/services/__init__.py app/main.py app/services/model/config_helpers.py`；`pytest tests/test_tdd_88_93_generation.py --timeout=120 -x --tb=short -v`；复跑 `pytest tests/test_tdd_64_73_bug_guard.py -k g2 --timeout=120 -x --tb=short -v`（M7 转绿）、`pytest tests/test_tdd_03_08_snapshot.py --timeout=120 -x --tb=short -v`（M10①②③ 转绿——基线红 4 case 中的 3 个）；**3.14 验证**：静态核 `config_helpers.py` 仅 `reload_ai_config():147` 一处 `reset()`（`_update_model_ref` 内已删），并**点名复跑 M9 两个回归文件**（v1.8 补闭环：原文只写"配置保存相关存量测试"未点名，照做会漏跑）——`pytest tests/test_model_ref_normalization.py --timeout=120 -x --tb=short -v`、`pytest tests/test_settings_editsave_red.py --timeout=120 -x --tb=short -v`；再跑真实 E2E"保存模型 → 新请求用新模型生效"（2.7⑤ 可证伪项）。

### 6.5 阶段3（step 6~7）：决议与接线

**step 6 — RED**：追加 TDD-94~98 到 `test_tdd_94_102_wiring.py` + 同批 M2（直调 8 处）、M10④（race 孤儿随 TDD-98 整体重写）、M3 step6 部分（4 处断言）、M4（snapshot 桩签名 + L177 死属性）。

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-94 | `test_resolve_acquires_on_entry_rejects_retired` | 退休 scope 调 `resolve_session_client(scope, sid)` → `RuntimeError` 原样上抛（进门 `acquire_lease()` 在 try 外，不建任务不吞异常——3.10 hunk-3） |
| TDD-95 | `test_resolve_empty_session_returns_snapshot` | `resolve_session_client(scope, "")` **恒非 None**（旧码空会话返回 None——语义反转，RED 信号即旧返回值）；走无覆盖分支派生默认快照 |
| TDD-96 | `test_resolve_cross_provider_releases_in_finally` | 跨 provider 路径（覆盖查配置走独占新池）返回后 `scope.ref_count` 回基线（lease 已在 finally 归还）、独占池归快照自身（3.10 hunk-5 `transferred` 语义） |
| TDD-97 | `test_resolve_snapshot_failure_releases` | `snapshot()` 构造抛错 → 异常如实上抛且 `scope.ref_count` 回基线（finally 归还，无 ref 悬挂——hunk-6） |
| TDD-98 | `test_resolve_regeneration_race_keeps_pool` | 改造存量 race case（M2 同文件）：`db.atxn` await 期间 `lifecycle.reset()` 换代 → 快照仍返回、旧池 `is_closed=False`（旧 scope lease 撑住）→ 快照 close 后归零关（[69] 4.3 场景3/4 合并） |

**GREEN**：step6 = 3.10（resolver 改签名 `(scope, session_id)` + 进门 acquire + transferred + finally 归还）。
**验证**：`python -m py_compile app/services/model/resolver.py`；`pytest tests/test_tdd_94_102_wiring.py -k "resolve" --timeout=120 -x --tb=short -v`；复跑存量 `pytest tests/test_resolve_session_client.py --timeout=120 -x --tb=short -v`（M2/M3 转绿）、`pytest tests/test_tdd_03_08_snapshot.py --timeout=120 -x --tb=short -v`、`pytest tests/test_tdd_41_46_bug_c_red.py --timeout=120 -x --tb=short -v`（M4 的 L177 死属性）、**`pytest tests/test_repro_v01936.py --timeout=120 -x --tb=short -v`（v1.8 补：M4 step6 批含其 L186/L225 桩签名——3.10 新传 `client_lease` 漏补即 `TypeError`，原验证清单漏此文件，桩未补则本步存量面留红）**

**step 7 — RED**：追加 TDD-99~102 + 同批 M1（58 调用点）、M5（orchestrator 桩）、M3 step7 部分（repro 2 处）+ M4 的 repro L118 死属性删除（与 M3 升级、3.13 同批）、M6（字段断言）、M11（s2_s4 源码断言）。

| 编号 | case（新增） | 断言要点 |
|------|-------------|----------|
| TDD-99 | `test_registry_stores_no_resource_fields` | `register_task(task_id, session_id=...)` 两参可用（旧 `ai_service` 参数消亡——`inspect.signature` 无之）；任务 dict **无** `ai_service`/`llm_client`/`snapshot` 资源键；`_inbox`/`created_at`/状态等身份字段照常（3.11） |
| TDD-100 | `test_orchestrator_scope_wiring` | monkeypatch `get_scope` → FakeScope（带 `.ai_service` 与 `acquire_lease()`）：编排② `ai_service = scope.ai_service` 生效（同代单例）；`resolve_session_client` 收到的第 1 参是 scope（spy 断言）；两处 `register_task` 均两参（spy）；resolve 返回快照直接赋 `agent.llm_client`（无 None 死分支——3.12 hunk-6） |
| TDD-101 | `test_runner_close_unconditional` | `run_agent_in_background` finally 对 `agent.llm_client.close()` **无条件**调用（mock 计数+1，无论对象带何种标记——`_is_snapshot` 死判据核证）；resolve 抛错时 runner 不执行（连接顺序 resolve(388) < bg_task(489) < finally，无裸单例入口）；close 抛错被 except 捕获记 warning 不打断终态（3.13） |
| TDD-102 | `test_orchestrator_finally_releases_unhanded_snapshot` | **v1.4 重写（对齐 [70] 实际执行顺序）**：真实窗口是 resolve 成功后至 bg_task 交接前——① `log_and_print`/组装段异常；② `await db.atxn`（`_setup_task_db`）被 `CancelledError` 中断（穿透 `except Exception`，落 `except asyncio.CancelledError: return`）；③ `asyncio.create_task` 失败。三条路径 → orchestrator `finally` 单点归还（3.12 hunk-7~9），`scope.ref_count` 回基线、池最终归零关。**v1.4 十遍复核增**：④ 归还时 `close()` 抛错（如独占池 `aclose` 失败）→ 记 warning、**不覆盖原始异常**、**不挡 `_current_task_id.reset()`**（hunk-9 try/except 分支，与 3.13 runner 同款）。**注**：`register_task` 占位失败与 `UniversalAgent` 构造失败在 HEAD 顺序下（均在 resolve 之前）**不产生快照**，无 lease 可泄漏（见 3.12 边界核证），不作为本 case 场景 |

**GREEN**：step7 = 3.11（registry 删参删字段）+ 3.12（orchestrator 接线）+ 3.13（runner 无条件 close）。
**验证**：`python -m py_compile app/services/task/task_registry.py app/services/chat/stream_orchestrator.py app/services/agent/agent_runner.py`；`pytest tests/test_tdd_94_102_wiring.py --timeout=120 -x --tb=short -v`（整文件 9 case 全绿）；复跑存量 `pytest tests/test_tdd_14_20_inbox.py --timeout=120 -x --tb=short -v`、`pytest tests/test_repro_v01936.py --timeout=120 -x --tb=short -v`、`pytest tests/test_s2_s4_review_bugs.py --timeout=120 -x --tb=short -v`（M11 转绿）；M1 的 16 文件逐个跑（见 6.7 定向序列）

### 6.6 阶段4：场景回归映射（[69] 4.3 十五场景 → 本方案 case）

| [69] 场景 | 本方案归属 | 动作 |
|-----------|-----------|------|
| 1 同一 lease 并发 release 只减一次 | TDD-77 | 新增 |
| 2 多 snapshot 并发关闭，最后一个才关 client | TDD-84 增强断言（两快照 `asyncio.gather` close，最后一个归还才归零关） | 增强 |
| 3 owner reset 后活动 snapshot 仍能执行 | TDD-89 | 新增 |
| 4 db await 期间 owner 被关，lease 仍保护池 | TDD-98 | 新增 |
| 5 resolver 创建 snapshot 失败，lease 自动释放 | TDD-97 | 新增 |
| 6 `register_task()` 同会话占位，快照自动释放 | **v1.4 修正**：本方案顺序下该路径在 resolve 之前失败，**无快照产生**（无需释放，见 3.12 边界核证） | 不适用（已消亡场景） |
| 7 `UniversalAgent` 构造失败，快照自动释放 | **v1.4 修正**：同上，构造在 resolve 之前，**无快照产生** | 不适用（已消亡场景） |
| 8 `asyncio.create_task()` 失败，快照自动释放 | TDD-102（v1.4 重写：窗口改为 resolve 后至交接前，含 db.atxn 取消/日志异常） | 新增 |
| 9 runner 被取消，关闭不被取消中断 | TDD-101 变体 + 存量 cancel 系列回归 | 增强+回归 |
| 10 `aclose()` 失败有 warning 可查（不炸流程） | TDD-76 增强断言（patch `client.aclose` 抛错 → 无异常 + logger.warning 留痕） | 增强 |
| 11 owner loop 与同步线程不同，关闭回 owner loop | TDD-86（`release_owner` 双分支：循环内 `create_task` / 无循环 `asyncio.run`）+ 存量 `close_instance_sync` case 回归 | 覆盖+回归 |
| 12 同 Provider 共享 client、跨 Provider 独立 | 存量 `test_tdd_p1_cross_provider_independent_pool`（M2/M4 迁移） | 迁移回归 |
| 13 `cancel_task()` 命中当前任务 snapshot | 存量 cancel 系列（test_tdd_21_25 等，M1 迁移后回归） | 迁移回归 |
| 14 `reset_cancel()` 不清除 `_cancelled` | 存量回归（M1 迁移后） | 迁移回归 |
| 15 `LLMClient.cancel()` 能关闭流式 HTTP response | 存量回归（test_tdd_64_73 G1 等） | 回归 |

> 阶段4 不新增独立 case：**增强断言并入**对应 case（断言只增强），**回归项** = 存量文件迁移后全绿即达成。**v1.8 补**：本表"增强"列的两条（TDD-76 场景10 关闭失败留痕、TDD-84 场景2 多快照并发关闭）已**回填 6.3 对应 case 规格并附可落盘代码**（6.3 末"6.6 增强段代码"）——本表此后仅作索引，不再是唯一出处，避免两节再次分叉。

### 6.7 阶段5：全量验收（全部满足才允许进入提交）

1. **静态验证**（[70] 4.1）：`python -m compileall -q app` + grep 清单（`_owns_client`/`_is_snapshot`/`_shared_client` 反射生产无引用、resolver 无任何 `_shared_client` 反射、registry 不存资源不 import 资源类型、无 `mark_config_changed`/`scope.resolve_session`/`scope.release_lease`/状态机残留、`reset_sdk` 无定义无调用、`reset()` 无 close 调用只经 `_retire_scope` 归还）。
2. **定向序列**（一次一个文件，全绿才下一个；[69] 4.2 的 7 个存量 + 3 个新文件 + M1 的 16 个迁移文件去重合并 + M11 的 test_s2_s4_review_bugs——M10 的 3 文件均已在列）：
   ```powershell
   pytest tests/test_tdd_74_87_scope_lease.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_88_93_generation.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_94_102_wiring.py --timeout=120 -x --tb=short -v
   pytest tests/test_resolve_session_client.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_03_08_snapshot.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_41_46_bug_c_red.py --timeout=120 -x --tb=short -v
   pytest tests/test_client_sdk_adapter.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_64_73_bug_guard.py --timeout=120 -x --tb=short -v
   pytest tests/test_repro_v01936.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_14_20_inbox.py --timeout=120 -x --tb=short -v
   pytest tests/test_7_03_cancel_releases.py --timeout=120 -x --tb=short -v
   pytest tests/test_critical_flow_deep_bugs.py --timeout=120 -x --tb=short -v
   pytest tests/test_tdd_34_40_bug_b_red.py --timeout=120 -x --tb=short -v
    pytest tests/test_model_ref_normalization.py --timeout=120 -x --tb=short -v
    pytest tests/test_settings_editsave_red.py --timeout=120 -x --tb=short -v
    pytest tests/test_s2_s4_review_bugs.py --timeout=120 -x --tb=short -v
    ```
   其余 M1 迁移文件（test_7_01/7_02/7_04/7_05、test_9_08、test_tdd_01_02、test_tdd_21_25、test_tdd_30_32、test_tdd_47_51、test_tdd_52_58）同法逐个执行。每文件完成后按 [69] 4.2 五项人工检查：无 traceback、无 `Task exception was never retrieved`、无 `httpx client closed` 误报、无归零未关、无取消误伤。
3. **全量对照**：**基线口径（v1.7 修正）**——[69] 4.4 的 `7355 passed / 1 skipped / 127 warnings` 为 6 文件撤销前旧口径已过期（v1.7 定向实测证明当前 HEAD 含 M10 的 4 个红：12 文件 349 case = 4 failed/345 passed，4 failed 全部为 M10 孤儿）；进入本节前先跑一次全量（后端按 E2E 手册启动）记为**基线 B0**（精确 passed/failed 与错误清单，M10 修复随 step5/6 落地后 B0 应为全绿）；实施后 = B0 + **新增 29 case** + 迁移不减 case——通过数变化必须逐项解释（新增哪些、断言升级哪些、M10 转绿哪些），**不允许放宽断言换全绿**。
4. **真实 E2E**（[69] 4.5 九步；真实后端 + 真实 LLM + 真实 SQLite，一次一个 case）：任务运行中改配置 → 任务不中断、日志无 `Cannot send a request, as the client has been closed`、SSE 正常结束、DB 终态/token/步骤完整、配置无临时 Provider/模型残留、shutdown 无未取出的关闭异常。
5. **并发矩阵**（[69] 4.6 六行）：同/异 Provider 双任务 + reload、A 取消 B 继续、resolver await 中换代、runner 创建前换代、finally 中取消——预期结果照 [69] 4.6 表逐行核对。
6. **验收基准**（[70] 4.4，全部满足）逐条核对（按 2.7 取舍校准：关闭失败"可查"非"可重试"、裸 client **反射**清零）。

### 6.8 提交切片与回滚

- **切片**：阶段1~5 每阶段验证全绿后为一个提交单元；提交范围遵循 AGENTS.md commit 铁规（**测试相关文件不入库**——3 个新测试文件与迁移 case 先在工作树验证全绿，入库时机由北京老陈单独裁定）；提交标题格式 `<type>:<文件名> <description> - <签名>-<日期>`。
- **回滚**：见五章回滚段（`git revert` 实施序列；摘资产三重备份在 [70] 定案前始终保留）。
- **API 对齐声明**：本章 case 引用的 API（`ensure_pool`/`acquire_lease`/`release_owner`/`drain`/`ref_count`/`is_released`/`ensure_client_pool`/`client_lease`/`relinquish_ownership`/`get_scope`/`shutdown`）逐一与第三章 diff 对齐；实施时若 diff 修订，case 同步修订（断言只增强不放宽）。

---

**文档签名**: 小欧  
**更新时间**: 2026-09-25 17:53:48
